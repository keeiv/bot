import json
import os
import re
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

import discord

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# --- 偵測類型常數 ---
DETECT_FLOOD = "flood"           # 訊息洪水
DETECT_DUPLICATE = "duplicate"   # 重複內容
DETECT_MENTION = "mention"       # 提及轟炸
DETECT_LINK = "link"             # 連結/邀請轟炸
DETECT_EMOJI = "emoji"           # 表情轟炸
DETECT_NEWLINE = "newline"       # 換行轟炸
DETECT_RAID = "raid"             # 加入突襲

ALL_DETECTIONS = [
    DETECT_FLOOD, DETECT_DUPLICATE, DETECT_MENTION,
    DETECT_LINK, DETECT_EMOJI, DETECT_NEWLINE, DETECT_RAID,
]

# --- 動作常數 (嚴重度由低到高) ---
ACTION_WARN = "warn"
ACTION_DELETE = "delete"
ACTION_MUTE = "mute"
ACTION_KICK = "kick"
ACTION_BAN = "ban"
ACTION_LOCKDOWN = "lockdown"

ACTION_SEVERITY = {
    ACTION_WARN: 0,
    ACTION_DELETE: 1,
    ACTION_MUTE: 2,
    ACTION_KICK: 3,
    ACTION_BAN: 4,
    ACTION_LOCKDOWN: 5,
}

VALID_ACTIONS = list(ACTION_SEVERITY.keys())

# 正則匹配
INVITE_RE = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[A-Za-z0-9\-]+",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
EMOJI_RE = re.compile(r"<a?:\w+:\d+>|[\U0001F600-\U0001FAFF]")

# 預設設定
DEFAULT_SETTINGS = {
    "enabled": True,
    # 洪水偵測
    "flood_messages": 10,
    "flood_window": 10,
    "flood_action": ACTION_MUTE,
    # 重複內容偵測
    "duplicate_enabled": True,
    "duplicate_count": 4,
    "duplicate_window": 30,
    "duplicate_action": ACTION_DELETE,
    # 提及轟炸偵測
    "mention_enabled": True,
    "mention_limit": 8,
    "mention_action": ACTION_MUTE,
    # 連結/邀請偵測
    "link_enabled": True,
    "link_limit": 5,
    "link_window": 15,
    "link_action": ACTION_DELETE,
    "invite_auto_delete": True,
    # 表情轟炸偵測
    "emoji_enabled": True,
    "emoji_limit": 20,
    "emoji_action": ACTION_DELETE,
    # 換行轟炸偵測
    "newline_enabled": True,
    "newline_limit": 30,
    "newline_action": ACTION_DELETE,
    # 突襲偵測
    "raid_enabled": True,
    "raid_joins": 10,
    "raid_window": 30,
    "raid_action": ACTION_LOCKDOWN,
    # 自動升級
    "auto_escalate": True,
    "escalate_strikes": 3,
    "escalate_window": 600,
    # 懲罰時長
    "mute_duration": 3600,
    "ban_delete_days": 1,
    # 白名單
    "whitelisted_roles": [],
    "whitelisted_channels": [],
}


