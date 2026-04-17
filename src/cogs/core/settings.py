from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.utils.config_manager import get_guild_log_channel
from src.utils.config_manager import get_guild_report_channel
from src.utils.config_manager import set_guild_log_channel
from src.utils.config_manager import set_guild_report_channel

TZ_OFFSET = timezone(timedelta(hours=8))

# 設定類別定義
SETTING_CATEGORIES = [
    discord.SelectOption(label="日誌頻道", value="log_channel", description="設定機器人日誌輸出頻道"),
    discord.SelectOption(label="舉報頻道", value="report_channel", description="設定舉報訊息接收頻道"),
    discord.SelectOption(label="防刷屏系統", value="anti_spam", description="查看/切換防刷屏開關"),
    discord.SelectOption(label="歡迎訊息", value="welcome", description="查看歡迎訊息設定"),
    discord.SelectOption(label="總覽", value="overview", description="查看所有設定摘要"),
]


# ==================== 設定頻道的 Select ====================


class ChannelSelectView(ui.View):
    """選擇頻道的視圖"""

    def __init__(self, setting_key: str, cog: "Settings"):
        super().__init__(timeout=120)
        self.setting_key = setting_key
        self.cog = cog

    @ui.select(
        cls=ui.ChannelSelect,
        placeholder="選擇一個文字頻道...",
        channel_types=[discord.ChannelType.text],
        min_values=1,
        max_values=1,
    )
    async def channel_select(
        self, interaction: discord.Interaction, select: ui.ChannelSelect
    ):
        """頻道選擇回調"""
        channel = select.values[0]

        if self.setting_key == "log_channel":
            set_guild_log_channel(interaction.guild_id, channel.id)
            label = "日誌頻道"
        elif self.setting_key == "report_channel":
            set_guild_report_channel(interaction.guild_id, channel.id)
            label = "舉報頻道"
        else:
            await interaction.response.send_message("[失敗] 未知設定", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"[成功] {label}已更新",
            description=f"已設定為 {channel.mention}",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

    @ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        await interaction.response.send_message("[提示] 已取消", ephemeral=True)
        self.stop()


# ==================== 防刷屏切換 ====================


class AntiSpamToggleView(ui.View):
    """防刷屏開關切換"""

    def __init__(self, guild_id: int, current_enabled: bool, cog: "Settings"):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.cog = cog
        self.current_enabled = current_enabled
        # 動態更新按鈕標籤
        if current_enabled:
            self.toggle_button.label = "關閉防刷屏"
            self.toggle_button.style = discord.ButtonStyle.danger
        else:
            self.toggle_button.label = "開啟防刷屏"
            self.toggle_button.style = discord.ButtonStyle.success

    @ui.button(label="切換", style=discord.ButtonStyle.primary)
    async def toggle_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """切換防刷屏開關"""
        anti_spam_cog = self.cog.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            await interaction.response.send_message(
                "[失敗] 防刷屏模組未載入", ephemeral=True
            )
            return

        new_state = not self.current_enabled
        anti_spam_cog.manager.update_settings(
            self.guild_id, {"enabled": new_state}
        )

        status = "開啟" if new_state else "關閉"
        embed = discord.Embed(
            title=f"[成功] 防刷屏已{status}",
            color=discord.Color.from_rgb(46, 204, 113) if new_state else discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

    @ui.button(label="返回", style=discord.ButtonStyle.secondary)
    async def back_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        await interaction.response.send_message("[提示] 已返回", ephemeral=True)
        self.stop()


# ==================== 主選單 ====================


class SettingsMenuView(ui.View):
    """設定儀表板主選單"""

    def __init__(self, cog: "Settings"):
        super().__init__(timeout=180)
        self.cog = cog

    @ui.select(
        placeholder="選擇要查看/修改的設定...",
        options=SETTING_CATEGORIES,
    )
    async def category_select(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """設定類別選擇"""
        value = select.values[0]
        guild_id = interaction.guild_id

        if value == "overview":
            embed = await self.cog.build_overview_embed(interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif value == "log_channel":
            current = get_guild_log_channel(guild_id)
            embed = discord.Embed(
                title="[設定] 日誌頻道",
                description=f"目前設定: {f'<#{current}>' if current else '未設定'}",
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.add_field(
                name="說明",
                value="日誌頻道用於接收訊息編輯/刪除/成員異動等事件記錄",
                inline=False,
            )
            view = ChannelSelectView("log_channel", self.cog)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "report_channel":
            current = get_guild_report_channel(guild_id)
            embed = discord.Embed(
                title="[設定] 舉報頻道",
                description=f"目前設定: {f'<#{current}>' if current else '未設定'}",
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.add_field(
                name="說明",
                value="舉報頻道用於接收成員右鍵舉報的訊息",
                inline=False,
            )
            view = ChannelSelectView("report_channel", self.cog)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "anti_spam":
            embed, view = self.cog.build_anti_spam_panel(guild_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "welcome":
            embed = self.cog.build_welcome_embed(guild_id)
            await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== Cog 主體 ====================


class Settings(commands.Cog):
    """伺服器設定儀表板"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="settings", description="伺服器設定儀表板")
    @app_commands.default_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """開啟設定儀表板"""
        await interaction.response.defer(ephemeral=True)
        embed = await self.build_overview_embed(interaction.guild)
        view = SettingsMenuView(self)
        await interaction.followup.send(embed=embed, view=view)

    # ==================== Embed 產生器 ====================

    async def build_overview_embed(self, guild: discord.Guild) -> discord.Embed:
        """產生設定總覽 Embed"""
        guild_id = guild.id

        embed = discord.Embed(
            title=f"[設定] {guild.name} 伺服器設定",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )

        # 日誌頻道
        log_ch = get_guild_log_channel(guild_id)
        log_text = f"<#{log_ch}>" if log_ch else "[未設定]"
        embed.add_field(name="日誌頻道", value=log_text, inline=True)

        # 舉報頻道
        report_ch = get_guild_report_channel(guild_id)
        report_text = f"<#{report_ch}>" if report_ch else "[未設定]"
        embed.add_field(name="舉報頻道", value=report_text, inline=True)

        # 防刷屏
        anti_spam_status = self._get_anti_spam_status(guild_id)
        embed.add_field(name="防刷屏", value=anti_spam_status, inline=True)

        # 歡迎訊息
        welcome_status = self._get_welcome_status(guild_id)
        embed.add_field(name="歡迎訊息", value=welcome_status, inline=True)

        # 倉庫追蹤
        repo_count = self._get_repo_count(guild_id)
        embed.add_field(name="倉庫追蹤", value=f"{repo_count} 個倉庫", inline=True)

        embed.set_footer(text="使用下方選單修改設定")
        return embed

    def build_anti_spam_panel(self, guild_id: int):
        """產生防刷屏設定面板"""
        anti_spam_cog = self.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            embed = discord.Embed(
                title="[設定] 防刷屏系統",
                description="[未載入] 防刷屏模組尚未啟用",
                color=discord.Color.from_rgb(231, 76, 60),
            )
            return embed, None

        settings = anti_spam_cog.manager.get_settings(guild_id)
        enabled = settings.get("enabled", True)

        embed = discord.Embed(
            title="[設定] 防刷屏系統",
            color=discord.Color.from_rgb(46, 204, 113) if enabled else discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )

        status_icon = "[啟用]" if enabled else "[停用]"
        embed.add_field(name="狀態", value=status_icon, inline=True)
        embed.add_field(
            name="洪水偵測",
            value=f"{settings.get('flood_messages', 10)} 則 / {settings.get('flood_window', 10)} 秒",
            inline=True,
        )
        embed.add_field(
            name="處罰方式", value=settings.get("flood_action", "mute"), inline=True
        )

        embed.add_field(
            name="重複偵測", value="[啟用]" if settings.get("duplicate_enabled", True) else "[停用]", inline=True
        )
        embed.add_field(
            name="提及偵測", value="[啟用]" if settings.get("mention_enabled", True) else "[停用]", inline=True
        )
        embed.add_field(
            name="連結偵測", value="[啟用]" if settings.get("link_enabled", True) else "[停用]", inline=True
        )

        embed.add_field(
            name="自動升級處罰",
            value=f"{'[啟用]' if settings.get('auto_escalate', True) else '[停用]'} ({settings.get('escalate_strikes', 3)} 次違規後升級)",
            inline=False,
        )

        white_roles = settings.get("whitelisted_roles", [])
        white_channels = settings.get("whitelisted_channels", [])
        embed.add_field(
            name="白名單",
            value=f"角色: {len(white_roles)} 個 | 頻道: {len(white_channels)} 個",
            inline=False,
        )

        embed.set_footer(text="使用 /anti_spam 指令可修改詳細參數")

        view = AntiSpamToggleView(guild_id, enabled, self)
        return embed, view

    def build_welcome_embed(self, guild_id: int) -> discord.Embed:
        """產生歡迎訊息設定面板"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return discord.Embed(
                title="[設定] 歡迎訊息",
                description="[未載入] 管理模組尚未啟用",
                color=discord.Color.from_rgb(231, 76, 60),
            )

        config = getattr(management_cog, "_config", {})
        guild_config = config.get(str(guild_id), {})
        welcome = guild_config.get("welcome", {})

        embed = discord.Embed(
            title="[設定] 歡迎訊息",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )

        if not welcome:
            embed.description = "[未設定] 尚未啟用歡迎訊息"
            embed.set_footer(text="使用 /welcome set 指令設定歡迎訊息")
            return embed

        ch_id = welcome.get("channel_id")
        embed.add_field(
            name="發送頻道",
            value=f"<#{ch_id}>" if ch_id else "[未設定]",
            inline=True,
        )
        embed.add_field(
            name="私訊通知",
            value="[啟用]" if welcome.get("send_dm") else "[停用]",
            inline=True,
        )

        msg = welcome.get("message", "")
        if msg:
            display_msg = msg[:200] + "..." if len(msg) > 200 else msg
            embed.add_field(name="訊息內容", value=display_msg, inline=False)

        auto_role = welcome.get("auto_role_id")
        if auto_role:
            embed.add_field(name="自動角色", value=f"<@&{auto_role}>", inline=True)

        embed.set_footer(text="使用 /welcome 指令修改詳細設定")
        return embed

    # ==================== 輔助方法 ====================

    def _get_anti_spam_status(self, guild_id: int) -> str:
        """取得防刷屏狀態文字"""
        anti_spam_cog = self.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            return "[未載入]"
        settings = anti_spam_cog.manager.get_settings(guild_id)
        return "[啟用]" if settings.get("enabled", True) else "[停用]"

    def _get_welcome_status(self, guild_id: int) -> str:
        """取得歡迎訊息狀態文字"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return "[未載入]"
        config = getattr(management_cog, "_config", {})
        guild_config = config.get(str(guild_id), {})
        welcome = guild_config.get("welcome", {})
        if not welcome:
            return "[未設定]"
        return "[啟用]"

    def _get_repo_count(self, guild_id: int) -> int:
        """取得倉庫追蹤數量"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return 0
        config = getattr(management_cog, "_config", {})
        guild_config = config.get(str(guild_id), {})
        return len(guild_config.get("tracked_repos", {}))


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
