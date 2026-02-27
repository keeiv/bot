import asyncio
from datetime import datetime
from datetime import timezone
import gc
import time
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import psutil

from src.utils.api_optimizer import connection_manager
from src.utils.api_optimizer import get_api_optimizer
from src.utils.api_optimizer import performance_monitor


class SystemMaintenance(commands.Cog):
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
            print(f"Maintenance task error: {e}")

    @tasks.loop(minutes=5)
    async def _performance_task(self):
        await self.bot.wait_until_ready()

        try:
            await self.collect_performance_metrics()
        except Exception as e:
            print(f"Performance monitoring error: {e}")

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
                print(f"High memory usage detected: {memory_percent}%")
                await self.perform_emergency_cleanup()

            if cpu_percent > self.cpu_threshold:
                print(f"High CPU usage detected: {cpu_percent}%")

            return {
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "uptime": time.time() - self.start_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            print(f"Health check error: {e}")
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
                    except:
                        pass

        finally:
            performance_monitor.end_timing(timing_id)

    async def collect_performance_metrics(self):
        api_optimizer = get_api_optimizer()
        if api_optimizer:
            stats = api_optimizer.get_cache_stats()

    @app_commands.command(name="system-status", description="系統狀態監控")
    @app_commands.checks.has_permissions(administrator=True)
    async def system_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            health = await self.check_system_health()
            if not health:
                await interaction.followup.send("Unable to retrieve system health")
                return

            embed = discord.Embed(title="System Status", color=discord.Color.blue())

            memory_color = (
                discord.Color.green()
                if health["memory_percent"] < self.memory_threshold
                else discord.Color.red()
            )
            cpu_color = (
                discord.Color.green()
                if health["cpu_percent"] < self.cpu_threshold
                else discord.Color.red()
            )

            embed.add_field(
                name="Memory Usage",
                value=f"{health['memory_percent']:.1f}%",
                inline=True,
            )
            embed.add_field(
                name="CPU Usage", value=f"{health['cpu_percent']:.1f}%", inline=True
            )

            uptime_hours = health["uptime"] / 3600
            embed.add_field(
                name="Uptime", value=f"{uptime_hours:.1f} hours", inline=True
            )

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="Cache Stats",
                    value=f"Total: {cache_stats['total_entries']}\nValid: {cache_stats['valid_entries']}",
                    inline=True,
                )

            performance_stats = performance_monitor.get_performance_stats()
            if performance_stats:
                avg_response_time = sum(
                    stats["avg"] for stats in performance_stats.values()
                ) / len(performance_stats)
                embed.add_field(
                    name="Avg Response Time",
                    value=f"{avg_response_time:.3f}s",
                    inline=True,
                )

            embed.set_footer(text=f"Checked at {health['timestamp']}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error retrieving system status: {e}")

    @app_commands.command(name="system-cleanup", description="執行系統清理")
    @app_commands.checks.has_permissions(administrator=True)
    async def system_cleanup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            timing_id = performance_monitor.start_timing("manual_cleanup")

            await self.perform_system_cleanup()
            await self.optimize_caches()

            duration = performance_monitor.end_timing(timing_id)

            embed = discord.Embed(
                title="System Cleanup Completed",
                description=f"Cleanup completed in {duration:.2f} seconds",
                color=discord.Color.green(),
            )

            api_optimizer = get_api_optimizer()
            if api_optimizer:
                cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="Cache Status",
                    value=f"Total entries: {cache_stats['total_entries']}\nValid entries: {cache_stats['valid_entries']}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Cleanup failed: {e}")

    @app_commands.command(name="performance-stats", description="性能統計數據")
    @app_commands.checks.has_permissions(administrator=True)
    async def performance_stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            stats = performance_monitor.get_performance_stats()

            if not stats:
                await interaction.followup.send("No performance data available")
                return

            embed = discord.Embed(
                title="Performance Statistics", color=discord.Color.purple()
            )

            for operation, data in stats.items():
                value = (
                    f"Count: {data['count']}\n"
                    f"Avg: {data['avg']:.3f}s\n"
                    f"Min: {data['min']:.3f}s\n"
                    f"Max: {data['max']:.3f}s\n"
                    f"Total: {data['total']:.2f}s"
                )
                embed.add_field(name=operation, value=value, inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error retrieving performance stats: {e}")

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
        if not confirm:
            await interaction.response.send_message(
                "Please set confirm=True to clear cache", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            api_optimizer = get_api_optimizer()
            if not api_optimizer:
                await interaction.followup.send("API optimizer not available")
                return

            if pattern == "all":
                api_optimizer.clear_cache()
                message = "All cache cleared"
            elif pattern in ["channel", "user", "guild"]:
                api_optimizer.clear_cache(f"{pattern}_")
                message = f"{pattern.capitalize()} cache cleared"
            else:
                await interaction.followup.send(
                    "Invalid pattern. Use: channel, user, guild, or all"
                )
                return

            performance_monitor.clear_metrics()

            embed = discord.Embed(
                title="Cache Cleared", description=message, color=discord.Color.green()
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Cache clear failed: {e}")


async def setup(bot: commands.Bot):
    from src.utils.api_optimizer import init_api_optimizer

    init_api_optimizer(bot)
    await bot.add_cog(SystemMaintenance(bot))
