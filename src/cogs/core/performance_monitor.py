from discord.ext import commands
from discord.ext import tasks

from src.utils.api_optimizer import get_api_optimizer
from src.utils.config_optimizer import get_config_manager
from src.utils.database_manager import get_database_manager
from src.utils.network_optimizer import get_network_optimizer


class PerformanceMonitorCog(commands.Cog):
    """機器人效能背景監控 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._monitor_task.start()

    def cog_unload(self):
        self._monitor_task.cancel()

    @tasks.loop(minutes=5)
    async def _monitor_task(self):
        await self.bot.wait_until_ready()

        try:
            await self.collect_performance_metrics()
        except Exception as e:
            print(f"[效能監控] 收集指標時發生錯誤: {e}")

    async def collect_performance_metrics(self):
        """收集效能指標"""
        db_manager = get_database_manager()
        if db_manager:
            cache_stats = await db_manager.get_cache_stats()
            await db_manager.store_metric(
                "database_cache_size",
                cache_stats["total_entries"],
                {
                    "valid_entries": cache_stats["valid_entries"],
                    "expired_entries": cache_stats["expired_entries"],
                },
            )

        config_manager = get_config_manager()
        if config_manager and db_manager:
            config_stats = config_manager.get_cache_stats()
            await db_manager.store_metric(
                "config_cache_size",
                config_stats["cache_size"],
                {
                    "file_locks": config_stats["file_locks"],
                    "active_watchers": config_stats["active_watchers"],
                },
            )

        network_optimizer = get_network_optimizer()
        if network_optimizer and db_manager:
            network_stats = network_optimizer.get_network_stats()
            for hostname, stats in network_stats.get("response_times", {}).items():
                await db_manager.store_metric(
                    f"network_response_time_{hostname}",
                    stats["avg"],
                    {"count": stats["count"], "min": stats["min"], "max": stats["max"]},
                )
            await db_manager.store_metric(
                "active_requests",
                sum(network_stats.get("active_requests", {}).values()),
            )
            await db_manager.store_metric(
                "dns_cache_size", network_stats.get("dns_cache_size", 0)
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PerformanceMonitorCog(bot))
