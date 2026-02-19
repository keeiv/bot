"""Core bot class and initialization."""

import discord
from discord.ext import commands
import os
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
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            help_command=None
        )
        
    async def setup_hook(self):
        """Load all cogs and setup bot."""
        await self.load_cogs()
        
    async def load_cogs(self):
        """Load all cogs from the new structure."""
        cogs = [
            'src.cogs.core.admin',
            'src.cogs.core.developer', 
            'src.cogs.core.message_logger',
            'src.cogs.features.achievements',
            'src.cogs.features.anti_spam',
            'src.cogs.features.github_watch',
            'src.cogs.features.osu_info',
            'src.cogs.features.user_server_info',
            'src.cogs.games.deep_sea_oxygen',
            'src.cogs.games.russian_roulette'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"Loaded {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")
                
    async def on_ready(self):
        """Called when bot is ready."""
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')
