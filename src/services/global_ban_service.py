"""Global bans everywhere.

A global_ban entry bans the user in every server BOT. is in, including ones they
have not joined, so they cannot even join.

Only the bans made here are lifted again, once the entry is gone (an accepted appeal,
a revoked entry), and only when the ban still carries BOT.'s reason: a server's own
ban of the same person stays.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Iterable

import discord

from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.storage_worker import run_storage

log = logging.getLogger(__name__)

# Marks a ban as BOT.'s own: a person typing "Global Ban" themselves is not BOT.
REASON = "[BOT.] Global Ban"
BULK_LIMIT = 200  # users per bulk ban request
SINGLE_LIMIT = 25  # one-by-one bans per server per round, without Manage Server
RETRY_SECONDS = 3600  # how long a user Discord would not ban is left alone
BULK_NOBODY_BANNED = 500000  # Discord's code for a batch where nobody could be banned


def sources(value: str) -> set[str]:
    """``"local,mori"`` -> ``{"local", "mori"}``: which lists a ban came from."""
    return {part for part in value.split(",") if part}


class GlobalBanEnforcer:
    # {guild_id: {user_id: "local" | "mori" | "local,mori"}}: the bans made here,
    # and every list they were seen on
    FILE = "data/storage/global_bans.json"

    def __init__(self, manager: Any, bot_user_id: int | None = None) -> None:
        self.manager = manager
        self.bot_user_id = bot_user_id
        # (guild_id, user_id) -> when to try again: Discord refused (someone above
        # BOT.) or they are banned already, by BOT. or by the server
        self._refused: dict[tuple[int, int], float] = {}
        self._lock = asyncio.Lock()

    def _load(self) -> Dict[str, Dict[str, str]]:
        try:
            raw = read_document(self.FILE)
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            raise TypeError("Global ban records must be an object")
        return raw

    def _save(self, data: Dict[str, Dict[str, str]]) -> None:
        write_document(self.FILE, data)

    async def remember(self, guild_id: int, user_id: int, source: str) -> None:
        """Record a ban made elsewhere (a join, a message, a command) as BOT.'s own."""
        if source not in ("local", "mori"):
            return  # CatHome cannot be listed, so its bans could never be lifted here
        async with self._lock:
            made = await run_storage(self._load)
            done = made.setdefault(str(guild_id), {})
            seen = sources(done.get(str(user_id), "")) | {source}
            done[str(user_id)] = ",".join(sorted(seen))
            await run_storage(self._save, made)

    async def forget(self, guild_id: int, user_id: int) -> None:
        """Someone lifted this ban: any later ban of this user is not the recorded one."""
        async with self._lock:
            made = await run_storage(self._load)
            done = made.get(str(guild_id), {})
            if done.pop(str(user_id), None) is None:
                return
            if not done:
                made.pop(str(guild_id), None)
            await run_storage(self._save, made)

    async def reconcile(self, guilds: Iterable[discord.Guild]) -> None:
        """Ban everyone on the lists in each server; lift the bans made here that are no longer listed."""
        async with self._lock:  # a round and a server join share the record file
            await self._reconcile(guilds)

    async def _reconcile(self, guilds: Iterable[discord.Guild]) -> None:
        targets = await self.manager.global_ban_targets()
        if targets is None:
            return
        mori_on = self.manager._configured("mori")
        made = await run_storage(self._load)
        now = time.monotonic()
        self._refused = {
            key: until
            for key, until in self._refused.items()
            if until > now and key[1] in targets
        }
        for guild in guilds:
            me = guild.me
            if me is None or not me.guild_permissions.ban_members:
                continue
            done = dict(made.get(str(guild.id), {}))
            for user, seen in done.items():
                listed = targets.get(int(user))
                if listed:
                    # While Mori.black is off its list is unknown, so a "mori"
                    # already seen is kept rather than read as gone.
                    known = (
                        sources(listed) if mori_on else sources(listed) | sources(seen)
                    )
                    done[user] = ",".join(sorted(known))
            try:
                await self._ban(guild, targets, done)
                await self._lift(guild, targets, done, mori_on)
            finally:
                if done:
                    made[str(guild.id)] = done
                else:
                    made.pop(str(guild.id), None)
                await run_storage(self._save, made)

    async def _ban(
        self, guild: discord.Guild, targets: Dict[int, str], done: Dict[str, str]
    ) -> None:
        new = [
            user
            for user in targets
            if str(user) not in done
            and user not in (guild.owner_id, self.bot_user_id)
            and (guild.id, user) not in self._refused
        ]
        if not new:
            return
        reason = f"{REASON}: Mori.black / BOT. blacklist"
        if guild.me.guild_permissions.manage_guild:
            for start in range(0, len(new), BULK_LIMIT):
                chunk = new[start : start + BULK_LIMIT]
                try:
                    result = await guild.bulk_ban(
                        [discord.Object(u) for u in chunk],
                        reason=reason,
                        delete_message_seconds=0,
                    )
                except discord.HTTPException as error:
                    if error.code != BULK_NOBODY_BANNED:
                        log.warning("Bulk global ban failed in guild %s", guild.id)
                        return  # a passing error: the whole batch again next round
                    # Nobody in this batch could be banned (all banned already,
                    # say): set them aside so the next batch is reached.
                    self._set_aside(guild, chunk)
                    continue
                for user in result.banned:
                    done[str(user.id)] = targets[user.id]
                self._set_aside(guild, [u.id for u in result.failed])
            return
        for user in new[:SINGLE_LIMIT]:  # the rest next round
            try:
                await guild.ban(
                    discord.Object(user), reason=reason, delete_message_seconds=0
                )
            except discord.Forbidden:
                self._set_aside(guild, [user])
                continue
            except discord.HTTPException:
                continue
            done[str(user)] = targets[user]

    def _set_aside(self, guild: discord.Guild, users: list[int]) -> None:
        """Leave these users for a while.

        They are not recorded: a ban not known to be BOT.'s own is never lifted by BOT.
        """
        until = time.monotonic() + RETRY_SECONDS
        for user in users:
            self._refused[(guild.id, user)] = until

    async def _lift(
        self,
        guild: discord.Guild,
        targets: Dict[int, str],
        done: Dict[str, str],
        mori_on: bool,
    ) -> None:
        for user, source in list(done.items()):
            if int(user) in targets:
                continue
            if "mori" in sources(source) and not mori_on:
                continue  # Mori.black switched off here: its list is unknown, not empty
            try:
                ban = await guild.fetch_ban(discord.Object(int(user)))
                if (ban.reason or "").startswith(REASON):
                    await guild.unban(
                        discord.Object(int(user)),
                        reason=f"{REASON} lifted: no longer listed",
                    )
            except discord.NotFound:
                pass  # unbanned by someone already
            except discord.HTTPException:
                continue  # try again next round
            del done[user]
