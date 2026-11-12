import asyncio
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
import logging
from typing import Any, Iterable

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.utils.anti_spam import ACTION_BAN
from src.utils.anti_spam import ACTION_DELETE
from src.utils.anti_spam import ACTION_KICK
from src.utils.anti_spam import ACTION_LOCKDOWN
from src.utils.anti_spam import ACTION_MUTE
from src.utils.anti_spam import action_name
from src.utils.anti_spam import ACTION_SEVERITY
from src.utils.anti_spam import ACTION_WARN
from src.utils.anti_spam import AntiSpamManager
from src.utils.anti_spam import create_anti_spam_log_embed
from src.utils.anti_spam import create_nuke_alert_embed
from src.utils.anti_spam import create_raid_alert_embed
from src.utils.anti_spam import DETECT_COORDINATED
from src.utils.anti_spam import DETECT_PHISHING
from src.utils.anti_spam import detection_name
from src.utils.anti_spam import Evidence
from src.utils.anti_spam import link_host
from src.utils.anti_spam import NUKE_ACTIONS
from src.utils.anti_spam import NUKE_STRIP
from src.utils.anti_spam import raid_member_action
from src.utils.anti_spam import TZ_OFFSET
from src.utils.anti_spam import VALID_ACTIONS
from src.utils.config_manager import get_guild_log_channel
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage

log = logging.getLogger(__name__)

# Audit log actions that count toward anti-nuke
AUDIT_KINDS = {
    discord.AuditLogAction.channel_delete: "channel_delete",
    discord.AuditLogAction.channel_create: "channel_create",
    discord.AuditLogAction.role_delete: "role_delete",
    discord.AuditLogAction.ban: "ban",
    discord.AuditLogAction.kick: "kick",
    discord.AuditLogAction.member_prune: "prune",
    discord.AuditLogAction.webhook_create: "webhook_create",
}
# Kick if these permissions remain once the roles are gone (a bot's own integration role, for example)
DANGEROUS_PERMISSIONS = (
    "administrator",
    "manage_guild",
    "manage_channels",
    "manage_roles",
    "manage_webhooks",
    "ban_members",
    "kick_members",
)
# Join actions are reported together after a few seconds, so a raid does not flood the log channel
JOIN_REPORT_DELAY = 5.0
JOIN_REPORT_LINES = 20
GREEN = discord.Color.from_rgb(46, 204, 113)


