from datetime import datetime
from typing import Any

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.services.report_service import ReportService
from src.utils.config_manager import get_guild_report_channel
from src.utils.config_manager import set_guild_report_channel
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedModal
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage
from src.utils.time_utils import TZ_OFFSET

_service = ReportService()


# ========== 禁言表單 ==========
class MuteModal(LocalizedModal, title="Mute member"):
    """禁言表單 - 填寫天/時/分/原因"""

    i18n = {
        "title": "report.mute_member",
        "days.label": "report.days",
        "hours.label": "report.hours",
        "minutes.label": "report.minutes",
        "reason.label": "blacklist.reason",
        "reason.placeholder": "report.enter_a_reason_for_the_mute",
    }

    days = ui.TextInput[Any](
        label="Days",
        placeholder="0",
        default="0",
        max_length=3,
        required=False,
    )

    hours = ui.TextInput[Any](
        label="Hours",
        placeholder="0",
        default="0",
        max_length=3,
        required=False,
    )

    minutes = ui.TextInput[Any](
        label="Minutes",
        placeholder="60",
        default="60",
        max_length=4,
        required=False,
    )

    reason = ui.TextInput[Any](
        label="Reason",
        placeholder="Enter a reason for the mute…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(
        self, target: discord.Member, reported_message: discord.Message
    ) -> None:
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """執行禁言"""
        try:
            d = int(self.days.value or "0")
            h = int(self.hours.value or "0")
            m = int(self.minutes.value or "0")
        except ValueError:
            await interaction.response.send_message(
                tx("report.failed_invalid_time_format_enter_numbers"), ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)
        success, error_msg = await _service.execute_mute(
            self.target, interaction.user, d, h, m, self.reason.value
        )
        if not success:
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        embed = _service.build_mute_embed(
            self.target, interaction.user, d, h, m, self.reason.value
        )
        await interaction.followup.send(embed=embed)


# ========== Ban 表單 ==========
class BanModal(LocalizedModal, title="Ban member"):
    """封禁表單 - 暫時封禁/刪除訊息天數/原因"""

    i18n = {
        "title": "report.ban_member",
        "temp_ban.label": "report.temporary_ban_enter_yes_leave_blank",
        "temp_ban.placeholder": "report.blank_permanent_ban",
        "temp_duration.label": "report.temporary_ban_duration_in_seconds",
        "temp_duration.placeholder": "report.example_86400_1_day_3600_1",
        "delete_days.label": "report.delete_messages_from_the_past_0",
        "reason.label": "blacklist.reason",
        "reason.placeholder": "report.enter_a_reason_for_the_ban",
    }

    temp_ban = ui.TextInput[Any](
        label="Temporary ban? Enter yes; leave blank for permanent",
        placeholder="Blank = permanent ban",
        max_length=10,
        required=False,
    )

    temp_duration = ui.TextInput[Any](
        label="Temporary ban duration in seconds",
        placeholder="Example: 86400 (1 day) / 3600 (1 hour)",
        max_length=10,
        required=False,
    )

    delete_days = ui.TextInput[Any](
        label="Delete messages from the past 0–7 days",
        placeholder="0",
        default="0",
        max_length=1,
        required=False,
    )

    reason = ui.TextInput[Any](
        label="Reason",
        placeholder="Enter a reason for the ban…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(
        self, target: discord.Member, reported_message: discord.Message
    ) -> None:
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """執行封禁"""
        reason_text = self.reason.value
        is_temp = self.temp_ban.value.strip().casefold() in {"是", "yes", "true", "1"}

        try:
            del_days = int(self.delete_days.value or "0")
            del_days = max(0, min(7, del_days))
        except ValueError:
            del_days = 0

        await interaction.response.defer(thinking=True)
        success, error_msg = await _service.execute_ban(
            self.target, interaction.user, reason_text, del_days
        )
        if not success:
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        try:
            temp_seconds = int(self.temp_duration.value or "0") if is_temp else 0
        except ValueError:
            temp_seconds = 0

        embed = _service.build_ban_embed(
            self.target, interaction.user, reason_text, is_temp, del_days, temp_seconds
        )
        await interaction.followup.send(embed=embed)


