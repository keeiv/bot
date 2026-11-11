"""osu! business logic."""

import json
import os
import threading
from typing import Any, Optional

from src.utils.document_store import open_document
from src.utils.document_store import read_document
from src.utils.i18n import text as tx

_DATA_FILE = "data/storage/osu_links.json"


class OsuService:
    """osu! account link data access and API setup."""

    def __init__(self) -> None:
        self._links_lock = threading.RLock()
        self._api = None
        self._api_error: Optional[str] = None
        self._links: dict[Any, Any] = self._load_links()
        self._init_api()

    def _init_api(self) -> None:
        """Set up the osu! API client."""
        try:
            # ossapi has no typing metadata.
            from ossapi import Ossapi  # type: ignore[import-untyped]
        except ImportError:
            self._api_error = tx("osu_service.the_ossapi_package_could_not_be")
            return

        client_id = os.getenv("OSU_CLIENT_ID")
        client_secret = os.getenv("OSU_CLIENT_SECRET")
        if not client_id or not client_secret:
            self._api_error = tx("osu_service.osu_client_id_or_osu_client")
            return

        self._api = Ossapi(int(client_id), client_secret)

    # ── Data access ───────────────────────────────────────────────────

    def _load_links(self) -> dict[Any, Any]:
        try:
            links = read_document(_DATA_FILE)
        except FileNotFoundError:
            return {}
        if not isinstance(links, dict):
            raise TypeError("Account links must be an object")
        return links

    def _save_links(self, links=None) -> None:
        with open_document(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                self._links if links is None else links, f, ensure_ascii=False, indent=2
            )

    # ── Linking ───────────────────────────────────────────────────────

    def bind(self, user_id: int, username: str) -> None:
        """Link a Discord user to an osu! account."""
        with self._links_lock:
            links = dict(self._links)
            links[str(user_id)] = username
            self._save_links(links)
            self._links = links

    def unbind(self, user_id: int) -> bool:
        """Unlink; return whether a link existed."""
        with self._links_lock:
            links = dict(self._links)
            if str(user_id) not in links:
                return False
            del links[str(user_id)]
            self._save_links(links)
            self._links = links
            return True

    def get_bound_username(self, user_id: int) -> Optional[str]:
        """The linked osu! username."""
        return self._links.get(str(user_id))

    # ── API ───────────────────────────────────────────────────────────

    @property
    def api(self) -> Any:
        """The osu! API client."""
        return self._api

    @property
    def api_error(self) -> Optional[str]:
        """The API setup error message."""
        return self._api_error

    def ensure_api(self) -> None:
        """Make sure the API is available; otherwise raise RuntimeError."""
        if self._api is None:
            raise RuntimeError(tx("osu_service.osu_is_unavailable_osu_client_id"))

    @staticmethod
    def format_playtime(seconds: Optional[int]) -> str:
        """Format play time."""
        if not seconds:
            return tx("osu_service.0_hours")
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours:
            return tx("osu_service.hours_minutes", v0=(hours), v1=(minutes))
        return tx("osu_service.minutes", v0=(minutes))
