"""黑名單申訴業務邏輯服務"""

from datetime import datetime

import discord

from src.config.constants import DEVELOPER_IDS
from src.utils.time_utils import TZ_OFFSET


class BlacklistService:
    """黑名單申訴流程邏輯 - 提交、接受、駁回與通知"""

    # ========== 申訴提交 ==========

    async def submit_appeal(
        self,
        manager,
        user: discord.User,
        entry: dict,
    ) -> str:
        """提交申訴並通知所有開發者。

        Returns:
            "ok"              — 提交成功
            "not_blacklisted" — 用戶不在黑名單
            "already_pending" — 已有待處理申訴
            "send_failed"     — 無法傳送 DM 給開發者
        """
        if not entry:
            return "not_blacklisted"

        existing = manager.get_appeal(user.id)
        if existing and existing.get("status") == "待處理":
            return "already_pending"

        source = entry.get("source", "local")
        reason = entry.get("reason", "未提供原因")
        manager.add_appeal(user.id, reason, source=source)
        return "ok"

    def build_review_embed(
        self,
        user: discord.User,
        entry: dict,
    ) -> discord.Embed:
        """建立供開發者審核的申訴 Embed"""
        source = entry.get("source", "local")
        source_label = "本地黑名單" if source == "local" else "CatHome API"
        reason = entry.get("reason", "未提供原因")

        embed = discord.Embed(
            title="[審核] 黑名單申訴",
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="申訴者",
            value=f"{user} ({user.id})",
            inline=False,
        )
        embed.add_field(name="黑名單來源", value=source_label, inline=True)
        embed.add_field(name="封鎖原因", value=reason, inline=True)
        embed.add_field(name="封鎖模式", value=entry.get("mode", "未知"), inline=True)
        return embed

    # ========== 接受申訴 ==========

    def accept_appeal(
        self,
        manager,
        target_user_id: int,
        reviewer: discord.User,
        reason_text: str = "",
    ):
        """更新申訴狀態為已接受，並從本地黑名單移除（如來源為 local）"""
        manager.update_appeal(
            target_user_id,
            status="已接受",
            reviewer_id=reviewer.id,
            review_reason=reason_text or None,
        )
        appeal = manager.get_appeal(target_user_id)
        source = appeal.get("source", "local") if appeal else "local"
        if source == "local":
            manager.local_remove(target_user_id)

    def build_accept_footer(self, reviewer: discord.User, reason_text: str = "") -> str:
        """建立接受申訴的 footer 文字"""
        footer = f"由 {reviewer} 於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M')} 接受"
        if reason_text:
            footer += f" | 原因: {reason_text}"
        return footer

    def build_notify_embed(
        self, accepted: bool, reason_text: str = ""
    ) -> discord.Embed:
        """建立通知用戶申訴結果的 Embed"""
        if accepted:
            embed = discord.Embed(
                title="[通知] 申訴結果",
                description="您的申訴已被 **接受**，黑名單已解除。",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
            if reason_text:
                embed.add_field(name="審核備註", value=reason_text, inline=False)
        else:
            embed = discord.Embed(
                title="[通知] 申訴結果",
                description="您的申訴已被 **駁回**。",
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
        return embed

    # ========== 駁回申訴 ==========

    def reject_appeal(
        self,
        manager,
        target_user_id: int,
        reviewer: discord.User,
    ):
        """更新申訴狀態為已駁回"""
        manager.update_appeal(
            target_user_id,
            status="已駁回",
            reviewer_id=reviewer.id,
        )

    def build_reject_footer(self, reviewer: discord.User) -> str:
        """建立駁回申訴的 footer 文字"""
        return f"由 {reviewer} 於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M')} 駁回"