# ========== 警告表單 ==========
class WarnModal(LocalizedModal, title="Warn member"):
    """警告表單 - 警告次數/原因"""

    i18n = {
        "title": "report.warn_member",
        "warn_count.label": "report.warning_count",
        "reason.label": "blacklist.reason",
        "reason.placeholder": "report.enter_a_reason_for_the_warning",
    }

    warn_count = ui.TextInput[Any](
        label="Warning count",
        placeholder="1",
        default="1",
        max_length=2,
        required=True,
    )

    reason = ui.TextInput[Any](
        label="Reason",
        placeholder="Enter a reason for the warning…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(
        self, target: discord.Member, reported_message: discord.Message
    ) -> None:
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """執行警告"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        try:
            count = max(1, int(self.warn_count.value or "1"))
        except ValueError:
            count = 1

        reason_text = self.reason.value
        await interaction.response.defer(thinking=True)
        target, error = await _service.authorize(
            self.target, interaction.user, "moderate_members"
        )
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        dm_sent = await _service.execute_warn(
            target, interaction.guild.name, count, reason_text
        )
        embed = _service.build_warn_result_embed(
            self.target, interaction.user, count, reason_text, dm_sent
        )
        await interaction.followup.send(embed=embed)


# ========== 舉報處理面板 (按鈕) ==========
class ReportActionView(LocalizedView):
    """舉報處理面板 - 禁言/封禁/警告 按鈕"""

    i18n = {
        "mute_button.label": "report.mute",
        "ban_button.label": "report.ban",
        "warn_button.label": "report.warn",
    }

    def __init__(
        self, target: discord.Member, reported_message: discord.Message
    ) -> None:
        super().__init__(timeout=None)
        self.target = target
        self.reported_message = reported_message

    async def _check_permissions(
        self, interaction: discord.Interaction, permission="moderate_members"
    ) -> bool:
        """檢查操作者權限"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return False
        error = ReportService.permission_error(
            self.target, interaction.user, permission
        )
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return False
        return True

    @ui.button(label="Mute", style=discord.ButtonStyle.primary, emoji=None)
    @localized("interaction")
    async def mute_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """開啟禁言表單"""
        if not await self._check_permissions(interaction):
            return
        modal = MuteModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)

    @ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji=None)
    @localized("interaction")
    async def ban_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """開啟封禁表單"""
        if not await self._check_permissions(interaction, "ban_members"):
            return
        modal = BanModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)

    @ui.button(label="Warn", style=discord.ButtonStyle.secondary, emoji=None)
    @localized("interaction")
    async def warn_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """開啟警告表單"""
        if not await self._check_permissions(interaction):
            return
        modal = WarnModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)


