import os
import pkgutil

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


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
        )

    async def setup_hook(self):
        """Load all cogs and setup bot."""
        await self.load_cogs()

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


            if module_name.endswith(".__init__"):
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
