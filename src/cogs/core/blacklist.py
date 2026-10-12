import asyncio
from datetime import datetime
from typing import Any, TYPE_CHECKING

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.config.constants import DEVELOPER_IDS
from src.services.blacklist_service import BlacklistService
from src.utils.domain_text import appeal_status
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedModal
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage
from src.utils.time_utils import TZ_OFFSET

_service = BlacklistService()


# ==================== 審核接受表單 ====================


class AppealAcceptModal(LocalizedModal, title="Accept appeal"):
    """開發者接受申訴時填寫原因"""

    i18n = {
        "title": "blacklist.accept_appeal",
        "reason.label": "blacklist.reason_optional",
        "reason.placeholder": "blacklist.enter_an_acceptance_reason_or_leave",
    }

    reason = ui.TextInput[Any](
        label="Reason (optional)",
        placeholder="Enter an acceptance reason, or leave blank…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

    def __init__(self, user_id: int, cog: "Blacklist") -> None:
        super().__init__()
        self.target_user_id = user_id
        self.cog = cog

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """執行接受申訴"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        reason_text = self.reason.value.strip() if self.reason.value else ""
        manager = self.cog.bot.blacklist_manager

        source = await run_storage(
            _service.accept_appeal,
            manager,
            self.target_user_id,
            interaction.user,
            reason_text,
        )

        # 更新原訊息外觀
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = discord.Color.from_rgb(46, 204, 113)
            embed.title = tx("blacklist.accepted_appeal_review")
            embed.set_footer(
                text=_service.build_accept_footer(interaction.user, reason_text)
            )
            await interaction.message.edit(embed=embed, view=None)

        await interaction.followup.send(
            tx(
                "blacklist.success_accepted_the_appeal_from_user",
                v0=(self.target_user_id),
            ),
            ephemeral=True,
        )

        # 嘗試通知用戶
        try:
            user = await self.cog.bot.fetch_user(self.target_user_id)
            await user.send(
                embed=_service.build_notify_embed(
                    accepted=True, reason_text=reason_text, source=source
                )
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


# ==================== 審核視圖 ====================


class AppealReviewView(LocalizedView):
    """開發者審核申訴的按鈕視圖"""

    i18n = {
        "accept_button.label": "blacklist.accept",
        "reject_button.label": "blacklist.reject",
    }

    def __init__(self, user_id: int, cog: "Blacklist") -> None:
        super().__init__(timeout=None)
        self.target_user_id = user_id
        self.cog = cog

    @ui.button(
        label="Accept", style=discord.ButtonStyle.success, custom_id="appeal_accept"
    )
    @localized("interaction")
    async def accept_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """接受申訴 - 開啟表單"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                tx("blacklist.denied_appeal_review_permission_is_required"),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            AppealAcceptModal(self.target_user_id, self.cog)
        )

    @ui.button(
        label="Reject", style=discord.ButtonStyle.danger, custom_id="appeal_reject"
    )
    @localized("interaction")
    async def reject_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """駁回申訴"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.followup.send(
                tx("blacklist.denied_appeal_review_permission_is_required"),
                ephemeral=True,
            )
            return

        manager = self.cog.bot.blacklist_manager
        await run_storage(
            _service.reject_appeal, manager, self.target_user_id, interaction.user
        )

        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = discord.Color.from_rgb(231, 76, 60)
            embed.title = tx("blacklist.rejected_appeal_review")
            embed.set_footer(text=_service.build_reject_footer(interaction.user))
            await interaction.message.edit(embed=embed, view=None)

        await interaction.followup.send(
            tx(
                "blacklist.success_rejected_the_appeal_from_user",
                v0=(self.target_user_id),
            ),
            ephemeral=True,
        )

        try:
            user = await self.cog.bot.fetch_user(self.target_user_id)
            await user.send(embed=_service.build_notify_embed(accepted=False))
        except (discord.Forbidden, discord.HTTPException):
            pass


# ==================== 封鎖通知視圖 (含申訴按鈕) ====================


class BlockedNoticeView(LocalizedView):
    """被封鎖時顯示的申訴按鈕"""

    i18n = {"appeal_button.label": "blacklist.submit_appeal"}

    def __init__(self, cog: "Blacklist") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(
        label="Submit appeal",
        style=discord.ButtonStyle.primary,
        custom_id="blacklist_appeal",
    )
    @localized("interaction")
    async def appeal_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """點擊申訴按鈕"""
        manager = self.cog.bot.blacklist_manager
        entry = await manager.check(interaction.user.id)

        result = await _service.submit_appeal(manager, interaction.user, entry)

        if result == "not_blacklisted":
            await interaction.response.send_message(
                tx("blacklist.info_this_account_is_not_currently"), ephemeral=True
            )
            return
        if result == "already_pending":
            await interaction.response.send_message(
                tx("blacklist.info_an_appeal_is_already_pending"), ephemeral=True
            )
            return
        if result == "send_failed":
            await interaction.response.send_message(
                tx("blacklist.failed_could_not_submit_appeal_try"), ephemeral=True
            )
            return

        # 通知開發者
        review_embed = _service.build_review_embed(interaction.user, entry)
        review_view = AppealReviewView(interaction.user.id, self.cog)
        for dev_id in DEVELOPER_IDS:
            try:
                developer = await self.cog.bot.fetch_user(dev_id)
                await developer.send(embed=review_embed, view=review_view)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await interaction.response.send_message(
            tx("blacklist.success_appeal_submitted_for_developer_review"),
            ephemeral=True,
        )


# ==================== Cog 主體 ====================


class Blacklist(commands.Cog):
    """黑名單管理 Cog"""

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """註冊持久化視圖"""
        self.bot.add_view(BlockedNoticeView(self))

    # ========== 使用者指令 ==========

    @app_commands.command(name="appeal", description="Appeal a blacklist block")
    @localized("interaction")
    async def appeal(self, interaction: discord.Interaction) -> None:
        """手動提交申訴"""
        manager = self.bot.blacklist_manager
        entry = await manager.check(interaction.user.id)

        result = await _service.submit_appeal(manager, interaction.user, entry)

        if result == "not_blacklisted":
            await interaction.response.send_message(
                tx("blacklist.info_this_account_is_not_currently"), ephemeral=True
            )
            return
        if result == "already_pending":
            await interaction.response.send_message(
                tx("blacklist.info_an_appeal_is_already_pending"), ephemeral=True
            )
            return

        review_embed = _service.build_review_embed(interaction.user, entry)
        review_view = AppealReviewView(interaction.user.id, self)
        for dev_id in DEVELOPER_IDS:
            try:
                developer = await self.bot.fetch_user(dev_id)
                await developer.send(embed=review_embed, view=review_view)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await interaction.response.send_message(
            tx("blacklist.success_appeal_submitted_for_developer_review"),
            ephemeral=True,
        )

    @app_commands.command(
        name="appeal_status", description="Check the status of your appeal"
    )
    @localized("interaction")
    async def appeal_status(self, interaction: discord.Interaction) -> None:
        """查看自己的申訴狀態"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        manager = self.bot.blacklist_manager
        appeal = await run_storage(manager.get_appeal, interaction.user.id)

        if not appeal:
            await interaction.followup.send(
                tx("blacklist.info_no_appeal_records"), ephemeral=True
            )
            return

        status = appeal["status"]
        color_map = {
            "待處理": discord.Color.from_rgb(241, 196, 15),
            "已接受": discord.Color.from_rgb(46, 204, 113),
            "已駁回": discord.Color.from_rgb(231, 76, 60),
        }

        embed = discord.Embed(
            title=tx("blacklist.info_appeal_status"),
            color=color_map.get(status, discord.Color.from_rgb(153, 170, 181)),
        )
        embed.add_field(
            name=tx("blacklist.status"), value=appeal_status(status), inline=True
        )
        source_label = (
            tx("blacklist.local_blacklist")
            if appeal.get("source") == "local"
            else "CatHome API"
        )
        embed.add_field(name=tx("blacklist.source"), value=source_label, inline=True)
        embed.add_field(
            name=tx("blacklist.submitted_at"),
            value=appeal.get("created_at", tx("audit_log.unknown")),
            inline=False,
        )

        if appeal.get("reviewed_at"):
            embed.add_field(
                name=tx("blacklist.reviewed_at"),
                value=appeal["reviewed_at"],
                inline=True,
            )
        if appeal.get("review_reason"):
            embed.add_field(
                name=tx("blacklist.review_notes"),
                value=appeal["review_reason"],
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ========== 開發者管理指令 ==========

    blacklist_group = app_commands.Group(
        name="blacklist",
        description="Manage the local blacklist (developers only)",
    )

    @blacklist_group.command(
        name="add", description="Add a user to the local blacklist"
    )
    @app_commands.describe(
        user="The user", reason="Reason for the block", mode="Block mode"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Block commands", value="block"),
            app_commands.Choice(name="Global ban", value="global_ban"),
        ]
    )
    @localized("interaction")
    async def bl_add(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        """加入本地黑名單"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.followup.send(
                tx("blacklist.denied_this_command_is_restricted_to"), ephemeral=True
            )
            return

        mode_value = mode.value if mode else "block"
        await run_storage(
            self.bot.blacklist_manager.local_add,
            user.id,
            reason=reason,
            mode=mode_value,
            added_by=interaction.user.id,
        )

        embed = discord.Embed(
            title=tx("blacklist.success_added_to_the_local_blacklist"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.user"), value=f"{user} ({user.id})", inline=False
        )
        embed.add_field(name=tx("blacklist.reason"), value=reason, inline=True)
        embed.add_field(name=tx("blacklist.mode"), value=mode_value, inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacklist_group.command(
        name="remove", description="Remove a user from the local blacklist"
    )
    @app_commands.describe(user="The user")
    @localized("interaction")
    async def bl_remove(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """移除本地黑名單"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.followup.send(
                tx("blacklist.denied_this_command_is_restricted_to"), ephemeral=True
            )
            return

        success = await run_storage(self.bot.blacklist_manager.local_remove, user.id)
        if not success:
            await interaction.followup.send(
                tx("blacklist.failed_user_is_not_in_the", v0=(user)), ephemeral=True
            )
            return

        await interaction.followup.send(
            tx(
                "blacklist.success_removed_from_the_local_blacklist",
                v0=(user),
                v1=(user.id),
            ),
            ephemeral=True,
        )

    @blacklist_group.command(name="list", description="Show the local blacklist")
    @localized("interaction")
    async def bl_list(self, interaction: discord.Interaction) -> None:
        """列出所有本地黑名單"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.followup.send(
                tx("blacklist.denied_this_command_is_restricted_to"), ephemeral=True
            )
            return

        users = await run_storage(self.bot.blacklist_manager.local_list)
        if not users:
            await interaction.followup.send(
                tx("blacklist.info_the_local_blacklist_is_empty"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("blacklist.info_local_blacklist"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        lines = [
            tx(
                "blacklist.value",
                v0=(uid),
                v1=(entry.get("reason", tx("blacklist.not_provided"))),
                v2=(entry.get("mode", "block")),
            )
            for uid, entry in users.items()
        ]
        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1021] + "..."
        embed.add_field(name=tx("blacklist.blocked_accounts"), value=text, inline=False)
        embed.set_footer(text=tx("blacklist.entries", v0=(len(users))))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @blacklist_group.command(name="info", description="Check a user's blacklist status")
    @app_commands.describe(user="The user")
    @localized("interaction")
    async def bl_info(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """查詢特定用戶的封鎖狀態 (本地 + API)"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                tx("blacklist.denied_this_command_is_restricted_to"), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        manager = self.bot.blacklist_manager
        local_entry = await run_storage(manager.local_check, user.id)
        try:
            api_entry = await asyncio.wait_for(manager.api_check(user.id), timeout=3.0)
        except asyncio.TimeoutError:
            api_entry = None

        embed = discord.Embed(
            title=tx("blacklist.info_blacklist_status_for", v0=(user)),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )

        if local_entry:
            local_text = tx(
                "blacklist.reason_mode_time",
                v0=(local_entry.get("reason", tx("blacklist.not_provided"))),
                v1=(local_entry.get("mode", "block")),
                v2=(local_entry.get("added_at", tx("audit_log.unknown"))),
            )
        else:
            local_text = tx("blacklist.not_blocked")
        embed.add_field(
            name=tx("blacklist.local_blacklist"), value=local_text, inline=False
        )

        if api_entry:
            api_text = tx(
                "blacklist.reason_mode",
                v0=(api_entry.get("reason", tx("blacklist.not_provided"))),
                v1=(api_entry.get("mode", tx("audit_log.unknown"))),
            )
        else:
            api_text = tx("blacklist.not_blocked")
        embed.add_field(name="CatHome API", value=api_text, inline=False)

        appeal = await run_storage(manager.get_appeal, user.id)
        if appeal:
            embed.add_field(
                name=tx("blacklist.appeal_status"),
                value=tx(
                    "blacklist.value_092d27",
                    v0=(appeal["status"]),
                    v1=(appeal.get("created_at", tx("audit_log.unknown"))),
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: "Bot") -> None:
    await bot.add_cog(Blacklist(bot))


if TYPE_CHECKING:
    from src.bot import Bot
