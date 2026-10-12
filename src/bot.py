import asyncio
import os
import pkgutil
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src.utils.blacklist_manager import BlacklistManager
from src.utils.command_translator import CommandTranslator
from src.utils.i18n import Lang
from src.utils.i18n import t
from src.utils.lang_context import interaction_lang
from src.utils.lang_context import message_lang
from src.utils.runtime import close_optimizations
from src.utils.runtime import initialize_optimizations

load_dotenv()


def blacklist_embed(lang: Lang, entry: dict[str, Any]) -> discord.Embed:
    """The notice shown to a blacklisted user, in the language of where they are."""
    reason = entry.get("reason") or t(lang, "blacklist.no_reason")
    source_key = (
        "blacklist.source_local"
        if entry.get("source") == "local"
        else "blacklist.source_api"
    )
    return discord.Embed(
        title=t(lang, "blacklist.title"),
        description=t(
            lang, "blacklist.body", reason=reason, source=t(lang, source_key)
        ),
        color=discord.Color.red(),
    )


class BlacklistCheckTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        bot = interaction.client
        if not isinstance(bot, Bot):
            raise TypeError("Blacklist tree requires Bot")
        cmd_name = interaction.command.name if interaction.command else None
        if cmd_name in ["appeal", "appeal_status"]:
            return True
        # 跳過 blacklist 群組指令 (開發者自行檢查權限)
        top_level = interaction.data.get("name") if interaction.data else None
        if top_level == "blacklist":
            return True
        # API 呼叫加超時，避免佔用 interaction 3 秒窗口
        try:
            entry = await asyncio.wait_for(
                bot.blacklist_manager.check(interaction.user.id), timeout=1.5
            )
        except asyncio.TimeoutError:
            return True  # API 太慢就放行，不要卡住指令
        if not entry:
            return True
        mode = entry.get("mode")
        reason = entry.get("reason") or "No reason given"
        # Only ban where the bot is a member, never via a personal-app command.
        guild = bot.get_guild(interaction.guild_id) if interaction.guild_id else None
        if mode == "global_ban" and guild is not None:
            try:
                await guild.ban(
                    interaction.user,
                    reason=f"Global Ban: {reason}",
                )
            except Exception:
                pass
        embed = blacklist_embed(await interaction_lang(interaction), entry)
        # 動態載入申訴按鈕 (避免循環 import)
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
        self.blacklist_manager = BlacklistManager(self.api_key, self.api_base)

    async def setup_hook(self) -> None:
        await initialize_optimizations()
        await self.blacklist_manager.setup()
        await self.load_cogs()
        await self.tree.set_translator(CommandTranslator())
        await self.tree.sync()

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
            reason = entry.get("reason") or "No reason given"
            if mode == "global_ban" and message.guild:
                try:
                    await message.guild.ban(
                        message.author,
                        reason=f"Global Ban: {reason}",
                    )
                except Exception:
                    pass
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
            reason = entry.get("reason") or "No reason given"
            if mode == "global_ban":
                try:
                    await member.guild.ban(
                        member,
                        reason=f"Global Ban: {reason}",
                    )
                except Exception:
                    pass
            elif mode == "block":
                # block 模式只擋指令，不踢人
                pass
