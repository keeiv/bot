import asyncio
import os
import pkgutil

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src.utils.blacklist_manager import BlacklistManager

load_dotenv()

class BlacklistCheckTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        bot: Bot = interaction.client
        cmd_name = interaction.command.name if interaction.command else None
        if cmd_name in ["申訴", "申訴狀態"]:
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
        reason = entry.get("reason", "未提供原因")
        if mode == "global_ban" and interaction.guild:
            try:
                await interaction.guild.ban(
                    interaction.user,
                    reason=f"Global Ban: {reason}",
                )
            except Exception:
                pass
        source = entry.get("source", "api")
        source_label = "本地黑名單" if source == "local" else "CatHome API"
        embed = discord.Embed(
            title="[拒絕] 禁止使用",
            description=(
                f"您已被加入黑名單。\n\n"
                f"原因: {reason}\n"
                f"來源: {source_label}"
            ),
            color=discord.Color.red(),
        )
        # 動態載入申訴按鈕 (避免循環 import)
        from src.cogs.core.blacklist import BlockedNoticeView
        blacklist_cog = bot.get_cog("Blacklist")
        view = BlockedNoticeView(blacklist_cog) if blacklist_cog else None
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return False

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
            tree_cls=BlacklistCheckTree,
        )
        self.api_key = os.getenv("BLACKLIST_API_KEY")
        self.api_base = "https://api.cathome.shop/blacklist"
        self.blacklist_manager = BlacklistManager(self.api_key, self.api_base)
    async def setup_hook(self):
        await self.blacklist_manager.setup()
        await self.load_cogs()
        await self.tree.sync()
    async def close(self):
        await self.blacklist_manager.close()
        await super().close()
    async def load_cogs(self):
        base_package = "src.cogs"
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
        loaded = 0
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
        print(f"[Cog] 共載入 {loaded} 個模組")
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            await self.process_commands(message)
            return
        entry = await self.blacklist_manager.check(message.author.id)
        if entry:
            mode = entry.get("mode")
            reason = entry.get("reason", "未提供原因")
            if mode == "global_ban" and message.guild:
                try:
                    await message.guild.ban(
                        message.author,
                        reason=f"Global Ban: {reason}",
                    )
                except Exception:
                    pass
            source = entry.get("source", "api")
            source_label = "本地黑名單" if source == "local" else "CatHome API"
            embed = discord.Embed(
                title="[拒絕] 禁止使用",
                description=(
                    f"您已被加入黑名單。\n\n"
                    f"原因: {reason}\n"
                    f"來源: {source_label}"
                ),
                color=discord.Color.red(),
            )
            from src.cogs.core.blacklist import BlockedNoticeView
            blacklist_cog = self.get_cog("Blacklist")
            view = BlockedNoticeView(blacklist_cog) if blacklist_cog else None
            await message.reply(embed=embed, view=view, delete_after=30)
            return
        await self.process_commands(message)
    async def on_member_join(self, member: discord.Member):
        entry = await self.blacklist_manager.check(member.id)
        if entry:
            mode = entry.get("mode")
            reason = entry.get("reason", "未提供原因")
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
