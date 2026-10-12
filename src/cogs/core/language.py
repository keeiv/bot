"""Language: the guide channel posted on joining a server, and /language.

* A server the bot joins gets English and a ``#bot-guide`` channel with an embed
  explaining the bot and a menu to switch the language. Only members with
  Manage Server can use the menu; the embed re-renders in the chosen language.
* Servers the bot was already in keep Chinese (recorded once on first start)
  and do not get a guide channel posted out of the blue.
* A guide that could not be posted (no permission, Discord error, bot offline
  when it joined) stays pending and is retried on every ready and on rejoin.
* ``/language`` changes the server's language inside a server the bot is in
  (Manage Server required) and the user's own language everywhere else: DMs and
  servers where BOT. is only used as a personal app.

Storage goes through a shared, serialized queue, so every interaction is
deferred before touching it; Discord only waits 3 seconds for the first reply.
"""

import asyncio
import logging
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.services.language_service import language_service
from src.utils.i18n import Lang
from src.utils.i18n import LANG_NAMES
from src.utils.i18n import LANGS
from src.utils.i18n import t
from src.utils.lang_context import bot_guild_id
from src.utils.lang_context import interaction_lang
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

GUIDE_SELECT_ID = "bot_guide:language"
GUIDE_COLOR = discord.Color.from_rgb(250, 138, 64)


def guide_embed(lang: Lang) -> discord.Embed:
    embed = discord.Embed(
        title=t(lang, "guide.title"),
        description=t(lang, "guide.intro"),
        color=GUIDE_COLOR,
    )
    for part in ("start", "setup", "language", "help"):
        embed.add_field(
            name=t(lang, f"guide.{part}.name"),
            value=t(lang, f"guide.{part}.value"),
            inline=False,
        )
    embed.set_footer(text=t(lang, "guide.footer"))
    return embed


def can_manage(interaction: discord.Interaction) -> bool:
    user = interaction.user
    return isinstance(user, discord.Member) and (
        user.guild_permissions.manage_guild or user.guild_permissions.administrator
    )


class GuideLanguageSelect(discord.ui.Select[Any]):
    def __init__(self, cog: "Language", lang: Lang) -> None:
        self.cog = cog
        super().__init__(
            custom_id=GUIDE_SELECT_ID,
            placeholder=t(lang, "guide.select.placeholder"),
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=LANG_NAMES[code],
                    value=code,
                    description=t(lang, f"guide.select.{code}"),
                    default=code == lang,
                )
                for code in LANGS
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Acknowledge first; the message is edited once the choice is saved.
        await interaction.response.defer()
        if interaction.guild is None or not can_manage(interaction):
            lang = await interaction_lang(interaction)
            await interaction.followup.send(t(lang, "language.denied"), ephemeral=True)
            return
        chosen: Lang = self.values[0]  # type: ignore[assignment]
        try:
            await run_storage(
                language_service().set_guild_lang, interaction.guild.id, chosen
            )
        except Exception:
            logger.exception("Saving the server language failed")
            lang = await interaction_lang(interaction)
            await interaction.followup.send(t(lang, "language.failed"), ephemeral=True)
            return
        await interaction.edit_original_response(
            embed=guide_embed(chosen), view=GuideView(self.cog, chosen)
        )
        await interaction.followup.send(
            t(chosen, "language.server_set", language=LANG_NAMES[chosen]),
            ephemeral=True,
        )


class GuideView(discord.ui.View):
    """Persistent: the menu keeps working after a restart (fixed custom_id)."""

    def __init__(self, cog: "Language", lang: Lang = "en") -> None:
        super().__init__(timeout=None)
        self.add_item(GuideLanguageSelect(cog, lang))


