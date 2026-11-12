"""Giveaway business logic."""

import asyncio
import copy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
import random
import re
from typing import Any, Optional

from src.utils.document_store import open_document
from src.utils.document_store import read_document

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/giveaways.json"


# A result that cannot be posted (deleted channel, lost access) is retried this
# many times, one loop apart, then left in the log.
ANNOUNCE_TRIES = 5


class GiveawayService:
    """Giveaway data access and business logic."""

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
            data = {}
        if not isinstance(data, dict):
            raise TypeError("Stored configuration must be an object")
        self._cache = data
        return copy.deepcopy(self._cache)

    def _save(self, data: dict[Any, Any]) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open_document(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = copy.deepcopy(data)

    # ── Queries ───────────────────────────────────────────────────────

    def get(self, giveaway_id: str) -> Optional[dict[Any, Any]]:
        """One giveaway's data."""
        return self._load().get(giveaway_id)

    def list_active(self, guild_id: int) -> list[tuple[str, dict[Any, Any]]]:
        """List every giveaway running in the server."""
        data = self._load()
        return [
            (gid, ga)
            for gid, ga in data.items()
            if ga.get("guild_id") == guild_id and not ga.get("ended")
        ]

    def list_all_active(self) -> list[tuple[str, dict[Any, Any]]]:
        """List every giveaway still running (across servers, for the scheduled check)."""
        data = self._load()
        return [(gid, ga) for gid, ga in data.items() if not ga.get("ended")]

    # ── Creating ──────────────────────────────────────────────────────

    def create(self, giveaway_id: str, giveaway_data: dict[Any, Any]) -> None:
        """Create a giveaway record."""
        data = self._load()
        data[giveaway_id] = giveaway_data
        self._save(data)

    # ── Joining and leaving ───────────────────────────────────────────

    @property
    def lock(self) -> asyncio.Lock:
        """The lock that keeps entries from racing; the view uses it."""
        return self._lock

    def toggle_participant(
        self, giveaway_id: str, user_id: str
    ) -> tuple[Optional[str], int]:
        """Toggle participation; return (action, count), where action is 'joined', 'left' or None."""
        data = self._load()
        ga = data.get(giveaway_id)
        if not ga or ga.get("ended"):
            return None, 0
        # Past the deadline the list is frozen, even while a draw that could
        # not be stored waits for its next try.
        if datetime.now(TZ_OFFSET).timestamp() >= ga.get("end_time", float("inf")):
            return None, 0

        participants: list[Any] = ga.setdefault("participants", [])
        if user_id in participants:
            participants.remove(user_id)
            action = "left"
        else:
            participants.append(user_id)
            action = "joined"

        self._save(data)
        return action, len(participants)

    # ── Settling ──────────────────────────────────────────────────────

    def pick_winners(self, giveaway_id: str) -> list[str]:
        """Pick the winners' IDs at random without changing any state."""
        ga = self.get(giveaway_id)
        if not ga:
            return []
        participants = ga.get("participants", [])
        num_winners = min(ga.get("winners", 1), len(participants))
        if not participants:
            return []
        return random.sample(participants, num_winners)

    def mark_ended(self, giveaway_id: str, winner_ids: list[str]) -> None:
        """Record the winners. The announcement is still owed until mark_announced."""
        data = self._load()
        ga = data.get(giveaway_id)
        if ga:
            ga["ended"] = True
            ga["winner_ids"] = winner_ids
            ga["settled"] = True
            ga.pop("drawing", None)
            ga["announced"] = False
            ga["announce_tries"] = 0
            self._save(data)

    def mark_announced(self, giveaway_id: str, posted: bool) -> None:
        """Record that the result was posted, or count one more failed try."""
        data = self._load()
        ga = data.get(giveaway_id)
        if not ga:
            return
        if posted:
            ga["announced"] = True
        else:
            ga["announce_tries"] = int(ga.get("announce_tries", 0)) + 1
        self._save(data)

    def pending_announcements(self) -> list[tuple[str, dict[Any, Any]]]:
        """Settled giveaways whose result has not been posted yet, within the try limit."""
        data = self._load()
        return [
            (gid, dict(ga))
            for gid, ga in data.items()
            if ga.get("settled")
            and ga.get("announced") is False
            and int(ga.get("announce_tries", 0)) < ANNOUNCE_TRIES
        ]

    def reopen(self, giveaway_id: str) -> None:
        """Put back a giveaway that was marked ended when it came due but has no winners drawn yet."""
        data = self._load()
        ga = data.get(giveaway_id)
        if (
            ga
            and ga.get("ended")
            and not ga.get("settled")
            and not ga.get("winner_ids")
        ):
            ga["ended"] = False
            self._save(data)

    def reroll(self, giveaway_id: str, num_winners: int) -> list[str]:
        """Draw again; return the new winners' IDs."""
        data = self._load()
        ga = data.get(giveaway_id)
        if not ga:
            return []
        participants = ga.get("participants", [])
        if not participants:
            return []
        winner_ids = random.sample(participants, min(num_winners, len(participants)))
        ga["winner_ids"] = winner_ids
        self._save(data)
        return winner_ids

    def check_expired(self) -> list[tuple[str, dict[Any, Any]]]:
        """Find every giveaway that is due, close it, and return it for drawing.

        A giveaway closed here carries `drawing` until its winners are stored, so
        one whose draw was cut short (a restart, a failed write) is returned again
        on the next check instead of staying closed with nobody drawn.
        """
        now = datetime.now(TZ_OFFSET).timestamp()
        expired: list[tuple[str, dict[Any, Any]]] = []
        data = self._load()
        changed = False

        for gid, ga in list(data.items()):
            if ga.get("ended"):
                if ga.get("drawing") and not ga.get("settled"):
                    expired.append((gid, dict(ga)))
                continue
            if now >= ga.get("end_time", float("inf")):
                ga["ended"] = True
                ga["drawing"] = True
                expired.append((gid, dict(ga)))
                changed = True

        if changed:
            self._save(data)
        return expired

    # ── Tools ─────────────────────────────────────────────────────────

    @staticmethod
    def parse_duration(duration: str) -> Optional[int]:
        """Parse a duration string (such as 1h, 30m, 1d, 2d6h); return seconds."""
        pattern = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?", re.IGNORECASE)
        match = pattern.fullmatch(duration.strip())
        if not match:
            return None
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        total = days * 86400 + hours * 3600 + minutes * 60
        return total if total > 0 else None
