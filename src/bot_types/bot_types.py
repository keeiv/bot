"""Type definitions for bot components."""

from typing import Any, Dict, Optional, Union

import discord

# Config types
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