class AntiSpamManager:
    """頂級防炸群管理器 — 多層偵測 + 自動升級"""

    SETTINGS_FILE = "data/storage/anti_spam_settings.json"

    def __init__(self):
        # {guild_id: settings}
        self.settings: Dict[int, dict] = self._load_all_settings()
        # {guild_id: {user_id: [timestamp]}} — 訊息時間戳
        self.message_log: Dict[int, Dict[int, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {guild_id: {user_id: [content]}} — 最近內容 (重複偵測)
        self.content_log: Dict[int, Dict[int, List[Tuple[float, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {guild_id: {user_id: [timestamp]}} — 連結時間戳
        self.link_log: Dict[int, Dict[int, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {guild_id: [timestamp]} — 加入時間戳 (突襲偵測)
        self.join_log: Dict[int, List[float]] = defaultdict(list)
        # {guild_id: {user_id: [(timestamp, detection_type)]}} — 違規紀錄
        self.strike_log: Dict[int, Dict[int, List[Tuple[float, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {guild_id: bool} — 封鎖模式狀態
        self.lockdown_active: Dict[int, bool] = {}

    # --- 設定管理 ---

    def _load_all_settings(self) -> Dict[int, dict]:
        """從檔案載入所有伺服器設定"""
        if not os.path.exists(self.SETTINGS_FILE):
            return {}
        try:
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except (json.JSONDecodeError, OSError) as e:
            print(f"[防刷屏] 無法載入設定: {e}")
            return {}

    def _save_all_settings(self):
        """儲存所有伺服器設定到檔案"""
        os.makedirs(os.path.dirname(self.SETTINGS_FILE), exist_ok=True)
        try:
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {str(k): v for k, v in self.settings.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError as e:
            print(f"[防刷屏] 無法儲存設定: {e}")

    def get_settings(self, guild_id: int) -> dict:
        """取得伺服器設定 (不存在則建立預設)"""
        if guild_id not in self.settings:
            self.settings[guild_id] = dict(DEFAULT_SETTINGS)
        return self.settings[guild_id]

    def update_settings(self, guild_id: int, updates: dict):
        """更新伺服器設定並儲存"""
        s = self.get_settings(guild_id)
        s.update(updates)
        self._save_all_settings()

    def is_whitelisted(
        self, guild_id: int, member: discord.Member, channel_id: int
    ) -> bool:
        """檢查成員/頻道是否在白名單"""
        s = self.get_settings(guild_id)
        if channel_id in s["whitelisted_channels"]:
            return True
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & set(s["whitelisted_roles"]):
            return True
        return False

    # --- 核心偵測引擎 ---

    def check_message(
        self, guild_id: int, user_id: int, content: str, channel_id: int,
        member: Optional[discord.Member] = None,
    ) -> List[Tuple[str, str, str]]:
        """
        全面檢查訊息，回傳觸發列表

        回傳: [(detection_type, action, detail_text), ...]
        """
        s = self.get_settings(guild_id)
        if not s["enabled"]:
            return []

        # 白名單跳過
        if member and self.is_whitelisted(guild_id, member, channel_id):
            return []

        now = datetime.now(TZ_OFFSET).timestamp()
        triggers = []

        # 1) 訊息洪水偵測
        flood = self._check_flood(guild_id, user_id, now, s)
        if flood:
            triggers.append(flood)

        # 2) 重複內容偵測
        if s["duplicate_enabled"] and content:
            dup = self._check_duplicate(guild_id, user_id, now, content, s)
            if dup:
                triggers.append(dup)

        # 3) 提及轟炸偵測
        if s["mention_enabled"] and content:
            mention = self._check_mentions(content, s)
            if mention:
                triggers.append(mention)

        # 4) 連結/邀請轟炸偵測
        if s["link_enabled"] and content:
            link = self._check_links(guild_id, user_id, now, content, s)
            if link:
                triggers.append(link)

        # 5) 表情轟炸偵測
        if s["emoji_enabled"] and content:
            emoji = self._check_emoji(content, s)
            if emoji:
                triggers.append(emoji)

        # 6) 換行轟炸偵測
        if s["newline_enabled"] and content:
            newline = self._check_newline(content, s)
            if newline:
                triggers.append(newline)

        # 記錄違規 + 自動升級
        if triggers and s["auto_escalate"]:
            triggers = self._apply_escalation(guild_id, user_id, now, triggers, s)

        return triggers

    def check_member_join(self, guild_id: int) -> Optional[Tuple[str, str, str]]:
        """檢查是否有加入突襲"""
        s = self.get_settings(guild_id)
        if not s["enabled"] or not s["raid_enabled"]:
            return None

        now = datetime.now(TZ_OFFSET).timestamp()
        window = s["raid_window"]

        self.join_log[guild_id].append(now)
        self.join_log[guild_id] = [
            t for t in self.join_log[guild_id] if now - t < window
        ]

        count = len(self.join_log[guild_id])
        if count >= s["raid_joins"]:
            self.join_log[guild_id].clear()
            return (
                DETECT_RAID,
                s["raid_action"],
                f"{window} 秒內有 {count} 人加入",
            )
        return None

    def is_invite_link(self, content: str, guild_id: int) -> bool:
        """快速檢查是否含有邀請連結"""
        s = self.get_settings(guild_id)
        return bool(s["invite_auto_delete"] and INVITE_RE.search(content))

    def is_lockdown(self, guild_id: int) -> bool:
        """是否處於封鎖模式"""
        return self.lockdown_active.get(guild_id, False)

    def set_lockdown(self, guild_id: int, active: bool):
        """設定封鎖模式"""
        self.lockdown_active[guild_id] = active

    def reset_user(self, guild_id: int, user_id: int):
        """重設用戶所有紀錄"""
        for log in (self.message_log, self.content_log, self.link_log):
            if guild_id in log and user_id in log[guild_id]:
                log[guild_id][user_id] = []

    def get_user_strikes(self, guild_id: int, user_id: int) -> int:
        """取得用戶當前違規次數"""
        s = self.get_settings(guild_id)
        now = datetime.now(TZ_OFFSET).timestamp()
        window = s["escalate_window"]
        strikes = self.strike_log[guild_id][user_id]
        return len([t for t, _ in strikes if now - t < window])

    # --- 各偵測子模組 ---

    def _check_flood(
        self, guild_id: int, user_id: int, now: float, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """洪水偵測"""
        window = s["flood_window"]
        limit = s["flood_messages"]

        log = self.message_log[guild_id][user_id]
        log.append(now)
        # 清理過期
        self.message_log[guild_id][user_id] = [
            t for t in log if now - t < window
        ]

        count = len(self.message_log[guild_id][user_id])
        if count > limit:
            return (
                DETECT_FLOOD,
                s["flood_action"],
                f"{window}s 內發送 {count}/{limit} 條訊息",
            )
        return None

    def _check_duplicate(
        self, guild_id: int, user_id: int, now: float, content: str, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """重複內容偵測"""
        window = s["duplicate_window"]
        limit = s["duplicate_count"]

        log = self.content_log[guild_id][user_id]
        normalized = content.strip().lower()
        log.append((now, normalized))

        # 清理過期
        self.content_log[guild_id][user_id] = [
            (t, c) for t, c in log if now - t < window
        ]

        # 計算相同內容出現次數
        dup_count = sum(
            1 for _, c in self.content_log[guild_id][user_id]
            if c == normalized
        )

        if dup_count >= limit:
            return (
                DETECT_DUPLICATE,
                s["duplicate_action"],
                f"{window}s 內重複相同內容 {dup_count} 次",
            )
        return None

    def _check_mentions(
        self, content: str, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """提及轟炸偵測"""
        limit = s["mention_limit"]
        mention_count = content.count("<@") + content.count("@everyone") + content.count("@here")

        if mention_count >= limit:
            return (
                DETECT_MENTION,
                s["mention_action"],
                f"單條訊息包含 {mention_count} 個提及",
            )
        return None

    def _check_links(
        self, guild_id: int, user_id: int, now: float, content: str, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """連結轟炸偵測"""
        urls = URL_RE.findall(content)
        if not urls:
            return None

        window = s["link_window"]
        limit = s["link_limit"]

        log = self.link_log[guild_id][user_id]
        for _ in urls:
            log.append(now)

        self.link_log[guild_id][user_id] = [
            t for t in log if now - t < window
        ]

        count = len(self.link_log[guild_id][user_id])
        if count >= limit:
            has_invite = bool(INVITE_RE.search(content))
            detail = f"{window}s 內貼出 {count} 個連結"
            if has_invite:
                detail += " (含邀請連結)"
            return (DETECT_LINK, s["link_action"], detail)
        return None

    def _check_emoji(
        self, content: str, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """表情轟炸偵測"""
        limit = s["emoji_limit"]
        count = len(EMOJI_RE.findall(content))

        if count >= limit:
            return (
                DETECT_EMOJI,
                s["emoji_action"],
                f"單條訊息包含 {count} 個表情",
            )
        return None

    def _check_newline(
        self, content: str, s: dict
    ) -> Optional[Tuple[str, str, str]]:
        """換行轟炸偵測"""
        limit = s["newline_limit"]
        count = content.count("\n")

        if count >= limit:
            return (
                DETECT_NEWLINE,
                s["newline_action"],
                f"單條訊息包含 {count} 個換行",
            )
        return None

    # --- 自動升級 ---

    def _apply_escalation(
        self,
        guild_id: int,
        user_id: int,
        now: float,
        triggers: List[Tuple[str, str, str]],
        s: dict,
    ) -> List[Tuple[str, str, str]]:
        """根據違規紀錄自動升級懲罰"""
        window = s["escalate_window"]
        threshold = s["escalate_strikes"]

        # 記錄本次違規
        for det_type, _, _ in triggers:
            self.strike_log[guild_id][user_id].append((now, det_type))

        # 清理過期違規
        self.strike_log[guild_id][user_id] = [
            (t, d) for t, d in self.strike_log[guild_id][user_id]
            if now - t < window
        ]

        strike_count = len(self.strike_log[guild_id][user_id])
        if strike_count < threshold:
            return triggers

        # 達到升級門檻 — 取最嚴重的現有動作，升一級
        max_severity = max(
            ACTION_SEVERITY.get(action, 0)
            for _, action, _ in triggers
        )

        escalated_action = None
        for act, sev in sorted(ACTION_SEVERITY.items(), key=lambda x: x[1]):
            if sev > max_severity:
                escalated_action = act
                break

        if escalated_action and escalated_action != ACTION_LOCKDOWN:
            return [
                (det, escalated_action, detail + f" [自動升級: {strike_count} 次違規]")
                for det, _, detail in triggers
            ]

        return triggers


# --- 日誌 Embed 建構 ---

DETECT_NAMES = {
    DETECT_FLOOD: "訊息洪水",
    DETECT_DUPLICATE: "重複內容",
    DETECT_MENTION: "提及轟炸",
    DETECT_LINK: "連結轟炸",
    DETECT_EMOJI: "表情轟炸",
    DETECT_NEWLINE: "換行轟炸",
    DETECT_RAID: "加入突襲",
}

ACTION_NAMES = {
    ACTION_WARN: "警告",
    ACTION_DELETE: "刪除訊息",
    ACTION_MUTE: "禁言",
    ACTION_KICK: "踢出",
    ACTION_BAN: "封禁",
    ACTION_LOCKDOWN: "封鎖頻道",
}

DETECT_COLORS = {
    DETECT_FLOOD: discord.Color.from_rgb(255, 165, 0),
    DETECT_DUPLICATE: discord.Color.from_rgb(255, 200, 0),
    DETECT_MENTION: discord.Color.from_rgb(255, 80, 80),
    DETECT_LINK: discord.Color.from_rgb(200, 100, 200),
    DETECT_EMOJI: discord.Color.from_rgb(100, 200, 255),
    DETECT_NEWLINE: discord.Color.from_rgb(150, 150, 150),
    DETECT_RAID: discord.Color.from_rgb(255, 0, 0),
}


def create_anti_spam_log_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    detection_type: str,
    action: str,
    detail: str,
    strike_count: int = 0,
) -> discord.Embed:
    """建立防炸群日誌 Embed"""
    color = DETECT_COLORS.get(detection_type, discord.Color.from_rgb(255, 165, 0))
    type_name = DETECT_NAMES.get(detection_type, detection_type)
    action_name = ACTION_NAMES.get(action, action)

    embed = discord.Embed(
        title=f"[防炸群] {type_name}",
        color=color,
        timestamp=datetime.now(TZ_OFFSET),
    )

    embed.add_field(
        name="用戶", value=f"<@{user_id}> ({user_id})", inline=False
    )
    embed.add_field(name="用戶名", value=user_name, inline=True)
    embed.add_field(
        name="頻道", value=f"<#{channel_id}> ({channel_id})", inline=True
    )
    embed.add_field(name="偵測類型", value=type_name, inline=True)
    embed.add_field(name="詳細資訊", value=detail, inline=False)
    embed.add_field(name="執行動作", value=action_name, inline=True)

    if strike_count > 0:
        embed.add_field(name="累計違規", value=f"{strike_count} 次", inline=True)

    embed.set_footer(text=f"{guild_name} ({guild_id})")

    return embed


def create_raid_alert_embed(
    guild_name: str,
    guild_id: int,
    join_count: int,
    window: int,
    action: str,
) -> discord.Embed:
    """建立突襲警報 Embed"""
    action_name = ACTION_NAMES.get(action, action)

    embed = discord.Embed(
        title="[防炸群] 突襲警報",
        description=(
            f"偵測到可能的突襲行為\n"
            f"{window} 秒內有 **{join_count}** 人加入伺服器"
        ),
        color=discord.Color.from_rgb(255, 0, 0),
        timestamp=datetime.now(TZ_OFFSET),
    )

    embed.add_field(name="執行動作", value=action_name, inline=True)
    embed.add_field(
        name="建議",
        value=(
            "1. 檢查近期加入的成員\n"
            "2. 考慮啟用驗證等級\n"
            "3. 使用 `/anti_spam lockdown_off` 解除封鎖"
        ),
        inline=False,
    )
    embed.set_footer(text=f"{guild_name} ({guild_id})")

    return embed
