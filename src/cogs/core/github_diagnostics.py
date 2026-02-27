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
from src.utils.github_manager import GitHubRequestQueue


class GitHubDiagnosticsCog(commands.Cog):
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
                    f"[GitHub Alert] Low rate limit: {rate_limit['rate']['remaining']} remaining"
                )

        except Exception as e:
            print(f"[GitHub Monitor] Error checking rate limit: {e}")

    @app_commands.command(name="github-diagnose", description="GitHub API 診斷工具")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(owner="倉庫擁有者", repo="倉庫名稱")
    async def github_diagnose(
        self, interaction: discord.Interaction, owner: str = None, repo: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            github_manager = get_github_manager()
            if not github_manager:
                await interaction.followup.send("GitHub manager not initialized")
                return

            self.diagnostics = GitHubDiagnostics(github_manager)

            embed = discord.Embed(
                title="GitHub API Diagnostics", color=discord.Color.blue()
            )

            await interaction.followup.send("Running diagnostics...")

            results = await self.diagnostics.run_diagnostics()

            embed.color = (
                discord.Color.green()
                if results["api_status"] == "operational"
                else discord.Color.red()
            )
            embed.add_field(name="API Status", value=results["api_status"], inline=True)

            embed.add_field(
                name="Token Valid", value=str(results["token_valid"]), inline=True
            )

            embed.add_field(
                name="Connectivity", value=str(results["connectivity"]), inline=True
            )

            embed.add_field(name="Rate Limit", value=results["rate_limit"], inline=True)

            if "connection_error" in results:
                embed.add_field(
                    name="Connection Error",
                    value=results["connection_error"],
                    inline=False,
                )

            embed.set_footer(text=f"Checked at {results['timestamp']}")

            await interaction.followup.send(embed=embed)

            if owner and repo:
                await asyncio.sleep(2)
                repo_results = await self.diagnostics.test_specific_repo(owner, repo)

                repo_embed = discord.Embed(
                    title=f"Repository Test: {owner}/{repo}",
                    color=discord.Color.orange(),
                )

                repo_embed.add_field(
                    name="Repo Accessible",
                    value=str(repo_results["repo_accessible"]),
                    inline=True,
                )

                repo_embed.add_field(
                    name="Commits Accessible",
                    value=str(repo_results["commits_accessible"]),
                    inline=True,
                )

                repo_embed.add_field(
                    name="PRs Accessible",
                    value=str(repo_results["pulls_accessible"]),
                    inline=True,
                )

                if repo_results["errors"]:
                    error_text = "\n".join(repo_results["errors"][:3])
                    repo_embed.add_field(name="Errors", value=error_text, inline=False)

                await interaction.followup.send(embed=repo_embed)

        except Exception as e:
            await interaction.followup.send(f"Diagnostics failed: {e}")

    @app_commands.command(name="github-status", description="GitHub API 狀態檢查")
    @app_commands.checks.has_permissions(administrator=True)
    async def github_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            github_manager = get_github_manager()
            if not github_manager:
                await interaction.followup.send("GitHub manager not initialized")
                return

            rate_limit = await github_manager.get_rate_limit_status()

            embed = discord.Embed(
                title="GitHub API Rate Limit Status", color=discord.Color.blue()
            )

            if "rate" in rate_limit:
                rate_info = rate_limit["rate"]
                remaining = rate_info.get("remaining", 0)
                limit = rate_info.get("limit", 5000)
                used = rate_info.get("used", 0)
                reset_time = rate_info.get("reset", 0)

                usage_percent = (used / limit) * 100 if limit > 0 else 0
                color = (
                    discord.Color.green()
                    if usage_percent < 80
                    else (
                        discord.Color.orange()
                        if usage_percent < 95
                        else discord.Color.red()
                    )
                )

                embed.color = color

                embed.add_field(name="Used", value=f"{used:,}", inline=True)

                embed.add_field(name="Remaining", value=f"{remaining:,}", inline=True)

                embed.add_field(name="Limit", value=f"{limit:,}", inline=True)

                embed.add_field(
                    name="Usage", value=f"{usage_percent:.1f}%", inline=True
                )

                if reset_time:
                    reset_datetime = datetime.fromtimestamp(reset_time, timezone.utc)
                    embed.add_field(
                        name="Reset Time",
                        value=f"<t:{int(reset_datetime.timestamp())}:R>",
                        inline=True,
                    )

                embed.add_field(
                    name="Status",
                    value=(
                        "Normal"
                        if remaining > 100
                        else "Low" if remaining > 10 else "Critical"
                    ),
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Failed to get GitHub status: {e}")

    @app_commands.command(name="github-fix", description="嘗試修復 GitHub API 連接問題")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="修復動作", reset_token="重設 API Token")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="重新初始化連接", value="reinit"),
            app_commands.Choice(name="清理快取", value="clear_cache"),
            app_commands.Choice(name="重設速率限制", value="reset_rate"),
            app_commands.Choice(name="測試 Token", value="test_token"),
        ]
    )
    async def github_fix(
        self, interaction: discord.Interaction, action: str, reset_token: bool = False
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            github_manager = get_github_manager()
            if not github_manager:
                await interaction.followup.send("GitHub manager not initialized")
                return

            if action == "reinit":
                await github_manager.close()
                await asyncio.sleep(2)

                new_token = os.getenv("GITHUB_TOKEN")
                from src.utils.github_manager import init_github_manager

                init_github_manager(new_token)

                await interaction.followup.send("GitHub connection reinitialized")

            elif action == "clear_cache":
                github_manager.rate_manager.rate_limits.clear()
                await interaction.followup.send("GitHub rate limit cache cleared")

            elif action == "reset_rate":
                github_manager.rate_manager.rate_limits.clear()
                await interaction.followup.send("Rate limit tracking reset")

            elif action == "test_token":
                if reset_token:
                    await interaction.followup.send(
                        "Token reset requested - please restart bot with new token"
                    )
                    return

                rate_limit = await github_manager.get_rate_limit_status()
                if "rate" in rate_limit:
                    await interaction.followup.send("Token is valid and working")
                else:
                    await interaction.followup.send("Token may be invalid or expired")

        except Exception as e:
            await interaction.followup.send(f"Fix attempt failed: {e}")

    @app_commands.command(name="github-config", description="GitHub 配置檢查")
    @app_commands.checks.has_permissions(administrator=True)
    async def github_config(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title="GitHub Configuration", color=discord.Color.blue())

        token_present = bool(os.getenv("GITHUB_TOKEN"))
        embed.add_field(
            name="GitHub Token",
            value="Set" if token_present else "Not set",
            inline=True,
        )

        github_manager = get_github_manager()
        if github_manager:
            embed.add_field(name="Manager Status", value="Initialized", inline=True)

            rate_info = github_manager.get_rate_limit_info("default")
            if rate_info:
                embed.add_field(
                    name="Cached Rate Limit",
                    value=f"{rate_info['remaining']} remaining",
                    inline=True,
                )
        else:
            embed.add_field(name="Manager Status", value="Not initialized", inline=True)

        embed.add_field(
            name="Environment",
            value=os.getenv("PYTHON_ENV", "development"),
            inline=True,
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    from src.utils.github_manager import init_github_manager

    token = os.getenv("GITHUB_TOKEN")
    init_github_manager(token)

    await bot.add_cog(GitHubDiagnosticsCog(bot))
