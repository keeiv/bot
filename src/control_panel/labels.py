"""Chinese names for the bot's stored documents and their fields.

The data browser shows the Chinese for "server ID" where the document says
``guild_id``. A
field is named from, in order: its exact entry in ``WORDS``; a known suffix
(``_id``, ``_at``, ``_enabled`` ...) applied to the Chinese of what comes before
it; or, failing both, its own English name. Fields that hold credentials are
recognised here too, so the browser can hide them.
"""

import re
from typing import Optional

# ── documents ─────────────────────────────────────────────────────

DOCUMENTS: dict[str, str] = {
    "data/config/bot.json": "機器人設定",
    "data/ai_usage.json": "AI 用量",
    "data/storage/blacklist.json": "黑名單",
    "data/storage/appeals.json": "黑名單申訴",
    "data/storage/achievements.json": "成就",
    "data/storage/age_guard.json": "年齡驗證",
    "data/storage/ai_chat.json": "AI 聊天",
    "data/storage/anti_nuke_strips.json": "防炸群：拔除的權限",
    "data/storage/anti_spam_lockdowns.json": "防洗版：封鎖紀錄",
    "data/storage/anti_spam_settings.json": "防洗版：設定",
    "data/storage/endfield_bindings.json": "明日方舟：終末地 綁定",
    "data/storage/genshin_accounts.json": "HoYoLAB／米游社 帳號",
    "data/storage/genshin_signin_log.json": "自動簽到紀錄",
    "data/storage/github_watch.json": "GitHub 倉庫通知",
    "data/storage/giveaways.json": "抽獎",
    "data/storage/global_bans.json": "全域封禁",
    "data/storage/languages.json": "語言設定",
    "data/storage/log_channels.json": "日誌頻道",
    "data/storage/management.json": "管理：歡迎訊息與自動身分組",
    "data/storage/petition.json": "請願",
    "data/storage/temp_voice.json": "臨時語音",
    "data/storage/tickets.json": "工單",
    "data/storage/pets/_index.json": "夥伴：索引",
    "data/logs/messages/message_log.json": "訊息日誌（已搬到資料表）",
}

# Copies left by older versions that no code reads any more.
UNUSED: dict[str, str] = {
    "data/blacklist.json": "黑名單（舊位置）",
    "data/achievements.json": "成就（舊位置）",
    "data/github_watch.json": "GitHub 倉庫通知（舊位置）",
    "data/log_channels.json": "日誌頻道（舊位置）",
    "data/message_log.json": "訊息日誌（舊位置）",
    "data/config/config.json": "舊設定",
    "data/cross_dressing_data.json": "舊功能資料",
    "data/storage/anti_spam.json": "防洗版（舊設定）",
    "data/storage/bot_status.json": "機器人狀態（舊）",
    "data/storage/daily.json": "每日簽到（舊）",
    "data/storage/economy.json": "經濟（舊）",
    "data/storage/shop.json": "商店（舊）",
}

# What the numeric keys at the top of a document stand for (from the services
# that read them).
TOP_IDS: dict[str, str] = {
    "data/storage/anti_spam_settings.json": "伺服器",
    "data/storage/age_guard.json": "伺服器",
    "data/storage/log_channels.json": "伺服器",
    "data/storage/management.json": "伺服器",
    "data/storage/github_watch.json": "伺服器",
    "data/storage/genshin_accounts.json": "使用者",
    "data/storage/endfield_bindings.json": "使用者",
    "data/storage/petition.json": "使用者",
    "data/storage/achievements.json": "使用者",
    "data/storage/giveaways.json": "抽獎",
}

PET_FOLDER = "data/storage/pets/"
_GUILD_FILE = re.compile(r"guild_(\d+)_(\w+)")


def is_unused(path: str) -> bool:
    """Whether the document is a leftover no code reads."""
    name = path.rsplit("/", 1)[-1].removesuffix(".json")
    return path in UNUSED or bool(_GUILD_FILE.fullmatch(name))


