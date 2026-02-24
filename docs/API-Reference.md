# API Reference

This document provides comprehensive API documentation for the Discord bot, including core classes, methods, and interfaces.

## Table of Contents

- [Core Classes](#core-classes)
- [Bot Class](#bot-class)
- [Cog Classes](#cog-classes)
- [Utility Functions](#utility-functions)
- [Type Definitions](#type-definitions)
- [Event Handlers](#event-handlers)
- [Error Handling](#error-handling)

## Core Classes

### Bot Class

The main bot class that extends `discord.ext.commands.Bot`.

```python
class Bot(commands.Bot):
    """Main bot class with enhanced functionality."""
```

#### Constructor

```python
def __init__(self) -> None:
    """Initialize the bot with default intents and settings.
    
    Sets up:
    - Discord intents (message content, guilds, members)
    - Command prefix (!)
    - Help command (disabled)
    """
```

#### Methods

##### setup_hook()

```python
async def setup_hook(self) -> None:
    """Called when the bot is starting up.
    
    Loads all cogs and performs initial setup.
    
    Raises:
        Exception: If cog loading fails.
    """
```

##### load_cogs()

```python
async def load_cogs(self) -> None:
    """Load all cogs from the configured list.
    
    Attempts to load:
    - Core cogs (admin, developer, message_logger)
    - Feature cogs (achievements, anti_spam, github_watch, osu_info, user_server_info)
    - Game cogs (deep_sea_oxygen, russian_roulette)
    
    Prints success/failure status for each cog.
    """
```

##### on_ready()

```python
async def on_ready(self) -> None:
    """Called when the bot has successfully connected to Discord.
    
    Prints connection information:
    - Bot user name and discriminator
    - Number of guilds the bot is in
    """
```

## Cog Classes

### Admin Cog

Administrative commands for server management.

```python
class Admin(commands.Cog):
    """Admin commands Cog"""
```

#### Methods

##### clear()

```python
@commands.hybrid_command(name="clear", description="Clear specified number of messages")
@commands.has_permissions(manage_messages=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def clear(self, ctx: commands.Context, amount: int = 10) -> None:
    """Clear a specified number of messages from the channel.
    
    Args:
        ctx: Command context containing channel and author information.
        amount: Number of messages to delete (1-100, default: 10).
        
    Raises:
        commands.MissingPermissions: If user lacks manage_messages permission.
        commands.BadArgument: If amount is outside valid range.
    """
```

##### kick()

```python
@commands.hybrid_command(name="kick", description="Kick member")
@commands.has_permissions(kick_members=True)
async def kick(self, ctx: commands.Context, user: discord.Member, reason: str = "No reason provided") -> None:
    """Kick a member from the server.
    
    Args:
        ctx: Command context.
        user: Member to kick.
        reason: Reason for kicking (default: "No reason provided").
        
    Raises:
        commands.MissingPermissions: If user lacks kick_members permission.
        commands.BadArgument: If trying to kick self or higher role member.
    """
```

##### ban()

```python
@commands.hybrid_command(name="ban", description="Ban member")
@commands.has_permissions(ban_members=True)
async def ban(self, ctx: commands.Context, user: discord.Member, reason: str = "No reason provided") -> None:
    """Ban a member from the server.
    
    Args:
        ctx: Command context.
        user: Member to ban.
        reason: Reason for banning (default: "No reason provided").
        
    Raises:
        commands.MissingPermissions: If user lacks ban_members permission.
        commands.BadArgument: If trying to ban self or higher role member.
    """
```

##### mute()

```python
@commands.hybrid_command(name="mute", description="Mute member")
@commands.has_permissions(moderate_members=True)
async def mute(self, ctx: commands.Context, user: discord.Member, duration: int = 60, reason: str = "No reason provided") -> None:
    """Mute a member for a specified duration.
    
    Args:
        ctx: Command context.
        user: Member to mute.
        duration: Mute duration in minutes (default: 60).
        reason: Reason for muting (default: "No reason provided").
        
    Raises:
        commands.MissingPermissions: If user lacks moderate_members permission.
        commands.BadArgument: If trying to mute self or higher role member.
    """
```

### Achievements Cog

Achievement system for user engagement.

```python
class Achievements(commands.Cog):
    """Achievement system Cog"""
```

#### Methods

##### check_achievement()

```python
async def check_achievement(self, user_id: int, achievement_key: str) -> bool:
    """Check if user has unlocked a specific achievement.
    
    Args:
        user_id: Discord user ID.
        achievement_key: Achievement identifier.
        
    Returns:
        True if achievement is unlocked, False otherwise.
    """
```

##### unlock_achievement()

```python
async def unlock_achievement(self, user_id: int, achievement_key: str) -> bool:
    """Unlock an achievement for a user.
    
    Args:
        user_id: Discord user ID.
        achievement_key: Achievement identifier.
        
    Returns:
        True if achievement was newly unlocked, False if already had it.
        
    Raises:
        ValueError: If achievement_key is not valid.
    """
```

##### get_user_achievements()

```python
async def get_user_achievements(self, user_id: int) -> Dict[str, AchievementData]:
    """Get all achievements for a user.
    
    Args:
        user_id: Discord user ID.
        
    Returns:
        Dictionary mapping achievement keys to achievement data.
    """
```

### Message Logger Cog

Comprehensive message logging and analytics.

```python
class MessageLogger(commands.Cog):
    """Message logging Cog"""
```

#### Methods

##### log_message()

```python
async def log_message(self, message: discord.Message) -> None:
    """Log a message to the storage system.
    
    Args:
        message: Discord message object to log.
        
    Logs:
        - Message ID, content, author, timestamp
        - Channel ID and guild ID
        - Attachments and embeds information
    """
```

##### get_message_history()

```python
async def get_message_history(self, channel_id: int, limit: int = 100) -> List[MessageEntry]:
    """Retrieve message history for a channel.
    
    Args:
        channel_id: Discord channel ID.
        limit: Maximum number of messages to retrieve (default: 100).
        
    Returns:
        List of message entries in chronological order.
    """
```

## Utility Functions

### Configuration Manager

```python
def load_config() -> Dict[str, Any]:
    """Load bot configuration from JSON file.
    
    Returns:
        Configuration dictionary with bot settings.
        
    Creates default config if file doesn't exist.
    """

def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to JSON file.
    
    Args:
        config: Configuration dictionary to save.
        
    Raises:
        IOError: If file cannot be written.
    """

def ensure_data_dir() -> None:
    """Create necessary data directories.
    
    Creates:
    - data/
    - data/config/
    - data/storage/
    - data/logs/messages/
    """
```

### Blacklist Manager

```python
class BlacklistManager:
    """Manages user and guild blacklists."""
    
    def is_blacklisted(self, user_id: int) -> bool:
        """Check if user is blacklisted.
        
        Args:
            user_id: Discord user ID.
            
        Returns:
            True if user is blacklisted, False otherwise.
        """
    
    def add_to_blacklist(self, user_id: int, reason: str, added_by: str) -> None:
        """Add user to blacklist.
        
        Args:
            user_id: Discord user ID.
            reason: Reason for blacklisting.
            added_by: Who added the user to blacklist.
        """
    
    def remove_from_blacklist(self, user_id: int) -> bool:
        """Remove user from blacklist.
        
        Args:
            user_id: Discord user ID.
            
        Returns:
            True if user was removed, False if not found.
        """
```

## Type Definitions

### Core Types

```python
# Configuration types
GuildConfig = Dict[str, Any]
BotConfig = Dict[str, GuildConfig]

# User data types
UserData = Dict[str, Any]
AchievementData = Dict[str, Any]

# Message log types
MessageEntry = Dict[str, Union[str, bool, int]]
MessageLog = Dict[str, MessageEntry]

# osu! types
OsuUserLink = Dict[int, str]  # discord_id -> osu_username

# GitHub types
GitHubCommit = Dict[str, str]
GitHubConfig = Dict[str, Any]

# Embed types
EmbedData = Dict[str, Any]

# Command context types
Context = Union[discord.ApplicationContext, discord.Interaction]
```

### Achievement Types

```python
class Achievement:
    """Represents an achievement."""
    
    def __init__(self, key: str, name: str, description: str, rarity: str, points: int):
        self.key = key
        self.name = name
        self.description = description
        self.rarity = rarity  # common, uncommon, rare, epic, legendary
        self.points = points
    
    def to_embed(self) -> discord.Embed:
        """Convert achievement to Discord embed.
        
        Returns:
            Discord embed with achievement information.
        """
```

## Event Handlers

### Message Events

```python
async def on_message(self, message: discord.Message) -> None:
    """Handle incoming message events.
    
    Args:
        message: Discord message object.
        
    Triggers:
        - Command processing
        - Message logging
        - Achievement checking
        - Anti-spam detection
    """

async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
    """Handle message edit events.
    
    Args:
        before: Message before edit.
        after: Message after edit.
        
    Logs:
        - Edit timestamp
        - Content changes
        - Author information
    """

async def on_message_delete(self, message: discord.Message) -> None:
    """Handle message deletion events.
    
    Args:
        message: Deleted message object.
        
    Logs:
        - Deletion timestamp
        - Original content
        - Deletion context
    """
```

### Member Events

```python
async def on_member_join(self, member: discord.Member) -> None:
    """Handle member join events.
    
    Args:
        member: Member who joined the server.
        
    Triggers:
        - Welcome messages
        - Role assignment
        - Initial data setup
    """

async def on_member_remove(self, member: discord.Member) -> None:
    """Handle member leave events.
    
    Args:
        member: Member who left the server.
        
    Triggers:
        - Goodbye messages
        - Data cleanup
        - Statistics updates
    """
```

### Guild Events

```python
async def on_guild_join(self, guild: discord.Guild) -> None:
    """Handle bot joining a new guild.
    
    Args:
        guild: Guild the bot joined.
        
    Triggers:
        - Guild setup
        - Default configuration
        - Welcome message
    """

async def on_guild_remove(self, guild: discord.Guild) -> None:
    """Handle bot leaving a guild.
    
    Args:
        guild: Guild the bot left.
        
    Triggers:
        - Data cleanup
        - Configuration removal
        - Statistics update
    """
```

## Error Handling

### Custom Exceptions

```python
class BotError(Exception):
    """Base exception for bot-related errors."""
    pass

class ConfigurationError(BotError):
    """Raised when configuration is invalid."""
    pass

class PermissionError(BotError):
    """Raised when user lacks required permissions."""
    pass

class DataError(BotError):
    """Raised when data operations fail."""
    pass

class APIError(BotError):
    """Raised when external API calls fail."""
    pass
```

### Error Handlers

```python
async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
    """Handle command errors globally.
    
    Args:
        ctx: Command context where error occurred.
        error: The exception that was raised.
        
    Handles:
        - Missing permissions
        - Invalid arguments
        - Command cooldowns
        - Bot permissions
    """

async def on_error(self, event_method: str, *args, **kwargs) -> None:
    """Handle uncaught event errors.
    
    Args:
        event_method: Name of the event method that raised error.
        *args: Positional arguments passed to event.
        **kwargs: Keyword arguments passed to event.
        
    Logs:
        - Error details
        - Event context
        - Stack trace
    """
```

## Usage Examples

### Basic Bot Usage

```python
import discord
from src.bot import Bot

# Create bot instance
bot = Bot()

# Run bot
bot.run("YOUR_DISCORD_TOKEN")
```

### Adding Custom Cogs

```python
from discord.ext import commands
from src.bot import Bot

class CustomCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
    
    @commands.command()
    async def hello(self, ctx: commands.Context):
        await ctx.send("Hello, World!")

# Add cog to bot
bot.add_cog(CustomCog(bot))
```

### Configuration Access

```python
from src.utils.config_manager import load_config

# Load configuration
config = load_config()

# Access bot settings
prefix = config["bot"]["prefix"]
status = config["bot"]["status"]["message"]

# Access guild settings
guild_config = config["guilds"].get(guild_id, {})
admin_role = guild_config.get("admin_role", "Admin")
```

### Data Storage

```python
from src.bot_types import UserData, MessageEntry

# Create user data
user_data: UserData = {
    "user_id": user.id,
    "username": user.name,
    "joined_at": user.joined_at.isoformat(),
    "message_count": 0,
    "achievements": []
}

# Create message entry
message_entry: MessageEntry = {
    "message_id": message.id,
    "content": message.content,
    "author_id": message.author.id,
    "channel_id": message.channel.id,
    "guild_id": message.guild.id,
    "timestamp": message.created_at.isoformat(),
    "edited": False,
    "deleted": False
}
```

---

**API Reference complete!** This documentation covers all major classes, methods, and interfaces available in the Discord bot.
