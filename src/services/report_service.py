"""舉報處理業務邏輯服務 (禁言 / 封禁 / 警告)"""

from datetime import datetime
from datetime import timedelta

import discord

from src.utils.time_utils import TZ_OFFSET


class ReportService:
    """舉報操作執行邏輯與 Embed 建立"""

    # ========== 禁言 ==========

    async def execute_mute(
        self,
        target: discord.Member,
        moderator: discord.User,
        days: int,
        hours: int,
        minutes: int,
        reason: str,
    ) -> tuple[bool, str]:
        """執行禁言操作。

        Returns:
            (success, error_message)  — 成功時 error_message 為空字串
        """
        if days == 0 and hours == 0 and minutes == 0:
            return False, "[失敗] 禁言時間不能為零"

        duration = timedelta(days=days, hours=hours, minutes=minutes)
        if duration.total_seconds() > 28 * 24 * 3600:
            return False, "[失敗] 禁言時間不能超過 28 天"

        try:
            await target.timeout(duration, reason=reason)
            return True, ""
        except discord.Forbidden:
            return False, "[失敗] 機器人權限不足，無法禁言此成員"
        except Exception as e:
            return False, f"[失敗] 禁言失敗: {e}"

    def build_mute_embed(
        self,
        target: discord.Member,
        moderator: discord.User,
        days: int,
        hours: int,
        minutes: int,
        reason: str,
    ) -> discord.Embed:
        """建立禁言完成 Embed"""
        parts = []
        if days:
            parts.append(f"{days} 天")
        if hours:
            parts.append(f"{hours} 小時")
        if minutes:
            parts.append(f"{minutes} 分鐘")
        time_str = " ".join(parts)

        return discord.Embed(
            title="[禁言] 舉報處理完成",
            description=(
                f"**被處理成員:** {target.mention} ({target.id})\n"
                f"**處理人:** {moderator.mention}\n"
                f"**禁言時長:** {time_str}\n"
                f"**原因:** {reason}"
            ),
            color=discord.Color.from_rgb(230, 126, 34),
            timestamp=datetime.now(TZ_OFFSET),
        )

    # ========== 封禁 ==========

    async def execute_ban(
        self,
        target: discord.Member,
        moderator: discord.User,
        reason: str,
        delete_days: int = 0,
    ) -> tuple[bool, str]:
        """執行封禁操作。

        Returns:
            (success, error_message)
        """
        try:
            await target.ban(
                reason=reason,
                delete_message_seconds=delete_days * 86400,
            )
            return True, ""
        except discord.Forbidden:
            return False, "[失敗] 機器人權限不足，無法封禁此成員"
        except Exception as e:
            return False, f"[失敗] 封禁失敗: {e}"

    def build_ban_embed(
        self,
        target: discord.Member,
        moderator: discord.User,
        reason: str,
        is_temp: bool,
        delete_days: int,
        temp_seconds: int = 0,
    ) -> discord.Embed:
        """建立封禁完成 Embed"""
        embed = discord.Embed(
            title="[封禁] 舉報處理完成",
            description=(
                f"**被處理成員:** {target.mention} ({target.id})\n"
                f"**處理人:** {moderator.mention}\n"
                f"**封禁類型:** {'暫時封禁' if is_temp else '永久封禁'}\n"
                f"**刪除訊息:** {delete_days} 天內\n"
                f"**原因:** {reason}"
            ),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        if is_temp and temp_seconds > 0:
            embed.add_field(
                name="暫時封禁時長",
                value=f"{temp_seconds} 秒 ({temp_seconds / 3600:.1f} 小時)",
                inline=False,
            )
            embed.set_footer(text="注意: 暫時封禁需手動解除或使用排程")
        return embed

    # ========== 警告 ==========

    async def execute_warn(
        self,
        target: discord.Member,
        guild_name: str,
        count: int,
        reason: str,
    ) -> bool:
        """發送警告 DM，回傳是否成功送達"""
        warn_embed = discord.Embed(
            title="[警告] 你已被警告",
            description=(
                f"**伺服器:** {guild_name}\n"
                f"**警告次數:** {count} 次\n"
                f"**原因:** {reason}"
            ),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        try:
            await target.send(embed=warn_embed)
            return True
        except Exception:
            return False

    def build_warn_result_embed(
        self,
        target: discord.Member,
        moderator: discord.User,
        count: int,
        reason: str,
        dm_sent: bool,
    ) -> discord.Embed:
        """建立警告完成 Embed"""
        return discord.Embed(
            title="[警告] 舉報處理完成",
            description=(
                f"**被處理成員:** {target.mention} ({target.id})\n"
                f"**處理人:** {moderator.mention}\n"
                f"**警告次數:** {count} 次\n"
                f"**原因:** {reason}\n"
                f"**私訊通知:** {'已送達' if dm_sent else '無法送達 (對方可能關閉私訊)'}"
            ),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
