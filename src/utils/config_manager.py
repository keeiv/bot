from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from typing import Optional

CONFIG_FILE = "data/config/bot.json"
MESSAGES_LOG_FILE = "data/logs/messages/訊息.json"
DATA_DIR = "data"

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


def ensure_data_dir():
    """確保數據目錄存在"""
    directories = ["data", "data/config", "data/storage", "data/logs/messages"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)


def load_config():
    """載入配置檔案"""
    if not os.path.exists(CONFIG_FILE):
        save_config({"guilds": {}})

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """儲存配置檔案"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_guild_log_channel(guild_id: int) -> Optional[int]:
    """獲取伺服器的日誌頻道 ID"""
    config = load_config()
    guild_str = str(guild_id)
    return config.get("guilds", {}).get(guild_str, {}).get("log_channel")


def set_guild_log_channel(guild_id: int, channel_id: int):
    """設置伺服器的日誌頻道 ID"""
    config = load_config()
    guild_str = str(guild_id)

    if "guilds" not in config:
        config["guilds"] = {}
    if guild_str not in config["guilds"]:
        config["guilds"][guild_str] = {}

    config["guilds"][guild_str]["log_channel"] = channel_id
    save_config(config)


# ========== 統一訊息日誌 JSON ==========


def load_messages_log() -> dict:
    """載入統一的訊息紀錄日誌"""
    if not os.path.exists(MESSAGES_LOG_FILE):
        return {}

    with open(MESSAGES_LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_messages_log(data: dict):
    """儲存統一的訊息紀錄日誌"""
    with open(MESSAGES_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_message_record(
    guild_id: int, message_id: int, content: str, author_id: int, channel_id: int
):
    """新增訊息記錄（統一 JSON）"""
    records = load_messages_log()
    # 複合金鑰：guild_message
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


def update_message_edit(guild_id: int, message_id: int, new_content: str):
    """更新訊息編輯歷史記錄（統一 JSON）"""
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
        # 如果沒有記錄，先建立一個空的，然後新增編輯內容
        add_message_record(guild_id, message_id, new_content, None, None)
        records = load_messages_log()
        msg_key = f"{guild_id}_{message_id}"
        if msg_key in records:
            records[msg_key]["edit_history"].append(new_content)
            save_messages_log(records)
        return False


def mark_message_deleted(guild_id: int, message_id: int):
    """標記訊息為已刪除（統一 JSON）"""
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


def get_message_record(guild_id: int, message_id: int) -> Optional[dict]:
    """取得訊息記錄（統一 JSON）"""
    records = load_messages_log()
    msg_key = f"{guild_id}_{message_id}"
    return records.get(msg_key)
