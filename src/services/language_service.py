"""Stored language choices for servers and for users of the personal app.

Layout of the document::

    {
      "baseline_done": true,
      "guilds": {"<guild id>": {"lang": "en", "guide_pending": true,
                                "guide_channel_id": 1, "guide_message_id": 2}},
      "users": {"<user id>": "en"}
    }

Servers the bot was already in when this feature shipped keep Chinese: the first
start records them once (``baseline``). Any server without an entry after that
is new and uses English. A new server keeps ``guide_pending`` until its guide
message is posted, so a failed attempt is retried on the next start or rejoin.
"""

import copy
import json
import os
import threading
import time
from typing import Any, Optional

from src.utils.document_store import open_document
from src.utils.document_store import read_document
from src.utils.i18n import DEFAULT_LANG
from src.utils.i18n import is_lang
from src.utils.i18n import Lang
from src.utils.i18n import LANGS

_DATA_FILE = "data/storage/languages.json"
_CACHE_TTL = 60.0
_LEGACY_LANG: Lang = "zh"


class LanguageService:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._cache_time = 0.0
        # Reads take the lock too, so a slow read cannot put an older document
        # back into the cache after a write. Re-entrant: writers call _load().
        self._lock = threading.RLock()

    # ── storage ───────────────────────────────────────────────────
    def _load(self) -> dict[str, Any]:
        with self._lock:
            return self._load_locked()

    def _load_locked(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cache and now - self._cache_time < _CACHE_TTL:
            return copy.deepcopy(self._cache)
        try:
            data = read_document(_DATA_FILE)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            raise TypeError("Stored language settings must be an object")
        data.setdefault("baseline_done", False)
        data.setdefault("guilds", {})
        data.setdefault("users", {})
        self._cache = data
        self._cache_time = now
        return copy.deepcopy(data)

    def _save(self, data: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open_document(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = copy.deepcopy(data)
        self._cache_time = time.monotonic()

    # ── reads ─────────────────────────────────────────────────────
    def cached_language(
        self, guild_id: Optional[int], user_id: int
    ) -> tuple[bool, Optional[Lang]]:
        """Read a fresh choice without I/O or waiting for a storage writer."""
        if not self._lock.acquire(blocking=False):
            return False, None
        try:
            if not self._cache or time.monotonic() - self._cache_time >= _CACHE_TTL:
                return False, None
            if guild_id is not None:
                entry = self._cache["guilds"].get(str(guild_id))
                value = entry.get("lang") if isinstance(entry, dict) else None
                if is_lang(value):
                    return True, value
                return True, (
                    DEFAULT_LANG if self._cache["baseline_done"] else _LEGACY_LANG
                )
            value = self._cache["users"].get(str(user_id))
            return True, value if is_lang(value) else None
        finally:
            self._lock.release()

    def guild_lang(self, guild_id: int) -> Lang:
        data = self._load()
        entry = data["guilds"].get(str(guild_id))
        lang = entry.get("lang") if isinstance(entry, dict) else None
        for code in LANGS:
            if lang == code:
                return code
        # Before the baseline runs every server is a pre-existing one.
        return DEFAULT_LANG if data["baseline_done"] else _LEGACY_LANG

    def user_lang(self, user_id: int) -> Optional[Lang]:
        value = self._load()["users"].get(str(user_id))
        return value if is_lang(value) else None

    def has_guild(self, guild_id: int) -> bool:
        return str(guild_id) in self._load()["guilds"]

    def guide(self, guild_id: int) -> tuple[Optional[int], Optional[int]]:
        entry = self._load()["guilds"].get(str(guild_id)) or {}
        return entry.get("guide_channel_id"), entry.get("guide_message_id")

    def guide_pending(self, guild_id: int) -> bool:
        entry = self._load()["guilds"].get(str(guild_id)) or {}
        return bool(entry.get("guide_pending"))

    def needs_welcome(self, guild_ids: list[int]) -> list[int]:
        """Of these servers, the ones that are new or whose guide is pending."""
        data = self._load()
        if not data["baseline_done"]:
            return []
        guilds = data["guilds"]
        return [
            guild_id
            for guild_id in guild_ids
            if str(guild_id) not in guilds
            or bool((guilds[str(guild_id)] or {}).get("guide_pending"))
        ]

    def baseline_done(self) -> bool:
        return bool(self._load()["baseline_done"])

    # ── writes ────────────────────────────────────────────────────
    def set_guild_lang(self, guild_id: int, lang: Lang) -> None:
        if not is_lang(lang):
            raise ValueError(f"Unsupported language: {lang!r}")
        with self._lock:
            data = self._load()
            entry: Optional[dict[str, Any]] = data["guilds"].get(str(guild_id))
            if entry is None:
                entry = {}
                data["guilds"][str(guild_id)] = entry
                # Set before the welcome ran: the server still needs its guide.
                if data["baseline_done"]:
                    entry["guide_pending"] = True
            entry["lang"] = lang
            self._save(data)

    def set_user_lang(self, user_id: int, lang: Lang) -> None:
        if not is_lang(lang):
            raise ValueError(f"Unsupported language: {lang!r}")
        with self._lock:
            data = self._load()
            data["users"][str(user_id)] = lang
            self._save(data)

    def record_guide_channel(self, guild_id: int, channel_id: int) -> None:
        """Remember a created guide channel so a retry reuses it."""
        with self._lock:
            data = self._load()
            entry = data["guilds"].setdefault(str(guild_id), {})
            entry.setdefault("lang", DEFAULT_LANG)
            entry["guide_channel_id"] = channel_id
            self._save(data)

    def record_guide(self, guild_id: int, channel_id: int, message_id: int) -> None:
        with self._lock:
            data = self._load()
            entry = data["guilds"].setdefault(str(guild_id), {})
            entry.setdefault("lang", DEFAULT_LANG)
            entry["guide_channel_id"] = channel_id
            entry["guide_message_id"] = message_id
            entry.pop("guide_pending", None)
            self._save(data)

    def baseline(self, guild_ids: list[int]) -> list[int]:
        """Record every current server as Chinese, once. Returns the ids recorded."""
        with self._lock:
            data = self._load()
            if data["baseline_done"]:
                return []
            recorded = []
            for guild_id in guild_ids:
                entry = data["guilds"].setdefault(str(guild_id), {})
                if not is_lang(entry.get("lang")):
                    entry["lang"] = _LEGACY_LANG
                    recorded.append(guild_id)
            data["baseline_done"] = True
            self._save(data)
            return recorded

    def mark_new_guild(self, guild_id: int) -> bool:
        """Give a newly joined server English and a pending guide.

        Returns False if the server already had an entry (a server from before
        the baseline, or one that was already welcomed); its state is unchanged.
        """
        with self._lock:
            data = self._load()
            if str(guild_id) in data["guilds"]:
                return False
            data["guilds"][str(guild_id)] = {
                "lang": DEFAULT_LANG,
                "guide_pending": True,
            }
            self._save(data)
            return True


_service: Optional[LanguageService] = None


def language_service() -> LanguageService:
    global _service
    if _service is None:
        _service = LanguageService()
    return _service
