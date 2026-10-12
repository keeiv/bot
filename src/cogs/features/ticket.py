from typing import Any, TYPE_CHECKING

from src.utils.storage_worker import run_storage

"""工單系統 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import ui
from discord.ext import commands

from src.services.ticket_service import TicketService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedModal
from src.utils.localized_ui import LocalizedView

if TYPE_CHECKING:
    from src.bot import Bot

TZ_OFFSET = timezone(timedelta(hours=8))

# 模組級單例，讓持久化 View 與 Cog 共享同一個 service 實例
_service = TicketService()


class CloseReasonModal(LocalizedModal, title="Close ticket"):
    """關閉工單原因表單"""

    i18n = {
        "title": "ticket.close_ticket",
        "reason.label": "ticket.closure_reason",
        "reason.placeholder": "ticket.enter_a_reason_for_closing_the",
    }

    reason = ui.TextInput[Any](
        label="Closure reason",
        placeholder="Enter a reason for closing the ticket…",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """提交關閉原因並鎖定討論串"""
        await interaction.response.defer(thinking=True)
        if not await TicketCloseView()._check_close_permission(interaction):
            return
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.followup.send(
                tx("ticket.failed_this_command_is_only_available"), ephemeral=True
            )
            return

        reason_text = self.reason.value

        embed = discord.Embed(
            title=tx("ticket.closed_ticket_closed"),
            description=tx(
                "ticket.this_ticket_was_closed_by", v0=(interaction.user.mention)
            ),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("ticket.closure_reason"), value=reason_text, inline=False
        )
        embed.set_footer(text=tx("ticket.ticket_id", v0=(thread.id)))

        await interaction.followup.send(embed=embed)

        await run_storage(
            _service.close_ticket,
            thread.id,
            interaction.user.id,
            reason=reason_text,
        )

        try:
            await thread.edit(locked=True, archived=True)
        except discord.Forbidden:
            pass


class TicketCloseView(LocalizedView):
    """工單關閉按鈕視圖 (持久化)"""

    i18n = {
        "close_button.label": "ticket.close_ticket",
        "close_reason_button.label": "ticket.close_with_reason",
    }

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @staticmethod
    async def _respond(interaction, *args, **kwargs):
        sender = (
            interaction.followup.send
            if interaction.response.is_done()
            else interaction.response.send_message
        )
        await sender(*args, **kwargs)

    async def _check_close_permission(self, interaction: discord.Interaction) -> bool:
        """檢查關閉工單權限 (管理員或工單建立者)"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await self._respond(
                interaction,
                tx("bot_appearance.this_feature_is_only_available_in"),
                ephemeral=True,
            )
            return False
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await self._respond(
                interaction,
                tx("ticket.failed_this_command_is_only_available"),
                ephemeral=True,
            )
            return False

        is_staff = interaction.user.guild_permissions.manage_threads
        if not (
            await run_storage(
                _service.can_close, thread.id, interaction.user.id, is_staff
            )
        ):
            await self._respond(
                interaction,
                tx("ticket.failed_only_staff_or_the_ticket"),
                ephemeral=True,
            )
            return False

        return True

    @ui.button(
        label="Close ticket",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close",
    )
    @localized("interaction")
    async def close_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """直接關閉工單"""
        await interaction.response.defer(thinking=True)
        if not await self._check_close_permission(interaction):
            return

        thread = interaction.channel

        if not isinstance(thread, discord.Thread):
            return

        embed = discord.Embed(
            title=tx("ticket.closed_ticket_closed"),
            description=tx(
                "ticket.this_ticket_was_closed_by", v0=(interaction.user.mention)
            ),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.set_footer(text=tx("ticket.ticket_id", v0=(thread.id)))

        await interaction.followup.send(embed=embed)

        await run_storage(_service.close_ticket, thread.id, interaction.user.id)

        try:
            await thread.edit(locked=True, archived=True)
        except discord.Forbidden:
            pass

    @ui.button(
        label="Close with reason",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_reason",
    )
    @localized("interaction")
    async def close_reason_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """帶原因的關閉工單"""
        await interaction.response.send_modal(CloseReasonModal())


class TicketOpenView(LocalizedView):
    """開啟工單按鈕視圖 (持久化)"""

    i18n = {"open_button.label": "ticket.open_ticket"}

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @ui.button(
        label="Open ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_open",
    )
    @localized("interaction")
    async def open_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """開啟新工單"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if not guild:
            return

        guild_config = await run_storage(_service.get_guild_config, guild.id)
        if (
            not guild_config
            or not guild_config.get("enabled", True)
            or interaction.channel_id != guild_config.get("channel_id")
        ):
            await interaction.followup.send(
                tx("ticket.failed_the_ticket_system_is_not"), ephemeral=True
            )
            return

        role_id = guild_config.get("role_id")

        # 檢查是否已有開啟中的工單
        existing_tid = await run_storage(
            _service.find_open_ticket, guild.id, interaction.user.id
        )
        if existing_tid:
            await interaction.followup.send(
                tx("ticket.failed_an_open_ticket_already_exists", v0=(existing_tid)),
                ephemeral=True,
            )
            return

        # 遞增工單編號
        ticket_count = await run_storage(_service.increment_ticket_count, guild.id)

        thread_name = tx(
            "ticket.ticket", v0=(ticket_count), v1=(interaction.user.display_name)
        )

        # 建立私人討論串
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                tx("ticket.the_ticket_panel_must_be_in"), ephemeral=True
            )
            return
        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                tx("ticket.failed_the_bot_cannot_create_private"), ephemeral=True
            )
            return
        except Exception as e:
            await interaction.followup.send(
                tx("ticket.failed_ticket_creation_failed", v0=(e)), ephemeral=True
            )
            return

        # 儲存工單資料
        await run_storage(
            _service.create_ticket,
            guild_id=guild.id,
            thread_id=thread.id,
            channel_id=channel.id,
            creator_id=interaction.user.id,
            ticket_number=ticket_count,
        )

        # 歡迎 Embed
        embed = discord.Embed(
            title=tx("ticket.ticket_new_ticket_created"),
            description=tx("ticket.describe_the_issue_in_detail_staff"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("ticket.created_by"),
            value=f"{interaction.user.mention} ({interaction.user.id})",
            inline=True,
        )
        embed.add_field(
            name=tx("ticket.ticket_number"),
            value=f"#{ticket_count:04d}",
            inline=True,
        )
        embed.set_footer(
            text=tx("ticket.ticket_id_server", v0=(thread.id), v1=(guild.name))
        )

        role_mention = f"<@&{role_id}>" if role_id else ""
        await thread.send(
            content=f"{interaction.user.mention} {role_mention}",
            embed=embed,
            view=TicketCloseView(),
        )

        await interaction.followup.send(
            tx("ticket.success_ticket_created", v0=(thread.mention)), ephemeral=True
        )


class Ticket(commands.Cog):
    """工單系統 Cog"""

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.service = _service

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """重新載入持久化視圖"""
        self.bot.add_view(TicketOpenView())
        self.bot.add_view(TicketCloseView())

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """處理 >>> 前綴指令"""
        if (
            message.author.bot
            or not message.guild
            or not isinstance(message.author, discord.Member)
        ):
            return
        if not message.content.startswith(">>>ticket"):
            return

        if await self.bot.blacklist_manager.check(message.author.id):
            return

        if not message.author.guild_permissions.administrator:
            await message.reply(
                tx("message_logger.failed_administrator_permission_is_required_for"),
                delete_after=5,
            )
            return

        parts = message.content.strip().split()
        if len(parts) >= 2 and parts[1] == "setup":
            await self._handle_setup(message)
        else:
            await message.reply(
                tx("ticket.info_syntax_ticket_setup_channel_role"),
                delete_after=10,
            )

    async def _handle_setup(self, message: discord.Message) -> None:
        """處理工單設定指令"""
        if message.guild is None:
            return
        if not message.channel_mentions or not message.role_mentions:
            await message.reply(
                tx("ticket.failed_provide_a_channel_and_role"),
                delete_after=10,
            )
            return

        channel = message.channel_mentions[0]
        if not isinstance(channel, discord.TextChannel):
            await message.reply(tx("ticket.the_ticket_panel_must_be_in"))
            return
        role = message.role_mentions[0]
        guild = message.guild

        if role.is_default():
            await message.reply(
                tx("ticket.failed_everyone_cannot_be_used_for"),
                delete_after=10,
            )
            return

        bot_perms = channel.permissions_for(guild.me)
        if not bot_perms.send_messages or not bot_perms.create_private_threads:
            await message.reply(
                tx("ticket.failed_the_bot_lacks_send_messages", v0=(channel.mention)),
                delete_after=10,
            )
            return

        panel_embed = discord.Embed(
            title=tx("ticket.tickets_support_tickets"),
            description=(tx("ticket.use_the_button_below_to_open")),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        panel_embed.set_footer(text=tx("age_guard.server", v0=(guild.name)))

        panel_message = await channel.send(embed=panel_embed, view=TicketOpenView())

        existing = (await run_storage(self.service.get_guild_config, guild.id)) or {}
        await run_storage(
            self.service.save_guild_config,
            guild_id=guild.id,
            channel_id=channel.id,
            role_id=role.id,
            panel_message_id=panel_message.id,
            ticket_count=existing.get("ticket_count", 0),
        )

        embed = discord.Embed(
            title=tx("ticket.success_ticket_system_configured"),
            description=(
                tx(
                    "ticket.ticket_channel_staff_role_panel_message",
                    v0=(channel.mention),
                    v1=(role.mention),
                    v2=(panel_message.id),
                )
            ),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await message.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(Ticket(bot))
