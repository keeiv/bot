from collections import Counter
from collections import defaultdict
import copy
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import difflib
from functools import lru_cache
from functools import partial
import json
import os
import re
import threading
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
import unicodedata
from urllib.parse import urlsplit

import discord

from src.utils.document_store import open_document
from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.i18n import text as tx

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# --- 偵測類型常數 ---
DETECT_FLOOD = "flood"  # 訊息洪水
DETECT_DUPLICATE = "duplicate"  # 重複內容
DETECT_MENTION = "mention"  # 提及轟炸
DETECT_LINK = "link"  # 連結/邀請轟炸
DETECT_EMOJI = "emoji"  # 表情轟炸
DETECT_NEWLINE = "newline"  # 換行轟炸
DETECT_RAID = "raid"  # 加入突襲
DETECT_SIMILAR = "similar"  # 同一人跨頻道洗相似內容
DETECT_COORDINATED = "coordinated"  # 多個帳號洗相似內容
DETECT_ATTACHMENT = "attachment"  # 附件/貼圖轟炸
DETECT_PHISHING = "phishing"  # 惡意連結
DETECT_NEW_ACCOUNT = "new_account"  # 新帳號加入
DETECT_NUKE = "nuke"  # 大量刪頻道/身分組、大量封禁

ALL_DETECTIONS = [
    DETECT_FLOOD,
    DETECT_DUPLICATE,
    DETECT_MENTION,
    DETECT_LINK,
    DETECT_EMOJI,
    DETECT_NEWLINE,
    DETECT_RAID,
    DETECT_SIMILAR,
    DETECT_COORDINATED,
    DETECT_ATTACHMENT,
    DETECT_PHISHING,
    DETECT_NEW_ACCOUNT,
    DETECT_NUKE,
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

# 防破壞的處置：拔掉身分組（可用 nuke_restore 還原）、踢出或封禁
NUKE_STRIP = "strip"
NUKE_ACTIONS = [NUKE_STRIP, ACTION_KICK, ACTION_BAN]
# 計入防破壞的操作（稽核日誌）
NUKE_KINDS = [
    "channel_delete",
    "channel_create",
    "role_delete",
    "ban",
    "kick",
    "prune",
    "webhook_create",
]

# 正則匹配
INVITE_RE = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[A-Za-z0-9\-]+",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
EMOJI_RE = re.compile(r"<a?:\w+:\d+>|[\U0001F600-\U0001FAFF]")
# [看起來像網址的文字](實際網址)
MASKED_LINK_RE = re.compile(r"\[([^\]\n]{1,200})\]\(\s*<?(https?://[^)\s>]+)>?\s*\)")

# --- 相似內容 ---
_INVISIBLE_RE = re.compile("[\u00ad\u200b-\u200f\u2060-\u2064\ufeff]")
_SPACE_RE = re.compile(r"\s+")
_RUN_RE = re.compile(r"(.)\1{3,}")
SIMILAR_RATIO = 0.85
# Shorter texts only count when identical: "hi" and "ok" are not alike.
SIMILAR_MIN_LENGTH = 10
SIGNATURE_LIMIT = 300
# How long a member's messages are kept so a detection can remove them everywhere.
RECENT_SECONDS = 60
RECENT_LIMIT = 50
RAIDERS_LIMIT = 5000  # accounts of one raid remembered per server


@dataclass
class Evidence:
    """What a detection found besides the message itself."""

    # (channel_id, message_id) to remove, in any channel
    messages: set[Tuple[int, int]] = field(default_factory=set)
    # other members taking part (a coordinated wave, the accounts of a raid)
    users: set[int] = field(default_factory=set)
    # a join wave was just detected (rather than one new account during a raid)
    wave: bool = False


def message_signature(
    content: str, attachments: Iterable[str] = (), stickers: Iterable[str] = ()
) -> str:
    """Text reduced to what a spammer cannot vary cheaply, plus file and sticker marks."""
    text = unicodedata.normalize("NFKC", content or "").casefold()
    text = _INVISIBLE_RE.sub("", text)
    text = _SPACE_RE.sub(" ", text).strip()
    text = _RUN_RE.sub(r"\1\1\1", text)[:SIGNATURE_LIMIT]
    marks = [f"[file:{a}]" for a in attachments] + [f"[sticker:{s}]" for s in stickers]
    return " ".join([text, *marks]).strip()


@lru_cache(maxsize=4096)
def _trigrams(text: str) -> frozenset[str]:
    return frozenset(text[i : i + 3] for i in range(len(text) - 2))


def is_similar(a: str, b: str) -> bool:
    """Same text, or long enough and sharing most three-letter pieces (linear time)."""
    if a == b:
        return bool(a)
    if "[file:" in a + b or "[sticker:" in a + b:
        return False  # a file's name and size say nothing about its content
    shorter, longer = sorted((len(a), len(b)))
    if shorter < SIMILAR_MIN_LENGTH or shorter / longer < SIMILAR_RATIO:
        return False
    x, y = _trigrams(a), _trigrams(b)
    return 2 * len(x & y) / (len(x) + len(y)) >= SIMILAR_RATIO


# --- 惡意連結 ---
# Domains of the brands phishing copies, and well-known sites that carry the name.
OFFICIAL_DOMAINS = frozenset(
    {
        "discord.com",
        "discord.gg",
        "discord.gift",
        "discord.new",
        "discord.media",
        "discord.dev",
        "discord.design",
        "discord.co",
        "discordapp.com",
        "discordapp.net",
        "discordstatus.com",
        "discordmerch.com",
        "discord.js.org",
        "discordpy.readthedocs.io",
        "dis.gd",
        "steampowered.com",
        "steamcommunity.com",
        "steamstatic.com",
        "steamdeck.com",
        "steamchina.com",
    }
)
# Link shorteners: free Nitro bait hides its address behind them.
SHORTENERS = frozenset(
    {
        "bit.ly",
        "tinyurl.com",
        "t.co",
        "is.gd",
        "cutt.ly",
        "shorturl.at",
        "rb.gy",
        "t.ly",
        "goo.su",
        "rebrand.ly",
        "s.id",
        "ow.ly",
        "v.gd",
        "reurl.cc",
        "lihi.cc",
        "pse.is",
    }
)
# A name that always means the brand; any other domain carrying it is a copy.
STRICT_BRANDS = ("steamcommunity", "steampowered")
# A name that also appears in honest sites (bot lists, docs), so it needs a lure too.
LOOSE_BRANDS = ("discord", "discordapp")
LURE_WORDS = (
    "gift",
    "nitro",
    "free",
    "promo",
    "claim",
    "drop",
    "give",
    "reward",
    "bonus",
    "verify",
    "login",
    "auth",
    "airdrop",
    "event",
)
# Digits and look-alike letters (Cyrillic, Greek) folded to the Latin they imitate.
_SKELETON = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ԁ": "d",
        "ѕ": "s",
        "ο": "o",
        "ι": "i",
        "κ": "k",
        "l": "i",  # dlscord
        "|": "i",
    }
)
# Words that make a domain's own name bait; ordinary ones like auth or login are not.
BAIT_WORDS = ("nitro", "gift", "airdrop", "freegame", "giveaway")
LURE_TEXT_RE = re.compile(
    r"(free|免費|claim|領取|送).{0,24}nitro|nitro.{0,24}(free|免費|gift|禮物|贈送)"
    r"|steam.{0,16}(gift|禮物|禮品卡|giveaway)",
    re.IGNORECASE | re.DOTALL,
)


