"""審計日誌業務邏輯服務"""

import copy
import time
from typing import Any, Optional

from src.utils.document_store import read_document
from src.utils.document_store import write_document

TZ_OFFSET_HOURS = 8
_CHANNELS_FILE = "data/storage/log_channels.json"
_CACHE_TTL = 60.0


class AuditLogService:
    """審計日誌頻道設定存取"""

    def __init__(self) -> None:
        self._cache: dict[Any, Any] = {}
        self._cache_time: float = 0.0

    def load(self, force=False) -> dict[Any, Any]:
        """Read a detached snapshot; failed reads do not clear valid cache."""
        now = time.monotonic()
        if not force and self._cache and (now - self._cache_time) < _CACHE_TTL:
            return copy.deepcopy(self._cache)
        try:
            data = read_document(_CHANNELS_FILE)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            raise TypeError("Channel configuration must be an object")
        self._cache = data
        self._cache_time = now
        return copy.deepcopy(data)

    def set_channel_id(self, guild_id: int, channel_id: Optional[int]) -> None:
        """Update one guild using current persisted configuration."""
        channels = self.load(force=True)
        if channel_id is None:
            channels.pop(str(guild_id), None)
        else:
            channels[str(guild_id)] = channel_id
        write_document(_CHANNELS_FILE, channels)
        self._cache = channels
        self._cache_time = time.monotonic()

    def get_channel_id(self, guild_id: int) -> Optional[int]:
        """取得伺服器的審計日誌頻道 ID"""
        return self.load().get(str(guild_id))
