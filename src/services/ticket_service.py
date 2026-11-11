"""Ticket business logic."""

import asyncio
import copy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from typing import Any, Optional

from src.utils.document_store import open_document
from src.utils.document_store import read_document
from src.utils.i18n import text as tx

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/tickets.json"


class TicketService:
    """Ticket data access and business logic."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cache: Optional[dict[Any, Any]] = None

    # ── Data access ───────────────────────────────────────────────────

    def _load(self) -> dict[Any, Any]:
        if self._cache is not None:
            return copy.deepcopy(self._cache)
        try:
            data = read_document(_DATA_FILE)
        except FileNotFoundError:
            data = {"guilds": {}, "tickets": {}}
        if not isinstance(data, dict):
            raise TypeError("Stored configuration must be an object")
        self._cache = data
        return copy.deepcopy(self._cache)

    def _save(self, data: dict[Any, Any]) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open_document(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = copy.deepcopy(data)

    # ── Server settings ───────────────────────────────────────────────

    def get_guild_config(self, guild_id: int) -> Optional[dict[Any, Any]]:
        """The server's ticket system settings."""
        result_value = self._load().get("guilds", {}).get(str(guild_id))
        if result_value is None:
            return None
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def update_guild_config(self, guild_id: int, updates: dict) -> None:
        """Merge configuration while preserving runtime records and counters."""
        data = self._load()
        data.setdefault("guilds", {}).setdefault(str(guild_id), {}).update(
            copy.deepcopy(updates)
        )
        self._save(data)

    def set_panel_message(self, guild_id, message_id, expected):
        """Do not attach a panel to settings changed while Discord was awaited."""
        data = self._load()
        config = data.get("guilds", {}).get(str(guild_id), {})
        if not config or any(
            config.get(k) != expected.get(k)
            for k in ("channel_id", "role_id", "enabled")
        ):
            raise ValueError(
                tx("ticket_service.ticket_settings_changed_deploy_the_panel")
            )
        config["panel_message_id"] = message_id
        self._save(data)

    def save_guild_config(
        self,
        guild_id: int,
        channel_id: int,
        role_id: int,
        panel_message_id: int,
        ticket_count: int = 0,
    ) -> None:
        """Save the server's ticket system settings."""
        data = self._load()
        data.setdefault("guilds", {})[str(guild_id)] = {
            "channel_id": channel_id,
            "role_id": role_id,
            "panel_message_id": panel_message_id,
            "ticket_count": ticket_count,
        }
        self._save(data)

    # ── Ticket CRUD ───────────────────────────────────────────────────

    def get_ticket(self, thread_id: int) -> Optional[dict[Any, Any]]:
        """One ticket's data."""
        result_value = self._load().get("tickets", {}).get(str(thread_id))
        if result_value is None:
            return None
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def find_open_ticket(self, guild_id: int, user_id: int) -> Optional[int]:
        """Find whether the user already has an open ticket in the server; return the thread_id."""
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
        """Create a ticket record."""
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
        """Close a ticket; return whether it succeeded."""
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
        """Increase the ticket counter and return the new value."""
        data = self._load()
        cfg = data.setdefault("guilds", {}).setdefault(str(guild_id), {})
        count = cfg.get("ticket_count", 0) + 1
        cfg["ticket_count"] = count
        self._save(data)
        result_value = count
        if not isinstance(result_value, int):
            raise TypeError("Unexpected stored or API value: expected int")
        return result_value

    def can_close(self, thread_id: int, user_id: int, is_staff: bool) -> bool:
        """Whether the user may close the ticket."""
        ticket = self.get_ticket(thread_id)
        if not ticket:
            return False
        return is_staff or ticket.get("creator_id") == user_id
