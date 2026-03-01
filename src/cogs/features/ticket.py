import asyncio
import json
import os
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional

import discord
from discord import ui
from discord.ext import commands

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# 資料檔案路徑
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "storage",
)
TICKET_FILE = os.path.join(DATA_DIR, "tickets.json")

# 全域鎖 + 快取
_ticket_lock = asyncio.Lock()
_ticket_cache: Optional[dict] = None


def _load_tickets() -> dict:
    """載入工單資料 (帶記憶體快取)"""
    global _ticket_cache
    if _ticket_cache is not None:
        return _ticket_cache

    if os.path.exists(TICKET_FILE):
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as f:
                _ticket_cache = json.load(f)
                return _ticket_cache
        except (json.JSONDecodeError, OSError):
            pass
    _ticket_cache = {"guilds": {}, "tickets": {}}
    return _ticket_cache


def _save_tickets(data: dict):
    """儲存工單資料並更新快取"""
    global _ticket_cache
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TICKET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _ticket_cache = data


class CloseReasonModal(ui.Modal, title="關閉工單"):
    """關閉工單原因表單"""

    reason = ui.TextInput(
        label="關閉原因",
        placeholder="請輸入關閉工單的原因...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交關閉原因並鎖定討論串"""
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "[失敗] 此指令只能在工單討論串中使用", ephemeral=True
            )
            return

        reason_text = self.reason.value

        embed = discord.Embed(
            title="[關閉] 工單已關閉",
            description=f"此工單已由 {interaction.user.mention} 關閉",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="關閉原因", value=reason_text, inline=False)
        embed.set_footer(text=f"工單ID: {thread.id}")

        await interaction.response.send_message(embed=embed)

        # 更新工單資料
        data = _load_tickets()
        ticket_id = str(thread.id)
        if ticket_id in data.get("tickets", {}):
            data["tickets"][ticket_id]["status"] = "closed"
            data["tickets"][ticket_id]["closed_by"] = interaction.user.id
            data["tickets"][ticket_id]["close_reason"] = reason_text
            data["tickets"][ticket_id]["closed_at"] = datetime.now(
                TZ_OFFSET
            ).isoformat()
            _save_tickets(data)

        # 鎖定並封存討論串
        try:
            await thread.edit(locked=True, archived=True)
        except discord.Forbidden:
            pass


class TicketCloseView(ui.View):
    """工單關閉按鈕視圖 (持久化)"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _check_close_permission(
        self, interaction: discord.Interaction
    ) -> bool:
        """檢查關閉工單權限 (管理員或工單建立者)"""
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "[失敗] 此指令只能在工單討論串中使用", ephemeral=True
            )
            return False

        data = _load_tickets()
        ticket_id = str(thread.id)
        ticket_info = data.get("tickets", {}).get(ticket_id, {})

        is_staff = interaction.user.guild_permissions.manage_threads
        is_creator = ticket_info.get("creator_id") == interaction.user.id

        if not is_staff and not is_creator:
            await interaction.response.send_message(
                "[失敗] 只有管理員或工單建立者可以關閉工單", ephemeral=True
            )
            return False

        return True

    @ui.button(
        label="關閉工單",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close",
    )
    async def close_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """直接關閉工單"""
        if not await self._check_close_permission(interaction):
            return

        thread = interaction.channel

        embed = discord.Embed(
            title="[關閉] 工單已關閉",
            description=f"此工單已由 {interaction.user.mention} 關閉",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.set_footer(text=f"工單ID: {thread.id}")

        await interaction.response.send_message(embed=embed)

        # 更新工單資料
        data = _load_tickets()
        ticket_id = str(thread.id)
        if ticket_id in data.get("tickets", {}):
            data["tickets"][ticket_id]["status"] = "closed"
            data["tickets"][ticket_id]["closed_by"] = interaction.user.id
            data["tickets"][ticket_id]["closed_at"] = datetime.now(
                TZ_OFFSET
            ).isoformat()
            _save_tickets(data)

        # 鎖定並封存討論串
        try:
            await thread.edit(locked=True, archived=True)
        except discord.Forbidden:
            pass

    @ui.button(
        label="有原因關閉工單",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_reason",
    )
    async def close_reason_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """帶原因的關閉工單"""
        if not await self._check_close_permission(interaction):
            return

        await interaction.response.send_modal(CloseReasonModal())


class TicketOpenView(ui.View):
    """開啟工單按鈕視圖 (持久化)"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="開啟工單",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_open",
    )
    async def open_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """開啟新工單"""
        guild = interaction.guild
        if not guild:
            return

        data = _load_tickets()
        guild_config = data.get("guilds", {}).get(str(guild.id), {})

        if not guild_config:
            await interaction.response.send_message(
                "[失敗] 工單系統尚未設定", ephemeral=True
            )
            return

        role_id = guild_config.get("role_id")

        # 檢查是否已有開啟中的工單
        for tid, tinfo in data.get("tickets", {}).items():
            if (
                tinfo.get("creator_id") == interaction.user.id
                and tinfo.get("guild_id") == guild.id
                and tinfo.get("status") == "open"
            ):
                await interaction.response.send_message(
                    f"[失敗] 你已有一個開啟中的工單: <#{tid}>",
                    ephemeral=True,
                )
                return

        # 工單編號
        ticket_count = guild_config.get("ticket_count", 0) + 1
        guild_config["ticket_count"] = ticket_count
        data.setdefault("guilds", {})[str(guild.id)] = guild_config

        thread_name = (
            f"工單-{ticket_count:04d}-{interaction.user.display_name}"
        )

        # 建立私人討論串
        channel = interaction.channel
        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "[失敗] 機器人權限不足，無法建立私人討論串", ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"[失敗] 建立工單失敗: {e}", ephemeral=True
            )
            return

        # 儲存工單資料
        data.setdefault("tickets", {})[str(thread.id)] = {
            "guild_id": guild.id,
            "channel_id": channel.id,
            "creator_id": interaction.user.id,
            "ticket_number": ticket_count,
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "status": "open",
            "closed_by": None,
            "close_reason": None,
            "closed_at": None,
        }
        _save_tickets(data)

        # 歡迎 Embed
        embed = discord.Embed(
            title="[工單] 新工單已建立",
            description="請詳細說明你的問題，工作人員會盡快回覆。",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="建立者",
            value=f"{interaction.user.mention} ({interaction.user.id})",
            inline=True,
        )
        embed.add_field(
            name="工單編號",
            value=f"#{ticket_count:04d}",
            inline=True,
        )
        embed.set_footer(
            text=f"工單ID: {thread.id} | 伺服器: {guild.name}"
        )

        # @身份組 + 發送 Embed 和關閉按鈕
        role_mention = f"<@&{role_id}>" if role_id else ""
        await thread.send(
            content=f"{interaction.user.mention} {role_mention}",
            embed=embed,
            view=TicketCloseView(),
        )

        await interaction.response.send_message(
            f"[成功] 已建立工單: {thread.mention}", ephemeral=True
        )


