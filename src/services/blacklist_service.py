"""黑名單申訴業務邏輯服務"""

from datetime import datetime
from typing import Any

import discord

from src.utils.i18n import text as tx
from src.utils.storage_worker import run_storage
from src.utils.time_utils import TZ_OFFSET


class BlacklistService:
    """黑名單申訴流程邏輯 - 提交、接受、駁回與通知"""

    # ========== 申訴提交 ==========

    async def submit_appeal(
        self,
        manager: Any,
        user: discord.User | discord.Member,
        entry: dict[Any, Any],
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

        existing = await run_storage(manager.get_appeal, user.id)
        if existing and existing.get("status") == "待處理":
            return "already_pending"

        source = entry.get("source", "local")
        reason = entry.get("reason", tx("blacklist_service.no_reason_given"))
        await run_storage(manager.add_appeal, user.id, reason, source=source)
        return "ok"

    def build_review_embed(
        self,
        user: discord.User | discord.Member,
        entry: dict[Any, Any],
    ) -> discord.Embed:
        """建立供開發者審核的申訴 Embed"""
        source = entry.get("source", "local")
        source_label = (
            tx("blacklist.local_blacklist") if source == "local" else "CatHome API"
        )
        reason = entry.get("reason", tx("blacklist_service.no_reason_given"))

        embed = discord.Embed(
            title=tx("blacklist_service.review_blacklist_appeal"),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("blacklist_service.appellant"),
            value=f"{user} ({user.id})",
            inline=False,
        )
        embed.add_field(
            name=tx("blacklist_service.blacklist_source"),
            value=source_label,
            inline=True,
        )
        embed.add_field(
            name=tx("blacklist_service.block_reason"), value=reason, inline=True
        )
        embed.add_field(
            name=tx("blacklist_service.block_mode"),
            value=entry.get("mode", tx("audit_log.unknown")),
            inline=True,
        )
        return embed

    # ========== 接受申訴 ==========

    def accept_appeal(
        self,
        manager: Any,
        target_user_id: int,
        reviewer: discord.User | discord.Member,
        reason_text: str = "",
    ) -> str:
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
        return source

    def build_accept_footer(
        self, reviewer: discord.User | discord.Member, reason_text: str = ""
    ) -> str:
        """建立接受申訴的 footer 文字"""
        footer = tx(
            "blacklist_service.accepted_by_at",
            v0=(reviewer),
            v1=(datetime.now(TZ_OFFSET).strftime("%Y/%m/%d %H:%M")),
        )
        if reason_text:
            footer += tx("blacklist_service.reason", v0=(reason_text))
        return footer

    def build_notify_embed(
        self, accepted: bool, reason_text: str = "", source: str = "local"
    ) -> discord.Embed:
        """建立通知用戶申訴結果的 Embed"""
        if accepted:
            description = (
                tx("blacklist_service.the_appeal_was_accepted_the_local")
                if source == "local"
                else tx("blacklist_service.the_appeal_was_accepted_the_cathome")
            )
            embed = discord.Embed(
                title=tx("blacklist_service.notice_appeal_result"),
                description=description,
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
            if reason_text:
                embed.add_field(
                    name=tx("blacklist.review_notes"), value=reason_text, inline=False
                )
        else:
            embed = discord.Embed(
                title=tx("blacklist_service.notice_appeal_result"),
                description=tx("blacklist_service.the_appeal_was_rejected"),
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
        return embed

    # ========== 駁回申訴 ==========

    def reject_appeal(
        self,
        manager: Any,
        target_user_id: int,
        reviewer: discord.User | discord.Member,
    ) -> None:
        """更新申訴狀態為已駁回"""
        manager.update_appeal(
            target_user_id,
            status="已駁回",
            reviewer_id=reviewer.id,
        )

    def build_reject_footer(self, reviewer: discord.User | discord.Member) -> str:
        """建立駁回申訴的 footer 文字"""
        return tx(
            "blacklist_service.rejected_by_at",
            v0=(reviewer),
            v1=(datetime.now(TZ_OFFSET).strftime("%Y/%m/%d %H:%M")),
        )
