"""Report handling business logic (timeout, ban, warning)."""

import asyncio
from datetime import datetime
from datetime import timedelta

import discord

from src.utils.i18n import text as tx
from src.utils.time_utils import TZ_OFFSET


class ReportService:
    """Carrying out report actions and building their embeds."""

    @staticmethod
    def permission_error(target, moderator, permission):
        if (
            not isinstance(moderator, discord.Member)
            or moderator.guild.id != target.guild.id
        ):
            return tx("report_service.failed_the_moderator_must_be_a")
        if not getattr(moderator.guild_permissions, permission, False):
            return tx("report_service.failed_the_moderator_lacks_the_permission")
        if target.id == target.guild.owner_id or target.id == moderator.id:
            return tx("report_service.failed_this_action_cannot_target_the")
        if (
            moderator.id != target.guild.owner_id
            and target.top_role >= moderator.top_role
        ):
            return tx("report_service.failed_the_target_s_highest_role")
        return ""

    async def authorize(self, target, moderator, permission):
        """Refresh member permissions when a modal is submitted."""
        if (
            not isinstance(moderator, discord.Member)
            or moderator.guild.id != target.guild.id
        ):
            return None, tx("report_service.failed_the_moderator_must_be_a")
        try:
            guild = target.guild
            actor, current_target = await asyncio.wait_for(
                asyncio.gather(
                    guild.fetch_member(moderator.id), guild.fetch_member(target.id)
                ),
                timeout=10,
            )
        except (discord.HTTPException, asyncio.TimeoutError):
            return None, tx("report_service.failed_could_not_verify_current_member")
        error = self.permission_error(current_target, actor, permission)
        bot_member = guild.me
        if not error and (
            bot_member is None
            or not getattr(bot_member.guild_permissions, permission, False)
            or current_target.top_role >= bot_member.top_role
        ):
            error = tx("report_service.failed_the_bot_lacks_the_required")
        return (None, error) if error else (current_target, "")

    # ── Timeout ───────────────────────────────────────────────────────

    async def execute_mute(
        self,
        target: discord.Member,
        moderator: discord.User | discord.Member,
        days: int,
        hours: int,
        minutes: int,
        reason: str,
    ) -> tuple[bool, str]:
        """Apply a timeout.

        Returns:
            (success, error_message): error_message is an empty string on success
        """
        target, error = await self.authorize(target, moderator, "moderate_members")
        if error:
            return False, error
        if min(days, hours, minutes) < 0 or days == hours == minutes == 0:
            return False, tx("report_service.failed_mute_duration_must_be_greater")

        duration = timedelta(days=days, hours=hours, minutes=minutes)
        if duration.total_seconds() > 28 * 24 * 3600:
            return False, tx("report_service.failed_mute_duration_must_not_exceed")

        try:
            await target.timeout(duration, reason=reason)
            return True, ""
        except discord.Forbidden:
            return False, tx("report_service.failed_the_bot_cannot_mute_this")
        except Exception as e:
            return False, tx("report_service.failed_mute_failed", v0=(e))

    def build_mute_embed(
        self,
        target: discord.Member,
        moderator: discord.User | discord.Member,
        days: int,
        hours: int,
        minutes: int,
        reason: str,
    ) -> discord.Embed:
        """Build the embed for a completed timeout."""
        parts = []
        if days:
            parts.append(tx("audit_log.days", v0=(days)))
        if hours:
            parts.append(tx("audit_log.hours", v0=(hours)))
        if minutes:
            parts.append(tx("osu_service.minutes", v0=(minutes)))
        time_str = " ".join(parts)

        return discord.Embed(
            title=tx("report_service.muted_report_action_completed"),
            description=(
                tx(
                    "report_service.target_moderator_duration_reason",
                    v0=(target.mention),
                    v1=(target.id),
                    v2=(moderator.mention),
                    v3=(time_str),
                    v4=(reason),
                )
            ),
            color=discord.Color.from_rgb(230, 126, 34),
            timestamp=datetime.now(TZ_OFFSET),
        )

    # ── Ban ───────────────────────────────────────────────────────────

    async def execute_ban(
        self,
        target: discord.Member,
        moderator: discord.User | discord.Member,
        reason: str,
        delete_days: int = 0,
    ) -> tuple[bool, str]:
        """Apply a ban.

        Returns:
            (success, error_message)
        """
        target, error = await self.authorize(target, moderator, "ban_members")
        if error:
            return False, error
        try:
            await target.ban(
                reason=reason,
                delete_message_seconds=delete_days * 86400,
            )
            return True, ""
        except discord.Forbidden:
            return False, tx("report_service.failed_the_bot_cannot_ban_this")
        except Exception as e:
            return False, tx("report_service.failed_ban_failed", v0=(e))

    def build_ban_embed(
        self,
        target: discord.Member,
        moderator: discord.User | discord.Member,
        reason: str,
        is_temp: bool,
        delete_days: int,
        temp_seconds: int = 0,
    ) -> discord.Embed:
        """Build the embed for a completed ban."""
        embed = discord.Embed(
            title=tx("report_service.banned_report_action_completed"),
            description=(
                tx(
                    "report_service.target_moderator_ban_type_delete_messages",
                    v0=(target.mention),
                    v1=(target.id),
                    v2=(moderator.mention),
                    v3=(
                        tx("report_service.temporary_ban")
                        if is_temp
                        else tx("report_service.permanent_ban")
                    ),
                    v4=(delete_days),
                    v5=(reason),
                )
            ),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        if is_temp and temp_seconds > 0:
            embed.add_field(
                name=tx("report_service.temporary_ban_duration"),
                value=tx(
                    "report_service.seconds_hours",
                    v0=(temp_seconds),
                    v1=(temp_seconds / 3600),
                ),
                inline=False,
            )
            embed.set_footer(
                text=tx("report_service.temporary_bans_require_manual_removal_or")
            )
        return embed

    # ── Warning ───────────────────────────────────────────────────────

    async def execute_warn(
        self,
        target: discord.Member,
        guild_name: str,
        count: int,
        reason: str,
    ) -> bool:
        """Send the warning DM; return whether it was delivered."""
        warn_embed = discord.Embed(
            title=tx("report_service.warning_member_warning"),
            description=(
                tx(
                    "report_service.server_warning_count_reason",
                    v0=(guild_name),
                    v1=(count),
                    v2=(reason),
                )
            ),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        try:
            await target.send(embed=warn_embed)
            return True
        except Exception:
            return False

    def build_warn_result_embed(
        self,
        target: discord.Member,
        moderator: discord.User | discord.Member,
        count: int,
        reason: str,
        dm_sent: bool,
    ) -> discord.Embed:
        """Build the embed for a completed warning."""
        return discord.Embed(
            title=tx("report_service.warned_report_action_completed"),
            description=(
                tx(
                    "report_service.target_moderator_warnings_reason_dm_notification",
                    v0=(target.mention),
                    v1=(target.id),
                    v2=(moderator.mention),
                    v3=(count),
                    v4=(reason),
                    v5=(
                        tx("report_service.delivered")
                        if dm_sent
                        else tx("report_service.not_delivered_dms_may_be_disabled")
                    ),
                )
            ),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