def document_label(path: str) -> str:
    """The Chinese name of a stored document, or its file name if unknown."""
    if path in DOCUMENTS:
        return DOCUMENTS[path]
    if path in UNUSED:
        return UNUSED[path]
    if path.startswith(PET_FOLDER):
        return f"夥伴：{path[len(PET_FOLDER):].removesuffix('.json')}"
    name = path.rsplit("/", 1)[-1].removesuffix(".json")
    guild = _GUILD_FILE.fullmatch(name)
    if guild:
        return f"伺服器 {guild.group(1)} 的 {guild.group(2)}"
    return name


# ── fields ────────────────────────────────────────────────────────

WORDS: dict[str, str] = {
    # who and where
    "guild": "伺服器",
    "guilds": "伺服器",
    "server": "伺服器",
    "server_name": "伺服器名稱",
    "channel": "頻道",
    "channels": "頻道",
    "user": "使用者",
    "users": "使用者",
    "username": "使用者名稱",
    "role": "身分組",
    "roles": "身分組",
    "message": "訊息",
    "author": "作者",
    "creator": "建立者",
    "host": "主辦者",
    "owner": "擁有者",
    "category": "分類",
    "trigger_channel": "觸發頻道",
    "status_channel": "狀態頻道",
    "report_channel": "檢舉頻道",
    "log_channel": "日誌頻道",
    "welcome_channel": "歡迎頻道",
    "guide_channel": "引導頻道",
    "guide_message": "引導訊息",
    "panel_message": "面板訊息",
    "adult_role": "成年身分組",
    "punishment_role": "懲罰身分組",
    "punish_role": "懲罰身分組",
    "staff_role": "客服身分組",
    "auto_role": "自動身分組",
    "auto_roles": "自動身分組",
    "welcome_auto_role": "歡迎後自動身分組",
    "whitelisted_channels": "白名單頻道",
    "whitelisted_roles": "白名單身分組",
    # time
    "created": "建立",
    "closed": "關閉",
    "deleted": "已刪除",
    "deleted_at": "刪除時間",
    "last_edited": "最後編輯",
    "bound": "綁定",
    "added": "加入",
    "expires": "到期",
    "reviewed": "審核",
    "unlocked": "已解鎖",
    "ended": "已結束",
    "end_time": "結束時間",
    "down_until": "暫停到",
    "downtime_start": "停機開始",
    "last_update": "最後更新",
    "last_run_date": "最後執行日期",
    "last_request_date": "最後請求日期",
    "last_sign": "最後簽名",
    "date": "日期",
    "day": "日期",
    "delay": "延遲（秒）",
    "interval_minutes": "檢查間隔（分鐘）",
    "mute_duration": "禁言時長（秒）",
    "ban_delete_days": "封禁時刪除幾天內的訊息",
    "consecutive_days": "連續天數",
    "streak": "連續天數",
    # anti-spam
    "flood": "洗版",
    "flood_messages": "洗版判定則數",
    "duplicate": "重複訊息",
    "emoji": "表情符號",
    "link": "連結",
    "mention": "提及",
    "newline": "換行",
    "raid": "突襲",
    "raid_joins": "突襲判定加入人數",
    "escalate": "加重處罰",
    "escalate_strikes": "加重處罰前的次數",
    "auto_escalate": "自動加重處罰",
    "invite_auto_delete": "自動刪除邀請連結",
    "send_dm": "私訊通知",
    "require_verification": "需要驗證",
    "min_members": "最少成員數",
    # tickets, giveaways, petitions
    "ticket_count": "工單總數",
    "ticket_number": "工單編號",
    "tickets": "工單",
    "close_reason": "關閉原因",
    "prize": "獎品",
    "winners": "得主人數",
    "winner_ids": "得主",
    "participants": "參加者",
    "settled": "已抽出得主",
    "drawing": "抽獎中",
    "announced": "已公告結果",
    "announce_tries": "公告失敗次數",
    "description": "說明",
    "desc": "說明",
    # general
    "enabled": "啟用",
    "status": "狀態",
    "reason": "原因",
    "review_reason": "審核意見",
    "mode": "模式",
    "source": "來源",
    "note": "備註",
    "name": "名稱",
    "nickname": "暱稱",
    "level": "等級",
    "uid": "UID",
    "token": "登入權杖",
    "encrypted_cookie": "Cookie（加密）",
    "region": "伺服器區域",
    "game_accounts": "遊戲帳號",
    "game_biz": "遊戲代號",
    "auto_sign_in": "自動簽到",
    "lang": "語言",
    "baseline_done": "已建立基準",
    "guide_pending": "引導待發送",
    "action": "處置",
    "count": "次數",
    "limit": "上限",
    "window": "判定區間（秒）",
    "price": "價格",
    "items": "項目",
    "id": "ID",
    "repo": "倉庫",
    "tracked_repos": "追蹤的倉庫",
    "last_sha": "最後一次提交",
    "last_commit": "最後一次提交",
    "last_pr": "最後一個拉取請求",
    "welcome": "歡迎設定",
    "welcome_enabled": "啟用歡迎訊息",
    "welcome_message": "歡迎訊息",
    "welcome_send_dm": "歡迎時私訊",
    "embed_color": "嵌入顏色",
    "embed_title": "嵌入標題",
    "name_template": "名稱範本",
    "original_content": "原始內容",
    "edit_history": "編輯紀錄",
    "attachments": "附件",
    "blacklisted_users": "黑名單使用者",
    "user_requests": "使用者請求",
    "calls": "呼叫次數",
    "failures": "失敗次數",
    "installed": "已安裝",
    "model": "模型",
    "models": "模型",
    "providers": "服務商",
    "tokens": "權杖數",
    # companions
    "pet": "夥伴",
    "pets": "夥伴",
    "species": "種族",
    "nature": "性格",
    "stage": "進化階段",
    "satiety": "飽足",
    "mood": "心情",
    "energy": "體力",
    "coins": "金幣",
    "bag": "背包",
    "trip": "遠征",
    "zone": "區域",
    "stats": "能力值",
    "aptitudes": "天賦",
    "breaks": "突破次數",
    "evolved": "已進化",
    "mutated": "已突變",
    "born": "誕生時間",
    "nature_at": "上次改性格時間",
    "owner_levels": "飼主等級",
}

SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_ids", "{} ID 清單"),
    ("_id", "{} ID"),
    ("_at", "{}時間"),
    ("_enabled", "啟用{}"),
    ("_limit", "{}上限"),
    ("_window", "{}判定區間（秒）"),
    ("_action", "{}處置"),
    ("_count", "{}次數"),
    ("_minutes", "{}（分鐘）"),
    ("_days", "{}（天）"),
    ("_seconds", "{}（秒）"),
    ("_by", "{}者"),
)

# Credentials and anything derived from them: shown masked, never editable.
SENSITIVE = re.compile(
    r"token|cookie|secret|password|passwd|api_?key|encrypted|signature|hash|jws",
    re.IGNORECASE,
)

# What a container of numeric keys holds, so "1461…" reads as a server or a member.
ID_KINDS: dict[str, str] = {
    "guilds": "伺服器",
    "users": "使用者",
    "channels": "頻道",
    "roles": "身分組",
    "tickets": "工單",
    "blacklisted_users": "使用者",
    "pets": "夥伴",
}

_ACHIEVEMENT = "unlocked_at_"


def is_sensitive(key: str) -> bool:
    return bool(SENSITIVE.search(key))


def field_label(
    key: str, parent: Optional[str] = None, document: Optional[str] = None
) -> str:
    """The Chinese for one field name.

    Numeric-ID keys are named from ``parent`` (the field holding them) or, at
    the top of a document, from ``document``.
    """
    if key.isdigit() or re.fullmatch(r"\d+_\d+", key):
        if parent is not None:
            kind = ID_KINDS.get(parent, "")
        else:
            kind = TOP_IDS.get(document or "", "")
        return f"{kind} {key}".strip()
    if key in WORDS:
        return WORDS[key]
    if key.startswith(_ACHIEVEMENT):
        return f"解鎖時間：{key[len(_ACHIEVEMENT):]}"
    for suffix, pattern in SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            stem = key[: -len(suffix)]
            if stem in WORDS:
                return pattern.format(WORDS[stem])
    return key


def is_named_document(path: str) -> bool:
    """Whether the document is one the bot uses by name (listed first)."""
    return path in DOCUMENTS or path.startswith(PET_FOLDER)


def is_named(key: str) -> bool:
    """Whether ``field_label`` has a Chinese name for it (not just the key back)."""
    return field_label(key) != key
