"""年齡守門員業務邏輯服務"""

import json
import os
import re
import time
from typing import Optional

_DATA_FILE = "data/storage/age_guard.json"
_CACHE_TTL = 60.0

# 偵測模式：任意位置的完整數字 + 「歲」
# (?<!\d) 負向回顧確保不截斷較長數字 (114514歲 不會被截為 14)
_AGE_PATTERN = re.compile(r"(?<!\d)(\d+)\s*歲")


class AgeGuardService:
    """年齡守門員資料存取與偵測邏輯"""

    def __init__(self) -> None:
        self._cache: dict = {}
        self._cache_time: float = 0.0

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict:
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < _CACHE_TTL:
            return self._cache
        if not os.path.exists(_DATA_FILE):
            self._cache = {}
            self._cache_time = now
            return self._cache
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        self._cache_time = now
        return self._cache

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = data
        self._cache_time = time.monotonic()

    # ─────────────── 設定存取 ───────────────

    def get_config(self, guild_id: int) -> dict:
        """取得伺服器設定，不存在則回傳空 dict"""
        return self._load().get(str(guild_id), {})

    def set_adult_role(self, guild_id: int, role_id: int) -> None:
        """設定成人身份組"""
        data = self._load()
        data.setdefault(str(guild_id), {})["adult_role_id"] = role_id
        self._save(data)

    def set_punishment_role(self, guild_id: int, role_id: int) -> None:
        """設定懲罰身份組"""
        data = self._load()
        data.setdefault(str(guild_id), {})["punishment_role_id"] = role_id
        self._save(data)

    def toggle_enabled(self, guild_id: int) -> bool:
        """切換啟用狀態，回傳新狀態"""
        data = self._load()
        cfg = data.setdefault(str(guild_id), {})
        new_state = not cfg.get("enabled", False)
        cfg["enabled"] = new_state
        self._save(data)
        return new_state

    # ─────────────── 偵測邏輯 ───────────────

    def detect_underage(self, content: str) -> Optional[int]:
        """從訊息內容偵測未成年年齡宣告，回傳年齡或 None"""
        match = _AGE_PATTERN.search(content)
        if not match:
            return None
        age = int(match.group(1))
        return age if age < 18 else None