class Language(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # on_ready can fire again after a reconnect; never run two passes at once.
        self._reconcile_lock = asyncio.Lock()
        # on_ready and on_guild_join can welcome the same server concurrently.
        self._welcome_locks: dict[int, asyncio.Lock] = {}

    async def cog_load(self) -> None:
        self.bot.add_view(GuideView(self))

    # ── joining servers ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        async with self._reconcile_lock:
            await self.reconcile()

    async def reconcile(self) -> None:
        """Welcome servers that have no entry yet or whose guide is pending.

        Runs on every ready: servers joined while the bot was offline or
        disconnected never fire on_guild_join. The first run only records the
        existing servers as Chinese and posts nothing.
        """
        service = language_service()
        # The baseline includes servers in an outage, so they are never "new".
        recorded = await run_storage(
            service.baseline, [guild.id for guild in self.bot.guilds]
        )
        if recorded:
            logger.info("Recorded %d existing servers as Chinese", len(recorded))
        available = [guild for guild in self.bot.guilds if not guild.unavailable]
        todo = set(await run_storage(service.needs_welcome, [g.id for g in available]))
        for guild in available:
            if guild.id not in todo:
                continue
            try:
                await self.welcome(guild)
            except Exception:
                logger.exception("Welcoming guild %s failed", guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        try:
            await self.welcome(guild)
        except Exception:
            logger.exception("Welcoming guild %s failed", guild.id)

    async def welcome(self, guild: discord.Guild) -> None:
        """Post the guide if this server is new or its guide is still pending."""
        lock = self._welcome_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            await self._welcome(guild)

    async def _welcome(self, guild: discord.Guild) -> None:
        service = language_service()
        if not await run_storage(service.baseline_done):
            return  # Unknown servers are pre-existing ones until the baseline.
        await run_storage(service.mark_new_guild, guild.id)
        if not await run_storage(service.guide_pending, guild.id):
            return
        # Typed as always set, but None until the server is fully loaded.
        me: Optional[discord.Member] = guild.me
        if me is None:
            return  # Retried on the next ready.
        lang = await run_storage(service.guild_lang, guild.id)
        channel = await self._guide_channel(guild, lang)
        if channel is None:
            logger.warning("No channel to post the guide in for guild %s", guild.id)
            return
        try:
            message = await channel.send(
                embed=guide_embed(lang), view=GuideView(self, lang)
            )
        except discord.HTTPException:
            logger.exception("Posting the guide failed in guild %s", guild.id)
            return
        await run_storage(service.record_guide, guild.id, channel.id, message.id)
        # /language may have run while this was posting; refresh_guide could not
        # find the message yet. Later changes are handled by refresh_guide.
        current = await run_storage(service.guild_lang, guild.id)
        if current != lang:
            try:
                await message.edit(
                    embed=guide_embed(current), view=GuideView(self, current)
                )
            except discord.HTTPException:
                logger.warning("Updating the guide language failed in %s", guild.id)

    async def _guide_channel(
        self, guild: discord.Guild, lang: Lang
    ) -> Optional[discord.TextChannel]:
        me = guild.me
        # Reuse a guide channel created by an earlier, failed attempt.
        channel_id, _ = await run_storage(language_service().guide, guild.id)
        existing = guild.get_channel(channel_id) if channel_id else None
        if isinstance(existing, discord.TextChannel):
            return existing
        if me.guild_permissions.manage_channels:
            overwrites: dict[
                discord.Role | discord.Member | discord.Object,
                discord.PermissionOverwrite,
            ] = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False,
                    add_reactions=False,
                    create_public_threads=False,
                    create_private_threads=False,
                ),
                me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    read_message_history=True,
                ),
            }
            try:
                created = await guild.create_text_channel(
                    t(lang, "guide.channel_name"),
                    overwrites=overwrites,
                    topic=t(lang, "guide.channel_topic"),
                    reason="BOT. guide channel",
                )
            except discord.HTTPException:
                logger.warning("Could not create the guide channel in %s", guild.id)
            else:
                await run_storage(
                    language_service().record_guide_channel, guild.id, created.id
                )
                return created
        # No permission to create one: use a channel the bot can already post in.
        candidates = [guild.system_channel, *guild.text_channels]
        for channel in candidates:
            if channel is None:
                continue
            perms = channel.permissions_for(me)
            if perms.send_messages and perms.embed_links:
                return channel
        return None

    async def refresh_guide(self, guild: discord.Guild, lang: Lang) -> None:
        """Re-render a server's guide after /language changed it (best effort)."""
        channel_id, message_id = await run_storage(language_service().guide, guild.id)
        if not channel_id or not message_id:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=guide_embed(lang), view=GuideView(self, lang))
        except discord.HTTPException:
            pass

    # ── /language ─────────────────────────────────────────────────
    @app_commands.command(
        name="language", description="Change the language BOT. replies in"
    )
    @app_commands.describe(language="The language to use")
    @app_commands.choices(
        language=[app_commands.Choice(name=LANG_NAMES[c], value=c) for c in LANGS]
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def language(
        self,
        interaction: discord.Interaction,
        language: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        service = language_service()
        guild_id = bot_guild_id(interaction.client, interaction.guild_id)
        current = await interaction_lang(interaction)
        reply = interaction.followup.send

        if language is None:
            key = "language.current_server" if guild_id else "language.current_personal"
            await reply(t(current, key, language=LANG_NAMES[current]), ephemeral=True)
            return

        chosen: Lang = language.value  # type: ignore[assignment]
        if guild_id is not None:
            if not can_manage(interaction):
                await reply(t(current, "language.denied"), ephemeral=True)
                return
            try:
                await run_storage(service.set_guild_lang, guild_id, chosen)
            except Exception:
                logger.exception("Saving the server language failed")
                await reply(t(current, "language.failed"), ephemeral=True)
                return
            await reply(
                t(chosen, "language.server_set", language=LANG_NAMES[chosen]),
                ephemeral=True,
            )
            guild = interaction.client.get_guild(guild_id)
            if guild is not None:
                await self.refresh_guide(guild, chosen)
            return

        try:
            await run_storage(service.set_user_lang, interaction.user.id, chosen)
        except Exception:
            logger.exception("Saving the personal language failed")
            await reply(t(current, "language.failed"), ephemeral=True)
            return
        await reply(
            t(chosen, "language.personal_set", language=LANG_NAMES[chosen]),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Language(bot))
