from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.utils.config_manager import get_guild_log_channel
from src.utils.config_manager import get_guild_report_channel
from src.utils.config_manager import set_guild_log_channel
from src.utils.config_manager import set_guild_report_channel
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage

TZ_OFFSET = timezone(timedelta(hours=8))

# 設定類別定義
SETTING_CATEGORIES = (
    "log_channel",
    "report_channel",
    "anti_spam",
    "welcome",
    "age_guard",
    "overview",
)


def setting_options() -> list[discord.SelectOption]:
    return [
        discord.SelectOption(
            label=tx(f"settings.category.{value}"),
            value=value,
            description=tx(f"settings.category.{value}.description"),
        )
        for value in SETTING_CATEGORIES
    ]


# ==================== 設定頻道的 Select ====================


class ChannelSelectView(LocalizedView):
    """選擇頻道的視圖"""

    i18n = {
        "cancel_button.label": "settings.cancel",
        "channel_select.placeholder": "settings.channel_placeholder",
    }

    def __init__(self, setting_key: str, cog: "Settings") -> None:
        super().__init__(timeout=120)
        self.setting_key = setting_key
        self.cog = cog

    @ui.select(
        cls=ui.ChannelSelect[Any],
        placeholder="Choose a text channel…",
        channel_types=[discord.ChannelType.text],
        min_values=1,
        max_values=1,
    )
    @localized("interaction")
    async def channel_select(
        self, interaction: discord.Interaction, select: ui.ChannelSelect[Any]
    ) -> None:
        """頻道選擇回調"""
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
        channel = select.values[0]

        if self.setting_key == "log_channel":
            await run_storage(set_guild_log_channel, interaction.guild_id, channel.id)
            label = tx("settings.log_channel")
        elif self.setting_key == "report_channel":
            await run_storage(
                set_guild_report_channel, interaction.guild_id, channel.id
            )
            label = tx("settings.report_channel")
        else:
            await interaction.followup.send(
                tx("settings.failed_unknown_setting"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("bot_appearance.success_updated", v0=(label)),
            description=tx("settings.set_to", v0=(channel.mention)),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    @localized("interaction")
    async def cancel_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        await interaction.response.send_message(
            tx("settings.info_cancelled"), ephemeral=True
        )
        self.stop()


# ==================== 防刷屏切換 ====================


class AntiSpamToggleView(LocalizedView):
    """防刷屏開關切換"""

    i18n = {
        "toggle_button.label": "settings.toggle",
        "back_button.label": "settings.back",
    }

    def __init__(self, guild_id: int, current_enabled: bool, cog: "Settings") -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.cog = cog
        self.current_enabled = current_enabled
        # 動態更新按鈕標籤
        if current_enabled:
            self.toggle_button.label = tx("settings.disable_spam_protection")
            self.toggle_button.style = discord.ButtonStyle.danger
        else:
            self.toggle_button.label = tx("settings.enable_spam_protection")
            self.toggle_button.style = discord.ButtonStyle.success

    @ui.button(label="Toggle", style=discord.ButtonStyle.primary)
    @localized("interaction")
    async def toggle_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """切換防刷屏開關"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        anti_spam_cog = self.cog.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            await interaction.followup.send(
                tx("settings.failed_spam_protection_module_is_not"), ephemeral=True
            )
            return

        new_state = not self.current_enabled
        await run_storage(
            anti_spam_cog.manager.update_settings,
            self.guild_id,
            {"enabled": new_state},
        )

        status = tx("settings.enabled_0ae5c7") if new_state else tx("settings.disabled")
        embed = discord.Embed(
            title=tx("settings.success_spam_protection", v0=(status)),
            color=(
                discord.Color.from_rgb(46, 204, 113)
                if new_state
                else discord.Color.from_rgb(231, 76, 60)
            ),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    @localized("interaction")
    async def back_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        await interaction.response.send_message(
            tx("settings.info_returned"), ephemeral=True
        )
        self.stop()


# ==================== 主選單 ====================


class SettingsMenuView(LocalizedView):
    """設定儀表板主選單"""

    i18n = {"category_select.placeholder": "settings.category_placeholder"}

    def __init__(self, cog: "Settings") -> None:
        super().__init__(timeout=180)
        self.category_select.options = setting_options()
        self.cog = cog

    @ui.select(
        placeholder="Choose settings to view or change…",
        options=[
            discord.SelectOption(label=value, value=value)
            for value in SETTING_CATEGORIES
        ],
    )
    @localized("interaction")
    async def category_select(
        self, interaction: discord.Interaction, select: ui.Select[Any]
    ) -> None:
        """設定類別選擇"""
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
        value = select.values[0]
        guild_id = interaction.guild_id

        if value == "overview":
            embed = await self.cog.build_overview_embed(interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif value == "log_channel":
            current = await run_storage(get_guild_log_channel, guild_id)
            embed = discord.Embed(
                title=tx("settings.settings_log_channel"),
                description=tx(
                    "settings.current_setting",
                    v0=(
                        f"<#{current}>"
                        if current
                        else tx("settings.not_configured_79aacc")
                    ),
                ),
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.add_field(
                name=tx("settings.description"),
                value=tx("settings.the_log_channel_receives_message_edit"),
                inline=False,
            )
            view = ChannelSelectView("log_channel", self.cog)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif value == "report_channel":
            current = await run_storage(get_guild_report_channel, guild_id)
            embed = discord.Embed(
                title=tx("settings.settings_report_channel"),
                description=tx(
                    "settings.current_setting",
                    v0=(
                        f"<#{current}>"
                        if current
                        else tx("settings.not_configured_79aacc")
                    ),
                ),
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.add_field(
                name=tx("settings.description"),
                value=tx("settings.the_report_channel_receives_messages_reported"),
                inline=False,
            )
            view = ChannelSelectView("report_channel", self.cog)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif value == "anti_spam":
            embed, view = self.cog.build_anti_spam_panel(guild_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif value == "welcome":
            embed = self.cog.build_welcome_embed(guild_id)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif value == "age_guard":
            embed = await run_storage(self.cog.build_age_guard_embed, guild_id)
            await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== Cog 主體 ====================


class Settings(commands.Cog):
    """伺服器設定儀表板"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="settings", description="Open this server's settings dashboard"
    )
    @app_commands.default_permissions(administrator=True)
    @localized("interaction")
    async def settings(self, interaction: discord.Interaction) -> None:
        """開啟設定儀表板"""
        if interaction.guild is None:
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        embed = await self.build_overview_embed(interaction.guild)
        view = SettingsMenuView(self)
        await interaction.followup.send(embed=embed, view=view)

    # ==================== Embed 產生器 ====================

    @localized("guild")
    async def build_overview_embed(self, guild: discord.Guild) -> discord.Embed:
        """產生設定總覽 Embed"""
        guild_id = guild.id

        embed = discord.Embed(
            title=tx("settings.settings_server_settings", v0=(guild.name)),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )

        # 日誌頻道
        log_ch = await run_storage(get_guild_log_channel, guild_id)
        log_text = f"<#{log_ch}>" if log_ch else tx("settings.not_configured")
        embed.add_field(name=tx("settings.log_channel"), value=log_text, inline=True)

        # 舉報頻道
        report_ch = await run_storage(get_guild_report_channel, guild_id)
        report_text = f"<#{report_ch}>" if report_ch else tx("settings.not_configured")
        embed.add_field(
            name=tx("settings.report_channel"), value=report_text, inline=True
        )

        # 防刷屏
        anti_spam_status = self._get_anti_spam_status(guild_id)
        embed.add_field(
            name=tx("settings.spam_protection"), value=anti_spam_status, inline=True
        )

        # 歡迎訊息
        welcome_status = self._get_welcome_status(guild_id)
        embed.add_field(
            name=tx("settings.welcome_messages"), value=welcome_status, inline=True
        )

        # 倉庫追蹤
        repo_count = self._get_repo_count(guild_id)
        embed.add_field(
            name=tx("settings.repository_tracking"),
            value=tx("settings.repositories", v0=(repo_count)),
            inline=True,
        )

        # 年齡守門員
        age_guard_status = await run_storage(self._get_age_guard_status, guild_id)
        embed.add_field(
            name=tx("settings.age_guard"), value=age_guard_status, inline=True
        )

        embed.set_footer(text=tx("settings.use_the_menu_below_to_change"))
        return embed

    def build_anti_spam_panel(self, guild_id: int) -> Any:
        """產生防刷屏設定面板"""
        anti_spam_cog = self.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            embed = discord.Embed(
                title=tx("settings.settings_spam_protection"),
                description=tx("settings.not_loaded_spam_protection_module_is"),
                color=discord.Color.from_rgb(231, 76, 60),
            )
            return embed, None

        settings = anti_spam_cog.manager.get_settings(guild_id)
        enabled = settings.get("enabled", True)

        embed = discord.Embed(
            title=tx("settings.settings_spam_protection"),
            color=(
                discord.Color.from_rgb(46, 204, 113)
                if enabled
                else discord.Color.from_rgb(231, 76, 60)
            ),
            timestamp=datetime.now(TZ_OFFSET),
        )

        status_icon = (
            tx("settings.enabled") if enabled else tx("settings.disabled_891b9e")
        )
        embed.add_field(name=tx("blacklist.status"), value=status_icon, inline=True)
        embed.add_field(
            name=tx("settings.flood_detection"),
            value=tx(
                "settings.messages_seconds",
                v0=(settings.get("flood_messages", 10)),
                v1=(settings.get("flood_window", 10)),
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.moderation_action"),
            value=settings.get("flood_action", "mute"),
            inline=True,
        )

        embed.add_field(
            name=tx("settings.duplicate_detection"),
            value=(
                tx("settings.enabled")
                if settings.get("duplicate_enabled", True)
                else tx("settings.disabled_891b9e")
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.mention_detection"),
            value=(
                tx("settings.enabled")
                if settings.get("mention_enabled", True)
                else tx("settings.disabled_891b9e")
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.link_detection"),
            value=(
                tx("settings.enabled")
                if settings.get("link_enabled", True)
                else tx("settings.disabled_891b9e")
            ),
            inline=True,
        )

        embed.add_field(
            name=tx("settings.automatic_escalation"),
            value=tx(
                "settings.escalates_after_violations",
                v0=(
                    tx("settings.enabled")
                    if settings.get("auto_escalate", True)
                    else tx("settings.disabled_891b9e")
                ),
                v1=(settings.get("escalate_strikes", 3)),
            ),
            inline=False,
        )

        white_roles = settings.get("whitelisted_roles", [])
        white_channels = settings.get("whitelisted_channels", [])
        embed.add_field(
            name=tx("settings.allowlist"),
            value=tx(
                "settings.roles_channels",
                v0=(len(white_roles)),
                v1=(len(white_channels)),
            ),
            inline=False,
        )

        embed.set_footer(text=tx("settings.use_anti_spam_to_change_detailed"))

        view = AntiSpamToggleView(guild_id, enabled, self)
        return embed, view

    def build_welcome_embed(self, guild_id: int) -> discord.Embed:
        """產生歡迎訊息設定面板"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return discord.Embed(
                title=tx("settings.settings_welcome_messages"),
                description=tx("settings.not_loaded_management_module_is_unavailable"),
                color=discord.Color.from_rgb(231, 76, 60),
            )

        welcome = management_cog.service.get_welcome_config(str(guild_id))

        embed = discord.Embed(
            title=tx("settings.settings_welcome_messages"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )

        if not welcome:
            embed.description = tx(
                "settings.not_configured_welcome_messages_are_disabled"
            )
            embed.set_footer(text=tx("settings.use_welcome_set_to_configure_welcome"))
            return embed

        ch_id = welcome.get("channel_id")
        embed.add_field(
            name=tx("settings.delivery_channel"),
            value=f"<#{ch_id}>" if ch_id else tx("settings.not_configured"),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.dm_notification"),
            value=(
                tx("settings.enabled")
                if welcome.get("send_dm")
                else tx("settings.disabled_891b9e")
            ),
            inline=True,
        )

        msg = welcome.get("message", "")
        if msg:
            display_msg = msg[:200] + "..." if len(msg) > 200 else msg
            embed.add_field(
                name=tx("report.message_content"), value=display_msg, inline=False
            )

        auto_role = welcome.get("auto_role_id")
        if auto_role:
            embed.add_field(
                name=tx("settings.automatic_roles"),
                value=f"<@&{auto_role}>",
                inline=True,
            )

        embed.set_footer(text=tx("settings.use_welcome_to_change_detailed_settings"))
        return embed

    # ==================== 輔助方法 ====================

    def _get_anti_spam_status(self, guild_id: int) -> str:
        """取得防刷屏狀態文字"""
        anti_spam_cog = self.bot.get_cog("AntiSpam")
        if not anti_spam_cog or not hasattr(anti_spam_cog, "manager"):
            return tx("settings.not_loaded")
        settings = anti_spam_cog.manager.get_settings(guild_id)
        return (
            tx("settings.enabled")
            if settings.get("enabled", True)
            else tx("settings.disabled_891b9e")
        )

    def _get_welcome_status(self, guild_id: int) -> str:
        """取得歡迎訊息狀態文字"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return tx("settings.not_loaded")
        welcome = management_cog.service.get_welcome_config(str(guild_id))
        if not welcome:
            return tx("settings.not_configured")
        return tx("settings.enabled")

    def _get_repo_count(self, guild_id: int) -> int:
        """取得倉庫追蹤數量"""
        management_cog = self.bot.get_cog("Management")
        if not management_cog:
            return 0
        return len(management_cog.service.get_tracked_repos(str(guild_id)))

    def _get_age_guard_status(self, guild_id: int) -> str:
        """取得年齡守門員狀態文字"""
        from src.services.age_guard_service import AgeGuardService

        cfg = AgeGuardService().get_config(guild_id)
        if not cfg.get("enabled", False):
            return tx("settings.disabled_891b9e")
        has_adult = bool(cfg.get("adult_role_id"))
        has_punish = bool(cfg.get("punishment_role_id"))
        if has_adult and has_punish:
            return tx("settings.enabled")
        return tx("settings.enabled_incomplete_configuration")

    def build_age_guard_embed(self, guild_id: int) -> discord.Embed:
        """產生年齡守門員設定面板"""
        from src.services.age_guard_service import AgeGuardService

        cfg = AgeGuardService().get_config(guild_id)
        enabled = cfg.get("enabled", False)
        adult_role_id = cfg.get("adult_role_id")
        punishment_role_id = cfg.get("punishment_role_id")

        guild = self.bot.get_guild(guild_id)
        adult_role = guild.get_role(adult_role_id) if guild and adult_role_id else None
        punishment_role = (
            guild.get_role(punishment_role_id) if guild and punishment_role_id else None
        )

        embed = discord.Embed(
            title=tx("settings.settings_age_guard"),
            color=(
                discord.Color.from_rgb(46, 204, 113)
                if enabled
                else discord.Color.from_rgb(231, 76, 60)
            ),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("blacklist.status"),
            value=tx("settings.enabled") if enabled else tx("settings.disabled_891b9e"),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.adult_role"),
            value=adult_role.mention if adult_role else tx("settings.not_configured"),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.penalty_role"),
            value=(
                punishment_role.mention
                if punishment_role
                else tx("settings.not_configured")
            ),
            inline=True,
        )
        embed.set_footer(text=tx("settings.use_age_guard_to_change_settings"))
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot))
