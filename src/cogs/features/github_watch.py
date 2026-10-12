from datetime import datetime
from datetime import timedelta
from datetime import timezone
import os
import time
from typing import Any, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.services.github_watch_service import GithubWatchService
from src.utils.github_manager import get_github_manager
from src.utils.github_manager import GitHubAPIManager
from src.utils.github_manager import init_github_manager
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


def _format_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")


class GithubWatch(commands.Cog):
    """GitHub 推送通知"""

    repo_watch = app_commands.Group(
        name="repo_watch", description="GitHub repository updates"
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = GithubWatchService()
        self._last_poll: dict[str, float] = {}
        self._session: aiohttp.ClientSession | None = None

        self._poll_task.start()

    async def cog_unload(self) -> None:
        self._poll_task.cancel()

    def _get_guild_cfg(self, guild_id: int) -> Optional[dict[Any, Any]]:
        return self.service.get_config(guild_id) or None

    def reset_poll(self, guild_id):
        """Schedule a changed subscription for the next polling iteration."""
        self._last_poll.pop(str(guild_id), None)

    async def _ensure_session(self) -> GitHubAPIManager:
        manager = get_github_manager()
        if manager is None:
            raise RuntimeError("GitHub manager is not initialized")
        return manager

    async def _fetch_latest_commit(
        self, owner: str, repo: str
    ) -> Optional[dict[Any, Any]]:
        """取得最新 commit，回傳 None 表示無變更 (304)"""
        github_manager = await self._ensure_session()

        try:
            commits = await github_manager.get_commits(owner, repo, per_page=1)

            # 304 Not Modified — 無變更
            if commits is None:
                return None

            if not commits:
                raise RuntimeError(tx("github_watch.github_api_returned_no_data"))

            c = commits[0]
            sha = c.get("sha")
            html_url = c.get("html_url")
            commit = c.get("commit") or {}
            message = (commit.get("message") or "").split("\n", 1)[0]
            author = (commit.get("author") or {}).get("name")
            date_str = (commit.get("author") or {}).get("date")

            dt = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    dt = None

            pusher = None
            if c.get("author") and isinstance(c["author"], dict):
                pusher = c["author"].get("login")

            return {
                "sha": sha,
                "url": html_url,
                "message": message,
                "author": author,
                "pusher": pusher,
                "date": dt,
            }
        except Exception as e:
            print(f"[GitHub Watch] Error fetching commit: {e}")
            raise RuntimeError(tx("github_watch.github_api_failed", v0=(e)))

    @localized("channel")
    async def _send_update_message(
        self,
        guild_id: int,
        channel_id: int,
        owner: str,
        repo: str,
        commit: dict[Any, Any],
    ) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        sha = commit.get("sha")
        url = commit.get("url")
        msg = commit.get("message")
        author = commit.get("author")
        pusher = commit.get("pusher")
        dt = commit.get("date")

        embed = discord.Embed(
            title=tx("github_watch.repository_update"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )

        embed.add_field(name="Repo", value=f"{owner}/{repo}", inline=False)
        if msg:
            embed.add_field(name="Commit", value=msg, inline=False)

        lines = []
        if sha:
            lines.append(f"SHA: {sha[:7]}")
        if author:
            lines.append(f"Author: {author}")
        if pusher:
            lines.append(f"GitHub: {pusher}")
        if dt:
            lines.append(f"Time: {_format_time(dt)}")
        if url:
            lines.append(f"Link: {url}")

        if lines:
            embed.add_field(
                name=tx("github_watch.info"), value="\n".join(lines), inline=False
            )

        await channel.send(embed=embed)

    @tasks.loop(seconds=30)
    async def _poll_task(self) -> None:
        for guild_key, cfg in self.service.get_all_configs().items():
            try:
                enabled = cfg.get("enabled", False)
                if not enabled:
                    continue

                now = time.monotonic()
                if (
                    now - self._last_poll.get(guild_key, -float("inf"))
                    < cfg.get("interval_minutes", 2) * 60
                ):
                    continue
                self._last_poll[guild_key] = now
                owner = cfg.get("owner")
                repo = cfg.get("repo")
                channel_id = cfg.get("channel_id")
                last_sha = cfg.get("last_sha")

                if not owner or not repo or not channel_id:
                    continue

                commit = await self._fetch_latest_commit(owner, repo)

                # None = 304 無變更，跳過
                if commit is None:
                    continue

                sha = commit.get("sha")
                if not sha:
                    continue

                if last_sha and sha == last_sha:
                    continue

                if not await run_storage(
                    self.service.record_commit, guild_key, cfg, sha
                ):
                    continue

                await self._send_update_message(
                    int(guild_key), int(channel_id), owner, repo, commit
                )
            except Exception as e:
                print(f"[github_watch] 輪詢失敗 guild={guild_key}: {e}")

    @_poll_task.before_loop
    async def _before_poll(self) -> None:
        try:
            await self.bot.wait_until_ready()
        except RuntimeError:
            self._poll_task.cancel()

    @repo_watch.command(name="set", description="Post updates from a GitHub repository")
    @app_commands.describe(
        owner="Repository owner (for example Finn0)",
        repo="Repository name (for example new_bot)",
        channel="The channel for updates",
        interval_minutes="How often to check, in minutes (at least 2)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @localized("interaction")
    async def repo_watch_set(
        self,
        interaction: discord.Interaction,
        owner: str,
        repo: str,
        channel: discord.TextChannel,
        interval_minutes: int = 2,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        interval_minutes = max(2, min(60, interval_minutes))

        config = {
            "enabled": True,
            "owner": owner.strip(),
            "repo": repo.strip(),
            "channel_id": channel.id,
            "last_sha": None,
            "interval_minutes": interval_minutes,
        }
        await run_storage(self.service.update_config, interaction.guild_id, config)
        self.reset_poll(interaction.guild_id)

        await interaction.followup.send(
            tx(
                "github_watch.repository_notifications_enabled_repository_channel_interval",
                v0=(owner),
                v1=(repo),
                v2=(channel.mention),
                v3=(interval_minutes),
            ),
            ephemeral=True,
        )

    @repo_watch.command(name="status", description="Show the GitHub update settings")
    @localized("interaction")
    async def repo_watch_status(self, interaction: discord.Interaction) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)

        cfg = self._get_guild_cfg(interaction.guild_id)
        if not cfg or not cfg.get("enabled"):
            await interaction.followup.send(
                tx("github_watch.repository_notifications_are_not_enabled_for"),
                ephemeral=True,
            )
            return

        owner = cfg.get("owner")
        repo = cfg.get("repo")
        channel_id = cfg.get("channel_id")
        interval = cfg.get("interval_minutes", 2)
        last_sha = cfg.get("last_sha")

        await interaction.followup.send(
            tx(
                "github_watch.enabled_repository_channel_id_interval_minutes",
                v0=(owner),
                v1=(repo),
                v2=(channel_id),
                v3=(interval),
                v4=(last_sha[:7] if last_sha else tx("audit_log.none")),
            ),
            ephemeral=True,
        )

    @repo_watch.command(name="disable", description="Stop GitHub repository updates")
    @app_commands.checks.has_permissions(manage_guild=True)
    @localized("interaction")
    async def repo_watch_disable(self, interaction: discord.Interaction) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)

        cfg = self._get_guild_cfg(interaction.guild_id)
        if not cfg:
            await interaction.followup.send(
                tx("github_watch.repository_notifications_are_not_enabled_for"),
                ephemeral=True,
            )
            return

        await run_storage(
            self.service.update_config, interaction.guild_id, {"enabled": False}
        )
        self.reset_poll(interaction.guild_id)
        await interaction.followup.send(
            tx("github_watch.repository_notifications_disabled"), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    token = os.getenv("GITHUB_TOKEN")
    init_github_manager(token)
    await bot.add_cog(GithubWatch(bot))
