import asyncio
import logging
import os
import pkgutil
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src.services.global_ban_service import REASON as GLOBAL_BAN_REASON
from src.utils.blacklist_manager import BlacklistManager
from src.utils.command_sync import sync_global
from src.utils.command_translator import CommandTranslator
from src.utils.i18n import Lang
from src.utils.i18n import t
from src.utils.lang_context import interaction_lang
from src.utils.lang_context import message_lang
from src.utils.runtime import close_optimizations
from src.utils.runtime import initialize_optimizations

load_dotenv()

logger = logging.getLogger(__name__)


def blacklist_embed(lang: Lang, entry: dict[str, Any]) -> discord.Embed:
    """The notice shown to a blacklisted user, in the language of where they are."""
    reason = entry.get("reason") or t(lang, "blacklist.no_reason")
    source_key = {
        "local": "blacklist.source_local",
        "mori": "blacklist.source_mori",
    }.get(entry.get("source"), "blacklist.source_api")
    return discord.Embed(
        title=t(lang, "blacklist.title"),
        description=t(
            lang, "blacklist.body", reason=reason, source=t(lang, source_key)
        ),
        color=discord.Color.red(),
    )


async def global_ban(
    bot: commands.Bot,
    guild: discord.Guild,
    user: discord.abc.Snowflake,
    entry: dict[str, Any],
) -> None:
    """Ban a global_ban user here, and note it so it can be lifted with the entry."""
    reason = entry.get("reason") or "No reason given"
    try:
        await guild.ban(user, reason=f"{GLOBAL_BAN_REASON}: {reason}")
    except Exception:
        return
    cog = bot.get_cog("GlobalBan")
    if cog is not None:
        try:
            await cog.remember(guild.id, user.id, entry.get("source") or "")
        except Exception:
            logger.exception("Could not record a global ban in %s", guild.id)


class BlacklistCheckTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        bot = interaction.client
        if not isinstance(bot, Bot):
            raise TypeError("Blacklist tree requires Bot")
        cmd_name = interaction.command.name if interaction.command else None
        if cmd_name in ["appeal", "appeal_status"]:
            return True
        # Skip the blacklist command group (developers check their own permission)
        top_level = interaction.data.get("name") if interaction.data else None
        if top_level == "blacklist":
            return True
        # Give the API call a timeout so it cannot use up the interaction's 3 seconds
        try:
            entry = await asyncio.wait_for(
                bot.blacklist_manager.check(interaction.user.id), timeout=1.5
            )
        except asyncio.TimeoutError:
            return True  # Let the command through when the API is slow, instead of holding it up
        if not entry:
            return True
        mode = entry.get("mode")
        # Only ban where the bot is a member, never via a personal-app command.
        guild = bot.get_guild(interaction.guild_id) if interaction.guild_id else None
        if mode == "global_ban" and guild is not None:
            await global_ban(bot, guild, interaction.user, entry)
        embed = blacklist_embed(await interaction_lang(interaction), entry)
        # Load the appeal button lazily (avoids a circular import)
        from src.cogs.core.blacklist import Blacklist
        from src.cogs.core.blacklist import BlockedNoticeView

        blacklist_cog = bot.get_cog("Blacklist")
        view = (
            BlockedNoticeView(blacklist_cog)
            if isinstance(blacklist_cog, Blacklist)
            else discord.ui.View(timeout=30)
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return False


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
            tree_cls=BlacklistCheckTree,
            # Commands are server-only unless one opts in to the personal app
            # (user install) with @app_commands.allowed_installs.
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=False, private_channel=False
            ),
        )
        self.api_key = os.getenv("BLACKLIST_API_KEY")
        self.api_base = "https://api.cathome.shop/v1/blacklist"
        self.blacklist_manager = BlacklistManager(
            self.api_key,
            self.api_base,
            mori_token=os.getenv("MORI_BLACK_TOKEN"),
            mori_url=os.getenv("MORI_BLACK_URL"),
        )

    async def setup_hook(self) -> None:
        await initialize_optimizations()
        await self.blacklist_manager.setup()
        await self.load_cogs()
        await self.tree.set_translator(CommandTranslator())
        await sync_global(self.tree)

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            try:
                await self.blacklist_manager.close()
            finally:
                await close_optimizations()

    async def load_cogs(self) -> None:
        base_package = "src.cogs"
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
        loaded = 0
        failures = []
        for module_info in pkgutil.walk_packages(
            path=[cogs_path],
            prefix=f"{base_package}.",
        ):
            if module_info.ispkg:
                continue
            try:
                await self.load_extension(module_info.name)
                print(f"[Cog] 已載入: {module_info.name}")
                loaded += 1
            except Exception as e:
                print(f"[Cog] 載入失敗: {module_info.name} - {e}")
                failures.append(module_info.name)
        print(f"[Cog] 共載入 {loaded} 個模組")
        if failures:
            raise RuntimeError(f"Cog 載入失敗: {', '.join(failures)}")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            await self.process_commands(message)
            return
        entry = await self.blacklist_manager.check(message.author.id)
        if entry:
            mode = entry.get("mode")
            if mode == "global_ban" and message.guild:
                await global_ban(self, message.guild, message.author, entry)
            embed = blacklist_embed(
                await message_lang(message.guild, message.author.id), entry
            )
            from src.cogs.core.blacklist import Blacklist
            from src.cogs.core.blacklist import BlockedNoticeView

            blacklist_cog = self.get_cog("Blacklist")
            view = (
                BlockedNoticeView(blacklist_cog)
                if isinstance(blacklist_cog, Blacklist)
                else discord.ui.View(timeout=30)
            )
            await message.reply(embed=embed, view=view, delete_after=30)
            return
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member) -> None:
        entry = await self.blacklist_manager.check(member.id)
        if entry:
            mode = entry.get("mode")
            if mode == "global_ban":
                await global_ban(self, member.guild, member, entry)
            elif mode == "block":
                # Block mode only stops commands; it does not kick
                pass
