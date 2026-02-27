import os
import pkgutil

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from src.utils.blacklist_manager import blacklist_manager

load_dotenv()


class BlacklistCheckTree(app_commands.CommandTree):
    """自定義 CommandTree，添加全局黑名單檢查"""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """全局黑名單檢查"""
        # 允許 "申訴" 和 "申訴狀態" 命令，即使用戶被黑名單
        if interaction.command and interaction.command.name in ["申訴", "申訴狀態"]:
            return True

        # 檢查用戶是否被黑名單
        if blacklist_manager.is_blacklisted(interaction.user.id):
            embed = discord.Embed(
                title="[拒絕] 禁止使用",
                description="您因被添加到黑名單而無法使用此命令。\n\n如果您認為這是誤會，可以使用 `/申訴` 命令提交申訴。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        return True


class Bot(commands.Bot):
    """Main bot class with enhanced functionality."""

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

    async def setup_hook(self):
        """Load all cogs and setup bot."""
        await self.load_cogs()
        await self.tree.sync()

    async def load_cogs(self):
        """Automatically discover and load all cogs under src.cogs."""
        base_package = "src.cogs"
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")

        if not os.path.isdir(cogs_path):
            print(f"Cog directory not found: {cogs_path}")
            return

        for module_info in pkgutil.walk_packages(
            path=[cogs_path],
            prefix=f"{base_package}.",
        ):
            module_name = module_info.name

            if module_info.ispkg:
                continue

            try:
                await self.load_extension(module_name)
                print(f"Loaded {module_name}")
            except Exception as error:
                print(f"Failed to load {module_name}: {error}")

    async def on_ready(self):
        """Called when bot is ready."""
        print(f"{self.user} has connected to Discord!")
        print(f"Bot is in {len(self.guilds)} guilds")

    async def on_message(self, message: discord.Message):
        """檢查訊息中的黑名單用戶"""
        # 忽略機器人訊息
        if message.author.bot:
            await self.process_commands(message)
            return

        # 檢查黑名單
        if blacklist_manager.is_blacklisted(message.author.id):
            # 允許申訴相關的命令
            if not any(cmd in message.content.lower() for cmd in ["申訴", "appeal_status"]):
                embed = discord.Embed(
                    title="[拒絕] 禁止使用",
                    description="您因被添加到黑名單而無法使用此命令。\n\n如果您認為這是誤會，可以使用 `/申訴` 命令提交申訴。",
                    color=discord.Color.red()
                )
                await message.reply(embed=embed, delete_after=10)
                return

        await self.process_commands(message)
