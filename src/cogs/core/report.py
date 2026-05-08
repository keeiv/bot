from datetime import datetime

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.services.report_service import ReportService
from src.utils.config_manager import get_guild_report_channel
from src.utils.config_manager import set_guild_report_channel
from src.utils.time_utils import TZ_OFFSET

_service = ReportService()


# ========== 禁言表單 ==========
class MuteModal(ui.Modal, title="禁言處理"):
    """禁言表單 - 填寫天/時/分/原因"""

    days = ui.TextInput(
        label="天數",
        placeholder="0",
        default="0",
        max_length=3,
        required=False,
    )

    hours = ui.TextInput(
        label="小時",
        placeholder="0",
        default="0",
        max_length=3,
        required=False,
    )

    minutes = ui.TextInput(
        label="分鐘",
        placeholder="60",
        default="60",
        max_length=4,
        required=False,
    )

    reason = ui.TextInput(
        label="原因",
        placeholder="請輸入禁言原因...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, target: discord.Member, reported_message: discord.Message):
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    async def on_submit(self, interaction: discord.Interaction):
        """執行禁言"""
        try:
            d = int(self.days.value or "0")
            h = int(self.hours.value or "0")
            m = int(self.minutes.value or "0")
        except ValueError:
            await interaction.response.send_message(
                "[失敗] 時間格式錯誤，請輸入數字", ephemeral=True
            )
            return

        success, error_msg = await _service.execute_mute(
            self.target, interaction.user, d, h, m, self.reason.value
        )
        if not success:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        embed = _service.build_mute_embed(
            self.target, interaction.user, d, h, m, self.reason.value
        )
        await interaction.response.send_message(embed=embed)


# ========== Ban 表單 ==========
class BanModal(ui.Modal, title="封禁處理"):
    """封禁表單 - 暫時封禁/刪除訊息天數/原因"""

    temp_ban = ui.TextInput(
        label="是否暫時封禁 (輸入 '是' 或留空為永久)",
        placeholder="留空 = 永久封禁",
        max_length=10,
        required=False,
    )

    temp_duration = ui.TextInput(
        label="暫時封禁時長 (秒，僅暫時封禁時填寫)",
        placeholder="例如: 86400 (1天) / 3600 (1小時)",
        max_length=10,
        required=False,
    )

    delete_days = ui.TextInput(
        label="刪除幾天內的訊息 (0-7)",
        placeholder="0",
        default="0",
        max_length=1,
        required=False,
    )

    reason = ui.TextInput(
        label="原因",
        placeholder="請輸入封禁原因...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, target: discord.Member, reported_message: discord.Message):
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    async def on_submit(self, interaction: discord.Interaction):
        """執行封禁"""
        reason_text = self.reason.value
        is_temp = self.temp_ban.value.strip() == "是"

        try:
            del_days = int(self.delete_days.value or "0")
            del_days = max(0, min(7, del_days))
        except ValueError:
            del_days = 0

        success, error_msg = await _service.execute_ban(
            self.target, interaction.user, reason_text, del_days
        )
        if not success:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        try:
            temp_seconds = int(self.temp_duration.value or "0") if is_temp else 0
        except ValueError:
            temp_seconds = 0

        embed = _service.build_ban_embed(
            self.target, interaction.user, reason_text, is_temp, del_days, temp_seconds
        )
        await interaction.response.send_message(embed=embed)


# ========== 警告表單 ==========
class WarnModal(ui.Modal, title="警告處理"):
    """警告表單 - 警告次數/原因"""

    warn_count = ui.TextInput(
        label="警告次數",
        placeholder="1",
        default="1",
        max_length=2,
        required=True,
    )

    reason = ui.TextInput(
        label="原因",
        placeholder="請輸入警告原因...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, target: discord.Member, reported_message: discord.Message):
        super().__init__()
        self.target = target
        self.reported_message = reported_message

    async def on_submit(self, interaction: discord.Interaction):
        """執行警告"""
        try:
            count = max(1, int(self.warn_count.value or "1"))
        except ValueError:
            count = 1

        reason_text = self.reason.value
        dm_sent = await _service.execute_warn(
            self.target, interaction.guild.name, count, reason_text
        )
        embed = _service.build_warn_result_embed(
            self.target, interaction.user, count, reason_text, dm_sent
        )
        await interaction.response.send_message(embed=embed)


# ========== 舉報處理面板 (按鈕) ==========
class ReportActionView(ui.View):
    """舉報處理面板 - 禁言/封禁/警告 按鈕"""

    def __init__(self, target: discord.Member, reported_message: discord.Message):
        super().__init__(timeout=None)
        self.target = target
        self.reported_message = reported_message

    async def _check_permissions(self, interaction: discord.Interaction) -> bool:
        """檢查操作者權限"""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "[失敗] 你需要有管理成員權限才能處理舉報", ephemeral=True
            )
            return False
        return True

    @ui.button(label="禁言", style=discord.ButtonStyle.primary, emoji=None)
    async def mute_button(self, interaction: discord.Interaction, button: ui.Button):
        """開啟禁言表單"""
        if not await self._check_permissions(interaction):
            return
        modal = MuteModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)

    @ui.button(label="封禁", style=discord.ButtonStyle.danger, emoji=None)
    async def ban_button(self, interaction: discord.Interaction, button: ui.Button):
        """開啟封禁表單"""
        if not await self._check_permissions(interaction):
            return
        modal = BanModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)

    @ui.button(label="警告", style=discord.ButtonStyle.secondary, emoji=None)
    async def warn_button(self, interaction: discord.Interaction, button: ui.Button):
        """開啟警告表單"""
        if not await self._check_permissions(interaction):
            return
        modal = WarnModal(self.target, self.reported_message)
        await interaction.response.send_modal(modal)


