"""審計日誌業務邏輯服務"""

import json
import os
import time
from typing import Optional

TZ_OFFSET_HOURS = 8
_CHANNELS_FILE = "data/storage/log_channels.json"
_CACHE_TTL = 60.0


class AuditLogService:
    """審計日誌頻道設定存取"""

    def __init__(self) -> None:
        self._cache: dict = {}
        self._cache_time: float = 0.0

    def load(self) -> dict:
        """載入所有伺服器日誌頻道設定 (帶快取)"""
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < _CACHE_TTL:
            return self._cache
        if not os.path.exists(_CHANNELS_FILE):
            self._cache = {}
            self._cache_time = now
            return self._cache
        try:
            with open(_CHANNELS_FILE, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        self._cache_time = now
        return self._cache

    def get_channel_id(self, guild_id: int) -> Optional[int]:
        """取得伺服器的審計日誌頻道 ID"""
        return self.load().get(str(guild_id))
