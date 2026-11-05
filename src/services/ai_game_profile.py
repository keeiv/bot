"""What the AI characters may know of a member's HoYoLAB games.

The accounts come from /mhy bind, every server the member linked (Asia,
America, Europe, TW/HK/MO...); nothing is asked of the member. The cookie and
the UID never reach a model: only the nickname, the server, a few numbers and
the characters the member owns with their gear, so a character can suggest teams.
A member only ever gets their own accounts.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Hashable, Optional

logger = logging.getLogger(__name__)

FETCH_SECONDS = 12  # longer than this and the last good read is used instead
REFRESH_MINUTES = 30  # the background loop reads every linked member this often
PAUSE_SECONDS = 2  # between two members in that loop, to go easy on HoYoLAB
MAX_ACCOUNTS = 8  # game accounts read per member
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
    """Which link a profile was read for: a new /mhy bind gives a new one."""
    uids = sorted(str(account.get("uid")) for account in bound.get("game_accounts", []))
    return bound.get("encrypted_cookie"), tuple(uids)


def accounts(service: Any, bound: dict[str, Any]) -> list[tuple[str, int, str]]:
    """``(game, uid, server)`` for each of the member's own accounts, every server."""
    found: list[tuple[str, int, str]] = []
    for account in bound.get("game_accounts", []):
        game = service.map_game_biz_to_str(account.get("game_biz", ""))
        try:
            uid = int(account.get("uid"))
        except (TypeError, ValueError):
            continue
        if game in GAMES and all((game, uid) != (g, u) for g, u, _ in found):
            found.append(
                (game, uid, _clean(account.get("server_name") or "", MAX_TEXT))
            )
    return found[:MAX_ACCOUNTS]


class GameProfiles:
    """Reads a member's linked games for the AI characters, live on every @BOT.

    Only the member's own accounts are read, one entry per member. The last good
    read is kept in memory and used, with its age, when HoYoLAB does not answer
    in time; a new bind is read at once and a background loop keeps it fresh.
    """

    def __init__(
        self,
        source: Callable[[], Any],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.source = source  # the GenshinService, or None while /mhy is not up
        self.clock = clock
        # member -> (read at, which link it was read for, the text)
        self._last: dict[int, tuple[float, Hashable, str]] = {}
        # member -> (link, the read in progress); messages sent meanwhile share it
        self._pending: dict[int, tuple[Hashable, asyncio.Future]] = {}

    async def snapshot(self, user_id: int) -> Optional[str]:
        """Read the member's games now; when HoYoLAB fails, the last good read.

        None when nothing is linked or nothing was ever readable.
        """
        link = await self.refresh(user_id)
        last = self._last.get(user_id)
        if link is None or last is None or last[1] != link:
            return None
        age = self.clock() - last[0]
        if age < 60:
            when = "read just now"
        else:
            when = f"read {int(age // 60)} min ago (HoYoLAB did not answer just now)"
        return f"({when})\n{last[2]}"

    async def refresh(self, user_id: int) -> Optional[Hashable]:
        """Read the member's games and keep the result; returns their link, or None."""
        service = self.source()
        if service is None:
            return None
        bound = service.get_bound_user(user_id)
        if not bound:
            self.forget(user_id)
            return None
        link = fingerprint(bound)
        pending = self._pending.get(user_id)
        if pending is None or pending[0] != link:
            task = asyncio.ensure_future(self._read(service, user_id, bound, link))
            pending = (link, task)
            self._pending[user_id] = pending
            task.add_done_callback(lambda _: self._done(user_id, pending))
        await asyncio.shield(pending[1])
        return link

    async def refresh_all(self) -> int:
        """Read every linked member once, one after another; returns how many."""
        service = self.source()
        if service is None:
            return 0
        done = 0
        for key in service.get_all_bound_users():
            try:
                user_id = int(key)
            except ValueError:
                continue
            try:
                await self.refresh(user_id)
            except Exception:
                logger.exception("Could not refresh the AI profile of %s", user_id)
                continue
            done += 1
            await asyncio.sleep(PAUSE_SECONDS)
        return done

    def forget(self, user_id: int) -> None:
        """Drop what was read for the member (they unlinked)."""
        self._last.pop(user_id, None)

    def _done(self, user_id: int, pending: tuple[Hashable, asyncio.Future]) -> None:
        if self._pending.get(user_id) is pending:
            del self._pending[user_id]

    async def _read(
        self, service: Any, user_id: int, bound: dict[str, Any], link: Hashable
    ) -> None:
        owned = accounts(service, bound)
        if not owned:
            return
        reads = [
            (index, section, read(user_id, game, uid=uid))
            for index, (game, uid, _) in enumerate(owned)
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
            return
        found: list[list[str]] = [[] for _ in owned]
        roster: dict[int, str] = {}
        for (index, section, _), data in zip(reads, results):
            if isinstance(data, BaseException):
                logger.info(
                    "HoYoLAB %s %s unreadable for %s: %s",
                    owned[index][0],
                    section,
                    user_id,
                    data,
                )
            elif section == "roster" and isinstance(data, list):
                roster[index] = describe_roster(data)
            elif isinstance(data, dict):
                found[index].append(describe(section, data))
        lines = []
        for index, (game, _, server) in enumerate(owned):
            if not found[index] and index not in roster:
                continue
            title = f"{GAMES[game]} ({server})" if server else GAMES[game]
            lines.append(
                f"{title} — " + "; ".join(found[index]) if found[index] else f"{title}:"
            )
            if index in roster:
                lines.append(roster[index])
        current = service.get_bound_user(user_id)
        if not current or fingerprint(current) != link:
            return  # unlinked or linked anew while reading: this read is stale
        if lines:
            self._last[user_id] = (self.clock(), link, "\n".join(lines))
