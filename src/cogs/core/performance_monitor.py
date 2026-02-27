import asyncio
from datetime import datetime
from datetime import timezone
import time
from typing import Any, Dict, List

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.utils.api_optimizer import get_api_optimizer
from src.utils.config_optimizer import get_config_manager
from src.utils.database_manager import get_database_manager
from src.utils.network_optimizer import get_network_optimizer
from src.utils.network_optimizer import NetworkDiagnostics


class PerformanceMonitorCog(commands.Cog):
    """機器人效能監控 Cog"""

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
            print(f"[Performance Monitor] Error collecting metrics: {e}")

    async def collect_performance_metrics(self):
        # Database metrics
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

        # Config metrics
        config_manager = get_config_manager()
        if config_manager:
            config_stats = config_manager.get_cache_stats()

            if db_manager:
                await db_manager.store_metric(
                    "config_cache_size",
                    config_stats["cache_size"],
                    {
                        "file_locks": config_stats["file_locks"],
                        "active_watchers": config_stats["active_watchers"],
                    },
                )

        # Network metrics
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

    @app_commands.command(name="performance-dashboard", description="綜合性能監控面板")
    @app_commands.checks.has_permissions(administrator=True)
    async def performance_dashboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            db_manager = get_database_manager()
            config_manager = get_config_manager()
            network_optimizer = get_network_optimizer()
            api_optimizer = get_api_optimizer()

            embed = discord.Embed(
                title="Performance Dashboard",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )

            # Database stats
            if db_manager:
                cache_stats = await db_manager.get_cache_stats()
                embed.add_field(
                    name="📊 Database Cache",
                    value=f"Total: {cache_stats['total_entries']}\nValid: {cache_stats['valid_entries']}\nExpired: {cache_stats['expired_entries']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="📊 Database Cache", value="Not initialized", inline=True
                )

            # Config stats
            if config_manager:
                config_stats = config_manager.get_cache_stats()
                embed.add_field(
                    name="⚙️ Config Cache",
                    value=f"Size: {config_stats['cache_size']}\nLocks: {config_stats['file_locks']}\nWatchers: {config_stats['active_watchers']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="⚙️ Config Cache", value="Not initialized", inline=True
                )

            # Network stats
            if network_optimizer:
                network_stats = network_optimizer.get_network_stats()
                active_requests = sum(network_stats.get("active_requests", {}).values())
                embed.add_field(
                    name="🌐 Network",
                    value=f"Active: {active_requests}\nDNS Cache: {network_stats.get('dns_cache_size', 0)}",
                    inline=True,
                )
            else:
                embed.add_field(name="🌐 Network", value="Not initialized", inline=True)

            # API optimizer stats
            if api_optimizer:
                api_cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="🚀 API Optimizer",
                    value=f"Cache: {api_cache_stats['total_entries']}\nValid: {api_cache_stats['valid_entries']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="🚀 API Optimizer", value="Not initialized", inline=True
                )

            # Recent performance metrics
            if db_manager:
                recent_metrics = await db_manager.get_metrics(limit=10)
                if recent_metrics:
                    performance_summary = {}
                    for metric in recent_metrics:
                        name = metric["metric_name"]
                        if name not in performance_summary:
                            performance_summary[name] = []
                        performance_summary[name].append(metric["value"])

                    summary_text = []
                    for name, values in list(performance_summary.items())[:5]:
                        avg_val = sum(values) / len(values)
                        summary_text.append(f"{name}: {avg_val:.2f}")

                    embed.add_field(
                        name="📈 Recent Metrics",
                        value="\n".join(summary_text),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error generating dashboard: {e}")

    @app_commands.command(name="network-diagnostics", description="網絡連接診斷")
    @app_commands.checks.has_permissions(administrator=True)
    async def network_diagnostics(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            network_optimizer = get_network_optimizer()
            diagnostics = NetworkDiagnostics(network_optimizer)

            await interaction.followup.send("Running network diagnostics...")

            results = await diagnostics.run_full_diagnostics()

            embed = discord.Embed(
                title="Network Diagnostics", color=discord.Color.orange()
            )

            # Connectivity test results
            connectivity = results.get("connectivity_test", {})
            success_count = sum(
                1
                for result in connectivity.values()
                if result.get("status") == "success"
            )
            total_count = len(connectivity)

            embed.add_field(
                name="🌐 Connectivity Test",
                value=f"Success: {success_count}/{total_count}",
                inline=True,
            )

            # DNS resolution
            dns_results = results.get("dns_resolution", {})
            dns_text = []
            for host, info in dns_results.items():
                dns_text.append(f"{host}: {info['count']} IPs")

            embed.add_field(
                name="🔍 DNS Resolution", value="\n".join(dns_text), inline=True
            )

            # Connection optimization
            conn_results = results.get("connection_optimization", {})
            conn_text = []
            for host, info in conn_results.items():
                if info.get("status") == "success":
                    conn_text.append(f"{host}: {info.get('connect_time', 0):.3f}s")
                else:
                    conn_text.append(f"{host}: Failed")

            embed.add_field(
                name="⚡ Connection Optimization",
                value="\n".join(conn_text),
                inline=True,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Network diagnostics failed: {e}")

    @app_commands.command(name="cache-management", description="快取管理工具")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="管理動作", target="目標快取")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="清理數據庫快取", value="clear_db"),
            app_commands.Choice(name="清理配置快取", value="clear_config"),
            app_commands.Choice(name="清理網絡快取", value="clear_network"),
            app_commands.Choice(name="清理所有快取", value="clear_all"),
            app_commands.Choice(name="查看快取統計", value="stats"),
        ]
    )
    async def cache_management(
        self, interaction: discord.Interaction, action: str, target: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            db_manager = get_database_manager()
            config_manager = get_config_manager()
            network_optimizer = get_network_optimizer()
            api_optimizer = get_api_optimizer()

            results = []

            if action == "clear_db":
                if target:
                    count = await db_manager.cache_clear_pattern(target)
                    results.append(f"Database cache cleared: {count} entries")
                else:
                    count = await db_manager.cleanup_expired_cache()
                    results.append(f"Database expired cache cleared: {count} entries")

            elif action == "clear_config":
                if target:
                    config_manager._cache.clear(target)
                    results.append(f"Config cache cleared for pattern: {target}")
                else:
                    config_manager._cache.clear()
                    results.append("All config cache cleared")

            elif action == "clear_network":
                if target:
                    network_optimizer.dns_cache.clear(target)
                    results.append(f"Network DNS cache cleared for: {target}")
                else:
                    network_optimizer.clear_caches()
                    results.append("All network caches cleared")

            elif action == "clear_all":
                await db_manager.cleanup_expired_cache()
                config_manager._cache.clear()
                network_optimizer.clear_caches()
                if api_optimizer:
                    api_optimizer.clear_cache()
                results.append("All caches cleared")

            elif action == "stats":
                db_stats = await db_manager.get_cache_stats()
                config_stats = config_manager.get_cache_stats()
                network_stats = network_optimizer.get_network_stats()

                embed = discord.Embed(
                    title="Cache Statistics", color=discord.Color.green()
                )

                embed.add_field(
                    name="Database Cache",
                    value=f"Total: {db_stats['total_entries']}\nValid: {db_stats['valid_entries']}",
                    inline=True,
                )

                embed.add_field(
                    name="Config Cache",
                    value=f"Size: {config_stats['cache_size']}\nLocks: {config_stats['file_locks']}",
                    inline=True,
                )

                embed.add_field(
                    name="Network Cache",
                    value=f"DNS: {network_stats.get('dns_cache_size', 0)}\nActive Requests: {sum(network_stats.get('active_requests', {}).values())}",
                    inline=True,
                )

                await interaction.followup.send(embed=embed)
                return

            if results:
                await interaction.followup.send("\n".join(results))

        except Exception as e:
            await interaction.followup.send(f"Cache management failed: {e}")

    @app_commands.command(name="performance-history", description="性能歷史數據")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(metric_name="指標名稱", hours="時間範圍（小時）")
    async def performance_history(
        self, interaction: discord.Interaction, metric_name: str = None, hours: int = 24
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            db_manager = get_database_manager()

            if metric_name:
                metrics = await db_manager.get_metrics(metric_name, limit=100)
            else:
                metrics = await db_manager.get_metrics(limit=200)

            if not metrics:
                await interaction.followup.send("No performance data available")
                return

            # Group metrics by name
            grouped_metrics = {}
            for metric in metrics:
                name = metric["metric_name"]
                if name not in grouped_metrics:
                    grouped_metrics[name] = []
                grouped_metrics[name].append(metric)

            embed = discord.Embed(
                title=f"Performance History ({hours}h)", color=discord.Color.purple()
            )

            for name, data in list(grouped_metrics.items())[:10]:
                values = [d["value"] for d in data]
                avg_val = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)

                embed.add_field(
                    name=name,
                    value=f"Avg: {avg_val:.2f}\nMin: {min_val:.2f}\nMax: {max_val:.2f}\nCount: {len(values)}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Failed to get performance history: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(PerformanceMonitorCog(bot))
