import asyncio
import gc
import time

from discord.ext import commands
from discord.ext import tasks
import psutil

from src.utils.api_optimizer import get_api_optimizer
from src.utils.api_optimizer import performance_monitor


class SystemMaintenance(commands.Cog):
    """系統背景維護 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.memory_threshold = 80.0
        self.cpu_threshold = 80.0

        self._maintenance_task.start()
        self._performance_task.start()

    def cog_unload(self):
        self._maintenance_task.cancel()
        self._performance_task.cancel()

    @tasks.loop(minutes=30)
    async def _maintenance_task(self):
        await self.bot.wait_until_ready()

        try:
            await self.perform_system_cleanup()
            await self.optimize_caches()
            await self.check_system_health()
        except Exception as e:
            print(f"[系統維護] 定期任務錯誤: {e}")

    @tasks.loop(minutes=5)
    async def _performance_task(self):
        await self.bot.wait_until_ready()

        try:
            await self.collect_performance_metrics()
        except Exception as e:
            print(f"[效能監控] 收集指標錯誤: {e}")

    async def perform_system_cleanup(self):
        timing_id = performance_monitor.start_timing("system_cleanup")

        try:
            gc.collect()

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                api_optimizer.clear_cache()

            await self.cleanup_old_data()

        finally:
            performance_monitor.end_timing(timing_id)

    async def optimize_caches(self):
        timing_id = performance_monitor.start_timing("cache_optimization")

        try:
            api_optimizer = get_api_optimizer()
            if api_optimizer:
                stats = api_optimizer.get_cache_stats()

                if stats["expired_entries"] > stats["valid_entries"]:
                    api_optimizer.clear_cache()

        finally:
            performance_monitor.end_timing(timing_id)

    async def cleanup_old_data(self):
        pass

    async def check_system_health(self):
        try:
            memory_percent = psutil.virtual_memory().percent
            cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 1)

            if memory_percent > self.memory_threshold:
                print(f"[診斷] 記憶體使用率過高: {memory_percent}%")
                await self.perform_emergency_cleanup()

            if cpu_percent > self.cpu_threshold:
                print(f"[診斷] CPU 使用率過高: {cpu_percent}%")

        except Exception as e:
            print(f"[診斷] 健康檢查錯誤: {e}")

    async def perform_emergency_cleanup(self):
        timing_id = performance_monitor.start_timing("emergency_cleanup")

        try:
            gc.collect()

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                api_optimizer.clear_cache("channel_")
                api_optimizer.clear_cache("user_")
                api_optimizer.clear_cache("guild_")

            for task in asyncio.all_tasks():
                if task.done() and not task.cancelled():
                    try:
                        task.exception()
                    except (asyncio.CancelledError, asyncio.InvalidStateError):
                        pass

        finally:
            performance_monitor.end_timing(timing_id)

    async def collect_performance_metrics(self):
        api_optimizer = get_api_optimizer()
        if api_optimizer:
            api_optimizer.get_cache_stats()


async def setup(bot: commands.Bot):
    from src.utils.api_optimizer import init_api_optimizer

    init_api_optimizer(bot)
    await bot.add_cog(SystemMaintenance(bot))