# ========== Report Cog ==========
class Report(commands.Cog):
    """右鍵選單舉報系統"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 註冊右鍵選單
        self.report_ctx_menu = app_commands.ContextMenu(
            name="舉報訊息",
            callback=self.report_message,
        )
        self.bot.tree.add_command(self.report_ctx_menu)

    async def cog_unload(self):
        """卸載 cog 時移除右鍵選單"""
        self.bot.tree.remove_command(
            self.report_ctx_menu.name, type=self.report_ctx_menu.type
        )

    async def report_message(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """右鍵選單 - 舉報訊息"""
        if not interaction.guild:
            await interaction.response.send_message(
                "[失敗] 此功能僅限伺服器內使用", ephemeral=True
            )
            return

        # 不能舉報自己
        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                "[失敗] 你不能舉報自己的訊息", ephemeral=True
            )
            return

        # 不能舉報機器人
        if message.author.bot:
            await interaction.response.send_message(
                "[失敗] 你不能舉報機器人的訊息", ephemeral=True
            )
            return

        # 取得舉報頻道
        report_channel_id = get_guild_report_channel(interaction.guild.id)
        if not report_channel_id:
            await interaction.response.send_message(
                "[失敗] 此伺服器尚未設定舉報頻道，請管理員使用 `/report_channel set` 設定",
                ephemeral=True,
            )
            return

        report_channel = interaction.guild.get_channel(report_channel_id)
        if not report_channel:
            await interaction.response.send_message(
                "[失敗] 舉報頻道不存在或已被刪除，請管理員重新設定",
                ephemeral=True,
            )
            return

        # 截斷過長內容
        content = message.content or "(無文字內容)"
        if len(content) > 1024:
            content = content[:1021] + "..."

        # 建立舉報 Embed
        embed = discord.Embed(
            title="[舉報] 新的訊息舉報",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="被舉報者",
            value=f"{message.author.mention} ({message.author.id})",
            inline=True,
        )
        embed.add_field(
            name="舉報人",
            value=f"{interaction.user.mention} ({interaction.user.id})",
            inline=True,
        )
        embed.add_field(
            name="頻道",
            value=f"{message.channel.mention}",
            inline=True,
        )
        embed.add_field(
            name="訊息內容",
            value=content,
            inline=False,
        )
        embed.add_field(
            name="訊息連結",
            value=f"[點擊跳轉]({message.jump_url})",
            inline=False,
        )

        # 如果有附件
        if message.attachments:
            attachment_list = "\n".join(
                f"[{att.filename}]({att.url})" for att in message.attachments[:5]
            )
            embed.add_field(
                name="附件",
                value=attachment_list,
                inline=False,
            )

        embed.set_footer(
            text=f"訊息 ID: {message.id} | 伺服器: {interaction.guild.name}"
        )

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
                name="注意",
                value="被舉報的用戶已不在伺服器中，無法執行處理動作",
                inline=False,
            )
            await report_channel.send(embed=embed)

        # 回覆舉報者
        await interaction.response.send_message(
            "[成功] 你的舉報已送出，管理員將會進行審查", ephemeral=True
        )

    # ========== 設定舉報頻道指令 ==========
    report_group = app_commands.Group(
        name="report_channel", description="舉報系統設定"
    )

    @report_group.command(name="set", description="設定舉報訊息接收頻道")
    @app_commands.describe(channel="要接收舉報訊息的頻道")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def report_channel_set(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """設定舉報頻道"""
        set_guild_report_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="[成功] 舉報頻道已設定",
            description=f"舉報訊息將發送至 {channel.mention}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @report_group.command(name="status", description="查看舉報頻道設定")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def report_channel_status(self, interaction: discord.Interaction):
        """查看舉報頻道設定"""
        channel_id = get_guild_report_channel(interaction.guild.id)
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                desc = f"目前舉報頻道: {channel.mention}"
            else:
                desc = "已設定的頻道不存在，請重新設定"
        else:
            desc = "尚未設定舉報頻道，請使用 `/report_channel set` 設定"

        embed = discord.Embed(
            title="[舉報系統] 頻道設定",
            description=desc,
            color=discord.Color.from_rgb(52, 152, 219),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """載入 Report cog"""
    await bot.add_cog(Report(bot))
