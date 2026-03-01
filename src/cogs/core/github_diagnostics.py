import asyncio
from datetime import datetime
from datetime import timezone
import os

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.utils.github_manager import get_github_manager
from src.utils.github_manager import GitHubDiagnostics


class GitHubDiagnosticsCog(commands.Cog):
    """GitHub API 診斷 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.diagnostics = None
        self.request_queue = None
        self._monitor_task.start()

    def cog_unload(self):
        self._monitor_task.cancel()

    @tasks.loop(minutes=10)
    async def _monitor_task(self):
        await self.bot.wait_until_ready()

        try:
            github_manager = get_github_manager()
            if not github_manager:
                return

            rate_limit = await github_manager.get_rate_limit_status()

            if rate_limit.get("rate", {}).get("remaining", 5000) < 100:
                print(
                    f"[GitHub 警告] 速率限制即將耗盡: 剩餘 {rate_limit['rate']['remaining']}"
                )

        except Exception as e:
            print(f"[GitHub 監控] 檢查速率限制錯誤: {e}")

    @app_commands.command(name="github-diagnose", description="GitHub API 診斷工具")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(owner="倉庫擁有者", repo="倉庫名稱")
    async def github_diagnose(
        self, interaction: discord.Interaction, owner: str = None, repo: str = None
    ):
        """GitHub API 診斷"""
        await interaction.response.defer(ephemeral=True)

        try:
            github_manager = get_github_manager()
            if not github_manager:
                await interaction.followup.send("[失敗] GitHub 管理器尚未初始化")
                return

            self.diagnostics = GitHubDiagnostics(github_manager)

            await interaction.followup.send("正在執行診斷...")

            results = await self.diagnostics.run_diagnostics()

            is_operational = results["api_status"] == "operational"
            embed = discord.Embed(
                title="[GitHub] API 診斷結果",
                color=discord.Color.from_rgb(46, 204, 113) if is_operational
                else discord.Color.from_rgb(231, 76, 60),
            )

            embed.add_field(
                name="[API 狀態]",
                value="運作中" if is_operational else results["api_status"],
                inline=True,
            )

            embed.add_field(
                name="[Token 有效]",
                value="是" if results["token_valid"] else "否",
                inline=True,
            )

            embed.add_field(
                name="[連線狀態]",
                value="正常" if results["connectivity"] else "失敗",
                inline=True,
            )

            embed.add_field(
                name="[速率限制]",
                value=results["rate_limit"],
                inline=True,
            )

            if "connection_error" in results:
                embed.add_field(
                    name="[連線錯誤]",
                    value=results["connection_error"],
                    inline=False,
                )

            embed.set_footer(text=f"檢查時間: {results['timestamp']}")

            await interaction.followup.send(embed=embed)

            if owner and repo:
                await asyncio.sleep(2)
                repo_results = await self.diagnostics.test_specific_repo(owner, repo)

                repo_embed = discord.Embed(
                    title=f"[GitHub] 倉庫測試: {owner}/{repo}",
                    color=discord.Color.from_rgb(241, 196, 15),
                )

                repo_embed.add_field(
                    name="[倉庫可存取]",
                    value="是" if repo_results["repo_accessible"] else "否",
                    inline=True,
                )

                repo_embed.add_field(
                    name="[Commits 可存取]",
                    value="是" if repo_results["commits_accessible"] else "否",
                    inline=True,
                )

                repo_embed.add_field(
                    name="[PRs 可存取]",
                    value="是" if repo_results["pulls_accessible"] else "否",
                    inline=True,
                )

                if repo_results["errors"]:
                    error_text = "\n".join(repo_results["errors"][:3])
                    repo_embed.add_field(
                        name="[錯誤]", value=error_text, inline=False
                    )

                await interaction.followup.send(embed=repo_embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 診斷失敗: {e}")

    @app_commands.command(name="github-status", description="GitHub API 狀態檢查")
    @app_commands.checks.has_permissions(administrator=True)
    async def github_status(self, interaction: discord.Interaction):
        """GitHub API 狀態檢查"""
        await interaction.response.defer(ephemeral=True)

        try:
            github_manager = get_github_manager()
            if not github_manager:
                await interaction.followup.send("[失敗] GitHub 管理器尚未初始化")
                return

            rate_limit = await github_manager.get_rate_limit_status()

            embed = discord.Embed(
                title="[GitHub] 速率限制狀態",
                color=discord.Color.from_rgb(52, 152, 219),
            )

            if "rate" in rate_limit:
                rate_info = rate_limit["rate"]
                remaining = rate_info.get("remaining", 0)
                limit = rate_info.get("limit", 5000)
                used = rate_info.get("used", 0)
                reset_time = rate_info.get("reset", 0)

                usage_percent = (used / limit) * 100 if limit > 0 else 0
                if usage_percent < 80:
                    embed.color = discord.Color.from_rgb(46, 204, 113)
                elif usage_percent < 95:
                    embed.color = discord.Color.from_rgb(241, 196, 15)
                else:
                    embed.color = discord.Color.from_rgb(231, 76, 60)

                embed.add_field(
                    name="[已使用]", value=f"{used:,}", inline=True
                )

                embed.add_field(
                    name="[剩餘]", value=f"{remaining:,}", inline=True
                )

                embed.add_field(
                    name="[上限]", value=f"{limit:,}", inline=True
                )

                embed.add_field(
                    name="[使用率]", value=f"{usage_percent:.1f}%", inline=True
                )

                if reset_time:
                    reset_datetime = datetime.fromtimestamp(reset_time, timezone.utc)
                    embed.add_field(
                        name="[重置時間]",
                        value=f"<t:{int(reset_datetime.timestamp())}:R>",
                        inline=True,
                    )

                if remaining > 100:
                    status_text = "正常"
                elif remaining > 10:
                    status_text = "偏低"
                else:
                    status_text = "危急"
                embed.add_field(
                    name="[狀態]", value=status_text, inline=True
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 無法取得 GitHub 狀態: {e}")




async def setup(bot: commands.Bot):
    from src.utils.github_manager import init_github_manager

    token = os.getenv("GITHUB_TOKEN")
    init_github_manager(token)

    await bot.add_cog(GitHubDiagnosticsCog(bot))
