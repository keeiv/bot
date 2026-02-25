import os
import json
import aiohttp
import shutil
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import discord
from discord.ext import commands, tasks
from discord import app_commands

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


def _format_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")


class Management(commands.Cog):
    """Server management commands including repository tracking, role assignment, emoji management, and welcome messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/storage/management.json"
        os.makedirs("data/storage", exist_ok=True)

        self._config = self._load_config()
        self._session: aiohttp.ClientSession | None = None

        self._repo_poll_task.start()

    def cog_unload(self):
        self._repo_poll_task.cancel()

    def _load_config(self) -> dict:
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        """Save configuration with backup mechanism"""
        try:
            # Create backup before saving
            if os.path.exists(self.data_file):
                backup_file = f"{self.data_file}.backup"
                shutil.copy2(self.data_file, backup_file)

            # Save main config
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")
            # Try to restore from backup if main save failed
            backup_file = f"{self.data_file}.backup"
            if os.path.exists(backup_file):
                print("Attempting to restore from backup...")
                shutil.copy2(backup_file, self.data_file)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with timeout and retry logic"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={'User-Agent': 'Discord-Bot/1.0'}
            )
        return self._session

    # Repository tracking commands
    repo_track = app_commands.Group(name="repo_track", description="追蹤倉庫更新與拉取請求")

    @repo_track.command(name="add", description="新增 keeiv/bot 倉庫追蹤")
    @app_commands.describe(
        channel="發送通知的頻道"
    )
    async def repo_track_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"
        owner = "keeiv"
        repo = "bot"

        if guild_id not in self._config:
            self._config[guild_id] = {}
        if "tracked_repos" not in self._config[guild_id]:
            self._config[guild_id]["tracked_repos"] = {}

        self._config[guild_id]["tracked_repos"][repo_key] = {
            "owner": owner,
            "repo": repo,
            "channel_id": channel.id,
            "last_commit": None,
            "last_pr": None
        }

        self._save_config()
        await interaction.response.send_message(f"Now tracking {repo_key} updates in {channel.mention}")

    @repo_track.command(name="remove", description="移除 keeiv/bot 倉庫追蹤")
    async def repo_track_remove(
        self,
        interaction: discord.Interaction
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"

        if (guild_id in self._config and
            "tracked_repos" in self._config[guild_id] and
            repo_key in self._config[guild_id]["tracked_repos"]):

            del self._config[guild_id]["tracked_repos"][repo_key]
            self._save_config()
            await interaction.response.send_message(f"Stopped tracking {repo_key}")
        else:
            await interaction.response.send_message(f"{repo_key} is not being tracked", ephemeral=True)

    @repo_track.command(name="status", description="顯示追蹤狀態")
    async def repo_track_status(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if (guild_id not in self._config or
            "tracked_repos" not in self._config[guild_id] or
            not self._config[guild_id]["tracked_repos"]):

            await interaction.response.send_message("No repositories are being tracked", ephemeral=True)
            return

        embed = discord.Embed(title="keeiv/bot Repository Tracking Status", color=discord.Color.blue())

        repo_key = "keeiv/bot"
        if (guild_id in self._config and
            "tracked_repos" in self._config[guild_id] and
            repo_key in self._config[guild_id]["tracked_repos"]):

            data = self._config[guild_id]["tracked_repos"][repo_key]
            channel = self.bot.get_channel(data["channel_id"])
            channel_name = channel.mention if channel else f"Unknown channel ({data['channel_id']})"

            embed.add_field(
                name=repo_key,
                value=f"Channel: {channel_name}\nLast commit: {data.get('last_commit', 'Never')}\nLast PR: {data.get('last_pr', 'Never')}",
                inline=False
            )
        else:
            embed.description = "keeiv/bot repository is not being tracked"

        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=5)
    async def _repo_poll_task(self):
        """Check for repository updates every 5 minutes with error handling"""
        if not self._config:
            return

        for guild_id, guild_config in self._config.items():
            if "tracked_repos" not in guild_config or not guild_config["tracked_repos"]:
                continue

            for repo_key, repo_data in guild_config["tracked_repos"].items():
                try:
                    await self._check_repo_updates(guild_id, repo_key, repo_data)
                except Exception as e:
                    print(f"Error checking {repo_key}: {e}")
                    # Continue with other repos even if one fails
                    continue

    async def _check_repo_updates(self, guild_id: str, repo_key: str, repo_data: dict):
        """Check repository updates with improved error handling"""
        session = await self._get_session()
        owner = repo_data["owner"]
        repo = repo_data["repo"]

        try:
            # Check commits with error handling
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            async with session.get(commits_url) as response:
                if response.status == 200:
                    commits = await response.json()
                    if commits and commits[0]["sha"] != repo_data.get("last_commit"):
                        latest_commit = commits[0]
                        repo_data["last_commit"] = latest_commit["sha"]

                        channel = self.bot.get_channel(repo_data["channel_id"])
                        if channel:
                            embed = discord.Embed(
                                title=f"New Commit in {repo_key}",
                                description=latest_commit["commit"]["message"][:200],
                                url=latest_commit["html_url"],
                                color=discord.Color.green()
                            )
                            embed.set_author(
                                name=latest_commit["author"]["login"],
                                url=latest_commit["author"]["html_url"],
                                icon_url=latest_commit["author"]["avatar_url"]
                            )
                            embed.add_field(name="SHA", value=latest_commit["sha"][:7], inline=True)
                            embed.add_field(name="Date", value=_format_time(datetime.fromisoformat(latest_commit["commit"]["committer"]["date"])), inline=True)

                            await channel.send(embed=embed)
                elif response.status == 403:
                    print(f"Rate limited for {repo_key}, skipping this check")
                else:
                    print(f"Failed to fetch commits for {repo_key}: {response.status}")

            # Check pull requests with error handling
            prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            async with session.get(prs_url) as response:
                if response.status == 200:
                    prs = await response.json()
                    if prs and prs[0]["number"] != repo_data.get("last_pr"):
                        latest_pr = prs[0]
                        repo_data["last_pr"] = latest_pr["number"]

                        channel = self.bot.get_channel(repo_data["channel_id"])
                        if channel:
                            embed = discord.Embed(
                                title=f"New Pull Request in {repo_key}",
                                description=latest_pr["title"][:200],
                                url=latest_pr["html_url"],
                                color=discord.Color.orange()
                            )
                            embed.set_author(
                                name=latest_pr["user"]["login"],
                                url=latest_pr["user"]["html_url"],
                                icon_url=latest_pr["user"]["avatar_url"]
                            )
                            embed.add_field(name="PR Number", value=str(latest_pr["number"]), inline=True)
                            embed.add_field(name="State", value=latest_pr["state"].title(), inline=True)

                            await channel.send(embed=embed)
                elif response.status == 403:
                    print(f"Rate limited for {repo_key} PRs, skipping this check")
                else:
                    print(f"Failed to fetch PRs for {repo_key}: {response.status}")

            # Only save if there were changes
            self._save_config()

        except aiohttp.ClientError as e:
            print(f"Network error checking {repo_key}: {e}")
        except Exception as e:
            print(f"Unexpected error checking {repo_key}: {e}")

    # Role management commands
    role = app_commands.Group(name="role", description="身份組管理指令")

    @role.command(name="assign", description="為用戶分配身份組")
    @app_commands.describe(
        user="要分配身份組的用戶",
        role="要分配的身份組"
    )
    async def role_assign(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role
    ):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You need 'Manage Roles' permission to use this command.", ephemeral=True)
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message("You cannot assign a role that is higher than or equal to your highest role.", ephemeral=True)
            return

        try:
            await user.add_roles(role)
            await interaction.response.send_message(f"Assigned {role.mention} to {user.mention}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to assign that role.", ephemeral=True)

    @role.command(name="remove", description="從用戶移除身份組")
    @app_commands.describe(
        user="要移除身份組的用戶",
        role="要移除的身份組"
    )
    async def role_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role
    ):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You need 'Manage Roles' permission to use this command.", ephemeral=True)
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message("You cannot remove a role that is higher than or equal to your highest role.", ephemeral=True)
            return

        try:
            await user.remove_roles(role)
            await interaction.response.send_message(f"Removed {role.mention} from {user.mention}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to remove that role.", ephemeral=True)

    # Emoji management commands
    emoji = app_commands.Group(name="emoji", description="表情符號管理指令")

    @emoji.command(name="get", description="獲取表情符號大圖")
    @app_commands.describe(emoji="要獲取的表情符號")
    async def emoji_get(self, interaction: discord.Interaction, emoji: str):
        try:
            # Parse emoji
            if emoji.startswith("<:") and emoji.endswith(">"):
                # Custom emoji
                parts = emoji.strip("<:>").split(":")
                if len(parts) == 2:
                    emoji_id = parts[1]
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
                else:
                    await interaction.response.send_message("Invalid emoji format", ephemeral=True)
                    return
            elif emoji.startswith("<a:") and emoji.endswith(">"):
                # Animated emoji
                parts = emoji.strip("<a:>").split(":")
                if len(parts) == 2:
                    emoji_id = parts[1]
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.gif"
                else:
                    await interaction.response.send_message("Invalid emoji format", ephemeral=True)
                    return
            else:
                await interaction.response.send_message("Please use a custom emoji", ephemeral=True)
                return

            embed = discord.Embed(title="Emoji Image", color=discord.Color.blue())
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error getting emoji: {e}", ephemeral=True)

    @emoji.command(name="upload", description="上傳表情符號到伺服器")
    @app_commands.describe(
        name="表情符號名稱",
        image="要上傳為表情符號的圖片檔案"
    )
    async def emoji_upload(
        self,
        interaction: discord.Interaction,
        name: str,
        image: discord.Attachment
    ):
        if not interaction.user.guild_permissions.manage_emojis:
            await interaction.response.send_message("You need 'Manage Emojis' permission to use this command.", ephemeral=True)
            return

        if not image.content_type.startswith("image/"):
            await interaction.response.send_message("Please upload an image file", ephemeral=True)
            return

        try:
            image_data = await image.read()
            emoji = await interaction.guild.create_custom_emoji(
                name=name,
                image=image_data,
                reason=f"Uploaded by {interaction.user}"
            )
            await interaction.response.send_message(f"Successfully uploaded emoji: {emoji}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to upload emojis", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error uploading emoji: {e}", ephemeral=True)

    # Welcome message commands
    welcome = app_commands.Group(name="welcome", description="歡迎訊息管理")

    @welcome.command(name="setup", description="設定新成員歡迎訊息")
    @app_commands.describe(
        channel="發送歡迎訊息的頻道",
        message="歡迎訊息範本（使用 {user} 代表用戶提及，{server} 代表伺服器名稱）"
    )
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = "Welcome {user} to {server}!"
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)

        if guild_id not in self._config:
            self._config[guild_id] = {}

        self._config[guild_id]["welcome"] = {
            "channel_id": channel.id,
            "message": message
        }

        self._save_config()
        await interaction.response.send_message(f"Welcome messages will be sent to {channel.mention}")

    @welcome.command(name="disable", description="停用歡迎訊息")
    async def welcome_disable(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need 'Manage Channels' permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)

        if guild_id in self._config and "welcome" in self._config[guild_id]:
            del self._config[guild_id]["welcome"]
            self._save_config()
            await interaction.response.send_message("Welcome messages disabled")
        else:
            await interaction.response.send_message("Welcome messages are not enabled", ephemeral=True)

    @welcome.command(name="preview", description="預覽歡迎訊息")
    async def welcome_preview(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in self._config or "welcome" not in self._config[guild_id]:
            await interaction.response.send_message("Welcome messages are not configured", ephemeral=True)
            return

        welcome_config = self._config[guild_id]["welcome"]
        message = welcome_config["message"].format(
            user=interaction.user.mention,
            server=interaction.guild.name
        )

        await interaction.response.send_message(f"Preview: {message}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)

        if guild_id not in self._config or "welcome" not in self._config[guild_id]:
            return

        welcome_config = self._config[guild_id]["welcome"]
        channel = member.guild.get_channel(welcome_config["channel_id"])

        if channel:
            message = welcome_config["message"].format(
                user=member.mention,
                server=member.guild.name
            )
            await channel.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))