def link_host(url: str) -> str:
    """The host of a link, lower case, with IDN labels decoded and no "www."."""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    labels = []
    for label in host.rstrip(".").split("."):
        if label.startswith("xn--"):
            try:
                label = label.encode("ascii").decode("idna")
            except UnicodeError:
                pass
        labels.append(label)
    host = unicodedata.normalize("NFKC", ".".join(labels)).casefold()
    return host[4:] if host.startswith("www.") else host


def domain_listed(host: str, domains: Iterable[str]) -> bool:
    """Whether host is one of the domains or under one of them."""
    return any(host == d or host.endswith("." + d) for d in domains)


def _one_letter_apart(a: str, b: str) -> bool:
    """Whether one letter more or less turns a into b (disscord, dscord)."""
    if abs(len(a) - len(b)) != 1:
        return False
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    return any(longer[:i] + longer[i + 1 :] == shorter for i in range(len(longer)))


def lookalike_brand(host: str) -> Optional[str]:
    """The brand a host imitates, or None; official hosts imitate nothing.

    Swapped letters, one letter too many or too few, digits and look-alike
    letters count; a different real word ("discard") does not.
    """
    if not host or domain_listed(host, OFFICIAL_DOMAINS):
        return None
    words = [w for w in re.split(r"[.\-_]", host) if w]
    lured = any(lure in host for lure in LURE_WORDS)
    for word in [*words, "".join(words[:-1])]:
        skeleton = word.translate(_SKELETON).replace("rn", "m").replace("vv", "w")
        for brand in STRICT_BRANDS + LOOSE_BRANDS:
            if brand in word:
                # the plain name: steam's always, discord's only next to a lure
                if brand in STRICT_BRANDS or lured:
                    return brand
                continue
            if brand in skeleton:
                return brand  # disc0rd, dіscord, dlscord: nobody honest spells it so
            if (len(skeleton) == len(brand) and sorted(skeleton) == sorted(brand)) or (
                _one_letter_apart(skeleton, brand)
            ):
                return brand  # discrod, dscord, disscord
            if (
                brand in STRICT_BRANDS
                and abs(len(skeleton) - len(brand)) <= 2
                and difflib.SequenceMatcher(None, skeleton, brand).ratio() >= 0.85
            ):
                return (
                    brand  # steamcommunlty, steamcomunity: long names, no honest twin
                )
    return None


def bait_named(host: str) -> bool:
    """Whether the domain's own name (not a subdomain like auth.) is bait."""
    labels = host.split(".")
    name = labels[-2] if len(labels) >= 2 else host
    return any(word in name for word in BAIT_WORDS)


