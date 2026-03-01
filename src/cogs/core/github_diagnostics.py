import os

from discord.ext import commands
from discord.ext import tasks

from src.utils.github_manager import get_github_manager


class GitHubDiagnosticsCog(commands.Cog):
    """GitHub API 背景監控 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
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


async def setup(bot: commands.Bot):
    from src.utils.github_manager import init_github_manager

    token = os.getenv("GITHUB_TOKEN")
    init_github_manager(token)

    await bot.add_cog(GitHubDiagnosticsCog(bot))
