from datetime import datetime
from datetime import timedelta
from datetime import timezone
import traceback

import discord
from discord import app_commands
from discord.ext import commands

TZ_OFFSET = timezone(timedelta(hours=8))
DEVELOPER_IDS = {241619561760292866, 964849855396741130}
ERROR_LOG_GUILD_ID = 1476182659054047282
ERROR_LOG_CHANNEL_ID = 1476182661352652891


class ErrorHandler(commands.Cog):
    """全域錯誤集中處理"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 註冊 app command error handler
        self.bot.tree.on_error = self.on_app_command_error

    async def cog_unload(self):
        """卸載時恢復預設 handler"""
        self.bot.tree.on_error = self.bot.tree.__class__.on_error

    # ==================== Slash Command 錯誤 ====================

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """所有 Slash Command 錯誤的集中處理"""
        error = getattr(error, "original", error)

        # 權限不足
        if isinstance(error, app_commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await self._respond(
                interaction,
                f"[失敗] 你缺少以下權限: {missing}",
            )
            return

        # Bot 權限不足
        if isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await self._respond(
                interaction,
                f"[失敗] 機器人缺少以下權限: {missing}",
            )
            return

        # 冷卻中
        if isinstance(error, app_commands.CommandOnCooldown):
            await self._respond(
                interaction,
                f"[提示] 指令冷卻中，請在 {error.retry_after:.1f} 秒後重試",
            )
            return

        # 指令未找到 (通常不會觸發)
        if isinstance(error, app_commands.CommandNotFound):
            return

        # 檢查失敗 (interaction_check 回傳 False)
        if isinstance(error, app_commands.CheckFailure):
            await self._respond(
                interaction,
                "[失敗] 您沒有使用此指令的權限",
            )
            return

        # 參數轉換錯誤
        if isinstance(error, app_commands.TransformerError):
            await self._respond(
                interaction,
                f"[失敗] 參數格式錯誤: {error}",
            )
            return

        # 未預期的錯誤 — 記錄完整堆疊
        await self._handle_unexpected(interaction, error)

    # ==================== Prefix Command 錯誤 ====================

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """所有前綴指令錯誤的集中處理"""
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.send(f"[失敗] 你缺少以下權限: {missing}")
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.send(f"[失敗] 機器人缺少以下權限: {missing}")
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"[失敗] 缺少必要參數: {error.param.name}")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(f"[失敗] 參數格式錯誤: {error}")
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"[提示] 指令冷卻中，請在 {error.retry_after:.1f} 秒後重試")
            return

        if isinstance(error, commands.CheckFailure):
            return

        # 未預期的錯誤
        await self._handle_unexpected_prefix(ctx, error)

    # ==================== 內部輔助方法 ====================

    async def _respond(self, interaction: discord.Interaction, message: str):
        """安全回覆 interaction (處理已回覆的情況)"""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except (discord.HTTPException, discord.InteractionResponded):
            pass

    async def _handle_unexpected(
        self, interaction: discord.Interaction, error: Exception
    ):
        """處理未預期的 Slash Command 錯誤"""
        # 回覆使用者
        await self._respond(
            interaction,
            "[錯誤] 發生未預期的錯誤，開發者已收到通知",
        )

        # 格式化堆疊
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        cmd_name = interaction.command.name if interaction.command else "未知"

        # 記錄到日誌頻道
        await self._log_error(
            guild=interaction.guild,
            user=interaction.user,
            command_name=cmd_name,
            error=error,
            traceback_str=tb,
        )

    async def _handle_unexpected_prefix(
        self, ctx: commands.Context, error: Exception
    ):
        """處理未預期的 Prefix Command 錯誤"""
        await ctx.send("[錯誤] 發生未預期的錯誤，開發者已收到通知")

        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        cmd_name = ctx.command.name if ctx.command else "未知"

        await self._log_error(
            guild=ctx.guild,
            user=ctx.author,
            command_name=cmd_name,
            error=error,
            traceback_str=tb,
        )

    async def _log_error(
        self,
        guild: discord.Guild,
        user: discord.User,
        command_name: str,
        error: Exception,
        traceback_str: str,
    ):
        """將錯誤記錄到日誌頻道 + 開發者私訊"""
        embed = discord.Embed(
            title="[錯誤] 未預期的指令錯誤",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="指令", value=f"`/{command_name}`", inline=True
        )
        embed.add_field(
            name="使用者",
            value=f"{user} ({user.id})",
            inline=True,
        )
        if guild:
            embed.add_field(
                name="伺服器",
                value=f"{guild.name} ({guild.id})",
                inline=False,
            )

        # 堆疊截斷到 1024
        short_tb = traceback_str[-1000:] if len(traceback_str) > 1000 else traceback_str
        embed.add_field(
            name="錯誤", value=f"```\n{short_tb}\n```", inline=False
        )

        # 發送到指定錯誤日誌頻道
        try:
            channel = self.bot.get_channel(ERROR_LOG_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # 終端輸出
        print(f"[Error] /{command_name} by {user}: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