def imitates(host: str) -> bool:
    """Whether a link's text shows an official or imitated Discord/Steam address."""
    return domain_listed(host, OFFICIAL_DOMAINS) or lookalike_brand(host) is not None


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
    # 突襲期間：多久後自動解除封鎖（0 = 手動），以及帳號未滿幾天的加入者直接處置
    "raid_lift_minutes": 30,
    "raid_age_days": 7,
    # 跨頻道／多帳號洗相似內容
    "similar_enabled": True,
    "similar_channels": 3,
    "similar_users": 4,
    "similar_window": 30,
    "similar_action": ACTION_MUTE,
    # 附件／貼圖轟炸
    "attachment_enabled": True,
    "attachment_limit": 8,
    "attachment_window": 15,
    "attachment_action": ACTION_DELETE,
    # 惡意連結
    "phishing_enabled": True,
    "phishing_action": ACTION_MUTE,
    "allowed_domains": [],
    "blocked_domains": [],
    # 新帳號門檻（小時，0 = 關閉）
    "new_account_hours": 0,
    "new_account_action": ACTION_KICK,
    # 防破壞：同一人在時間內做了幾次危險操作
    "nuke_enabled": True,
    "nuke_limit": 5,
    "nuke_window": 30,
    "nuke_action": NUKE_STRIP,
    "nuke_trusted": [],
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
    # Lockdowns in force, with each channel's send_messages before it, so a
    # restart can still lift them, and whether every channel was locked yet:
    # {guild_id: {"channels": {channel_id: True | False | None}, "complete": bool}}
    LOCKDOWN_FILE = "data/storage/anti_spam_lockdowns.json"
    # Roles taken from someone stopped by anti-nuke, for nuke_restore:
    # {guild_id: {user_id: [role_id]}}
    NUKE_FILE = "data/storage/anti_nuke_strips.json"

    def __init__(self) -> None:
        # {guild_id: settings}
        self._settings_lock = threading.RLock()
        self._settings: Dict[int, dict[Any, Any]] = self._load_all_settings()
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
        # {guild_id: timestamp} — 封鎖自動解除的時間
        self.lockdown_until: Dict[int, float] = {}
        # {guild_id: timestamp} — 突襲模式結束的時間（期間新帳號加入直接處置）
        self.raid_until: Dict[int, float] = {}
        # {guild_id: [(timestamp, user_id, account_is_new)]} — 突襲時找出那一波帳號
        self.joiners: Dict[int, List[Tuple[float, int, bool]]] = defaultdict(list)
        # {guild_id: {user_id: [(timestamp, channel_id, message_id, signature)]}}
        self.recent_messages: Dict[
            int, Dict[int, List[Tuple[float, int, int, str]]]
        ] = defaultdict(lambda: defaultdict(list))
        # {guild_id: [(timestamp, user_id, channel_id, message_id, signature)]}
        self.guild_messages: Dict[int, List[Tuple[float, int, int, int, str]]] = (
            defaultdict(list)
        )
        # {guild_id: [(until, signature)]} — 已確認的多帳號洗版內容
        self.hot_signatures: Dict[int, List[Tuple[float, str]]] = defaultdict(list)
        # {guild_id: {user_id: [timestamp]}} — 附件/貼圖時間戳
        self.attachment_log: Dict[int, Dict[int, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # {guild_id: {user_id}} — 突襲期間加入的帳號（封禁或踢出它們不算破壞）
        self.raiders: Dict[int, set[int]] = defaultdict(set)
        # {guild_id: {user_id: [(timestamp, kind)]}} — 危險操作
        self.nuke_log: Dict[int, Dict[int, List[Tuple[float, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )

    # --- 設定管理 ---

    def _load_all_settings(self) -> Dict[int, dict[Any, Any]]:
        try:
            raw = read_document(self.SETTINGS_FILE)
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            raise TypeError("Anti-spam configuration must be an object")
        return {int(k): v for k, v in raw.items()}

    def _save_all_settings(self, settings=None) -> None:
        proposed = self._settings if settings is None else settings
        os.makedirs(os.path.dirname(self.SETTINGS_FILE), exist_ok=True)
        with open_document(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in proposed.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    @property
    def settings(self):
        with self._settings_lock:
            return copy.deepcopy(self._settings)

    def get_settings(self, guild_id: int) -> dict[Any, Any]:
        """Return a detached snapshot; settings added since a guild saved get their defaults."""
        return copy.deepcopy({**DEFAULT_SETTINGS, **self._settings.get(guild_id, {})})

    def update_settings(self, guild_id: int, updates: dict[Any, Any]) -> None:
        with self._settings_lock:
            proposed = copy.deepcopy(self._settings)
            proposed[guild_id] = {
                **copy.deepcopy(DEFAULT_SETTINGS),
                **proposed.get(guild_id, {}),
                **copy.deepcopy(updates),
            }
            self._save_all_settings(proposed)
            self._settings = proposed

    def update_whitelist(self, guild_id, action, role_id=None, channel_id=None):
        """Return changed kinds only after successfully persisting the lists."""
        if action not in ("add", "remove"):
            raise ValueError("Invalid whitelist action")
        with self._settings_lock:
            settings = self.get_settings(guild_id)
            changes = []
            for kind, item in (("roles", role_id), ("channels", channel_id)):
                if item is None:
                    continue
                items = settings["whitelisted_" + kind]
                if action == "add" and item not in items:
                    items.append(item)
                    changes.append(kind)
                elif action == "remove" and item in items:
                    items.remove(item)
                    changes.append(kind)
            if changes:
                self.update_settings(guild_id, settings)
            return changes

    def update_list(self, guild_id: int, key: str, action: str, item: Any) -> bool:
        """Add to or remove from a list setting; whether it changed (saved first)."""
        if action not in ("add", "remove") or not isinstance(
            DEFAULT_SETTINGS.get(key), list
        ):
            raise ValueError("Invalid list update")
        with self._settings_lock:
            items = self.get_settings(guild_id)[key]
            if (item in items) == (action == "add"):
                return False
            if action == "add":
                items.append(item)
            else:
                items.remove(item)
            self.update_settings(guild_id, {key: items})
            return True

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
        self,
        guild_id: int,
        user_id: int,
        content: str,
        channel_id: int,
        member: Optional[discord.Member] = None,
        *,
        message_id: int = 0,
        attachments: Iterable[str] = (),
        stickers: Iterable[str] = (),
        evidence: Optional[Evidence] = None,
    ) -> List[Tuple[str, str, str]]:
        """
        全面檢查訊息，回傳觸發列表

        attachments 是各附件的「檔名:大小」，stickers 是貼圖 ID。
        有觸發時，evidence 會收到這個人最近在各頻道的訊息，以及一起洗版的其他帳號。

        回傳: [(detection_type, action, detail_text), ...]
        """
        s = self.get_settings(guild_id)
        if not s["enabled"]:
            return []

        # 白名單跳過
        if member and self.is_whitelisted(guild_id, member, channel_id):
            return []

        now = datetime.now(TZ_OFFSET).timestamp()
        attachments, stickers = list(attachments), list(stickers)
        signature = message_signature(content, attachments, stickers)
        evidence = evidence if evidence is not None else Evidence()
        triggers = []

        # 0) 惡意連結
        if s["phishing_enabled"] and content:
            phishing = self._check_phishing(content, s)
            if phishing:
                triggers.append(phishing)

        recent = self._remember(
            guild_id, user_id, now, channel_id, message_id, signature
        )

        # 跨頻道／多帳號洗相似內容
        if s["similar_enabled"] and signature:
            similar = self._check_similar(
                guild_id,
                user_id,
                now,
                channel_id,
                message_id,
                signature,
                message_signature(content),
                recent,
                s,
                evidence,
            )
            if similar:
                triggers.append(similar)

        # 附件／貼圖轟炸
        if s["attachment_enabled"] and (attachments or stickers):
            attached = self._check_attachments(
                guild_id, user_id, now, len(attachments) + len(stickers), s
            )
            if attached:
                triggers.append(attached)

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

        # 這個人最近在各頻道的訊息都要能一起清掉
        if triggers:
            evidence.messages.update(
                (ch, msg)
                for at, ch, msg, _ in recent
                if msg and now - at < RECENT_SECONDS
            )

        # 記錄違規 + 自動升級
        if triggers and s["auto_escalate"]:
            triggers = self._apply_escalation(guild_id, user_id, now, triggers, s)

        return triggers

    def check_member_join(
        self,
        guild_id: int,
        user_id: int = 0,
        created_at: Optional[datetime] = None,
        evidence: Optional[Evidence] = None,
    ) -> Optional[Tuple[str, str, Callable[[], str]]]:
        """檢查是否有加入突襲

        第三項是產生說明文字的函式：呼叫端在確定語言之後才呼叫。

        一波突襲：evidence.users 收到這一波裡帳號太新的人（raid_age_days 為 0 時是全部），
        之後進入突襲模式。突襲模式中，帳號太新的加入者單獨回傳處置（evidence 不變）。
        """
        s = self.get_settings(guild_id)
        if not s["enabled"] or not s["raid_enabled"]:
            return None

        now = datetime.now(TZ_OFFSET).timestamp()
        window = s["raid_window"]
        if 0 < self.raid_until.get(guild_id, 0) <= now:
            self.end_raid(guild_id)  # over: its accounts are ordinary members again

        self.join_log[guild_id].append(now)
        self.join_log[guild_id] = [
            t for t in self.join_log[guild_id] if now - t < window
        ]
        self.joiners[guild_id].append(
            (now, user_id, self._is_young(created_at, s, now))
        )
        if user_id and self.raid_until.get(guild_id, 0) > now:
            self._raider(guild_id, user_id)
        self.joiners[guild_id] = [
            j for j in self.joiners[guild_id] if now - j[0] < window
        ]

        count = len(self.join_log[guild_id])
        if count >= s["raid_joins"]:
            self.join_log[guild_id].clear()
            if evidence is not None:
                evidence.wave = True
                evidence.users.update(
                    u for _, u, young in self.joiners[guild_id] if u and young
                )
            for _, joined, _ in self.joiners[guild_id]:
                if joined:
                    self._raider(guild_id, joined)
            self.joiners[guild_id].clear()
            minutes = s["raid_lift_minutes"]
            self.raid_until[guild_id] = (
                now + minutes * 60 if minutes > 0 else float("inf")
            )
            return (
                DETECT_RAID,
                s["raid_action"],
                partial(tx, "protection.19", v0=(window), v1=(count)),
            )
        if (
            self.raid_until.get(guild_id, 0) > now
            and self._is_young(created_at, s, now)
            and raid_member_action(s) is not None
        ):
            return (
                DETECT_RAID,
                raid_member_action(s),
                partial(tx, "anti_spam.young_during_raid"),
            )
        return None

    @staticmethod
    def _is_young(
        created_at: Optional[datetime], s: dict[Any, Any], now: float
    ) -> bool:
        """Whether an account counts as new during a raid (always, when the limit is 0)."""
        days = s["raid_age_days"]
        if days <= 0:
            return True
        return created_at is not None and now - created_at.timestamp() < days * 86400

    def _raider(self, guild_id: int, user_id: int) -> None:
        raiders = self.raiders[guild_id]
        if len(raiders) < RAIDERS_LIMIT:
            raiders.add(user_id)

    def raid_active(self, guild_id: int) -> bool:
        return self.raid_until.get(guild_id, 0) > datetime.now(TZ_OFFSET).timestamp()

    def end_raid(self, guild_id: int) -> None:
        self.raid_until.pop(guild_id, None)
        self.raiders.pop(guild_id, None)

    def check_new_account(
        self, guild_id: int, created_at: Optional[datetime]
    ) -> Optional[Tuple[str, str, Callable[[], str]]]:
        """帳號建立未滿 new_account_hours 小時的加入者"""
        s = self.get_settings(guild_id)
        hours = s["new_account_hours"]
        if not s["enabled"] or hours <= 0 or created_at is None:
            return None
        age = datetime.now(TZ_OFFSET).timestamp() - created_at.timestamp()
        if age >= hours * 3600:
            return None
        return (
            DETECT_NEW_ACCOUNT,
            s["new_account_action"],
            partial(
                tx,
                "anti_spam.new_account_detail",
                v0=(max(0, int(age // 3600))),
                v1=(hours),
            ),
        )

    def check_nuke(
        self, guild_id: int, actor_id: int, kind: str, target_id: Optional[int] = None
    ) -> Optional[Tuple[str, str, str]]:
        """同一人在 nuke_window 秒內做了 nuke_limit 次危險操作

        只看 nuke_enabled（只有擁有者能改），不看總開關：管理員關掉防炸群不能順便關掉防破壞。
        """
        s = self.get_settings(guild_id)
        if not s["nuke_enabled"] or actor_id in s["nuke_trusted"]:
            return None
        now = datetime.now(TZ_OFFSET).timestamp()
        if kind in ("ban", "kick") and target_id in self.raiders.get(guild_id, ()):
            return None  # removing an account that came in with the raid
        window = s["nuke_window"]
        log = [(t, k) for t, k in self.nuke_log[guild_id][actor_id] if now - t < window]
        log.append((now, kind))
        if len(log) < s["nuke_limit"]:
            self.nuke_log[guild_id][actor_id] = log
            return None
        self.nuke_log[guild_id].pop(actor_id, None)
        counts = Counter(k for _, k in log)
        kinds = ", ".join(f"{nuke_kind_name(k)} ×{n}" for k, n in counts.most_common())
        return (
            DETECT_NUKE,
            s["nuke_action"],
            tx("anti_spam.nuke_detail", v0=(window), v1=(len(log)), v2=(kinds)),
        )

    def save_strip(self, guild_id: int, user_id: int, role_ids: List[int]) -> None:
        """記下防破壞拔掉的身分組（role_ids 為空時移除紀錄）"""
        with self._settings_lock:
            try:
                raw = read_document(self.NUKE_FILE)
            except FileNotFoundError:
                raw = {}
            if not isinstance(raw, dict):
                raise TypeError("Anti-nuke records must be an object")
            guild = raw.setdefault(str(guild_id), {})
            if role_ids:
                kept = set(guild.get(str(user_id), []))
                guild[str(user_id)] = sorted(kept | set(role_ids))
            else:
                guild.pop(str(user_id), None)
                if not guild:
                    raw.pop(str(guild_id), None)
            write_document(self.NUKE_FILE, raw)

    def get_strip(self, guild_id: int, user_id: int) -> List[int]:
        try:
            raw = read_document(self.NUKE_FILE)
        except FileNotFoundError:
            return []
        if not isinstance(raw, dict):
            raise TypeError("Anti-nuke records must be an object")
        return [int(r) for r in raw.get(str(guild_id), {}).get(str(user_id), [])]

    def prune(self, now: Optional[float] = None) -> None:
        """丟掉已過期的偵測紀錄，避免長期執行時字典只增不減"""
        now = now if now is not None else datetime.now(TZ_OFFSET).timestamp()
        horizon = 3600

        def last(entries: list) -> float:
            if not entries:
                return 0.0
            item = entries[-1]
            return item[0] if isinstance(item, tuple) else item

        for log, keep in (
            (self.message_log, horizon),
            (self.content_log, horizon),
            (self.link_log, horizon),
            (self.strike_log, 86400),  # escalate_window can be long
            (self.recent_messages, horizon),
            (self.attachment_log, horizon),
            (self.nuke_log, horizon),
        ):
            for guild_id in list(log):
                users = log[guild_id]
                for user_id in [
                    u for u, entries in users.items() if now - last(entries) > keep
                ]:
                    del users[user_id]
                if not users:
                    del log[guild_id]
        for flat in (self.join_log, self.joiners, self.guild_messages):
            for guild_id in [
                g for g, entries in flat.items() if now - last(entries) > horizon
            ]:
                del flat[guild_id]
        for guild_id in list(self.hot_signatures):
            self.hot_signatures[guild_id] = [
                (until, sig)
                for until, sig in self.hot_signatures[guild_id]
                if until > now
            ]
            if not self.hot_signatures[guild_id]:
                del self.hot_signatures[guild_id]
        for guild_id in [g for g, until in self.raid_until.items() if until <= now]:
            self.end_raid(guild_id)

    def is_invite_link(self, content: str, guild_id: int) -> bool:
        """快速檢查是否含有邀請連結"""
        s = self.get_settings(guild_id)
        return bool(s["invite_auto_delete"] and INVITE_RE.search(content))

    def is_lockdown(self, guild_id: int) -> bool:
        """是否處於封鎖模式"""
        return self.lockdown_active.get(guild_id, False)

    def set_lockdown(self, guild_id: int, active: bool) -> None:
        """設定封鎖模式"""
        self.lockdown_active[guild_id] = active

    def load_lockdowns(
        self,
    ) -> Tuple[Dict[int, Dict[int, Optional[bool]]], set[int]]:
        """讀回重啟前的封鎖：各頻道原本的發言權限，以及還沒鎖完的伺服器"""
        try:
            raw = read_document(self.LOCKDOWN_FILE)
        except FileNotFoundError:
            return {}, set()
        if not isinstance(raw, dict):
            raise TypeError("Lockdown records must be an object")
        states: Dict[int, Dict[int, Optional[bool]]] = {}
        unfinished: set[int] = set()
        for guild, record in raw.items():
            states[int(guild)] = {
                int(channel): value for channel, value in record["channels"].items()
            }
            if record.get("until") is not None:
                self.lockdown_until[int(guild)] = float(record["until"])
            if not record.get("complete"):
                unfinished.add(int(guild))
            self.lockdown_active[int(guild)] = True
        return states, unfinished

    def save_lockdown(
        self,
        guild_id: int,
        channels: Dict[int, Optional[bool]] | None,
        complete: bool = False,
    ) -> None:
        """記下（channels 為 None 時移除）一個伺服器的封鎖紀錄"""
        with self._settings_lock:
            try:
                raw = read_document(self.LOCKDOWN_FILE)
            except FileNotFoundError:
                raw = {}
            if not isinstance(raw, dict):
                raise TypeError("Lockdown records must be an object")
            if channels is None:
                raw.pop(str(guild_id), None)
            else:
                raw[str(guild_id)] = {
                    "channels": {str(k): v for k, v in channels.items()},
                    "complete": complete,
                    # when it lifts itself; None waits for /anti_spam lockdown_off
                    "until": self.lockdown_until.get(guild_id),
                }
            write_document(self.LOCKDOWN_FILE, raw)

    def save_lockdown_until(self, guild_id: int, until: Optional[float]) -> None:
        """更新封鎖自動解除的時間（已存在的封鎖紀錄一併改寫）"""
        with self._settings_lock:
            if until is None:
                self.lockdown_until.pop(guild_id, None)
            else:
                self.lockdown_until[guild_id] = until
            try:
                raw = read_document(self.LOCKDOWN_FILE)
            except FileNotFoundError:
                return
            if not isinstance(raw, dict):
                raise TypeError("Lockdown records must be an object")
            if str(guild_id) in raw:
                raw[str(guild_id)]["until"] = until
                write_document(self.LOCKDOWN_FILE, raw)

    def due_lockdowns(self, now: Optional[float] = None) -> List[int]:
        """已到自動解除時間的伺服器"""
        now = now if now is not None else datetime.now(TZ_OFFSET).timestamp()
        return [
            g
            for g, until in self.lockdown_until.items()
            if until <= now and self.is_lockdown(g)
        ]

    def reset_user(self, guild_id: int, user_id: int) -> None:
        """重設用戶所有紀錄"""
        for log in (
            self.message_log,
            self.content_log,
            self.link_log,
            self.recent_messages,
            self.attachment_log,
        ):
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
        self, guild_id: int, user_id: int, now: float, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """洪水偵測"""
        window = s["flood_window"]
        limit = s["flood_messages"]

        log = self.message_log[guild_id][user_id]
        log.append(now)
        # 清理過期
        self.message_log[guild_id][user_id] = [t for t in log if now - t < window]

        count = len(self.message_log[guild_id][user_id])
        if count > limit:
            return (
                DETECT_FLOOD,
                s["flood_action"],
                tx("protection.20", v0=(window), v1=(count), v2=(limit)),
            )
        return None

    def _check_duplicate(
        self, guild_id: int, user_id: int, now: float, content: str, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """重複內容偵測"""
        window = s["duplicate_window"]
        limit = s["duplicate_count"]

        log = self.content_log[guild_id][user_id]
        normalized = message_signature(content)
        log.append((now, normalized))

        # 清理過期
        self.content_log[guild_id][user_id] = [
            (t, c) for t, c in log if now - t < window
        ]

        # 計算相同或幾乎相同的內容出現次數
        dup_count = sum(
            1
            for _, c in self.content_log[guild_id][user_id]
            if is_similar(c, normalized)
        )

        if dup_count >= limit:
            return (
                DETECT_DUPLICATE,
                s["duplicate_action"],
                tx("protection.21", v0=(window), v1=(dup_count)),
            )
        return None

    def _check_mentions(
        self, content: str, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """提及轟炸偵測"""
        limit = s["mention_limit"]
        mention_count = (
            content.count("<@") + content.count("@everyone") + content.count("@here")
        )

        if mention_count >= limit:
            return (
                DETECT_MENTION,
                s["mention_action"],
                tx("protection.22", v0=(mention_count)),
            )
        return None

    def _check_links(
        self, guild_id: int, user_id: int, now: float, content: str, s: dict[Any, Any]
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

        self.link_log[guild_id][user_id] = [t for t in log if now - t < window]

        count = len(self.link_log[guild_id][user_id])
        if count >= limit:
            has_invite = bool(INVITE_RE.search(content))
            detail = tx("protection.9", v0=(window), v1=(count))
            if has_invite:
                detail += tx("protection.23")
            return (DETECT_LINK, s["link_action"], detail)
        return None

    def _check_emoji(
        self, content: str, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """表情轟炸偵測"""
        limit = s["emoji_limit"]
        count = len(EMOJI_RE.findall(content))

        if count >= limit:
            return (
                DETECT_EMOJI,
                s["emoji_action"],
                tx("protection.24", v0=(count)),
            )
        return None

    def _check_newline(
        self, content: str, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """換行轟炸偵測"""
        limit = s["newline_limit"]
        count = content.count("\n")

        if count >= limit:
            return (
                DETECT_NEWLINE,
                s["newline_action"],
                tx("protection.25", v0=(count)),
            )
        return None

    def _remember(
        self,
        guild_id: int,
        user_id: int,
        now: float,
        channel_id: int,
        message_id: int,
        signature: str,
    ) -> List[Tuple[float, int, int, str]]:
        """記下這則訊息，回傳這個人最近（含這則）的訊息"""
        keep = max(RECENT_SECONDS, self.get_settings(guild_id)["similar_window"])
        recent = [
            m for m in self.recent_messages[guild_id][user_id] if now - m[0] < keep
        ]
        recent.append((now, channel_id, message_id, signature))
        recent = recent[-RECENT_LIMIT:]
        self.recent_messages[guild_id][user_id] = recent
        return recent

    def _check_similar(
        self,
        guild_id: int,
        user_id: int,
        now: float,
        channel_id: int,
        message_id: int,
        signature: str,
        text: str,
        recent: List[Tuple[float, int, int, str]],
        s: dict[Any, Any],
        evidence: Evidence,
    ) -> Optional[Tuple[str, str, str]]:
        """同一人跨頻道洗相似內容，或多個帳號洗相似內容"""
        window = s["similar_window"]
        action = s["similar_action"]

        # 一個人：相似內容出現在幾個不同頻道
        if len(signature) >= 5 or "[file:" in signature or "[sticker:" in signature:
            alike = [
                m for m in recent if now - m[0] < window and is_similar(m[3], signature)
            ]
            channels = {m[1] for m in alike}
            if len(channels) >= s["similar_channels"]:
                evidence.messages.update((m[1], m[2]) for m in alike if m[2])
                return (
                    DETECT_SIMILAR,
                    action,
                    tx("anti_spam.similar_detail", v0=(window), v1=(len(channels))),
                )

        # 多個帳號只比文字：短句（早安、哈哈）不算；檔名與大小相同不代表是同一個檔案
        signature = text
        if not (len(signature) >= 20 or URL_RE.search(signature)):
            return None
        hot = [
            (until, sig) for until, sig in self.hot_signatures[guild_id] if until > now
        ]
        self.hot_signatures[guild_id] = hot
        log = [m for m in self.guild_messages[guild_id] if now - m[0] < window]
        log.append((now, user_id, channel_id, message_id, signature))
        self.guild_messages[guild_id] = log[-200:]
        if any(is_similar(sig, signature) for _, sig in hot):
            # a wave already caught: whoever joins in now is part of it
            return (DETECT_COORDINATED, action, tx("anti_spam.coordinated_more"))
        alike = [m for m in log if is_similar(m[4], signature)]
        users = {m[1] for m in alike}
        if len(users) < s["similar_users"]:
            return None
        evidence.users.update(users - {user_id})
        evidence.messages.update((m[2], m[3]) for m in alike if m[3])
        self.hot_signatures[guild_id].append((now + window, signature))
        self.guild_messages[guild_id] = [m for m in log if m not in alike]
        return (
            DETECT_COORDINATED,
            action,
            tx("anti_spam.coordinated_detail", v0=(window), v1=(len(users))),
        )

    def _check_attachments(
        self, guild_id: int, user_id: int, now: float, count: int, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """附件／貼圖轟炸"""
        window = s["attachment_window"]
        log = [t for t in self.attachment_log[guild_id][user_id] if now - t < window]
        log.extend([now] * count)
        self.attachment_log[guild_id][user_id] = log
        if len(log) >= s["attachment_limit"]:
            return (
                DETECT_ATTACHMENT,
                s["attachment_action"],
                tx("anti_spam.attachment_detail", v0=(window), v1=(len(log))),
            )
        return None

    def _check_phishing(
        self, content: str, s: dict[Any, Any]
    ) -> Optional[Tuple[str, str, str]]:
        """惡意連結：封鎖清單、仿冒網域、偽裝連結、免費 Nitro 誘餌"""
        allowed = [d.casefold() for d in s["allowed_domains"]]
        blocked = [d.casefold() for d in s["blocked_domains"]]
        urls = URL_RE.findall(content)
        hosts = [link_host(url) for url in urls]
        for host in hosts:
            if not host or domain_listed(host, allowed):
                continue
            if domain_listed(host, blocked):
                return self._phishing(s, tx("anti_spam.phishing_blocked", v0=(host)))
            brand = lookalike_brand(host)
            if brand:
                return self._phishing(
                    s, tx("anti_spam.phishing_lookalike", v0=(host), v1=(brand))
                )
        for label, url in MASKED_LINK_RE.findall(content):
            # Only a label showing a Discord or Steam address counts: [README.md](...)
            # and [socket.io](github) are honest names, not a disguise.
            shown = link_host(label if "://" in label else "https://" + label.strip())
            target = link_host(url)
            if (
                " " not in label.strip()
                and target
                and imitates(shown)
                and not domain_listed(target, [*allowed, *OFFICIAL_DOMAINS])
            ):
                return self._phishing(
                    s, tx("anti_spam.phishing_masked", v0=(shown), v1=(target))
                )
        if LURE_TEXT_RE.search(content):
            # bait text alone also appears in warnings about the scam; it counts
            # with a hidden address (a shortener) or a host named after the bait
            for host in hosts:
                if (
                    host
                    and not domain_listed(host, [*allowed, *OFFICIAL_DOMAINS])
                    and (domain_listed(host, SHORTENERS) or bait_named(host))
                ):
                    return self._phishing(s, tx("anti_spam.phishing_lure", v0=(host)))
        return None

    @staticmethod
    def _phishing(s: dict[Any, Any], detail: str) -> Tuple[str, str, str]:
        return (DETECT_PHISHING, s["phishing_action"], detail)

    # --- 自動升級 ---

    def _apply_escalation(
        self,
        guild_id: int,
        user_id: int,
        now: float,
        triggers: List[Tuple[str, str, str]],
        s: dict[Any, Any],
    ) -> List[Tuple[str, str, str]]:
        """根據違規紀錄自動升級懲罰"""
        window = s["escalate_window"]
        threshold = s["escalate_strikes"]

        # 記錄本次違規
        for det_type, _, _ in triggers:
            self.strike_log[guild_id][user_id].append((now, det_type))

        # 清理過期違規
        self.strike_log[guild_id][user_id] = [
            (t, d) for t, d in self.strike_log[guild_id][user_id] if now - t < window
        ]

        strike_count = len(self.strike_log[guild_id][user_id])
        if strike_count < threshold:
            return triggers

        # 達到升級門檻 — 取最嚴重的現有動作，升一級
        max_severity = max(ACTION_SEVERITY.get(action, 0) for _, action, _ in triggers)

        escalated_action = None
        for act, sev in sorted(ACTION_SEVERITY.items(), key=lambda x: x[1]):
            if sev > max_severity:
                escalated_action = act
                break

        if escalated_action and escalated_action != ACTION_LOCKDOWN:
            return [
                (det, escalated_action, detail + tx("protection.27", v0=(strike_count)))
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


def detection_name(value: str, default=None) -> str:
    keys = {
        DETECT_FLOOD: "anti_spam.message_flood",
        DETECT_DUPLICATE: "protection.0",
        DETECT_MENTION: "protection.1",
        DETECT_LINK: "protection.2",
        DETECT_EMOJI: "protection.3",
        DETECT_NEWLINE: "protection.4",
        DETECT_RAID: "protection.5",
        DETECT_SIMILAR: "anti_spam.detect_similar",
        DETECT_COORDINATED: "anti_spam.detect_coordinated",
        DETECT_ATTACHMENT: "anti_spam.detect_attachment",
        DETECT_PHISHING: "anti_spam.detect_phishing",
        DETECT_NEW_ACCOUNT: "anti_spam.detect_new_account",
        DETECT_NUKE: "anti_spam.detect_nuke",
    }
    key = keys.get(value)
    return tx(key) if key else (default or value)


def nuke_kind_name(kind: str) -> str:
    return tx(f"anti_spam.nuke_kind_{kind}") if kind in NUKE_KINDS else kind


def raid_member_action(s: dict[Any, Any]) -> Optional[str]:
    """What happens to a new account in a raid.

    The raid action, a kick for a lockdown, nothing for "delete" (a joining
    account has no messages yet).
    """
    action = s["raid_action"]
    if action == ACTION_LOCKDOWN:
        return ACTION_KICK
    return (
        action
        if action in (ACTION_WARN, ACTION_MUTE, ACTION_KICK, ACTION_BAN)
        else None
    )


def action_name(value: str, default=None) -> str:
    keys = {
        ACTION_WARN: "report.warn",
        ACTION_DELETE: "protection.6",
        ACTION_MUTE: "report.mute",
        ACTION_KICK: "protection.7",
        ACTION_BAN: "report.ban",
        ACTION_LOCKDOWN: "protection.8",
        NUKE_STRIP: "anti_spam.nuke_strip",
    }
    key = keys.get(value)
    return tx(key) if key else (default or value)


DETECT_COLORS = {
    DETECT_FLOOD: discord.Color.from_rgb(255, 165, 0),
    DETECT_DUPLICATE: discord.Color.from_rgb(255, 200, 0),
    DETECT_MENTION: discord.Color.from_rgb(255, 80, 80),
    DETECT_LINK: discord.Color.from_rgb(200, 100, 200),
    DETECT_EMOJI: discord.Color.from_rgb(100, 200, 255),
    DETECT_NEWLINE: discord.Color.from_rgb(150, 150, 150),
    DETECT_RAID: discord.Color.from_rgb(255, 0, 0),
    DETECT_SIMILAR: discord.Color.from_rgb(255, 140, 60),
    DETECT_COORDINATED: discord.Color.from_rgb(230, 60, 60),
    DETECT_ATTACHMENT: discord.Color.from_rgb(120, 170, 255),
    DETECT_PHISHING: discord.Color.from_rgb(180, 0, 90),
    DETECT_NEW_ACCOUNT: discord.Color.from_rgb(255, 120, 0),
    DETECT_NUKE: discord.Color.from_rgb(150, 0, 0),
}


def create_anti_spam_log_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: Optional[int],
    detection_type: str,
    action: str,
    detail: str,
    strike_count: int = 0,
) -> discord.Embed:
    """建立防炸群日誌 Embed"""
    color = DETECT_COLORS.get(detection_type, discord.Color.from_rgb(255, 165, 0))
    type_name = detection_name(detection_type, detection_type)
    action_label = action_name(action, action)

    embed = discord.Embed(
        title=tx("protection.10", v0=(type_name)),
        color=color,
        timestamp=datetime.now(TZ_OFFSET),
    )

    embed.add_field(
        name=tx("audit_log.user"), value=f"<@{user_id}> ({user_id})", inline=False
    )
    embed.add_field(name=tx("protection.11"), value=user_name, inline=True)
    if channel_id:
        embed.add_field(
            name=tx("audit_log.channel"),
            value=f"<#{channel_id}> ({channel_id})",
            inline=True,
        )
    embed.add_field(name=tx("protection.12"), value=type_name, inline=True)
    embed.add_field(name=tx("protection.13"), value=detail, inline=False)
    embed.add_field(name=tx("protection.14"), value=action_label, inline=True)

    if strike_count > 0:
        embed.add_field(
            name=tx("protection.26"),
            value=tx("anti_spam.times", v0=(strike_count)),
            inline=True,
        )

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
    action_label = action_name(action, action)

    embed = discord.Embed(
        title=tx("protection.15"),
        description=(tx("protection.16", v0=(window), v1=(join_count))),
        color=discord.Color.from_rgb(255, 0, 0),
        timestamp=datetime.now(TZ_OFFSET),
    )

    embed.add_field(name=tx("protection.14"), value=action_label, inline=True)
    embed.add_field(
        name=tx("protection.17"),
        value=(tx("protection.18")),
        inline=False,
    )
    embed.set_footer(text=f"{guild_name} ({guild_id})")

    return embed


def create_nuke_alert_embed(
    guild_name: str,
    guild_id: int,
    actor_id: int,
    detail: str,
    outcome: str,
) -> discord.Embed:
    """建立防破壞警報 Embed"""
    embed = discord.Embed(
        title=tx("anti_spam.nuke_alert_title"),
        description=detail,
        color=DETECT_COLORS[DETECT_NUKE],
        timestamp=datetime.now(TZ_OFFSET),
    )
    embed.add_field(
        name=tx("anti_spam.nuke_actor"),
        value=f"<@{actor_id}> ({actor_id})",
        inline=False,
    )
    embed.add_field(name=tx("protection.14"), value=outcome, inline=False)
    embed.add_field(
        name=tx("protection.17"), value=tx("anti_spam.nuke_next_steps"), inline=False
    )
    embed.set_footer(text=f"{guild_name} ({guild_id})")
    return embed
