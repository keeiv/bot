"""Business logic for blacklist appeals."""

from datetime import datetime
from typing import Any

import discord

from src.utils.i18n import text as tx
from src.utils.storage_worker import run_storage
from src.utils.time_utils import TZ_OFFSET


def source_label(source: str | None) -> str:
    """Where a blacklist entry came from, as shown to people."""
    if source == "local":
        return tx("blacklist.local_blacklist")
    if source == "mori":
        return "Mori.black"
    return "CatHome API"


class BlacklistService:
    """The blacklist appeal flow: submit, accept, reject and notify."""

    # ── Submitting an appeal ──────────────────────────────────────────

    async def submit_appeal(
        self,
        manager: Any,
        user: discord.User | discord.Member,
        entry: dict[Any, Any],
    ) -> str:
        """Submit an appeal and tell every developer.

        Returns:
            "ok"              submitted
            "not_blacklisted" the user is not on the blacklist
            "already_pending" an appeal is already waiting
            "send_failed"     no developer could be sent a DM
        """
        if not entry:
            return "not_blacklisted"

        existing = await run_storage(manager.get_appeal, user.id)
        if existing and existing.get("status") == "待處理":
            return "already_pending"

        source = entry.get("source", "local")
        reason = entry.get("reason", tx("blacklist_service.no_reason_given"))
        await run_storage(
            manager.add_appeal,
            user.id,
            reason,
            source=source,
            entry_ids=entry.get("entry_ids"),
        )
        return "ok"

    def build_review_embed(
        self,
        user: discord.User | discord.Member,
        entry: dict[Any, Any],
    ) -> discord.Embed:
        """Build the appeal embed the developers review."""
        source = entry.get("source", "local")
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
            value=source_label(source),
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

    # ── Accepting an appeal ───────────────────────────────────────────

    def accept_appeal(
        self,
        manager: Any,
        target_user_id: int,
        reviewer: discord.User | discord.Member,
        reason_text: str = "",
    ) -> str:
        """Mark the appeal accepted, and remove it from the local blacklist (if its source is local)."""
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
        """Build the footer text for an accepted appeal."""
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
        """Build the embed that tells the user the outcome of the appeal."""
        if accepted:
            description = tx(
                {
                    "local": "blacklist_service.the_appeal_was_accepted_the_local",
                    "mori": "blacklist_service.the_appeal_was_accepted_the_mori",
                    "mori_pending": "blacklist_service.the_appeal_was_accepted_the_mori_pending",
                }.get(source, "blacklist_service.the_appeal_was_accepted_the_cathome")
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

    # ── Rejecting an appeal ───────────────────────────────────────────

    def reject_appeal(
        self,
        manager: Any,
        target_user_id: int,
        reviewer: discord.User | discord.Member,
    ) -> None:
        """Mark the appeal rejected."""
        manager.update_appeal(
            target_user_id,
            status="已駁回",
            reviewer_id=reviewer.id,
        )

    def build_reject_footer(self, reviewer: discord.User | discord.Member) -> str:
        """Build the footer text for a rejected appeal."""
        return tx(
            "blacklist_service.rejected_by_at",
            v0=(reviewer),
            v1=(datetime.now(TZ_OFFSET).strftime("%Y/%m/%d %H:%M")),
        )
