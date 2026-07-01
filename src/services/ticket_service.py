"""工單業務邏輯服務"""

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from typing import Optional

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/tickets.json"


class TicketService:
    """工單資料存取與業務邏輯"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
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
        self._cache = {"guilds": {}, "tickets": {}}
        return self._cache

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = data

    # ─────────────── 伺服器設定 ───────────────

    def get_guild_config(self, guild_id: int) -> Optional[dict]:
        """取得伺服器工單系統設定"""
        return self._load().get("guilds", {}).get(str(guild_id))

    def save_guild_config(
        self,
        guild_id: int,
        channel_id: int,
        role_id: int,
        panel_message_id: int,
        ticket_count: int = 0,
    ) -> None:
        """儲存伺服器工單系統設定"""
        data = self._load()
        data.setdefault("guilds", {})[str(guild_id)] = {
            "channel_id": channel_id,
            "role_id": role_id,
            "panel_message_id": panel_message_id,
            "ticket_count": ticket_count,
        }
        self._save(data)

    # ─────────────── 工單 CRUD ───────────────

    def get_ticket(self, thread_id: int) -> Optional[dict]:
        """取得工單資料"""
        return self._load().get("tickets", {}).get(str(thread_id))

    def find_open_ticket(self, guild_id: int, user_id: int) -> Optional[int]:
        """尋找用戶在指定伺服器是否已有開啟中工單，回傳 thread_id"""
        data = self._load()
        for tid, tinfo in data.get("tickets", {}).items():
            if (
                tinfo.get("creator_id") == user_id
                and tinfo.get("guild_id") == guild_id
                and tinfo.get("status") == "open"
            ):
                return int(tid)
        return None

    def create_ticket(
        self,
        guild_id: int,
        thread_id: int,
        channel_id: int,
        creator_id: int,
        ticket_number: int,
    ) -> None:
        """建立工單記錄"""
        data = self._load()
        data.setdefault("tickets", {})[str(thread_id)] = {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "creator_id": creator_id,
            "ticket_number": ticket_number,
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "status": "open",
            "closed_by": None,
            "close_reason": None,
            "closed_at": None,
        }
        self._save(data)

    def close_ticket(
        self,
        thread_id: int,
        closed_by_id: int,
        reason: Optional[str] = None,
    ) -> bool:
        """關閉工單，回傳是否成功"""
        data = self._load()
        ticket_id = str(thread_id)
        if ticket_id not in data.get("tickets", {}):
            return False
        data["tickets"][ticket_id]["status"] = "closed"
        data["tickets"][ticket_id]["closed_by"] = closed_by_id
        data["tickets"][ticket_id]["close_reason"] = reason
        data["tickets"][ticket_id]["closed_at"] = datetime.now(TZ_OFFSET).isoformat()
        self._save(data)
        return True

    def increment_ticket_count(self, guild_id: int) -> int:
        """遞增工單計數並回傳新值"""
        data = self._load()
        cfg = data.setdefault("guilds", {}).setdefault(str(guild_id), {})
        count = cfg.get("ticket_count", 0) + 1
        cfg["ticket_count"] = count
        self._save(data)
        return count

    def can_close(self, thread_id: int, user_id: int, is_staff: bool) -> bool:
        """判斷用戶是否有權限關閉工單"""
        ticket = self.get_ticket(thread_id)
        if not ticket:
            return False
        return is_staff or ticket.get("creator_id") == user_id
