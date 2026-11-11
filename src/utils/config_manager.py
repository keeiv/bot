import asyncio
import copy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
import time
from typing import Any, Optional

from src.utils.document_store import document_exists
from src.utils.document_store import open_document
from src.utils.document_store import write_document

CONFIG_FILE = "data/config/bot.json"
MESSAGES_LOG_FILE = "data/logs/messages/訊息.json"
DATA_DIR = "data"

# The UTC+8 time zone
TZ_OFFSET = timezone(timedelta(hours=8))

# ── In-memory cache layer ─────────────────────────────────────────
_config_cache: Optional[dict[Any, Any]] = None
_config_cache_time: float = 0
_CONFIG_CACHE_TTL: float = 30.0  # 30-second TTL
_config_lock = asyncio.Lock()


def _invalidate_config_cache() -> None:
    """Invalidate the cache on purpose."""
    global _config_cache, _config_cache_time
    _config_cache = None
    _config_cache_time = 0


def ensure_data_dir() -> None:
    """Make sure the data directory exists."""
    for directory in ["data", "data/config", "data/storage", "data/logs/messages"]:
        os.makedirs(directory, exist_ok=True)


def load_config() -> Any:
    """Load a config file (with the in-memory cache)."""
    global _config_cache, _config_cache_time

    now = time.monotonic()
    if _config_cache is not None and (now - _config_cache_time) < _CONFIG_CACHE_TTL:
        return copy.deepcopy(_config_cache)

    if not document_exists(CONFIG_FILE):
        save_config({"guilds": {}})

    with open_document(CONFIG_FILE, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
    _config_cache_time = now
    return copy.deepcopy(_config_cache)


def save_config(config: Any) -> None:
    """Save a config file and update the cache (atomic write)."""
    global _config_cache, _config_cache_time
    write_document(CONFIG_FILE, config)
    _config_cache = copy.deepcopy(config)
    _config_cache_time = time.monotonic()


def get_guild_log_channel(guild_id: int) -> Optional[int]:
    """The ID of the server's log channel."""
    config = load_config()
    guild_str = str(guild_id)
    result_value = config.get("guilds", {}).get(guild_str, {}).get("log_channel")
    if result_value is None:
        return None
    if not isinstance(result_value, int):
        raise TypeError("Unexpected stored or API value: expected int")
    return result_value


def set_guild_log_channel(guild_id: int, channel_id: int) -> None:
    """Set the ID of the server's log channel."""
    config = load_config()
    guild_str = str(guild_id)

    if "guilds" not in config:
        config["guilds"] = {}
    if guild_str not in config["guilds"]:
        config["guilds"][guild_str] = {}

    config["guilds"][guild_str]["log_channel"] = channel_id
    save_config(config)


def get_guild_report_channel(guild_id: int) -> Optional[int]:
    """The ID of the server's report channel."""
    config = load_config()
    guild_str = str(guild_id)
    result_value = config.get("guilds", {}).get(guild_str, {}).get("report_channel")
    if result_value is None:
        return None
    if not isinstance(result_value, int):
        raise TypeError("Unexpected stored or API value: expected int")
    return result_value


def set_guild_report_channel(guild_id: int, channel_id: int) -> None:
    """Set the ID of the server's report channel."""
    config = load_config()
    guild_str = str(guild_id)

    if "guilds" not in config:
        config["guilds"] = {}
    if guild_str not in config["guilds"]:
        config["guilds"][guild_str] = {}

    config["guilds"][guild_str]["report_channel"] = channel_id
    save_config(config)


# Unified message log JSON (in-memory cache and batched writes)

_messages_cache: Optional[dict[Any, Any]] = None
_messages_cache_time: float = 0
_MESSAGES_CACHE_TTL: float = 60.0  # 60-second TTL
_messages_dirty: bool = False


def load_messages_log() -> dict[Any, Any]:
    """Load the unified message log (with the in-memory cache)."""
    global _messages_cache, _messages_cache_time

    now = time.monotonic()
    if (
        _messages_cache is not None
        and (now - _messages_cache_time) < _MESSAGES_CACHE_TTL
    ):
        return _messages_cache

    if not document_exists(MESSAGES_LOG_FILE):
        _messages_cache = {}
        _messages_cache_time = now
        return _messages_cache

    try:
        with open_document(MESSAGES_LOG_FILE, "r", encoding="utf-8") as f:
            _messages_cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        _messages_cache = {}
    _messages_cache_time = now
    return _messages_cache


def save_messages_log(data: dict[Any, Any]) -> None:
    """Save the unified message log and update the cache."""
    global _messages_cache, _messages_cache_time
    try:
        with open_document(MESSAGES_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[錯誤] 無法保存訊息日誌: {e}")
    _messages_cache = data
    _messages_cache_time = time.monotonic()


def add_message_record(
    guild_id: int,
    message_id: int,
    content: str,
    author_id: int | None,
    channel_id: int | None,
) -> Any:
    """Add a message record (unified JSON)."""
    records = load_messages_log()
    # Composite key: guild_message
    msg_key = f"{guild_id}_{message_id}"

    if msg_key not in records:
        records[msg_key] = {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "author_id": author_id,
            "original_content": content,
            "edit_history": [],
            "deleted": False,
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
        }
        save_messages_log(records)
        print(f"[JSON] 已新增訊息記錄: {msg_key}")
        return True
    return False


def update_message_edit(guild_id: int, message_id: int, new_content: str) -> Any:
    """Update a message's edit history (unified JSON)."""
    records = load_messages_log()
    msg_key = f"{guild_id}_{message_id}"

    if msg_key in records:
        records[msg_key]["edit_history"].append(new_content)
        records[msg_key]["last_edited_at"] = datetime.now(TZ_OFFSET).isoformat()
        save_messages_log(records)
        print(
            f"[JSON] 已更新編輯歷史: {msg_key} (編輯次數: {len(records[msg_key]['edit_history'])})"
        )
        return True
    else:
        print(f"[JSON] 未找到訊息記錄: {msg_key}，建立新紀錄...")
        # With no record yet, create an empty one first, then add the edit
        add_message_record(guild_id, message_id, new_content, None, None)
        records = load_messages_log()
        msg_key = f"{guild_id}_{message_id}"
        if msg_key in records:
            records[msg_key]["edit_history"].append(new_content)
            save_messages_log(records)
        return False


def mark_message_deleted(guild_id: int, message_id: int) -> Any:
    """Mark a message deleted (unified JSON)."""
    records = load_messages_log()
    msg_key = f"{guild_id}_{message_id}"

    if msg_key in records:
        records[msg_key]["deleted"] = True
        records[msg_key]["deleted_at"] = datetime.now(TZ_OFFSET).isoformat()
        save_messages_log(records)
        print(f"[JSON] 已標記刪除: {msg_key}")
        return True
    else:
        print(f"[JSON] 未找到訊息記錄: {msg_key}")
        return False


def get_message_record(guild_id: int, message_id: int) -> Optional[dict[Any, Any]]:
    """Get a message record (unified JSON)."""
    records = load_messages_log()
    msg_key = f"{guild_id}_{message_id}"
    return records.get(msg_key)
