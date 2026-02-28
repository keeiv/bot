from datetime import datetime
from datetime import timezone

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
            print(f"[效能監控] 收集指標時發生錯誤: {e}")

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

    @app_commands.command(name="performance-dashboard", description="綜合效能監控面板")
    @app_commands.checks.has_permissions(administrator=True)
    async def performance_dashboard(self, interaction: discord.Interaction):
        """效能監控面板"""
        await interaction.response.defer(ephemeral=True)

        try:
            db_manager = get_database_manager()
            config_manager = get_config_manager()
            network_optimizer = get_network_optimizer()
            api_optimizer = get_api_optimizer()

            embed = discord.Embed(
                title="[效能] 效能監控面板",
                color=discord.Color.from_rgb(52, 152, 219),
                timestamp=datetime.now(timezone.utc),
            )

            # 資料庫快取統計
            if db_manager:
                cache_stats = await db_manager.get_cache_stats()
                embed.add_field(
                    name="[資料庫快取]",
                    value=f"總計: {cache_stats['total_entries']}\n有效: {cache_stats['valid_entries']}\n過期: {cache_stats['expired_entries']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="[資料庫快取]", value="尚未初始化", inline=True
                )

            # 設定快取統計
            if config_manager:
                config_stats = config_manager.get_cache_stats()
                embed.add_field(
                    name="[設定快取]",
                    value=f"大小: {config_stats['cache_size']}\n檔案鎖: {config_stats['file_locks']}\n監聽器: {config_stats['active_watchers']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="[設定快取]", value="尚未初始化", inline=True
                )

            # 網路統計
            if network_optimizer:
                network_stats = network_optimizer.get_network_stats()
                active_requests = sum(network_stats.get("active_requests", {}).values())
                embed.add_field(
                    name="[網路]",
                    value=f"活躍請求: {active_requests}\nDNS 快取: {network_stats.get('dns_cache_size', 0)}",
                    inline=True,
                )
            else:
                embed.add_field(name="[網路]", value="尚未初始化", inline=True)

            # API 優化統計
            if api_optimizer:
                api_cache_stats = api_optimizer.get_cache_stats()
                embed.add_field(
                    name="[API 優化]",
                    value=f"快取: {api_cache_stats['total_entries']}\n有效: {api_cache_stats['valid_entries']}",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="[API 優化]", value="尚未初始化", inline=True
                )

            # 近期效能指標
            if db_manager:
                recent_metrics = await db_manager.get_metrics(limit=10)
                if recent_metrics:
                    performance_summary = {}
                    for metric in recent_metrics:
                        metric_name = metric["metric_name"]
                        if metric_name not in performance_summary:
                            performance_summary[metric_name] = []
                        performance_summary[metric_name].append(metric["value"])

                    summary_text = []
                    for metric_name, values in list(performance_summary.items())[:5]:
                        avg_val = sum(values) / len(values)
                        summary_text.append(f"{metric_name}: {avg_val:.2f}")

                    embed.add_field(
                        name="[近期指標]",
                        value="\n".join(summary_text),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 無法產生效能面板: {e}")

    @app_commands.command(name="network-diagnostics", description="網路連線診斷")
    @app_commands.checks.has_permissions(administrator=True)
    async def network_diagnostics(self, interaction: discord.Interaction):
        """網路連線診斷"""
        await interaction.response.defer(ephemeral=True)

        try:
            network_optimizer = get_network_optimizer()
            diagnostics = NetworkDiagnostics(network_optimizer)

            await interaction.followup.send("正在執行網路診斷...")

            results = await diagnostics.run_full_diagnostics()

            embed = discord.Embed(
                title="[診斷] 網路連線診斷",
                color=discord.Color.from_rgb(241, 196, 15),
            )

            # 連線測試結果
            connectivity = results.get("connectivity_test", {})
            success_count = sum(
                1
                for result in connectivity.values()
                if result.get("status") == "success"
            )
            total_count = len(connectivity)

            embed.add_field(
                name="[連線測試]",
                value=f"成功: {success_count}/{total_count}",
                inline=True,
            )

            # DNS 解析
            dns_results = results.get("dns_resolution", {})
            dns_text = []
            for host, info in dns_results.items():
                dns_text.append(f"{host}: {info['count']} 個 IP")

            embed.add_field(
                name="[DNS 解析]",
                value="\n".join(dns_text) if dns_text else "無資料",
                inline=True,
            )

            # 連線優化
            conn_results = results.get("connection_optimization", {})
            conn_text = []
            for host, info in conn_results.items():
                if info.get("status") == "success":
                    conn_text.append(f"{host}: {info.get('connect_time', 0):.3f}s")
                else:
                    conn_text.append(f"{host}: 失敗")

            embed.add_field(
                name="[連線優化]",
                value="\n".join(conn_text) if conn_text else "無資料",
                inline=True,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 網路診斷失敗: {e}")

    @app_commands.command(name="cache-management", description="快取管理工具")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="管理動作", target="目標快取")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="清理資料庫快取", value="clear_db"),
            app_commands.Choice(name="清理設定快取", value="clear_config"),
            app_commands.Choice(name="清理網路快取", value="clear_network"),
            app_commands.Choice(name="清理所有快取", value="clear_all"),
            app_commands.Choice(name="查看快取統計", value="stats"),
        ]
    )
    async def cache_management(
        self, interaction: discord.Interaction, action: str, target: str = None
    ):
        """快取管理工具"""
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
                    results.append(f"[成功] 已清理資料庫快取: {count} 筆")
                else:
                    count = await db_manager.cleanup_expired_cache()
                    results.append(f"[成功] 已清理過期資料庫快取: {count} 筆")

            elif action == "clear_config":
                if target:
                    config_manager._cache.clear(target)
                    results.append(f"[成功] 已清理設定快取: {target}")
                else:
                    config_manager._cache.clear()
                    results.append("[成功] 已清理所有設定快取")

            elif action == "clear_network":
                if target:
                    network_optimizer.dns_cache.clear(target)
                    results.append(f"[成功] 已清理網路 DNS 快取: {target}")
                else:
                    network_optimizer.clear_caches()
                    results.append("[成功] 已清理所有網路快取")

            elif action == "clear_all":
                await db_manager.cleanup_expired_cache()
                config_manager._cache.clear()
                network_optimizer.clear_caches()
                if api_optimizer:
                    api_optimizer.clear_cache()
                results.append("[成功] 已清理所有快取")

            elif action == "stats":
                db_stats = await db_manager.get_cache_stats()
                config_stats = config_manager.get_cache_stats()
                network_stats = network_optimizer.get_network_stats()

                embed = discord.Embed(
                    title="[快取] 快取統計",
                    color=discord.Color.from_rgb(46, 204, 113),
                )

                embed.add_field(
                    name="[資料庫快取]",
                    value=f"總計: {db_stats['total_entries']}\n有效: {db_stats['valid_entries']}",
                    inline=True,
                )

                embed.add_field(
                    name="[設定快取]",
                    value=f"大小: {config_stats['cache_size']}\n檔案鎖: {config_stats['file_locks']}",
                    inline=True,
                )

                embed.add_field(
                    name="[網路快取]",
                    value=f"DNS: {network_stats.get('dns_cache_size', 0)}\n活躍請求: {sum(network_stats.get('active_requests', {}).values())}",
                    inline=True,
                )

                await interaction.followup.send(embed=embed)
                return

            if results:
                await interaction.followup.send("\n".join(results))

        except Exception as e:
            await interaction.followup.send(f"[失敗] 快取管理失敗: {e}")

    @app_commands.command(name="performance-history", description="效能歷史數據")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(metric_name="指標名稱", hours="時間範圍 (小時)")
    async def performance_history(
        self, interaction: discord.Interaction, metric_name: str = None, hours: int = 24
    ):
        """效能歷史數據"""
        await interaction.response.defer(ephemeral=True)

        try:
            db_manager = get_database_manager()

            if metric_name:
                metrics = await db_manager.get_metrics(metric_name, limit=100)
            else:
                metrics = await db_manager.get_metrics(limit=200)

            if not metrics:
                await interaction.followup.send("[提示] 目前沒有效能數據")
                return

            # 依名稱分組指標
            grouped_metrics = {}
            for metric in metrics:
                m_name = metric["metric_name"]
                if m_name not in grouped_metrics:
                    grouped_metrics[m_name] = []
                grouped_metrics[m_name].append(metric)

            embed = discord.Embed(
                title=f"[效能] 歷史數據 ({hours}h)",
                color=discord.Color.from_rgb(155, 89, 182),
            )

            for m_name, data in list(grouped_metrics.items())[:10]:
                values = [d["value"] for d in data]
                avg_val = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)

                embed.add_field(
                    name=m_name,
                    value=f"平均: {avg_val:.2f}\n最小: {min_val:.2f}\n最大: {max_val:.2f}\n筆數: {len(values)}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"[失敗] 無法取得效能歷史: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(PerformanceMonitorCog(bot))
