import asyncio
from datetime import datetime
from datetime import timezone
import gc
import time

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import psutil

from src.utils.api_optimizer import connection_manager
from src.utils.api_optimizer import get_api_optimizer
from src.utils.api_optimizer import performance_monitor


class SystemMaintenance(commands.Cog):
    """系統維護 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.memory_threshold = 80.0
        self.cpu_threshold = 80.0
        self.cleanup_interval = 3600

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
            cpu_percent = psutil.cpu_percent(interval=1)

            if memory_percent > self.memory_threshold:
                print(f"[診斷] 記憶體使用率過高: {memory_percent}%")
                await self.perform_emergency_cleanup()

            if cpu_percent > self.cpu_threshold:
                print(f"[診斷] CPU 使用率過高: {cpu_percent}%")

            return {
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "uptime": time.time() - self.start_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            print(f"[診斷] 健康檢查錯誤: {e}")
            return None

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

    @app_commands.command(name="system-status", description="系統狀態監控")
    @app_commands.checks.has_permissions(administrator=True)
    async def system_status(self, interaction: discord.Interaction):
        """系統狀態監控"""
        await interaction.response.defer(ephemeral=True)

        try:
            health = await self.check_system_health()
            if not health:
                await interaction.followup.send("[失敗] 無法取得系統狀態")
                return

            is_healthy = (
                health["memory_percent"] < self.memory_threshold
                and health["cpu_percent"] < self.cpu_threshold
            )
            embed = discord.Embed(
                title="[系統] 系統狀態",
                color=discord.Color.from_rgb(46, 204, 113) if is_healthy
                else discord.Color.from_rgb(231, 76, 60),
            )

            embed.add_field(
                name="[記憶體使用率]",
                value=f"{health['memory_percent']:.1f}%",
                inline=True,
            )
            embed.add_field(
                name="[CPU 使用率]",
                value=f"{health['cpu_percent']:.1f}%",
                inline=True,
            )

            uptime_hours = health["uptime"] / 3600
            embed.add_field(
                name="[運行時間]",
                value=f"{uptime_hours:.1f} 小時",
                inline=True,
            )

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="[快取統計]",
                    value=f"總計: {cache_stats['total_entries']}\n有效: {cache_stats['valid_entries']}",
                    inline=True,
                )

            performance_stats = performance_monitor.get_performance_stats()
            if performance_stats:
                avg_response_time = sum(
                    stats["avg"] for stats in performance_stats.values()
                ) / len(performance_stats)
                embed.add_field(
                    name="[平均回應時間]",
                    value=f"{avg_response_time:.3f}s",
                    inline=True,
                )

            embed.set_footer(text=f"檢查時間: {health['timestamp']}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 無法取得系統狀態: {e}")

    @app_commands.command(name="system-cleanup", description="執行系統清理")
    @app_commands.checks.has_permissions(administrator=True)
    async def system_cleanup(self, interaction: discord.Interaction):
        """執行系統清理"""
        await interaction.response.defer(ephemeral=True)

        try:
            timing_id = performance_monitor.start_timing("manual_cleanup")

            await self.perform_system_cleanup()
            await self.optimize_caches()

            duration = performance_monitor.end_timing(timing_id)

            embed = discord.Embed(
                title="[成功] 系統清理完成",
                description=f"清理耗時 {duration:.2f} 秒",
                color=discord.Color.from_rgb(46, 204, 113),
            )

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="[快取狀態]",
                    value=f"總計: {cache_stats['total_entries']}\n有效: {cache_stats['valid_entries']}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 系統清理失敗: {e}")

    @app_commands.command(name="performance-stats", description="效能統計數據")
    @app_commands.checks.has_permissions(administrator=True)
    async def performance_stats(self, interaction: discord.Interaction):
        """效能統計數據"""
        await interaction.response.defer(ephemeral=True)

        try:
            stats = performance_monitor.get_performance_stats()

            if not stats:
                await interaction.followup.send("[提示] 目前沒有效能數據")
                return

            embed = discord.Embed(
                title="[效能] 效能統計",
                color=discord.Color.from_rgb(155, 89, 182),
            )

            for operation, data in stats.items():
                value = (
                    f"次數: {data['count']}\n"
                    f"平均: {data['avg']:.3f}s\n"
                    f"最小: {data['min']:.3f}s\n"
                    f"最大: {data['max']:.3f}s\n"
                    f"總計: {data['total']:.2f}s"
                )
                embed.add_field(name=operation, value=value, inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 無法取得效能統計: {e}")

    @app_commands.command(name="clear-cache", description="清理系統快取")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        pattern="清理模式 (channel/user/guild/all)", confirm="確認清理操作"
    )
    async def clear_cache(
        self,
        interaction: discord.Interaction,
        pattern: str = "all",
        confirm: bool = False,
    ):
        """清理系統快取"""
        if not confirm:
            await interaction.response.send_message(
                "[提示] 請將 confirm 設為 True 以確認清理", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            api_optimizer = get_api_optimizer()
            if not api_optimizer:
                await interaction.followup.send("[失敗] API 優化器尚未初始化")
                return

            if pattern == "all":
                api_optimizer.clear_cache()
                message = "已清理所有快取"
            elif pattern in ["channel", "user", "guild"]:
                api_optimizer.clear_cache(f"{pattern}_")
                message = f"已清理 {pattern} 快取"
            else:
                await interaction.followup.send(
                    "[失敗] 無效的模式，請使用: channel, user, guild 或 all"
                )
                return

            performance_monitor.clear_metrics()

            embed = discord.Embed(
                title="[成功] 快取已清理",
                description=message,
                color=discord.Color.from_rgb(46, 204, 113),
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 快取清理失敗: {e}")


async def setup(bot: commands.Bot):
    from src.utils.api_optimizer import init_api_optimizer

    init_api_optimizer(bot)
    await bot.add_cog(SystemMaintenance(bot))
