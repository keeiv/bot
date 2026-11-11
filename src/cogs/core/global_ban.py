"""Global bans: whoever is on the global_ban list is banned ahead of time in every server BOT. is in."""

import logging

import discord
from discord.ext import commands
from discord.ext import tasks

from src.services.global_ban_service import GlobalBanEnforcer

log = logging.getLogger(__name__)


class GlobalBan(commands.Cog):
    """Keeps every server's bans in line with the local and Mori.black global_ban entries."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.enforcer = GlobalBanEnforcer(getattr(bot, "blacklist_manager", None))

    async def cog_load(self) -> None:
        if self.enforcer.manager is not None:
            self._round.start()

    async def cog_unload(self) -> None:
        self._round.cancel()

    @tasks.loop(minutes=5)
    async def _round(self) -> None:
        await self._reconcile(self.bot.guilds)

    @_round.before_loop
    async def _before_round(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if self.enforcer.manager is not None:
            await self._reconcile([guild])

    @commands.Cog.listener()
    async def on_member_unban(
        self, guild: discord.Guild, user: discord.abc.Snowflake
    ) -> None:
        """A lifted ban leaves the record.

        BOT. bans a listed user again next round, and never treats a later ban by
        the server as its own.
        """
        if self.enforcer.manager is not None:
            await self.enforcer.forget(guild.id, user.id)

    async def remember(self, guild_id: int, user_id: int, source: str) -> None:
        """Note a ban made on a join, a message or a command as BOT.'s own."""
        await self.enforcer.remember(guild_id, user_id, source)

    async def _reconcile(self, guilds: list[discord.Guild]) -> None:
        self.enforcer.bot_user_id = self.bot.user.id if self.bot.user else None
        try:
            await self.enforcer.reconcile(guilds)
        except Exception:
            log.exception("Global ban round failed")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GlobalBan(bot))
