from datetime import datetime
import traceback
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from src.config.constants import ERROR_LOG_CHANNEL_ID
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.time_utils import TZ_OFFSET


class ErrorHandler(commands.Cog):
    """全域錯誤集中處理"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 註冊 app command error handler
        self._previous_error_handler = self.bot.tree.on_error
        self.bot.tree.on_error = self.on_app_command_error  # type: ignore[method-assign]  # supported Discord handler hook

    async def cog_unload(self) -> None:
        """卸載時恢復預設 handler"""
        self.bot.tree.on_error = self._previous_error_handler  # type: ignore[method-assign]  # restore bound handler

    # ==================== Slash Command 錯誤 ====================

    @localized("interaction")
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """所有 Slash Command 錯誤的集中處理"""
        error = getattr(error, "original", error)

        # 權限不足
        if isinstance(error, app_commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await self._respond(
                interaction,
                tx("error_handler.failed_missing_permissions", v0=(missing)),
            )
            return

        # Bot 權限不足
        if isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await self._respond(
                interaction,
                tx("error_handler.failed_the_bot_is_missing_permissions", v0=(missing)),
            )
            return

        # 冷卻中
        if isinstance(error, app_commands.CommandOnCooldown):
            await self._respond(
                interaction,
                tx(
                    "error_handler.info_command_on_cooldown_retry_in",
                    v0=(error.retry_after),
                ),
            )
            return

        # 指令未找到 (通常不會觸發)
        if isinstance(error, app_commands.CommandNotFound):
            return

        # 檢查失敗 (interaction_check 回傳 False)
        if isinstance(error, app_commands.CheckFailure):
            await self._respond(
                interaction,
                tx("error_handler.failed_permission_to_use_this_command"),
            )
            return

        # 參數轉換錯誤
        if isinstance(error, app_commands.TransformerError):
            await self._respond(
                interaction,
                tx("error_handler.failed_invalid_argument_format", v0=(error)),
            )
            return

        # 未預期的錯誤 — 記錄完整堆疊
        await self._handle_unexpected(interaction, error)

    # ==================== Prefix Command 錯誤 ====================

    @commands.Cog.listener()
    @localized("ctx")
    async def on_command_error(
        self, ctx: commands.Context[Any], error: commands.CommandError
    ) -> None:
        """所有前綴指令錯誤的集中處理"""
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.send(tx("error_handler.failed_missing_permissions", v0=(missing)))
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.send(
                tx("error_handler.failed_the_bot_is_missing_permissions", v0=(missing))
            )
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                tx(
                    "error_handler.failed_required_argument_missing",
                    v0=(error.param.name),
                )
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(
                tx("error_handler.failed_invalid_argument_format", v0=(error))
            )
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                tx(
                    "error_handler.info_command_on_cooldown_retry_in",
                    v0=(error.retry_after),
                )
            )
            return

        if isinstance(error, commands.CheckFailure):
            return

        # 未預期的錯誤
        await self._handle_unexpected_prefix(ctx, error)

    # ==================== 內部輔助方法 ====================

    async def _respond(self, interaction: discord.Interaction, message: str) -> None:
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
    ) -> None:
        """處理未預期的 Slash Command 錯誤"""
        # 回覆使用者
        await self._respond(
            interaction,
            tx("error_handler.error_an_unexpected_error_occurred_the"),
        )

        # 格式化堆疊
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        cmd_name = (
            interaction.command.name if interaction.command else tx("audit_log.unknown")
        )

        # 記錄到日誌頻道
        await self._log_error(
            guild=interaction.guild,
            user=interaction.user,
            command_name=cmd_name,
            error=error,
            traceback_str=tb,
        )

    async def _handle_unexpected_prefix(
        self, ctx: commands.Context[Any], error: Exception
    ) -> None:
        """處理未預期的 Prefix Command 錯誤"""
        await ctx.send(tx("error_handler.error_an_unexpected_error_occurred_the"))

        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        cmd_name = ctx.command.name if ctx.command else tx("audit_log.unknown")

        await self._log_error(
            guild=ctx.guild,
            user=ctx.author,
            command_name=cmd_name,
            error=error,
            traceback_str=tb,
        )

    async def _log_error(
        self,
        guild: discord.Guild | None,
        user: discord.User | discord.Member,
        command_name: str,
        error: Exception,
        traceback_str: str,
    ) -> None:
        """將錯誤記錄到日誌頻道 + 開發者私訊"""
        embed = discord.Embed(
            title=tx("error_handler.error_unexpected_command_error"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("error_handler.command"), value=f"`/{command_name}`", inline=True
        )
        embed.add_field(
            name=tx("error_handler.user"),
            value=f"{user} ({user.id})",
            inline=True,
        )
        if guild:
            embed.add_field(
                name=tx("bot_appearance.server"),
                value=f"{guild.name} ({guild.id})",
                inline=False,
            )

        # 堆疊截斷到 1024
        short_tb = traceback_str[-1000:] if len(traceback_str) > 1000 else traceback_str
        embed.add_field(
            name=tx("error_handler.error"), value=f"```\n{short_tb}\n```", inline=False
        )

        # 發送到指定錯誤日誌頻道
        try:
            channel = self.bot.get_channel(ERROR_LOG_CHANNEL_ID)
            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.Thread,
                    discord.VoiceChannel,
                    discord.StageChannel,
                ),
            ):
                await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # 終端輸出
        print(f"[Error] /{command_name} by {user}: {error}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
