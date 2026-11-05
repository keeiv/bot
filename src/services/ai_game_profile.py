"""What the AI characters may know of a member's HoYoLAB games.

The accounts come from /genshin's links; nothing is asked of the member. The
cookie and the UID never reach a model: only the nickname, a few numbers and
the characters the member owns with their gear, so a character can suggest teams.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Hashable, Optional

logger = logging.getLogger(__name__)

CACHE_SECONDS = 600  # a profile is remembered this long before HoYoLAB is read again
FETCH_SECONDS = 12  # longer than this and the character answers without it
MAX_TEXT = 40  # characters kept of a text field (a nickname, say)
MAX_GEAR = 60  # characters kept of a weapon or set line
MAX_ROSTER = 60  # characters listed per game, the highest levels first

GAMES = {
    "genshin": "Genshin Impact",
    "starrail": "Honkai: Star Rail",
    "zzz": "Zenless Zone Zero",
    "honkai": "Honkai Impact 3rd",
}
_HIDDEN = {"uid", "type"}
ROSTER_GAMES = {"genshin", "starrail", "zzz"}  # Honkai 3rd has no gear list here


def _value(key: str, value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        if key.endswith("recovery"):
            return "full" if value <= 0 else f"full in {value // 60} min"
        return str(value)
    if isinstance(value, str):
        text = " ".join(value.split())[:MAX_TEXT]
        return text or None
    if isinstance(value, list):
        return f"{len(value)} sent"
    return None


def describe(section: str, data: dict[str, Any]) -> str:
    """``{"level": 60, ...}`` -> ``stats: level 60, ...``; unknown kinds are left out."""
    fields = []
    for key, value in data.items():
        if key in _HIDDEN:
            continue
        shown = _value(key, value)
        if shown is not None:
            fields.append(f"{key.replace('_', ' ')} {shown}")
    return f"{section}: " + ", ".join(fields)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value).split())[:limit]


def describe_roster(roster: list[dict[str, Any]]) -> str:
    """One line per owned character: name, kind, rarity, level, rank, gear, sets."""
    lines = [f"characters owned ({len(roster)}):"]
    for char in roster[:MAX_ROSTER]:
        head = " ".join(
            _clean(char.get(key, ""), MAX_TEXT)
            for key in ("name", "kind", "rarity")
            if char.get(key)
        )
        parts = [
            f"{head} Lv{int(char.get('level') or 0)} {_clean(char.get('rank', ''), 4)}"
        ]
        if char.get("gear"):
            parts.append(_clean(char["gear"], MAX_GEAR))
        sets = ", ".join(_clean(name, MAX_GEAR) for name in char.get("sets") or [])
        if sets:
            parts.append(sets)
        lines.append("- " + " · ".join(parts))
    if len(roster) > MAX_ROSTER:
        lines.append(f"- and {len(roster) - MAX_ROSTER} more at lower levels")
    return "\n".join(lines)


def fingerprint(bound: dict[str, Any]) -> Hashable:
    """Which link a profile was read for: a new /genshin bind gives a new one."""
    uids = sorted(str(account.get("uid")) for account in bound.get("game_accounts", []))
    return bound.get("encrypted_cookie"), tuple(uids)


class GameProfiles:
    """Reads and briefly remembers a member's linked games for the AI characters."""

    def __init__(
        self,
        source: Callable[[], Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source  # the GenshinService, or None while /genshin is not up
        self.clock = clock
        # member -> (read at, which link it was read for, the text)
        self._cache: dict[int, tuple[float, Hashable, str]] = {}
        # member -> (link, the read in progress); messages sent meanwhile share it
        self._pending: dict[int, tuple[Hashable, asyncio.Future]] = {}

    async def snapshot(self, user_id: int) -> Optional[str]:
        """The member's games as short lines, or None when nothing is linked or readable."""
        service = self.source()
        if service is None:
            return None
        bound = service.get_bound_user(user_id)
        if not bound:
            self._cache.pop(user_id, None)  # unlinked since: forget it
            return None
        link = fingerprint(bound)
        cached = self._cache.get(user_id)
        if cached and cached[1] == link and self.clock() - cached[0] < CACHE_SECONDS:
            return cached[2]
        pending = self._pending.get(user_id)
        if pending is None or pending[0] != link:
            task = asyncio.ensure_future(self._read(service, user_id, bound, link))
            pending = (link, task)
            self._pending[user_id] = pending
            task.add_done_callback(lambda _: self._done(user_id, pending))
        return await asyncio.shield(pending[1])

    def _done(self, user_id: int, pending: tuple[Hashable, asyncio.Future]) -> None:
        if self._pending.get(user_id) is pending:
            del self._pending[user_id]

    async def _read(
        self, service: Any, user_id: int, bound: dict[str, Any], link: Hashable
    ) -> Optional[str]:
        games = []
        for account in bound.get("game_accounts", []):
            game = service.map_game_biz_to_str(account.get("game_biz", ""))
            if game in GAMES and game not in games:
                games.append(game)
        if not games:
            return None
        reads = [
            (game, section, read(user_id, game))
            for game in games
            for section, read in (
                ("overview", service.get_stats),
                ("now", service.get_notes),
                ("roster", service.get_roster),
            )
            if section != "roster" or game in ROSTER_GAMES
        ]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*(call for _, _, call in reads), return_exceptions=True),
                FETCH_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("HoYoLAB took too long for the AI profile of %s", user_id)
            return None
        found: dict[str, list[str]] = {game: [] for game in games}
        roster: dict[str, str] = {}
        for (game, section, _), data in zip(reads, results):
            if isinstance(data, BaseException):
                logger.info(
                    "HoYoLAB %s %s unreadable for %s: %s", game, section, user_id, data
                )
            elif section == "roster" and isinstance(data, list):
                roster[game] = describe_roster(data)
            elif isinstance(data, dict):
                found[game].append(describe(section, data))
        lines = []
        for game in games:
            if found[game]:
                lines.append(f"{GAMES[game]} — " + "; ".join(found[game]))
            if game in roster:
                if not found[game]:
                    lines.append(f"{GAMES[game]}:")
                lines.append(roster[game])
        if not lines:
            return None
        text = "\n".join(lines)
        self._cache[user_id] = (self.clock(), link, text)
        return text
