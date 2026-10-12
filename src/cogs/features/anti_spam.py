from datetime import timedelta
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.anti_spam import ACTION_BAN
from src.utils.anti_spam import ACTION_DELETE
from src.utils.anti_spam import ACTION_KICK
from src.utils.anti_spam import ACTION_LOCKDOWN
from src.utils.anti_spam import ACTION_MUTE
from src.utils.anti_spam import action_name
from src.utils.anti_spam import ACTION_WARN
from src.utils.anti_spam import AntiSpamManager
from src.utils.anti_spam import create_anti_spam_log_embed
from src.utils.anti_spam import create_raid_alert_embed
from src.utils.anti_spam import detection_name
from src.utils.anti_spam import VALID_ACTIONS
from src.utils.config_manager import get_guild_log_channel
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage


class AntiSpam(commands.Cog):
    """頂級防炸群系統 Cog — 多層偵測、自動升級、突襲防護"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = AntiSpamManager()
        # guild_id -> {channel_id -> original send_messages (True/False/None)}
        self._lockdown_states: dict[int, dict[int, bool | None]] = {}

    # ───────────── 輔助方法 ─────────────

    async def _send_log(self, guild_id: int, embed: discord.Embed) -> None:
        """發送日誌到設定的頻道"""
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
        """執行懲罰動作。回傳 (success, fail_reason)。"""
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
                    pass  # DM 封鎖不影響主要動作

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

    async def _activate_lockdown(self, guild: discord.Guild) -> None:
        """啟用封鎖模式 — 鎖定所有文字頻道，并廮存原始權限"""
        if self.manager.is_lockdown(guild.id):
            return
        self.manager.set_lockdown(guild.id, True)

        default_role = guild.default_role
        channel_states: dict[int, bool | None] = {}
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(default_role)
                # 廮存原始 send_messages 狀態，以便解除時精準回復
                channel_states[channel.id] = overwrite.send_messages
                overwrite.update(send_messages=False)
                await channel.set_permissions(
                    default_role,
                    overwrite=overwrite,
                    reason=tx("anti_spam.spam_protection_raid_lockdown_activated"),
                )
            except discord.Forbidden:
                continue
        self._lockdown_states[guild.id] = channel_states

    async def _deactivate_lockdown(self, guild: discord.Guild) -> None:
        """解除封鎖模式，回復封鎖前原始權限"""
        self.manager.set_lockdown(guild.id, False)
        channel_states = self._lockdown_states.pop(guild.id, {})

        default_role = guild.default_role
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(default_role)
                # 回復到封鎖前的狀態；若無廮存則用 None (繼承伺服器預設)
                overwrite.update(send_messages=channel_states.get(channel.id))
                await channel.set_permissions(
                    default_role,
                    overwrite=overwrite,
                    reason=tx("anti_spam.spam_protection_lockdown_lifted"),
                )
            except discord.Forbidden:
                continue

    # ───────────── 事件監聽 ─────────────

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """監聽訊息 — 多層偵測"""
        if message.author.bot or message.guild is None:
            return

        # 權限跳過: 管理員與機器人無法懲罰的成員
        member = message.author
        if isinstance(member, discord.Member):
            if member.guild_permissions.administrator:
                return
            if message.guild.me.top_role <= member.top_role:
                return

        # 邀請連結快速攔截
        if self.manager.is_invite_link(message.content or "", message.guild.id):
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        triggers = self.manager.check_message(
            guild_id=message.guild.id,
            user_id=message.author.id,
            content=message.content or "",
            channel_id=message.channel.id,
            member=message.author,
        )

        if not triggers:
            return

        # 取最嚴重的動作執行
        from src.utils.anti_spam import ACTION_SEVERITY

        triggers.sort(key=lambda t: ACTION_SEVERITY.get(t[1], 0), reverse=True)
        worst_det, worst_action, worst_detail = triggers[0]
        strike_count = self.manager.get_user_strikes(
            message.guild.id, message.author.id
        )

        # 執行動作
        action_ok, fail_reason = await self._execute_action(
            worst_action, message, worst_detail, worst_det
        )

        # 發送日誌
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

        # 如果有多個觸發，列出所有
        if len(triggers) > 1:
            others = "\n".join(
                f"- {detection_name(d, d)}: {det}" for d, _, det in triggers[1:]
            )
            embed.add_field(
                name=tx("anti_spam.other_trigger"), value=others, inline=False
            )

        # 如果執行失敗，日誌標注原因
        if not action_ok:
            embed.add_field(
                name=tx("anti_spam.warning_action_failed"),
                value=fail_reason or tx("anti_spam.unknown_reason"),
                inline=False,
            )

        await self._send_log(message.guild.id, embed)

        # 對於執行成功的動作才重設紀錄，避免失敗時阐失尚未處理的違規記錄
        if action_ok:
            self.manager.reset_user(message.guild.id, message.author.id)

    @commands.Cog.listener()
    @localized("member")
    async def on_member_join(self, member: discord.Member) -> None:
        """監聽成員加入 — 突襲偵測"""
        if member.bot:
            return

        result = self.manager.check_member_join(member.guild.id)
        if not result:
            return

        det_type, action, detail = result
        s = self.manager.get_settings(member.guild.id)

        embed = create_raid_alert_embed(
            guild_name=member.guild.name,
            guild_id=member.guild.id,
            join_count=s["raid_joins"],
            window=s["raid_window"],
            action=action,
        )

        await self._send_log(member.guild.id, embed)

        if action == ACTION_LOCKDOWN:
            await self._activate_lockdown(member.guild)

    # ───────────── 指令群組 ─────────────

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
        """快速啟用/禁用"""
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
        """設定洪水偵測"""
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
        """設定重複偵測"""
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
        """設定提及偵測"""
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
        """設定連結偵測"""
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
    )
    @localized("interaction")
    async def raid_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        joins: int = 10,
        window: int = 30,
        action: str = "lockdown",
    ) -> None:
        """設定突襲偵測"""
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
        """設定自動升級"""
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
        """管理白名單"""
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
        """手動解除封鎖模式"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not self.manager.is_lockdown(interaction.guild_id):
            await interaction.response.send_message(
                tx("anti_spam.info_lockdown_is_not_active"), ephemeral=True
            )
            return

        await interaction.response.defer()
        await self._deactivate_lockdown(interaction.guild)

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
        """顯示完整防炸群設定狀態"""
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

        # 洪水
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

        # 重複
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

        # 提及
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

        # 連結
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

        # 表情
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

        # 換行
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

        # 突襲
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

        # 自動升級
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

        # 白名單
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
        """設定禁言時長"""
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

    # ───────────── 向下相容舊指令 ─────────────

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
        """向下相容的舊版設定指令"""
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
        """向下相容的舊版狀態指令"""
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
    """載入 Cog"""
    await bot.add_cog(AntiSpam(bot))
