from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.utils.github_manager import get_github_manager
from src.utils.github_manager import init_github_manager

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


def _format_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")


class GithubWatch(commands.Cog):
    """GitHub 推送通知"""

    repo_watch = app_commands.Group(
        name="repo_watch", description="GitHub 檔案庫更新通知"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/storage/github_watch.json"
        os.makedirs("data/storage", exist_ok=True)

        self._config = self._load_config()
        self._session: aiohttp.ClientSession | None = None

        self._poll_task.start()

    def cog_unload(self):
        self._poll_task.cancel()

    def _load_config(self) -> dict:
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def _get_guild_cfg(self, guild_id: int) -> Optional[dict]:
        return self._config.get(str(guild_id))

    async def _ensure_session(self) -> aiohttp.ClientSession:
        return get_github_manager()

    async def _fetch_latest_commit(self, owner: str, repo: str) -> Optional[dict]:
        """取得最新 commit，回傳 None 表示無變更 (304)"""
        github_manager = await self._ensure_session()

        try:
            commits = await github_manager.get_commits(owner, repo, per_page=1)

            # 304 Not Modified — 無變更
            if commits is None:
                return None

            if not commits:
                raise RuntimeError("GitHub API 回傳空資料")

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
            raise RuntimeError(f"GitHub API 失敗: {e}")

    async def _send_update_message(
        self, guild_id: int, channel_id: int, owner: str, repo: str, commit: dict
    ):
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
            title="檔案庫更新",
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
            embed.add_field(name="資訊", value="\n".join(lines), inline=False)

        await channel.send(embed=embed)

    @tasks.loop(minutes=2)
    async def _poll_task(self):
        for guild_key, cfg in list(self._config.items()):
            try:
                enabled = cfg.get("enabled", False)
                if not enabled:
                    continue

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

                cfg["last_sha"] = sha
                self._save_config()

                await self._send_update_message(
                    int(guild_key), int(channel_id), owner, repo, commit
                )
            except Exception as e:
                print(f"[github_watch] 輪詢失敗 guild={guild_key}: {e}")

    @_poll_task.before_loop
    async def _before_poll(self):
        await self.bot.wait_until_ready()

    @repo_watch.command(name="set", description="設定 GitHub 檔案庫更新通知")
    @app_commands.describe(
        owner="repo 擁有者 (例如 Finn0)",
        repo="repo 名稱 (例如 new_bot)",
        channel="要發通知的頻道",
        interval_minutes="檢查間隔 (分鐘，最小 2)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def repo_watch_set(
        self,
        interaction: discord.Interaction,
        owner: str,
        repo: str,
        channel: discord.TextChannel,
        interval_minutes: int = 2,
    ):
        await interaction.response.defer(ephemeral=True)

        interval_minutes = max(2, min(60, interval_minutes))
        self._poll_task.change_interval(minutes=interval_minutes)

        self._config[str(interaction.guild_id)] = {
            "enabled": True,
            "owner": owner.strip(),
            "repo": repo.strip(),
            "channel_id": channel.id,
            "last_sha": None,
            "interval_minutes": interval_minutes,
        }
        self._save_config()

        await interaction.followup.send(
            f"已啟用 repo 通知\nRepo: {owner}/{repo}\nChannel: {channel.mention}\nInterval: {interval_minutes} 分鐘",
            ephemeral=True,
        )

    @repo_watch.command(name="status", description="查看 GitHub 檔案庫通知狀態")
    async def repo_watch_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cfg = self._get_guild_cfg(interaction.guild_id)
        if not cfg or not cfg.get("enabled"):
            await interaction.followup.send(
                "此伺服器尚未啟用 repo 通知", ephemeral=True
            )
            return

        owner = cfg.get("owner")
        repo = cfg.get("repo")
        channel_id = cfg.get("channel_id")
        interval = cfg.get("interval_minutes", 2)
        last_sha = cfg.get("last_sha")

        await interaction.followup.send(
            f"已啟用\nRepo: {owner}/{repo}\nChannel ID: {channel_id}\nInterval: {interval} 分鐘\nLast SHA: {last_sha[:7] if last_sha else '無'}",
            ephemeral=True,
        )

    @repo_watch.command(name="disable", description="停用 GitHub 檔案庫更新通知")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def repo_watch_disable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cfg = self._get_guild_cfg(interaction.guild_id)
        if not cfg:
            await interaction.followup.send(
                "此伺服器尚未啟用 repo 通知", ephemeral=True
            )
            return

        cfg["enabled"] = False
        self._save_config()
        await interaction.followup.send("已停用 repo 通知", ephemeral=True)


async def setup(bot: commands.Bot):
    token = os.getenv("GITHUB_TOKEN")
    init_github_manager(token)
    await bot.add_cog(GithubWatch(bot))
