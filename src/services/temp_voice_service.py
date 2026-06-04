import json
import os
from typing import Optional

_DATA_FILE = "data/storage/temp_voice.json"


class TempVoiceService:
    """暫時語音頻道資料存取與業務邏輯"""

    def __init__(self) -> None:
        self._cache: Optional[dict] = None

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                    return self._cache
            except (json.JSONDecodeError, OSError):
                pass
        self._cache = {"guilds": {}, "channels": {}}
        return self._cache

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = data

    # ─────────────── 伺服器設定 ───────────────

    def get_guild_config(self, guild_id: int) -> Optional[dict]:
        """取得伺服器暫時語音頻道設定"""
        return self._load().get("guilds", {}).get(str(guild_id))

    def save_guild_config(
        self,
        guild_id: int,
        trigger_channel_id: int,
        category_id: Optional[int],
        name_template: str,
    ) -> None:
        """儲存伺服器暫時語音頻道設定"""
        data = self._load()
        data.setdefault("guilds", {})[str(guild_id)] = {
            "trigger_channel_id": trigger_channel_id,
            "category_id": category_id,
            "name_template": name_template,
        }
        self._save(data)

    def remove_guild_config(self, guild_id: int) -> None:
        """移除伺服器設定"""
        data = self._load()
        data.setdefault("guilds", {}).pop(str(guild_id), None)
        self._save(data)

    # ─────────────── 暫時頻道管理 ───────────────

    def get_channel(self, channel_id: int) -> Optional[dict]:
        """取得暫時頻道資料"""
        return self._load().get("channels", {}).get(str(channel_id))

    def get_guild_channels(self, guild_id: int) -> list[dict]:
        """取得伺服器所有暫時頻道資料"""
        data = self._load()
        return [
            ch for ch in data.get("channels", {}).values()
            if ch.get("guild_id") == guild_id
        ]

    def get_all_channel_ids(self) -> list[int]:
        """取得所有已記錄的暫時頻道 ID"""
        return [int(cid) for cid in self._load().get("channels", {}).keys()]

    def save_channel(
        self,
        channel_id: int,
        guild_id: int,
        owner_id: int,
    ) -> None:
        """建立暫時頻道記錄"""
        data = self._load()
        data.setdefault("channels", {})[str(channel_id)] = {
            "guild_id": guild_id,
            "owner_id": owner_id,
            "banned_users": [],
        }
        self._save(data)

    def remove_channel(self, channel_id: int) -> None:
        """移除暫時頻道記錄"""
        data = self._load()
        data.setdefault("channels", {}).pop(str(channel_id), None)
        self._save(data)

    def remove_stale_channels(self, valid_channel_ids: set[int]) -> int:
        """移除不再存在的頻道記錄，回傳清理數量"""
        data = self._load()
        channels = data.get("channels", {})
        stale = [cid for cid in channels if int(cid) not in valid_channel_ids]
        for cid in stale:
            del channels[cid]
        if stale:
            self._save(data)
        return len(stale)

    # ─────────────── 擁有者管理 ───────────────

    def set_owner(self, channel_id: int, new_owner_id: int) -> None:
        """更新頻道擁有者"""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch:
            ch["owner_id"] = new_owner_id
            self._save(data)

    # ─────────────── 封鎖清單 ───────────────

    def add_ban(self, channel_id: int, user_id: int) -> None:
        """新增封鎖用戶"""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch and user_id not in ch.get("banned_users", []):
            ch.setdefault("banned_users", []).append(user_id)
            self._save(data)

    def remove_ban(self, channel_id: int, user_id: int) -> None:
        """移除封鎖用戶"""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch and user_id in ch.get("banned_users", []):
            ch["banned_users"].remove(user_id)
            self._save(data)
