import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

TZ_OFFSET = timezone(timedelta(hours=8))
DEVELOPER_IDS = {241619561760292866, 964849855396741130}


# ==================== 審核接受表單 ====================


class AppealAcceptModal(ui.Modal, title="接受申訴"):
    """開發者接受申訴時填寫原因"""

    reason = ui.TextInput(
        label="原因 (可留空)",
        placeholder="輸入接受原因或留空...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

    def __init__(self, user_id: int, cog: "Blacklist"):
        super().__init__()
        self.target_user_id = user_id
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        """執行接受申訴"""
        reason_text = self.reason.value.strip() if self.reason.value else ""
        manager = self.cog.bot.blacklist_manager

        # 更新申訴狀態
        manager.update_appeal(
            self.target_user_id,
            status="已接受",
            reviewer_id=interaction.user.id,
            review_reason=reason_text or None,
        )

        # 從本地黑名單移除
        appeal = manager.get_appeal(self.target_user_id)
        source = appeal.get("source", "local") if appeal else "local"

        if source == "local":
            manager.local_remove(self.target_user_id)

        # 更新原訊息
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = discord.Color.from_rgb(46, 204, 113)
            embed.title = "[已接受] 申訴審核"
            footer_text = f"由 {interaction.user} 於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M')} 接受"
            if reason_text:
                footer_text += f" | 原因: {reason_text}"
            embed.set_footer(text=footer_text)
            await interaction.message.edit(embed=embed, view=None)

        await interaction.response.send_message(
            f"[成功] 已接受用戶 {self.target_user_id} 的申訴",
            ephemeral=True,
        )

        # 嘗試通知用戶
        try:
            user = await self.cog.bot.fetch_user(self.target_user_id)
            notify_embed = discord.Embed(
                title="[通知] 申訴結果",
                description="您的申訴已被 **接受**，黑名單已解除。",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
            if reason_text:
                notify_embed.add_field(name="審核備註", value=reason_text, inline=False)
            await user.send(embed=notify_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ==================== 審核視圖 ====================


class AppealReviewView(ui.View):
    """開發者審核申訴的按鈕視圖"""

    def __init__(self, user_id: int, cog: "Blacklist"):
        super().__init__(timeout=None)
        self.target_user_id = user_id
        self.cog = cog

    @ui.button(label="接受", style=discord.ButtonStyle.success, custom_id="appeal_accept")
    async def accept_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """接受申訴 - 開啟表單"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 你沒有權限審核", ephemeral=True
            )
            return
        modal = AppealAcceptModal(self.target_user_id, self.cog)
        await interaction.response.send_modal(modal)

    @ui.button(label="駁回", style=discord.ButtonStyle.danger, custom_id="appeal_reject")
    async def reject_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """駁回申訴"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 你沒有權限審核", ephemeral=True
            )
            return

        manager = self.cog.bot.blacklist_manager

        manager.update_appeal(
            self.target_user_id,
            status="已駁回",
            reviewer_id=interaction.user.id,
        )

        # 更新原訊息
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = discord.Color.from_rgb(231, 76, 60)
            embed.title = "[已駁回] 申訴審核"
            embed.set_footer(
                text=f"由 {interaction.user} 於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M')} 駁回"
            )
            await interaction.message.edit(embed=embed, view=None)

        await interaction.response.send_message(
            f"[成功] 已駁回用戶 {self.target_user_id} 的申訴",
            ephemeral=True,
        )

        # 嘗試通知用戶
        try:
            user = await self.cog.bot.fetch_user(self.target_user_id)
            notify_embed = discord.Embed(
                title="[通知] 申訴結果",
                description="您的申訴已被 **駁回**。",
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
            await user.send(embed=notify_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ==================== 封鎖通知視圖 (含申訴按鈕) ====================


class BlockedNoticeView(ui.View):
    """被封鎖時顯示的申訴按鈕"""

    def __init__(self, cog: "Blacklist"):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="提交申訴", style=discord.ButtonStyle.primary, custom_id="blacklist_appeal")
    async def appeal_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """點擊申訴按鈕"""
        manager = self.cog.bot.blacklist_manager

        # 確認仍在黑名單中
        entry = await manager.check(interaction.user.id)
        if not entry:
            await interaction.response.send_message(
                "[提示] 您目前不在黑名單中", ephemeral=True
            )
            return

        # 檢查是否已有待處理申訴
        existing = manager.get_appeal(interaction.user.id)
        if existing and existing.get("status") == "待處理":
            await interaction.response.send_message(
                "[提示] 您已有一筆待處理的申訴，請耐心等候", ephemeral=True
            )
            return

        source = entry.get("source", "local")
        reason = entry.get("reason", "未提供原因")

        # 記錄申訴
        manager.add_appeal(interaction.user.id, reason, source=source)

        # 發送審核通知到開發者私訊
        try:
            source_label = "本地黑名單" if source == "local" else "CatHome API"
            review_embed = discord.Embed(
                title="[審核] 黑名單申訴",
                color=discord.Color.from_rgb(241, 196, 15),
                timestamp=datetime.now(TZ_OFFSET),
            )
            review_embed.add_field(
                name="申訴者",
                value=f"{interaction.user} ({interaction.user.id})",
                inline=False,
            )
            review_embed.add_field(
                name="黑名單來源", value=source_label, inline=True
            )
            review_embed.add_field(
                name="封鎖原因", value=reason, inline=True
            )
            review_embed.add_field(
                name="封鎖模式", value=entry.get("mode", "未知"), inline=True
            )

            review_view = AppealReviewView(interaction.user.id, self.cog)
            for dev_id in DEVELOPER_IDS:
                try:
                    developer = await self.cog.bot.fetch_user(dev_id)
                    await developer.send(embed=review_embed, view=review_view)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        except Exception:
            await interaction.response.send_message(
                "[失敗] 無法送出申訴，請稍後再試", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "[成功] 申訴已提交，請耐心等候開發者審核", ephemeral=True
        )


# ==================== Cog 主體 ====================


class Blacklist(commands.Cog):
    """黑名單管理 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """註冊持久化視圖"""
        self.bot.add_view(BlockedNoticeView(self))

    # ========== 使用者指令 ==========

    @app_commands.command(name="申訴", description="申訴黑名單封鎖")
    async def appeal(self, interaction: discord.Interaction):
        """手動提交申訴"""
        manager = self.bot.blacklist_manager

        entry = await manager.check(interaction.user.id)
        if not entry:
            await interaction.response.send_message(
                "[提示] 您目前不在黑名單中", ephemeral=True
            )
            return

        existing = manager.get_appeal(interaction.user.id)
        if existing and existing.get("status") == "待處理":
            await interaction.response.send_message(
                "[提示] 您已有一筆待處理的申訴，請耐心等候", ephemeral=True
            )
            return

        source = entry.get("source", "local")
        reason = entry.get("reason", "未提供原因")

        manager.add_appeal(interaction.user.id, reason, source=source)

        try:
            source_label = "本地黑名單" if source == "local" else "CatHome API"
            review_embed = discord.Embed(
                title="[審核] 黑名單申訴",
                color=discord.Color.from_rgb(241, 196, 15),
                timestamp=datetime.now(TZ_OFFSET),
            )
            review_embed.add_field(
                name="申訴者",
                value=f"{interaction.user} ({interaction.user.id})",
                inline=False,
            )
            review_embed.add_field(
                name="黑名單來源", value=source_label, inline=True
            )
            review_embed.add_field(
                name="封鎖原因", value=reason, inline=True
            )

            review_view = AppealReviewView(interaction.user.id, self)
            for dev_id in DEVELOPER_IDS:
                try:
                    developer = await self.bot.fetch_user(dev_id)
                    await developer.send(embed=review_embed, view=review_view)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "[失敗] 無法送出申訴，請稍後再試", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "[成功] 申訴已提交，請耐心等候開發者審核", ephemeral=True
        )

    @app_commands.command(name="申訴狀態", description="查看申訴狀態")
    async def appeal_status(self, interaction: discord.Interaction):
        """查看自己的申訴狀態"""
        manager = self.bot.blacklist_manager
        appeal = manager.get_appeal(interaction.user.id)

        if not appeal:
            await interaction.response.send_message(
                "[提示] 沒有申訴紀錄", ephemeral=True
            )
            return

        status = appeal["status"]
        color_map = {
            "待處理": discord.Color.from_rgb(241, 196, 15),
            "已接受": discord.Color.from_rgb(46, 204, 113),
            "已駁回": discord.Color.from_rgb(231, 76, 60),
        }

        embed = discord.Embed(
            title="[資訊] 申訴狀態",
            color=color_map.get(status, discord.Color.greyple()),
        )
        embed.add_field(name="狀態", value=status, inline=True)
        source_label = "本地黑名單" if appeal.get("source") == "local" else "CatHome API"
        embed.add_field(name="來源", value=source_label, inline=True)
        embed.add_field(name="提交時間", value=appeal.get("created_at", "未知"), inline=False)

        if appeal.get("reviewed_at"):
            embed.add_field(name="審核時間", value=appeal["reviewed_at"], inline=True)
        if appeal.get("review_reason"):
            embed.add_field(name="審核備註", value=appeal["review_reason"], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ========== 開發者管理指令 ==========

    blacklist_group = app_commands.Group(
        name="blacklist",
        description="本地黑名單管理 (開發者專用)",
    )

    @blacklist_group.command(name="add", description="加入本地黑名單")
    @app_commands.describe(
        user="目標用戶",
        reason="封鎖原因",
        mode="封鎖模式",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="封鎖指令", value="block"),
            app_commands.Choice(name="全域封禁", value="global_ban"),
        ]
    )
    async def bl_add(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str,
        mode: app_commands.Choice[str] = None,
    ):
        """加入本地黑名單"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 此指令僅限開發者使用", ephemeral=True
            )
            return

        mode_value = mode.value if mode else "block"
        manager = self.bot.blacklist_manager
        manager.local_add(
            user.id,
            reason=reason,
            mode=mode_value,
            added_by=interaction.user.id,
        )

        embed = discord.Embed(
            title="[成功] 已加入本地黑名單",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="用戶", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="原因", value=reason, inline=True)
        embed.add_field(name="模式", value=mode_value, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @blacklist_group.command(name="remove", description="移除本地黑名單")
    @app_commands.describe(user="目標用戶")
    async def bl_remove(
        self,
        interaction: discord.Interaction,
        user: discord.User,
    ):
        """移除本地黑名單"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 此指令僅限開發者使用", ephemeral=True
            )
            return

        manager = self.bot.blacklist_manager
        success = manager.local_remove(user.id)

        if not success:
            await interaction.response.send_message(
                f"[失敗] 用戶 {user} 不在本地黑名單中", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"[成功] 已將 {user} ({user.id}) 從本地黑名單移除", ephemeral=True
        )

    @blacklist_group.command(name="list", description="查看本地黑名單")
    async def bl_list(self, interaction: discord.Interaction):
        """列出所有本地黑名單"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 此指令僅限開發者使用", ephemeral=True
            )
            return

        manager = self.bot.blacklist_manager
        users = manager.local_list()

        if not users:
            await interaction.response.send_message(
                "[提示] 本地黑名單為空", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="[資訊] 本地黑名單",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )

        lines = []
        for uid, entry in users.items():
            reason = entry.get("reason", "未提供")
            mode = entry.get("mode", "block")
            lines.append(f"**{uid}** - {reason} (`{mode}`)")

        # Embed field 上限 1024
        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1021] + "..."

        embed.add_field(name="封鎖名單", value=text, inline=False)
        embed.set_footer(text=f"共 {len(users)} 筆")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @blacklist_group.command(name="info", description="查詢用戶黑名單狀態")
    @app_commands.describe(user="目標用戶")
    async def bl_info(
        self,
        interaction: discord.Interaction,
        user: discord.User,
    ):
        """查詢特定用戶的封鎖狀態 (本地 + API)"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 此指令僅限開發者使用", ephemeral=True
            )
            return

        manager = self.bot.blacklist_manager

        local_entry = manager.local_check(user.id)
        try:
            api_entry = await asyncio.wait_for(
                manager.api_check(user.id), timeout=3.0
            )
        except asyncio.TimeoutError:
            api_entry = None

        embed = discord.Embed(
            title=f"[資訊] {user} 的黑名單狀態",
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )

        # 本地
        if local_entry:
            local_text = (
                f"原因: {local_entry.get('reason', '未提供')}\n"
                f"模式: {local_entry.get('mode', 'block')}\n"
                f"時間: {local_entry.get('added_at', '未知')}"
            )
        else:
            local_text = "未封鎖"
        embed.add_field(name="本地黑名單", value=local_text, inline=False)

        # API
        if api_entry:
            api_text = (
                f"原因: {api_entry.get('reason', '未提供')}\n"
                f"模式: {api_entry.get('mode', '未知')}"
            )
        else:
            api_text = "未封鎖"
        embed.add_field(name="CatHome API", value=api_text, inline=False)

        # 申訴
        appeal = manager.get_appeal(user.id)
        if appeal:
            embed.add_field(
                name="申訴狀態",
                value=f"{appeal['status']} ({appeal.get('created_at', '未知')})",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))