class AntiSpam(commands.Cog):
    """Anti-raid system: layered detection, automatic escalation, raid protection."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = AntiSpamManager()
        # guild_id -> {channel_id -> original send_messages (True/False/None)};
        # kept in storage too, so a lockdown can still be lifted after a restart
        self._lockdown_states: dict[int, dict[int, bool | None]]
        # lockdowns cut short (a restart or an error mid-way), finished on the next raid
        self._unfinished: set[int]
        self._lockdown_states, self._unfinished = self.manager.load_lockdowns()
        # one lockdown change at a time per server (a raid keeps triggering it)
        self._lockdown_locks: dict[int, asyncio.Lock] = {}
        # guild_id -> lines waiting to be reported together
        self._join_reports: dict[int, list[str]] = {}
        self._report_tasks: set[asyncio.Task[None]] = set()

    async def cog_load(self) -> None:
        self._lift_loop.start()

    async def cog_unload(self) -> None:
        self._lift_loop.cancel()

    @tasks.loop(seconds=60)
    async def _lift_loop(self) -> None:
        """Lift lockdowns whose time is up, and drop detection records that expired."""
        self.manager.prune()
        for guild_id in self.manager.due_lockdowns():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            try:
                await self._auto_lift(guild)
            except Exception:
                log.exception("Could not lift the lockdown of guild %s", guild_id)

    @_lift_loop.before_loop
    async def _before_lift_loop(self) -> None:
        await self.bot.wait_until_ready()

    @localized("guild")
    async def _auto_lift(self, guild: discord.Guild) -> None:
        left = await self._deactivate_lockdown(guild, only_if_due=True)
        if left is None:
            return
        if left:
            # Retrying every minute would not fix permissions; wait for an admin.
            await run_storage(self.manager.save_lockdown_until, guild.id, None)
            await self._send_log(guild.id, self._still_locked(left))
            return
        await self._send_log(
            guild.id,
            discord.Embed(
                title=tx("anti_spam.lockdown_auto_lifted"),
                description=tx(
                    "anti_spam.channel_sending_permissions_have_been_restored"
                ),
                color=GREEN,
            ),
        )

    # ── Helpers ───────────────────────────────────────────────────────

    async def _send_log(self, guild_id: int, embed: discord.Embed) -> None:
        """Send a log to the configured channel."""
        log_channel_id = await run_storage(get_guild_log_channel, guild_id)
        if not log_channel_id:
            return
        try:
            ch = self.bot.get_channel(log_channel_id)
            if not ch:
                ch = await self.bot.fetch_channel(log_channel_id)
            if isinstance(ch, discord.abc.Messageable):
                await ch.send(embed=embed)
        except Exception:
            pass

    async def _execute_action(
        self,
        action: str,
        message: discord.Message,
        detail: str,
        detection_type: str,
    ) -> tuple[bool, str]:
        """Carry out a punishment. Returns (success, fail_reason)."""
        member = message.author
        guild = message.guild
        if (
            guild is None
            or not isinstance(member, discord.Member)
            or not isinstance(
                message.channel,
                (
                    discord.TextChannel,
                    discord.Thread,
                    discord.VoiceChannel,
                    discord.StageChannel,
                ),
            )
        ):
            return False, tx("anti_spam.unsupported_member_or_channel")
        s = self.manager.get_settings(guild.id)
        reason = tx(
            "anti_spam.spam_protection",
            v0=(detection_name(detection_type, detection_type)),
            v1=(detail),
        )

        try:
            if action == ACTION_WARN:
                try:
                    warn_embed = discord.Embed(
                        title=tx("anti_spam.warning_spam_protection"),
                        description=tx(
                            "anti_spam.this_activity_triggered_detection_further_violations",
                            v0=(detection_name(detection_type)),
                        ),
                        color=discord.Color.from_rgb(255, 200, 0),
                    )
                    await member.send(embed=warn_embed)
                except discord.Forbidden:
                    pass  # A blocked DM does not affect the main action

            elif action == ACTION_DELETE:
                try:
                    await message.channel.purge(
                        limit=15,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    try:
                        await message.delete()
                    except discord.HTTPException:
                        pass

            elif action == ACTION_MUTE:
                duration = s.get("mute_duration", 3600)
                await member.timeout(timedelta(seconds=duration), reason=reason)
                try:
                    await message.channel.purge(
                        limit=10,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    pass

            elif action == ACTION_KICK:
                try:
                    await message.channel.purge(
                        limit=15,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    pass
                await guild.kick(member, reason=reason)

            elif action == ACTION_BAN:
                delete_days = s.get("ban_delete_days", 1)
                await guild.ban(
                    member,
                    reason=reason,
                    delete_message_days=delete_days,
                )

            elif action == ACTION_LOCKDOWN:
                await self._activate_lockdown(guild)

            return True, ""

        except discord.Forbidden:
            return False, tx("anti_spam.bot_lacks_permission")
        except Exception as exc:
            return False, str(exc)[:120]

    def _lockdown_lock(self, guild_id: int) -> asyncio.Lock:
        return self._lockdown_locks.setdefault(guild_id, asyncio.Lock())

    async def _activate_lockdown(self, guild: discord.Guild) -> None:
        """Start a lockdown: lock every text channel and store the original permissions.

        When raid_lift_minutes is above 0 the lockdown lifts itself after that long; being triggered again during a lockdown pushes it back.
        """
        async with self._lockdown_lock(guild.id):
            minutes = self.manager.get_settings(guild.id)["raid_lift_minutes"]
            until = (
                datetime.now(TZ_OFFSET).timestamp() + minutes * 60
                if minutes > 0
                else None
            )
            if self.manager.is_lockdown(guild.id) and guild.id not in self._unfinished:
                await run_storage(self.manager.save_lockdown_until, guild.id, until)
                return
            if until is None:
                self.manager.lockdown_until.pop(guild.id, None)
            else:
                self.manager.lockdown_until[guild.id] = until
            await self._lock_channels(guild)

    async def _lock_channels(self, guild: discord.Guild) -> None:
        if self.manager.is_lockdown(guild.id) and guild.id not in self._unfinished:
            return
        default_role = guild.default_role
        if guild.id in self._unfinished:
            # Finish a lockdown cut short: its snapshot still has the originals;
            # a channel made since gets its own before it is locked.
            channel_states = self._lockdown_states[guild.id]
            # Channels already on record keep their originals even if they refuse now.
            carried = set(channel_states)
            added = {
                channel.id: channel.overwrites_for(default_role).send_messages
                for channel in guild.text_channels
                if channel.id not in channel_states
            }
            if added:
                merged = {**channel_states, **added}
                await run_storage(self.manager.save_lockdown, guild.id, merged)
                channel_states = self._lockdown_states[guild.id] = merged  # saved
        else:
            carried = set()
            self.manager.set_lockdown(guild.id, True)
            # Store the original send_messages state before changing permissions: a restart midway can still restore it exactly
            channel_states = {
                channel.id: channel.overwrites_for(default_role).send_messages
                for channel in guild.text_channels
            }
            self._lockdown_states[guild.id] = channel_states
            try:
                await run_storage(self.manager.save_lockdown, guild.id, channel_states)
            except Exception:
                # Never lock what could not be unlocked after a restart; the next
                # raid tries again once storage works.
                self._lockdown_states.pop(guild.id, None)
                self.manager.set_lockdown(guild.id, False)
                raise
            self._unfinished.add(guild.id)
        untouched = []
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(default_role)
                overwrite.update(send_messages=False)
                await channel.set_permissions(
                    default_role,
                    overwrite=overwrite,
                    reason=tx("anti_spam.spam_protection_raid_lockdown_activated"),
                )
            except discord.Forbidden:
                # Never locked, so there is nothing to restore there later.
                untouched.append(channel.id)
        # A channel first seen now that refused the lock was never changed.
        channel_states = {
            cid: state
            for cid, state in channel_states.items()
            if cid in carried or cid not in untouched
        }
        self._lockdown_states[guild.id] = channel_states
        await run_storage(
            self.manager.save_lockdown, guild.id, channel_states, complete=True
        )
        self._unfinished.discard(guild.id)

    async def _deactivate_lockdown(
        self, guild: discord.Guild, only_if_due: bool = False
    ) -> list[int] | None:
        """Lift the lockdown and restore the permissions from before it.

        Returns the channels that are still locked (empty when all were restored),
        or None when only_if_due was asked and the lockdown is not due.
        """
        async with self._lockdown_lock(guild.id):
            if only_if_due and guild.id not in self.manager.due_lockdowns():
                return None  # a raid in the meantime put it off
            return await self._unlock_channels(guild)

    async def _unlock_channels(self, guild: discord.Guild) -> list[int]:
        channel_states = self._lockdown_states.get(guild.id, {})

        default_role = guild.default_role
        left: dict[int, bool | None] = {}
        # Only the channels this lockdown changed; any other keeps whatever it has.
        for channel in guild.text_channels:
            if channel.id not in channel_states:
                continue
            try:
                overwrite = channel.overwrites_for(default_role)
                # Restore the state from before the lockdown.
                overwrite.update(send_messages=channel_states[channel.id])
                await channel.set_permissions(
                    default_role,
                    overwrite=overwrite,
                    reason=tx("anti_spam.spam_protection_lockdown_lifted"),
                )
            except discord.NotFound:
                continue  # deleted meanwhile: nothing left to restore
            except discord.HTTPException:
                # Refused (permissions changed) or failed: keep what it is owed.
                left[channel.id] = channel_states[channel.id]
        if left:
            # Only these stay on record, still locked; the next lift starts from them.
            # The lockdown is now incomplete, like one cut short: a new raid
            # snapshots the reopened channels again and locks them all.
            await run_storage(
                self.manager.save_lockdown, guild.id, left, complete=False
            )
            self._lockdown_states[guild.id] = left
            self._unfinished.add(guild.id)
            return list(left)
        # Delete the record only after everything is restored; if it fails midway the original state is still there for the next lift
        try:
            await run_storage(self.manager.save_lockdown, guild.id, None)
        except Exception:
            # The channels are open again but the record stays: let the next raid
            # lock them anew from it, and lifting can still be retried.
            self._unfinished.add(guild.id)
            raise
        self._lockdown_states.pop(guild.id, None)
        self._unfinished.discard(guild.id)
        self.manager.set_lockdown(guild.id, False)
        self.manager.lockdown_until.pop(guild.id, None)
        self.manager.end_raid(guild.id)
        return []

    def _still_locked(self, channels: list[int]) -> discord.Embed:
        return discord.Embed(
            title=tx("anti_spam.lockdown_partly_lifted"),
            description=tx(
                "anti_spam.channels_still_locked",
                v0=" ".join(f"<#{channel}>" for channel in channels),
            ),
            color=discord.Color.from_rgb(241, 196, 15),
        )

    async def _punish_member(
        self, member: discord.Member, action: str, reason: str
    ) -> bool:
        """Act on members who were not caught through a message (joiners, accounts spamming together)."""
        guild = member.guild
        if (
            member.bot
            or member.id == guild.owner_id
            or member.guild_permissions.administrator
            or guild.me.top_role <= member.top_role
            or self.manager.is_whitelisted(guild.id, member, 0)
        ):
            return False
        s = self.manager.get_settings(guild.id)
        try:
            if action == ACTION_WARN:
                await member.send(
                    embed=discord.Embed(
                        title=tx("anti_spam.warning_spam_protection"),
                        description=reason,
                        color=discord.Color.from_rgb(255, 200, 0),
                    )
                )
            elif action == ACTION_MUTE:
                await member.timeout(
                    timedelta(seconds=s.get("mute_duration", 3600)), reason=reason
                )
            elif action == ACTION_KICK:
                await guild.kick(member, reason=reason)
            elif action == ACTION_BAN:
                await guild.ban(
                    member,
                    reason=reason,
                    delete_message_days=s.get("ban_delete_days", 1),
                )
            else:
                return False
            return True
        except discord.HTTPException:
            return False

    async def _delete_messages(
        self, guild: discord.Guild, messages: Iterable[tuple[int, int]]
    ) -> None:
        """Delete these messages in each channel (missing ones are skipped)."""
        by_channel: dict[int, list[int]] = defaultdict(list)
        for channel_id, message_id in messages:
            by_channel[channel_id].append(message_id)
        for channel_id, ids in by_channel.items():
            channel = guild.get_channel_or_thread(channel_id)
            if channel is None or not hasattr(channel, "delete_messages"):
                continue
            if len(ids) > 1:
                try:
                    for start in range(0, len(ids), 100):
                        await channel.delete_messages(
                            [discord.Object(i) for i in ids[start : start + 100]]
                        )
                    continue
                except discord.HTTPException:
                    pass  # some were gone already: one by one below
            for message_id in ids:
                try:
                    await channel.get_partial_message(message_id).delete()
                except discord.HTTPException:
                    continue

    def _report_join(
        self,
        guild: discord.Guild,
        member: discord.Member,
        detection: str,
        action: str,
        ok: bool,
    ) -> None:
        """Note one join action; a few seconds later it goes to the log with the others from the same moment."""
        pending = self._join_reports.setdefault(guild.id, [])
        pending.append(
            tx(
                "anti_spam.join_report_line",
                v0=(member.mention),
                v1=(member.id),
                v2=(detection_name(detection, detection)),
                v3=(action_name(action, action)),
                v4=(tx("anti_spam.done") if ok else tx("anti_spam.not_done")),
            )
        )
        if len(pending) == 1:
            task = asyncio.get_running_loop().create_task(
                self._flush_join_reports(guild)
            )
            self._report_tasks.add(task)
            task.add_done_callback(self._report_tasks.discard)

    async def _flush_join_reports(self, guild: discord.Guild) -> None:
        await asyncio.sleep(JOIN_REPORT_DELAY)
        lines = self._join_reports.pop(guild.id, [])
        if not lines:
            return
        shown = lines[:JOIN_REPORT_LINES]
        if len(lines) > len(shown):
            shown.append(tx("anti_spam.and_more", v0=(len(lines) - len(shown))))
        await self._send_log(
            guild.id,
            discord.Embed(
                title=tx("anti_spam.join_report_title", v0=(len(lines))),
                description="\n".join(shown),
                color=discord.Color.from_rgb(255, 120, 0),
                timestamp=datetime.now(TZ_OFFSET),
            ),
        )

    async def _disarm(
        self, guild: discord.Guild, member: discord.Member | None, action: str
    ) -> str:
        """Act on someone doing mass damage; return what was done."""
        if member is None:
            return tx("anti_spam.nuke_member_gone")
        me = guild.me
        if member.top_role >= me.top_role:
            return tx("anti_spam.nuke_role_too_high")
        reason = tx("anti_spam.nuke_reason")
        try:
            if action == ACTION_BAN:
                await guild.ban(member, reason=reason, delete_message_days=0)
                return action_name(ACTION_BAN)
            if action == ACTION_KICK:
                await guild.kick(member, reason=reason)
                return action_name(ACTION_KICK)
            removable = [
                r
                for r in member.roles
                if not r.is_default() and not r.managed and r < me.top_role
            ]
            if removable:
                # saved before removing, so nuke_restore can always give them back
                await run_storage(
                    self.manager.save_strip,
                    guild.id,
                    member.id,
                    [r.id for r in removable],
                )
                await member.remove_roles(*removable, reason=reason)
            value = 0
            for role in member.roles:
                if role not in removable:
                    value |= role.permissions.value
            kept = discord.Permissions(value)
            if any(getattr(kept, name) for name in DANGEROUS_PERMISSIONS):
                await guild.kick(member, reason=reason)
                return tx("anti_spam.nuke_stripped_and_kicked", v0=(len(removable)))
            return tx("anti_spam.nuke_stripped", v0=(len(removable)))
        except discord.Forbidden:
            return tx("anti_spam.bot_lacks_permission")
        except discord.HTTPException as exc:
            return str(exc)[:120]

    @localized("guild")
    async def _stop_nuker(
        self, guild: discord.Guild, actor_id: int, result: tuple[str, str, str]
    ) -> None:
        _, action, detail = result
        member = guild.get_member(actor_id)
        if member is None:
            try:
                member = await guild.fetch_member(actor_id)
            except discord.HTTPException:
                member = None
        outcome = await self._disarm(guild, member, action)
        embed = create_nuke_alert_embed(guild.name, guild.id, actor_id, detail, outcome)
        await self._send_log(guild.id, embed)
        try:
            owner = guild.owner or await self.bot.fetch_user(guild.owner_id)
            await owner.send(embed=embed)
        except discord.HTTPException:
            pass  # DMs closed: the log channel has it

    # ── Listeners ─────────────────────────────────────────────────────

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """Watch messages: layered detection."""
        if message.author.bot or message.guild is None:
            return

        # Skipped by permission: administrators, and members the bot cannot punish
        member = message.author
        if isinstance(member, discord.Member):
            if member.guild_permissions.administrator:
                return
            if message.guild.me.top_role <= member.top_role:
                return

        # Catch invite links early
        if self.manager.is_invite_link(message.content or "", message.guild.id):
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        evidence = Evidence()
        triggers = self.manager.check_message(
            guild_id=message.guild.id,
            user_id=message.author.id,
            content=message.content or "",
            channel_id=message.channel.id,
            member=message.author,
            message_id=message.id,
            attachments=[f"{a.filename}:{a.size}" for a in message.attachments],
            stickers=[str(sticker.id) for sticker in message.stickers],
            evidence=evidence,
        )

        if not triggers:
            return

        # Carry out the most severe action
        triggers.sort(key=lambda t: ACTION_SEVERITY.get(t[1], 0), reverse=True)
        worst_det, worst_action, worst_detail = triggers[0]
        strike_count = self.manager.get_user_strikes(
            message.guild.id, message.author.id
        )

        # Malicious links are deleted first whatever the action, so nobody else can click them
        if any(det == DETECT_PHISHING for det, _, _ in triggers):
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        # Carry out the action
        action_ok, fail_reason = await self._execute_action(
            worst_action, message, worst_detail, worst_det
        )

        # For delete and above: also clear this member's recent messages in every channel (every member's, for multi-account spam)
        severities = [ACTION_SEVERITY.get(action, 0) for _, action, _ in triggers]
        if any(
            ACTION_SEVERITY[ACTION_DELETE] <= severity <= ACTION_SEVERITY[ACTION_BAN]
            for severity in severities
        ):
            await self._delete_messages(message.guild, evidence.messages)

        # Multi-account spam: the other accounts are handled by this rule, even if this member also triggered a heavier one
        others = 0
        wave = next((t for t in triggers if t[0] == DETECT_COORDINATED), None)
        if wave and evidence.users:
            reason = tx(
                "anti_spam.spam_protection",
                v0=(detection_name(wave[0], wave[0])),
                v1=(wave[2]),
            )
            # At most a timeout for those not caught in the act: it undoes itself
            # if someone did set them up.
            action = wave[1] if wave[1] in (ACTION_WARN, ACTION_MUTE) else ACTION_MUTE
            for user_id in evidence.users:
                other = message.guild.get_member(user_id)
                if other is not None and await self._punish_member(
                    other, action, reason
                ):
                    others += 1
                    self.manager.reset_user(message.guild.id, user_id)

        # Send the log
        embed = create_anti_spam_log_embed(
            user_id=message.author.id,
            user_name=str(message.author),
            guild_id=message.guild.id,
            guild_name=message.guild.name,
            channel_id=message.channel.id,
            detection_type=worst_det,
            action=worst_action,
            detail=worst_detail,
            strike_count=strike_count,
        )

        if others:
            embed.add_field(
                name=tx("anti_spam.also_handled"),
                value=tx("anti_spam.accounts", v0=(others)),
                inline=True,
            )

        # List every trigger when there are several
        if len(triggers) > 1:
            others = "\n".join(
                f"- {detection_name(d, d)}: {det}" for d, _, det in triggers[1:]
            )
            embed.add_field(
                name=tx("anti_spam.other_trigger"), value=others, inline=False
            )

        # If the action failed, say why in the log
        if not action_ok:
            embed.add_field(
                name=tx("anti_spam.warning_action_failed"),
                value=fail_reason or tx("anti_spam.unknown_reason"),
                inline=False,
            )

        await self._send_log(message.guild.id, embed)

        # Reset the record only for actions that succeeded, so a failure does not lose violations not yet handled
        if action_ok:
            self.manager.reset_user(message.guild.id, message.author.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Watch members joining: the new-account threshold and raid detection."""
        if member.bot:
            return
        # Both checks before anything that waits, the language lookup included: a
        # moderator banning this account meanwhile must already find it among the raid's.
        gate = self.manager.check_new_account(member.guild.id, member.created_at)
        evidence = Evidence()
        result = self.manager.check_member_join(
            member.guild.id, member.id, member.created_at, evidence
        )
        if gate or result:
            await self._handle_join(member, gate, result, evidence)

    @localized("member")
    async def _handle_join(
        self,
        member: discord.Member,
        gate: Any,
        result: Any,
        evidence: Evidence,
    ) -> None:
        guild = member.guild
        s = self.manager.get_settings(guild.id)

        removed = False
        if gate:
            det, action, detail = gate
            if action in (ACTION_KICK, ACTION_BAN):
                try:
                    await member.send(
                        tx(
                            "anti_spam.new_account_dm",
                            v0=(guild.name),
                            v1=(s["new_account_hours"]),
                        )
                    )
                except discord.HTTPException:
                    pass  # DMs closed
            ok = await self._punish_member(
                member,
                action,
                tx(
                    "anti_spam.spam_protection",
                    v0=(detection_name(det)),
                    v1=(detail()),
                ),
            )
            removed = ok and action in (ACTION_KICK, ACTION_BAN)
            self._report_join(guild, member, det, action, ok)

        if not result:
            return
        det, action, detail = result
        reason = tx(
            "anti_spam.spam_protection", v0=(detection_name(det)), v1=(detail())
        )

        if not evidence.wave:
            # A new account that joined during a raid
            if not removed:
                ok = await self._punish_member(member, action, reason)
                self._report_join(guild, member, det, action, ok)
            return

        embed = create_raid_alert_embed(
            guild_name=guild.name,
            guild_id=guild.id,
            join_count=s["raid_joins"],
            window=s["raid_window"],
            action=action,
        )
        member_action = raid_member_action(s)
        handled = 0
        for user_id in evidence.users if member_action else ():
            raider = guild.get_member(user_id)
            if raider is not None and await self._punish_member(
                raider, member_action, reason
            ):
                handled += 1
        if evidence.users and member_action:
            embed.add_field(
                name=tx("anti_spam.raid_handled"),
                value=tx(
                    "anti_spam.raid_handled_value",
                    v0=(handled),
                    v1=(len(evidence.users)),
                    v2=(action_name(member_action)),
                ),
                inline=False,
            )
        if s["raid_lift_minutes"] > 0 and action == ACTION_LOCKDOWN:
            embed.add_field(
                name=tx("anti_spam.auto_lift"),
                value=tx("anti_spam.after_minutes", v0=(s["raid_lift_minutes"])),
                inline=True,
            )

        await self._send_log(guild.id, embed)

        if action == ACTION_LOCKDOWN:
            await self._activate_lockdown(guild)

    async def count_moderation(
        self, guild: discord.Guild, actor_id: int, kind: str, target_id: int
    ) -> None:
        """Count a kick or ban a moderator made through BOT.

        The audit log names BOT., so it is counted here for the person who asked.
        """
        if actor_id == guild.owner_id:
            return
        try:
            result = self.manager.check_nuke(guild.id, actor_id, kind, target_id)
            if result:
                await self._stop_nuker(guild, actor_id, result)
        except Exception:
            log.exception("Could not count a moderation action in %s", guild.id)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry) -> None:
        """Anti-nuke: one member deleting channels or roles, banning, kicking or creating webhooks in bulk within a short time."""
        kind = AUDIT_KINDS.get(entry.action)
        guild = entry.guild
        actor_id = entry.user_id
        if kind is None or actor_id is None or actor_id == guild.owner_id:
            return
        if self.bot.user is not None and actor_id == self.bot.user.id:
            return  # BOT.'s own; moderators' commands arrive through count_moderation
        target = getattr(entry, "target", None)
        result = self.manager.check_nuke(
            guild.id, actor_id, kind, getattr(target, "id", None)
        )
        if result:
            await self._stop_nuker(guild, actor_id, result)

    # ── Command group ─────────────────────────────────────────────────

    anti_spam_group = app_commands.Group(
        name="anti_spam",
        description="Spam protection settings",
        default_permissions=discord.Permissions(administrator=True),
    )

    @anti_spam_group.command(name="setup", description="Turn spam protection on or off")
    @app_commands.describe(enabled="Whether spam protection is on")
    @localized("interaction")
    async def setup_cmd(
        self, interaction: discord.Interaction, enabled: bool = True
    ) -> None:
        """Quick enable or disable."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings, interaction.guild_id, {"enabled": enabled}
        )
        status = tx("anti_spam.enabled") if enabled else tx("anti_spam.disabled")
        embed = discord.Embed(
            title=tx("anti_spam.settings_spam_protection", v0=(status)),
            color=(
                discord.Color.from_rgb(46, 204, 113)
                if enabled
                else discord.Color.from_rgb(231, 76, 60)
            ),
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="flood", description="Set up message flood detection")
    @app_commands.describe(
        messages="Most messages allowed in the time window",
        window="Time window in seconds",
        action="What to do (warn/delete/mute/kick/ban)",
    )
    @localized("interaction")
    async def flood_cmd(
        self,
        interaction: discord.Interaction,
        messages: int = 10,
        window: int = 10,
        action: str = "mute",
    ) -> None:
        """Set up flood detection."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "flood_messages": max(1, messages),
                "flood_window": max(1, window),
                "flood_action": action,
            },
        )
        embed = discord.Embed(
            title=tx("anti_spam.settings_flood_detection_updated"),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.message_limit"),
            value=tx("anti_spam.messages", v0=(messages)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.time_window"),
            value=tx("audit_log.seconds", v0=(window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(
        name="duplicate", description="Set up repeated content detection"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        count="How many repeats trigger it",
        window="Time window in seconds",
        action="What to do",
    )
    @localized("interaction")
    async def duplicate_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        count: int = 4,
        window: int = 30,
        action: str = "delete",
    ) -> None:
        """Set up duplicate detection."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "duplicate_enabled": enabled,
                "duplicate_count": max(2, count),
                "duplicate_window": max(5, window),
                "duplicate_action": action,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        embed = discord.Embed(
            title=tx("anti_spam.settings_duplicate_detection", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.trigger_count"),
            value=tx("anti_spam.times", v0=(count)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.time_window"),
            value=tx("audit_log.seconds", v0=(window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(
        name="mention", description="Set up mass mention detection"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        limit="Most mentions allowed in one message",
        action="What to do",
    )
    @localized("interaction")
    async def mention_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 8,
        action: str = "mute",
    ) -> None:
        """Set up mention detection."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "mention_enabled": enabled,
                "mention_limit": max(1, limit),
                "mention_action": action,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        embed = discord.Embed(
            title=tx("anti_spam.settings_mention_detection", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.mention_limit"),
            value=tx("anti_spam.items", v0=(limit)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(
        name="link", description="Set up link and invite detection"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        limit="Most links allowed in the time window",
        window="Time window in seconds",
        action="What to do",
        invite_auto_delete="Delete invite links automatically",
    )
    @localized("interaction")
    async def link_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 5,
        window: int = 15,
        action: str = "delete",
        invite_auto_delete: bool = True,
    ) -> None:
        """Set up link detection."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "link_enabled": enabled,
                "link_limit": max(1, limit),
                "link_window": max(5, window),
                "link_action": action,
                "invite_auto_delete": invite_auto_delete,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        embed = discord.Embed(
            title=tx("anti_spam.settings_link_detection", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.link_limit"),
            value=tx("anti_spam.items", v0=(limit)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.time_window"),
            value=tx("audit_log.seconds", v0=(window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        embed.add_field(
            name=tx("anti_spam.automatically_delete_invites"),
            value=tx("anti_spam.yes") if invite_auto_delete else tx("anti_spam.no"),
            inline=True,
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="raid", description="Set up raid detection")
    @app_commands.describe(
        enabled="Whether it is on",
        joins="How many joins trigger it",
        window="Time window in seconds",
        action="What to do (lockdown recommended)",
        auto_lift_minutes="Lift the lockdown by itself after this many minutes (0 = by hand)",
        young_days="During a raid, accounts younger than this many days are removed (0 = everyone)",
    )
    @localized("interaction")
    async def raid_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        joins: int = 10,
        window: int = 30,
        action: str = "lockdown",
        auto_lift_minutes: int = 30,
        young_days: int = 7,
    ) -> None:
        """Set up raid detection."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in VALID_ACTIONS and action != "lockdown":
            await interaction.response.send_message(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "raid_enabled": enabled,
                "raid_joins": max(3, joins),
                "raid_window": max(10, window),
                "raid_action": action,
                "raid_lift_minutes": max(0, min(auto_lift_minutes, 1440)),
                "raid_age_days": max(0, min(young_days, 365)),
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        embed = discord.Embed(
            title=tx("anti_spam.settings_raid_detection", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.join_threshold"),
            value=tx("anti_spam.members", v0=(joins)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.auto_lift"),
            value=(
                tx("anti_spam.after_minutes", v0=(auto_lift_minutes))
                if auto_lift_minutes > 0
                else tx("anti_spam.by_hand")
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.young_accounts"),
            value=tx("anti_spam.younger_than_days", v0=(max(0, young_days))),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.time_window"),
            value=tx("audit_log.seconds", v0=(window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(
        name="escalation", description="Set up escalating penalties"
    )
    @app_commands.describe(
        enabled="Whether penalties escalate",
        strikes="Violations before escalating",
        window="How long violations are remembered, in seconds",
    )
    @localized("interaction")
    async def escalation_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        strikes: int = 3,
        window: int = 600,
    ) -> None:
        """Set up automatic escalation."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "auto_escalate": enabled,
                "escalate_strikes": max(2, strikes),
                "escalate_window": max(60, window),
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        embed = discord.Embed(
            title=tx("anti_spam.settings_automatic_escalation", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.escalation_threshold"),
            value=tx("anti_spam.violations", v0=(strikes)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.tracking_window"),
            value=tx("audit_log.seconds", v0=(window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.how_it_works"),
            value=tx("anti_spam.reaching_the_violation_threshold_within_the"),
            inline=False,
        )
        await interaction.followup.send(embed=embed)

    async def _outside_guild(self, interaction: discord.Interaction) -> bool:
        """Answer and return True when the command was not used in a server."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return True
        return False

    async def _not_owner(self, interaction: discord.Interaction) -> bool:
        """Anti-nuke settings are the owner's: an admin could otherwise switch it off and nuke."""
        if await self._outside_guild(interaction):
            return True
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                tx("anti_spam.failed_owner_only"), ephemeral=True
            )
            return True
        return False

    async def _bad_action(
        self, interaction: discord.Interaction, action: str, allowed: list[str]
    ) -> bool:
        if action in allowed:
            return False
        await interaction.response.send_message(
            tx(
                "anti_spam.failed_invalid_action_available_actions",
                v0=(", ".join(allowed)),
            ),
            ephemeral=True,
        )
        return True

    async def _saved(
        self,
        interaction: discord.Interaction,
        title: str,
        fields: list[tuple[str, str]],
    ) -> None:
        embed = discord.Embed(title=title, color=GREEN)
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(
        name="similar",
        description="Set up detection of similar messages across channels and accounts",
    )
    @app_commands.describe(
        enabled="Whether it is on",
        channels="Channels one member posts alike messages in before it triggers",
        users="Accounts posting alike messages before it triggers",
        window="Time window in seconds",
        action="What to do",
    )
    @localized("interaction")
    async def similar_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        channels: int = 3,
        users: int = 4,
        window: int = 30,
        action: str = "mute",
    ) -> None:
        """Set up detection of similar content across channels and accounts."""
        if await self._outside_guild(interaction) or await self._bad_action(
            interaction, action, VALID_ACTIONS
        ):
            return
        await interaction.response.defer()
        channels, users, window = (
            max(2, channels),
            max(2, users),
            max(5, min(window, 600)),
        )
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "similar_enabled": enabled,
                "similar_channels": channels,
                "similar_users": users,
                "similar_window": window,
                "similar_action": action,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        await self._saved(
            interaction,
            tx("anti_spam.settings_similar_detection", v0=(status)),
            [
                (tx("anti_spam.channels_threshold"), str(channels)),
                (tx("anti_spam.accounts_threshold"), str(users)),
                (tx("anti_spam.time_window"), tx("audit_log.seconds", v0=(window))),
                (tx("anti_spam.action"), action_name(action, action)),
            ],
        )

    @anti_spam_group.command(
        name="attachment", description="Set up attachment and sticker spam detection"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        limit="Most attachments and stickers allowed in the time window",
        window="Time window in seconds",
        action="What to do",
    )
    @localized("interaction")
    async def attachment_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 8,
        window: int = 15,
        action: str = "delete",
    ) -> None:
        """Set up attachment and sticker spam detection."""
        if await self._outside_guild(interaction) or await self._bad_action(
            interaction, action, VALID_ACTIONS
        ):
            return
        await interaction.response.defer()
        limit, window = max(2, limit), max(5, min(window, 600))
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "attachment_enabled": enabled,
                "attachment_limit": limit,
                "attachment_window": window,
                "attachment_action": action,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        await self._saved(
            interaction,
            tx("anti_spam.settings_attachment_detection", v0=(status)),
            [
                (tx("anti_spam.attachment_limit"), tx("anti_spam.items", v0=(limit))),
                (tx("anti_spam.time_window"), tx("audit_log.seconds", v0=(window))),
                (tx("anti_spam.action"), action_name(action, action)),
            ],
        )

    @anti_spam_group.command(
        name="phishing", description="Set up malicious link detection"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        action="What to do besides deleting the message",
    )
    @localized("interaction")
    async def phishing_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        action: str = "mute",
    ) -> None:
        """Set up malicious link detection."""
        if await self._outside_guild(interaction) or await self._bad_action(
            interaction, action, VALID_ACTIONS
        ):
            return
        await interaction.response.defer()
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {"phishing_enabled": enabled, "phishing_action": action},
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        await self._saved(
            interaction,
            tx("anti_spam.settings_phishing_detection", v0=(status)),
            [(tx("anti_spam.action"), action_name(action, action))],
        )

    @anti_spam_group.command(
        name="domain", description="Trust or block a link domain for this server"
    )
    @app_commands.describe(
        kind="allow (never flagged) or block (always flagged)",
        action="add or remove",
        domain="The domain, like example.com",
    )
    @localized("interaction")
    async def domain_cmd(
        self,
        interaction: discord.Interaction,
        kind: str,
        action: str,
        domain: str,
    ) -> None:
        """Manage this server's domain allow and block lists."""
        if await self._outside_guild(interaction):
            return
        host = link_host(domain if "://" in domain else "https://" + domain.strip())
        if kind not in ("allow", "block") or action not in ("add", "remove"):
            await interaction.response.send_message(
                tx("anti_spam.failed_domain_usage"), ephemeral=True
            )
            return
        if "." not in host or len(host) > 253:
            await interaction.response.send_message(
                tx("anti_spam.failed_invalid_domain"), ephemeral=True
            )
            return
        await interaction.response.defer()
        key = "allowed_domains" if kind == "allow" else "blocked_domains"
        changed = await run_storage(
            self.manager.update_list, interaction.guild_id, key, action, host
        )
        if not changed:
            await interaction.followup.send(
                tx("anti_spam.info_no_changes"), ephemeral=True
            )
            return
        verb = tx("anti_spam.added") if action == "add" else tx("anti_spam.removed")
        listed = (
            tx("anti_spam.allowed_domains")
            if kind == "allow"
            else tx("anti_spam.blocked_domains")
        )
        await self._saved(
            interaction,
            tx("anti_spam.settings_domain_list_updated"),
            [(listed, f"{verb} `{host}`")],
        )

    @anti_spam_group.command(
        name="new_account",
        description="Set up what happens to very new accounts that join",
    )
    @app_commands.describe(
        hours="Accounts younger than this many hours are caught (0 = off)",
        action="What to do (kick recommended)",
    )
    @localized("interaction")
    async def new_account_cmd(
        self,
        interaction: discord.Interaction,
        hours: int = 0,
        action: str = "kick",
    ) -> None:
        """Set the new-account threshold."""
        allowed = [ACTION_WARN, ACTION_MUTE, ACTION_KICK, ACTION_BAN]
        if await self._outside_guild(interaction) or await self._bad_action(
            interaction, action, allowed
        ):
            return
        await interaction.response.defer()
        hours = max(0, min(hours, 24 * 90))
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {"new_account_hours": hours, "new_account_action": action},
        )
        await self._saved(
            interaction,
            tx("anti_spam.settings_new_account_updated"),
            [
                (
                    tx("anti_spam.young_accounts"),
                    (
                        tx("anti_spam.younger_than_hours", v0=(hours))
                        if hours
                        else tx("anti_spam.off")
                    ),
                ),
                (tx("anti_spam.action"), action_name(action, action)),
            ],
        )

    @anti_spam_group.command(
        name="nuke", description="Set up anti-nuke (server owner only)"
    )
    @app_commands.describe(
        enabled="Whether it is on",
        limit="Dangerous actions by one member before it triggers",
        window="Time window in seconds",
        action="strip (take their roles), kick or ban",
    )
    @localized("interaction")
    async def nuke_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 5,
        window: int = 30,
        action: str = NUKE_STRIP,
    ) -> None:
        """Set up anti-nuke (server owner only)."""
        if await self._not_owner(interaction) or await self._bad_action(
            interaction, action, NUKE_ACTIONS
        ):
            return
        await interaction.response.defer()
        limit, window = max(2, min(limit, 50)), max(5, min(window, 600))
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {
                "nuke_enabled": enabled,
                "nuke_limit": limit,
                "nuke_window": window,
                "nuke_action": action,
            },
        )
        status = tx("anti_spam.enable") if enabled else tx("anti_spam.disable")
        await self._saved(
            interaction,
            tx("anti_spam.settings_nuke", v0=(status)),
            [
                (tx("anti_spam.nuke_threshold"), tx("anti_spam.times", v0=(limit))),
                (tx("anti_spam.time_window"), tx("audit_log.seconds", v0=(window))),
                (tx("anti_spam.action"), action_name(action, action)),
            ],
        )

    @anti_spam_group.command(
        name="nuke_trust",
        description="Let a member or bot skip anti-nuke (server owner only)",
    )
    @app_commands.describe(action="add or remove", user="The member or bot")
    @localized("interaction")
    async def nuke_trust_cmd(
        self, interaction: discord.Interaction, action: str, user: discord.User
    ) -> None:
        """Manage the anti-nuke trusted list (server owner only)."""
        if await self._not_owner(interaction):
            return
        if action not in ("add", "remove"):
            await interaction.response.send_message(
                tx("anti_spam.failed_action_must_be_add_or"), ephemeral=True
            )
            return
        await interaction.response.defer()
        changed = await run_storage(
            self.manager.update_list,
            interaction.guild_id,
            "nuke_trusted",
            action,
            user.id,
        )
        if not changed:
            await interaction.followup.send(
                tx("anti_spam.info_no_changes"), ephemeral=True
            )
            return
        verb = tx("anti_spam.added") if action == "add" else tx("anti_spam.removed")
        await self._saved(
            interaction,
            tx("anti_spam.settings_nuke_trust_updated"),
            [(tx("anti_spam.nuke_trusted"), f"{verb} {user.mention}")],
        )

    @anti_spam_group.command(
        name="nuke_restore",
        description="Give back the roles anti-nuke took (server owner only)",
    )
    @app_commands.describe(member="The member whose roles were taken")
    @localized("interaction")
    async def nuke_restore_cmd(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Give back the roles anti-nuke took (server owner only)."""
        if await self._not_owner(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        role_ids = await run_storage(self.manager.get_strip, guild.id, member.id)
        if not role_ids:
            await interaction.followup.send(
                tx("anti_spam.info_nothing_to_restore"), ephemeral=True
            )
            return
        roles = [
            role
            for role_id in role_ids
            if (role := guild.get_role(role_id)) is not None
            and role < guild.me.top_role
        ]
        try:
            if roles:
                await member.add_roles(
                    *roles, reason=tx("anti_spam.nuke_restore_reason")
                )
        except discord.HTTPException:
            await interaction.followup.send(
                tx("anti_spam.bot_lacks_permission"), ephemeral=True
            )
            return
        await run_storage(self.manager.save_strip, guild.id, member.id, [])
        await interaction.followup.send(
            tx(
                "anti_spam.success_roles_restored",
                v0=(member.mention),
                v1=(len(roles)),
                v2=(len(role_ids) - len(roles)),
            ),
            ephemeral=True,
        )

    @anti_spam_group.command(name="whitelist", description="Manage the allow list")
    @app_commands.describe(
        action="add or remove",
        role="The role to add or remove",
        channel="The channel to add or remove",
    )
    @localized("interaction")
    async def whitelist_cmd(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role | None = None,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Manage the whitelist."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if action not in ("add", "remove"):
            await interaction.response.send_message(
                tx("anti_spam.failed_action_must_be_add_or"), ephemeral=True
            )
            return
        if not role and not channel:
            await interaction.response.send_message(
                tx("anti_spam.failed_specify_a_role_or_channel"), ephemeral=True
            )
            return

        await interaction.response.defer()
        changed = await run_storage(
            self.manager.update_whitelist,
            interaction.guild_id,
            action,
            role.id if role else None,
            channel.id if channel else None,
        )
        verb = tx("anti_spam.added") if action == "add" else tx("anti_spam.removed")
        changes = []
        if "roles" in changed:
            changes.append(tx("anti_spam.role_allowlist", v0=(verb), v1=(role.mention)))
        if "channels" in changed:
            changes.append(
                tx("anti_spam.channel_allowlist", v0=(verb), v1=(channel.mention))
            )

        if not changes:
            await interaction.followup.send(
                tx("anti_spam.info_no_changes"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("anti_spam.settings_allowlist_updated"),
            description="\n".join(changes),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="lockdown_off", description="Lift a lockdown")
    @localized("interaction")
    async def lockdown_off_cmd(self, interaction: discord.Interaction) -> None:
        """Lift the lockdown by hand."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        locked = self.manager.is_lockdown(interaction.guild_id)
        if not locked and not self.manager.raid_active(interaction.guild_id):
            await interaction.response.send_message(
                tx("anti_spam.info_lockdown_is_not_active"), ephemeral=True
            )
            return

        await interaction.response.defer()
        if not locked:
            # A raid set to kick or ban locks nothing, yet it can run on with no end.
            self.manager.end_raid(interaction.guild_id)
            await interaction.followup.send(
                embed=discord.Embed(
                    title=tx("anti_spam.success_raid_mode_ended"), color=GREEN
                )
            )
            await self._send_log(
                interaction.guild_id,
                discord.Embed(
                    title=tx("anti_spam.success_raid_mode_ended"),
                    description=tx(
                        "anti_spam.lifted_by", v0=(interaction.user.mention)
                    ),
                    color=GREEN,
                ),
            )
            return
        left = await self._deactivate_lockdown(interaction.guild)
        if left:
            await interaction.followup.send(embed=self._still_locked(left))
            await self._send_log(interaction.guild_id, self._still_locked(left))
            return

        embed = discord.Embed(
            title=tx("anti_spam.success_lockdown_lifted"),
            description=tx("anti_spam.channel_sending_permissions_have_been_restored"),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

        await self._send_log(
            interaction.guild_id,
            discord.Embed(
                title=tx("anti_spam.spam_protection_lockdown_manually_lifted"),
                description=tx("anti_spam.lifted_by", v0=(interaction.user.mention)),
                color=discord.Color.from_rgb(46, 204, 113),
            ),
        )

    @anti_spam_group.command(
        name="status", description="Show the full spam protection status"
    )
    @localized("interaction")
    async def status_cmd(self, interaction: discord.Interaction) -> None:
        """Show the full anti-raid settings."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        s = self.manager.get_settings(interaction.guild_id)

        main_status = (
            tx("anti_spam.enabled") if s["enabled"] else tx("anti_spam.disabled")
        )
        lockdown = (
            tx("anti_spam.active")
            if self.manager.is_lockdown(interaction.guild_id)
            else tx("anti_spam.normal")
        )

        embed = discord.Embed(
            title=tx("anti_spam.status_spam_protection"),
            description=tx(
                "anti_spam.system_lockdown", v0=(main_status), v1=(lockdown)
            ),
            color=discord.Color.from_rgb(52, 152, 219),
        )

        # Flood
        embed.add_field(
            name=tx("anti_spam.message_flood"),
            value=tx(
                "anti_spam.messages_s",
                v0=(s["flood_messages"]),
                v1=(s["flood_window"]),
                v2=(action_name(s["flood_action"])),
            ),
            inline=True,
        )

        # Duplicates
        dup_st = tx("anti_spam.on") if s["duplicate_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.duplicate_content", v0=(dup_st)),
            value=tx(
                "anti_spam.times_s",
                v0=(s["duplicate_count"]),
                v1=(s["duplicate_window"]),
                v2=(action_name(s["duplicate_action"])),
            ),
            inline=True,
        )

        # Mentions
        men_st = tx("anti_spam.on") if s["mention_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.mention_spam", v0=(men_st)),
            value=tx(
                "anti_spam.per_message",
                v0=(s["mention_limit"]),
                v1=(action_name(s["mention_action"])),
            ),
            inline=True,
        )

        # Links
        link_st = tx("anti_spam.on") if s["link_enabled"] else tx("anti_spam.off")
        inv = tx("anti_spam.yes") if s["invite_auto_delete"] else tx("anti_spam.no")
        embed.add_field(
            name=tx("anti_spam.link_spam", v0=(link_st)),
            value=tx(
                "anti_spam.links_s_delete_invites",
                v0=(s["link_limit"]),
                v1=(s["link_window"]),
                v2=(action_name(s["link_action"])),
                v3=(inv),
            ),
            inline=True,
        )

        # Emoji
        emo_st = tx("anti_spam.on") if s["emoji_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.emoji_spam", v0=(emo_st)),
            value=tx(
                "anti_spam.per_message",
                v0=(s["emoji_limit"]),
                v1=(action_name(s["emoji_action"])),
            ),
            inline=True,
        )

        # Line breaks
        nl_st = tx("anti_spam.on") if s["newline_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.line_break_spam", v0=(nl_st)),
            value=tx(
                "anti_spam.lines_per_message",
                v0=(s["newline_limit"]),
                v1=(action_name(s["newline_action"])),
            ),
            inline=True,
        )

        # Raid
        raid_st = tx("anti_spam.on") if s["raid_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.raid_detection", v0=(raid_st)),
            value=tx(
                "anti_spam.members_s",
                v0=(s["raid_joins"]),
                v1=(s["raid_window"]),
                v2=(action_name(s["raid_action"])),
            ),
            inline=True,
        )

        # Cross-channel and multi-account
        sim_st = tx("anti_spam.on") if s["similar_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.similar_status", v0=(sim_st)),
            value=tx(
                "anti_spam.similar_status_value",
                v0=(s["similar_channels"]),
                v1=(s["similar_users"]),
                v2=(s["similar_window"]),
                v3=(action_name(s["similar_action"])),
            ),
            inline=True,
        )

        # Attachments
        att_st = tx("anti_spam.on") if s["attachment_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.attachment_status", v0=(att_st)),
            value=tx(
                "anti_spam.times_s",
                v0=(s["attachment_limit"]),
                v1=(s["attachment_window"]),
                v2=(action_name(s["attachment_action"])),
            ),
            inline=True,
        )

        # Malicious links
        ph_st = tx("anti_spam.on") if s["phishing_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.phishing_status", v0=(ph_st)),
            value=tx(
                "anti_spam.phishing_status_value",
                v0=(action_name(s["phishing_action"])),
                v1=(len(s["allowed_domains"])),
                v2=(len(s["blocked_domains"])),
            ),
            inline=True,
        )

        # New accounts and during a raid
        embed.add_field(
            name=tx("anti_spam.young_accounts"),
            value=tx(
                "anti_spam.young_status_value",
                v0=(
                    tx("anti_spam.younger_than_hours", v0=(s["new_account_hours"]))
                    if s["new_account_hours"]
                    else tx("anti_spam.off")
                ),
                v1=(action_name(s["new_account_action"])),
                v2=(s["raid_age_days"]),
                v3=(
                    tx("anti_spam.after_minutes", v0=(s["raid_lift_minutes"]))
                    if s["raid_lift_minutes"]
                    else tx("anti_spam.by_hand")
                ),
            ),
            inline=True,
        )

        # Anti-nuke
        nuke_st = tx("anti_spam.on") if s["nuke_enabled"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.nuke_status", v0=(nuke_st)),
            value=tx(
                "anti_spam.nuke_status_value",
                v0=(s["nuke_limit"]),
                v1=(s["nuke_window"]),
                v2=(action_name(s["nuke_action"])),
                v3=(len(s["nuke_trusted"])),
            ),
            inline=True,
        )

        # Automatic escalation
        esc_st = tx("anti_spam.on") if s["auto_escalate"] else tx("anti_spam.off")
        embed.add_field(
            name=tx("anti_spam.automatic_escalation", v0=(esc_st)),
            value=tx(
                "anti_spam.times_s_271f02",
                v0=(s["escalate_strikes"]),
                v1=(s["escalate_window"]),
            ),
            inline=True,
        )

        # Whitelist
        roles = [f"<@&{r}>" for r in s["whitelisted_roles"]] or [tx("audit_log.none")]
        channels = [f"<#{c}>" for c in s["whitelisted_channels"]] or [
            tx("audit_log.none")
        ]
        embed.add_field(
            name=tx("settings.allowlist"),
            value=tx(
                "anti_spam.roles_channels",
                v0=(", ".join(roles)),
                v1=(", ".join(channels)),
            ),
            inline=False,
        )

        embed.set_footer(
            text=tx(
                "anti_spam.mute_duration_s_message_deletion_on",
                v0=(s["mute_duration"]),
                v1=(s["ban_delete_days"]),
            )
        )

        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="mute_duration", description="Set the timeout length")
    @app_commands.describe(seconds="Timeout in seconds (default 3600 = 1 hour)")
    @localized("interaction")
    async def mute_duration_cmd(
        self, interaction: discord.Interaction, seconds: int = 3600
    ) -> None:
        """Set the timeout length."""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        sec = max(60, min(seconds, 2419200))  # 60s ~ 28d
        await run_storage(
            self.manager.update_settings,
            interaction.guild_id,
            {"mute_duration": sec},
        )
        embed = discord.Embed(
            title=tx("anti_spam.settings_mute_duration_updated"),
            description=tx(
                "anti_spam.mute_duration_seconds_h_m",
                v0=(sec),
                v1=(sec // 3600),
                v2=((sec % 3600) // 60),
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

    # ── Old commands kept for compatibility ───────────────────────────

    @commands.hybrid_command(
        name="anti_spam_set", description="Quick spam protection setup (legacy)"
    )
    @commands.has_permissions(administrator=True)
    @localized("ctx")
    async def anti_spam_set_legacy(
        self,
        ctx: commands.Context[Any],
        enabled: bool = True,
        messages_per_window: int = 10,
        window_seconds: int = 10,
        action: str = "mute",
    ) -> None:
        """The old settings command, kept for compatibility."""
        if action not in VALID_ACTIONS:
            await ctx.send(
                tx(
                    "anti_spam.failed_invalid_action_available_actions",
                    v0=(", ".join(VALID_ACTIONS)),
                ),
                ephemeral=True,
            )
            return

        await run_storage(
            self.manager.update_settings,
            ctx.guild.id,
            {
                "enabled": enabled,
                "flood_messages": max(1, messages_per_window),
                "flood_window": max(1, window_seconds),
                "flood_action": action,
            },
        )

        status = tx("anti_spam.enabled") if enabled else tx("anti_spam.disabled")
        embed = discord.Embed(
            title=tx("anti_spam.settings_spam_protection", v0=(status)),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("anti_spam.time_window"),
            value=tx("audit_log.seconds", v0=(window_seconds)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.message_limit_7e55ac"),
            value=tx("anti_spam.messages", v0=(messages_per_window)),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"), value=action_name(action, action), inline=True
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="anti_spam_status", description="Show spam protection status (legacy)"
    )
    @commands.has_permissions(administrator=True)
    @localized("ctx")
    async def anti_spam_status_legacy(self, ctx: commands.Context[Any]) -> None:
        """The old status command, kept for compatibility."""
        s = self.manager.get_settings(ctx.guild.id)
        status = tx("anti_spam.enabled") if s["enabled"] else tx("anti_spam.disabled")

        embed = discord.Embed(
            title=tx("anti_spam.info_spam_protection_status"),
            description=tx("anti_spam.use_anti_spam_status_to_view"),
            color=discord.Color.from_rgb(52, 152, 219),
        )
        embed.add_field(name=tx("blacklist.status"), value=status, inline=True)
        embed.add_field(
            name=tx("settings.flood_detection"),
            value=tx(
                "anti_spam.messages_s_0c1e04",
                v0=(s["flood_messages"]),
                v1=(s["flood_window"]),
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("anti_spam.action"),
            value=action_name(s["flood_action"], s["flood_action"]),
            inline=True,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(AntiSpam(bot))