# ========== Report Cog ==========
class Report(commands.Cog):
    """右鍵選單舉報系統"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # 註冊右鍵選單
        self.report_ctx_menu = app_commands.ContextMenu(
            name="Report message",
            callback=self.report_message,
        )
        self.bot.tree.add_command(self.report_ctx_menu)

    async def cog_unload(self) -> None:
        """卸載 cog 時移除右鍵選單"""
        self.bot.tree.remove_command(
            self.report_ctx_menu.name, type=self.report_ctx_menu.type
        )

    @localized("interaction")
    async def report_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """右鍵選單 - 舉報訊息"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.guild:
            await interaction.response.send_message(
                tx("report.failed_this_feature_is_only_available"), ephemeral=True
            )
            return

        # 不能舉報自己
        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                tx("report.failed_reporting_one_s_own_messages"), ephemeral=True
            )
            return

        # 不能舉報機器人
        if message.author.bot:
            await interaction.response.send_message(
                tx("report.failed_bot_messages_cannot_be_reported"), ephemeral=True
            )
            return

        # 取得舉報頻道
        report_channel_id = await run_storage(
            get_guild_report_channel, interaction.guild.id
        )
        if not report_channel_id:
            await interaction.response.send_message(
                tx("report.failed_no_report_channel_is_configured"),
                ephemeral=True,
            )
            return

        report_channel = interaction.guild.get_channel(report_channel_id)
        if not isinstance(
            report_channel,
            (
                discord.TextChannel,
                discord.Thread,
                discord.VoiceChannel,
                discord.StageChannel,
            ),
        ):
            await interaction.response.send_message(
                tx("report.failed_the_report_channel_does_not"),
                ephemeral=True,
            )
            return

        # 截斷過長內容
        content = message.content or tx("report.no_text_content")
        if len(content) > 1024:
            content = content[:1021] + "..."

        # 建立舉報 Embed
        embed = discord.Embed(
            title=tx("report.report_new_message_report"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("report.reported_user"),
            value=f"{message.author.mention} ({message.author.id})",
            inline=True,
        )
        embed.add_field(
            name=tx("report.reported_by"),
            value=f"{interaction.user.mention} ({interaction.user.id})",
            inline=True,
        )
        embed.add_field(
            name=tx("audit_log.channel"),
            value=f"{message.channel.mention}",
            inline=True,
        )
        embed.add_field(
            name=tx("report.message_content"),
            value=content,
            inline=False,
        )
        embed.add_field(
            name=tx("report.message_link"),
            value=tx("report.open_message", v0=(message.jump_url)),
            inline=False,
        )

        # 如果有附件
        if message.attachments:
            attachment_list = "\n".join(
                f"[{att.filename}]({att.url})" for att in message.attachments[:5]
            )
            embed.add_field(
                name=tx("report.attachments"),
                value=attachment_list,
                inline=False,
            )

        embed.set_footer(
            text=tx(
                "report.message_id_server", v0=(message.id), v1=(interaction.guild.name)
            )
        )

        await interaction.response.defer(ephemeral=True)
        # 取得被舉報者的 Member 物件
        target_member = interaction.guild.get_member(message.author.id)
        if not target_member:
            try:
                target_member = await interaction.guild.fetch_member(message.author.id)
            except discord.NotFound:
                target_member = None

        if target_member:
            view = ReportActionView(target_member, message)
            await report_channel.send(embed=embed, view=view)
        else:
            embed.add_field(
                name=tx("report.notice"),
                value=tx("report.the_reported_user_has_left_the"),
                inline=False,
            )
            await report_channel.send(embed=embed)

        # 回覆舉報者
        await interaction.followup.send(
            tx("report.success_report_submitted_for_moderator_review"), ephemeral=True
        )

    # ========== 設定舉報頻道指令 ==========
    report_group = app_commands.Group(
        name="report_channel", description="Report settings"
    )

    @report_group.command(
        name="set", description="Set the channel that receives reports"
    )
    @app_commands.describe(channel="The channel for reports")
    @app_commands.checks.has_permissions(manage_guild=True)
    @localized("interaction")
    async def report_channel_set(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        """設定舉報頻道"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await run_storage(set_guild_report_channel, interaction.guild.id, channel.id)

        embed = discord.Embed(
            title=tx("report.success_report_channel_saved"),
            description=tx("report.reports_will_be_sent_to", v0=(channel.mention)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @report_group.command(name="status", description="Show the report channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    @localized("interaction")
    async def report_channel_status(self, interaction: discord.Interaction) -> None:
        """查看舉報頻道設定"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        channel_id = await run_storage(get_guild_report_channel, interaction.guild.id)
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.Thread,
                    discord.VoiceChannel,
                    discord.StageChannel,
                ),
            ):
                desc = tx("report.current_report_channel", v0=(channel.mention))
            else:
                desc = tx("report.the_configured_channel_no_longer_exists")
        else:
            desc = tx("report.no_report_channel_is_configured_use")

        embed = discord.Embed(
            title=tx("report.reports_channel_settings"),
            description=desc,
            color=discord.Color.from_rgb(52, 152, 219),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """載入 Report cog"""
    await bot.add_cog(Report(bot))
