import copy
import json
import os
from typing import Any, Optional

from src.utils.document_store import open_document
from src.utils.document_store import read_document

_DATA_FILE = "data/storage/temp_voice.json"


class TempVoiceService:
    """Temporary voice channel data access and business logic."""

    def __init__(self) -> None:
        self._cache: Optional[dict[Any, Any]] = None

    # ── Data access ───────────────────────────────────────────────────

    def _load(self) -> dict[Any, Any]:
        if self._cache is not None:
            return copy.deepcopy(self._cache)
        try:
            data = read_document(_DATA_FILE)
        except FileNotFoundError:
            data = {"guilds": {}, "channels": {}}
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
        """The server's temporary voice channel settings."""
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

    def save_guild_config(
        self,
        guild_id: int,
        trigger_channel_id: int,
        category_id: Optional[int],
        name_template: str,
    ) -> None:
        """Save the server's temporary voice channel settings."""
        data = self._load()
        data.setdefault("guilds", {})[str(guild_id)] = {
            "trigger_channel_id": trigger_channel_id,
            "category_id": category_id,
            "name_template": name_template,
        }
        self._save(data)

    def remove_guild_config(self, guild_id: int) -> None:
        """Remove the server's settings."""
        data = self._load()
        data.setdefault("guilds", {}).pop(str(guild_id), None)
        self._save(data)

    # ── Temporary channel management ──────────────────────────────────

    def get_channel(self, channel_id: int) -> Optional[dict[Any, Any]]:
        """One temporary channel's data."""
        result_value = self._load().get("channels", {}).get(str(channel_id))
        if result_value is None:
            return None
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def get_guild_channels(self, guild_id: int) -> list[dict[Any, Any]]:
        """Every temporary channel's data in the server."""
        data = self._load()
        return [
            ch
            for ch in data.get("channels", {}).values()
            if ch.get("guild_id") == guild_id
        ]

    def get_all_channel_ids(self) -> list[int]:
        """The IDs of every recorded temporary channel."""
        return [int(cid) for cid in self._load().get("channels", {}).keys()]

    def save_channel(
        self,
        channel_id: int,
        guild_id: int,
        owner_id: int,
    ) -> None:
        """Create a temporary channel record."""
        data = self._load()
        data.setdefault("channels", {})[str(channel_id)] = {
            "guild_id": guild_id,
            "owner_id": owner_id,
            "banned_users": [],
        }
        self._save(data)

    def remove_channel(self, channel_id: int) -> None:
        """Remove a temporary channel record."""
        data = self._load()
        data.setdefault("channels", {}).pop(str(channel_id), None)
        self._save(data)

    def remove_stale_channels(self, valid_channel_ids: set[int]) -> int:
        """Remove records of channels that no longer exist; return how many were removed."""
        data = self._load()
        channels = data.get("channels", {})
        stale = [cid for cid in channels if int(cid) not in valid_channel_ids]
        for cid in stale:
            del channels[cid]
        if stale:
            self._save(data)
        return len(stale)

    # ── Owner management ──────────────────────────────────────────────

    def set_owner(self, channel_id: int, new_owner_id: int) -> None:
        """Update the channel's owner."""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch:
            ch["owner_id"] = new_owner_id
            self._save(data)

    # ── Block list ────────────────────────────────────────────────────

    def add_ban(self, channel_id: int, user_id: int) -> None:
        """Add a blocked user."""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch and user_id not in ch.get("banned_users", []):
            ch.setdefault("banned_users", []).append(user_id)
            self._save(data)

    def remove_ban(self, channel_id: int, user_id: int) -> None:
        """Remove a blocked user."""
        data = self._load()
        ch = data.get("channels", {}).get(str(channel_id))
        if ch and user_id in ch.get("banned_users", []):
            ch["banned_users"].remove(user_id)
            self._save(data)