class Ticket(commands.Cog):
    """工單系統 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """重新載入持久化視圖"""
        self.bot.add_view(TicketOpenView())
        self.bot.add_view(TicketCloseView())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """處理 >>> 前綴指令"""
        if message.author.bot or not message.guild:
            return
        if not message.content.startswith(">>>ticket"):
            return

        # 檢查管理員權限
        if not message.author.guild_permissions.administrator:
            await message.reply(
                "[失敗] 你需要管理員權限才能使用此指令", delete_after=5
            )
            return

        parts = message.content.strip().split()
        if len(parts) >= 2 and parts[1] == "setup":
            await self._handle_setup(message)
        else:
            await message.reply(
                "[提示] 使用方式: `>>>ticket setup <#頻道> <@身份組>`",
                delete_after=10,
            )

    async def _handle_setup(self, message: discord.Message):
        """處理工單設定指令"""
        if not message.channel_mentions or not message.role_mentions:
            await message.reply(
                "[失敗] 請提供頻道和身份組\n"
                "使用方式: `>>>ticket setup <#頻道> <@身份組>`",
                delete_after=10,
            )
            return

        channel = message.channel_mentions[0]
        role = message.role_mentions[0]
        guild = message.guild

        # 禁止使用 @everyone 作為通知身份組
        if role.is_default():
            await message.reply(
                "[失敗] 無法使用 @everyone 作為工單通知身份組\n"
                "請建立專用的工作人員身份組",
                delete_after=10,
            )
            return

        # 檢查機器人在目標頻道的權限
        bot_perms = channel.permissions_for(guild.me)
        if not bot_perms.send_messages or not bot_perms.create_private_threads:
            await message.reply(
                f"[失敗] 機器人在 {channel.mention} 中缺少"
                "「發送訊息」或「建立私人討論串」權限",
                delete_after=10,
            )
            return

        # 在目標頻道發送工單面板
        panel_embed = discord.Embed(
            title="[工單] 支援工單系統",
            description=(
                "如果你需要協助，請點擊下方按鈕開啟工單。\n"
                "工作人員會在私人討論串中回覆你。"
            ),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        panel_embed.set_footer(text=f"伺服器: {guild.name}")

        panel_message = await channel.send(
            embed=panel_embed, view=TicketOpenView()
        )

        # 儲存設定
        data = _load_tickets()
        existing = data.get("guilds", {}).get(str(guild.id), {})
        data.setdefault("guilds", {})[str(guild.id)] = {
            "channel_id": channel.id,
            "role_id": role.id,
            "panel_message_id": panel_message.id,
            "ticket_count": existing.get("ticket_count", 0),
        }
        _save_tickets(data)

        # 確認訊息
        embed = discord.Embed(
            title="[成功] 工單系統已設定",
            description=(
                f"工單頻道: {channel.mention}\n"
                f"通知身份組: {role.mention}\n"
                f"面板訊息ID: {panel_message.id}"
            ),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await message.reply(embed=embed)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Ticket(bot))
