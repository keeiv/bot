from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from src.services.temp_voice_service import TempVoiceService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage

if TYPE_CHECKING:
    from src.bot import Bot

TZ_OFFSET = timezone(timedelta(hours=8))
ENVC_PREFIX = "envc*"

_service = TempVoiceService()


class TempVoice(commands.Cog):
    """暫時語音頻道系統"""

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.service = _service

    # ─────────────────── 管理員斜線指令 ───────────────────

    temp_voice = app_commands.Group(
        name="temp_voice",
        description="Temporary voice channels (admins only)",
    )

    @temp_voice.command(
        name="setup", description="Set the channel that creates temporary voice rooms"
    )
    @app_commands.describe(
        trigger="Joining this channel creates a temporary voice room",
        category="Category for new rooms (defaults to the trigger channel's)",
        name_template="Room name; {username} is replaced by the member's name",
    )
    @localized("interaction")
    async def setup(
        self,
        interaction: discord.Interaction,
        trigger: discord.VoiceChannel,
        category: Optional[discord.CategoryChannel] = None,
        name_template: Optional[str] = None,
    ) -> None:
        """設定暫時語音頻道觸發房間"""
        await interaction.response.defer(thinking=True, ephemeral=False)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("temp_voice.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        name_template = name_template or tx("temp_voice.s_room")
        if len(name_template) > 100:
            await interaction.followup.send(
                tx("temp_voice.failed_the_name_template_must_not"), ephemeral=True
            )
            return

        resolved_category_id = category.id if category else trigger.category_id

        await run_storage(
            self.service.save_guild_config,
            guild_id=interaction.guild.id,
            trigger_channel_id=trigger.id,
            category_id=resolved_category_id,
            name_template=name_template,
        )

        category_display = (
            category.name
            if category
            else (
                trigger.category.name
                if trigger.category
                else tx("temp_voice.no_category_root")
            )
        )

        embed = discord.Embed(
            title=tx("temp_voice.success_temporary_voice_channels_configured"),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("temp_voice.trigger_channel"), value=trigger.mention, inline=True
        )
        embed.add_field(
            name=tx("temp_voice.channel_category"), value=category_display, inline=True
        )
        embed.add_field(
            name=tx("temp_voice.name_template"),
            value=tx(
                "temp_voice.example",
                v0=(name_template),
                v1=(name_template.replace("{username}", interaction.user.display_name)),
            ),
            inline=False,
        )
        embed.add_field(
            name=tx("temp_voice.user_command_prefix"),
            value=tx(
                "temp_voice.use_help_for_instructions",
                v0=(ENVC_PREFIX),
                v1=(ENVC_PREFIX),
            ),
            inline=False,
        )
        embed.set_footer(
            text=tx(
                "temp_voice.configured_by_server",
                v0=(interaction.user),
                v1=(interaction.guild.name),
            )
        )
        await interaction.followup.send(embed=embed)

    @temp_voice.command(
        name="status", description="Show this server's temporary voice settings"
    )
    @localized("interaction")
    async def status(self, interaction: discord.Interaction) -> None:
        """顯示暫時語音頻道系統設定狀態"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("temp_voice.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        config = await run_storage(self.service.get_guild_config, interaction.guild.id)
        if not config:
            await interaction.followup.send(
                tx("temp_voice.info_temporary_voice_channels_are_not"),
                ephemeral=True,
            )
            return

        trigger_ch = interaction.guild.get_channel(config["trigger_channel_id"])
        category_id = config.get("category_id")
        category = interaction.guild.get_channel(category_id) if category_id else None
        active_channels = await run_storage(
            self.service.get_guild_channels, interaction.guild.id
        )

        embed = discord.Embed(
            title=tx("temp_voice.info_temporary_voice_channel_status"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("temp_voice.trigger_channel"),
            value=(
                trigger_ch.mention
                if trigger_ch
                else tx("temp_voice.deleted_id", v0=(config["trigger_channel_id"]))
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("temp_voice.channel_category"),
            value=category.name if category else tx("temp_voice.no_category_root"),
            inline=True,
        )
        embed.add_field(
            name=tx("temp_voice.name_template"),
            value=tx(
                "temp_voice.value",
                v0=(config.get("name_template", tx("temp_voice.s_room"))),
            ),
            inline=True,
        )
        embed.add_field(
            name=tx("temp_voice.active_temporary_channels"),
            value=str(len(active_channels)),
            inline=True,
        )
        embed.set_footer(text=tx("temp_voice.server", v0=(interaction.guild.name)))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @temp_voice.command(
        name="disable", description="Turn off temporary voice channels in this server"
    )
    @localized("interaction")
    async def disable(self, interaction: discord.Interaction) -> None:
        """停用暫時語音頻道系統"""
        await interaction.response.defer(thinking=True, ephemeral=False)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("temp_voice.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        config = await run_storage(self.service.get_guild_config, interaction.guild.id)
        if not config:
            await interaction.followup.send(
                tx("temp_voice.info_temporary_voice_channels_are_not_c97b22"),
                ephemeral=True,
            )
            return

        await run_storage(self.service.remove_guild_config, interaction.guild.id)
        await interaction.followup.send(
            tx("temp_voice.success_temporary_voice_channels_disabled_in")
        )

    # ─────────────────── 事件監聽 ───────────────────

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """啟動時清理殘留的暫時頻道記錄"""
        all_ids = await run_storage(self.service.get_all_channel_ids)
        if not all_ids:
            return

        valid_ids: set[int] = set()
        for channel_id in all_ids:
            ch = self.bot.get_channel(channel_id)
            if ch is not None:
                valid_ids.add(channel_id)

        removed = await run_storage(self.service.remove_stale_channels, valid_ids)
        if removed:
            print(f"[TempVoice] 啟動清理：已移除 {removed} 筆殘留頻道記錄")

    @commands.Cog.listener()
    @localized("member")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """監聽語音狀態：觸發建立、偵測空頻道刪除"""
        guild = member.guild
        config = await run_storage(self.service.get_guild_config, guild.id)

        # ── 使用者加入觸發頻道 → 建立暫時頻道 ──
        if (
            config
            and after.channel
            and after.channel.id == config["trigger_channel_id"]
        ):
            await self._create_temp_channel(member, guild, config)

        # ── 使用者離開頻道 → 若頻道為空則刪除 ──
        if before.channel and before.channel.id != (
            config["trigger_channel_id"] if config else None
        ):
            ch_data = await run_storage(self.service.get_channel, before.channel.id)
            if ch_data and len(before.channel.members) == 0:
                await run_storage(self.service.remove_channel, before.channel.id)
                try:
                    await before.channel.delete(
                        reason=tx(
                            "temp_voice.empty_temporary_voice_channel_deleted_automatically"
                        )
                    )
                except discord.HTTPException:
                    pass

    async def _create_temp_channel(
        self,
        member: discord.Member,
        guild: discord.Guild,
        config: dict[Any, Any],
    ) -> None:
        """建立暫時語音頻道並將成員移入"""
        template = config.get("name_template", tx("temp_voice.s_room"))
        channel_name = template.replace("{username}", member.display_name)

        category_id = config.get("category_id")
        category = guild.get_channel(category_id) if category_id else None

        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=(
                    category if isinstance(category, discord.CategoryChannel) else None
                ),
                reason=tx(
                    "temp_voice.temporary_voice_channel_created",
                    v0=(member),
                    v1=(member.id),
                ),
            )
            # 給創立者頻道管理權限
            await new_channel.set_permissions(
                member,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            await run_storage(
                self.service.save_channel,
                channel_id=new_channel.id,
                guild_id=guild.id,
                owner_id=member.id,
            )
            await member.move_to(
                new_channel, reason=tx("temp_voice.moved_to_temporary_voice_channel")
            )
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    # ─────────────────── envc* 前綴指令處理 ───────────────────

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """處理 envc* 前綴指令"""
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content.startswith(ENVC_PREFIX):
            return

        if await self.bot.blacklist_manager.check(message.author.id):
            return

        content = message.content[len(ENVC_PREFIX) :].strip()
        parts = content.split(maxsplit=1)
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        handlers = {
            "help": self._cmd_help,
            "name": self._cmd_name,
            "limit": self._cmd_limit,
            "bitrate": self._cmd_bitrate,
            "hide": self._cmd_hide,
            "unhide": self._cmd_unhide,
            "lock": self._cmd_lock,
            "unlock": self._cmd_unlock,
            "kick": self._cmd_kick,
            "ban": self._cmd_ban,
            "unban": self._cmd_unban,
            "transfer": self._cmd_transfer,
            "claim": self._cmd_claim,
        }

        handler = handlers.get(cmd)
        if handler:
            await handler(message, args)
        else:
            await message.reply(
                tx(
                    "temp_voice.failed_unknown_command_use_help_to",
                    v0=(ENVC_PREFIX),
                    v1=(cmd),
                    v2=(ENVC_PREFIX),
                ),
                mention_author=False,
            )

    # ─────────────── 輔助函式 ───────────────

    def _get_user_owned_channel(
        self, member: discord.Member
    ) -> Optional[tuple[discord.VoiceChannel, dict[Any, Any]]]:
        """取得使用者目前所在且擁有的暫時語音頻道"""
        voice = member.voice
        if not voice or not voice.channel:
            return None
        ch_data = self.service.get_channel(voice.channel.id)
        if not ch_data:
            return None
        if ch_data["owner_id"] != member.id:
            return None
        return voice.channel, ch_data  # type: ignore[return-value]

    def _get_user_in_temp_channel(
        self, member: discord.Member
    ) -> Optional[tuple[discord.VoiceChannel, dict[Any, Any]]]:
        """取得使用者目前所在的暫時語音頻道（不限擁有者）"""
        voice = member.voice
        if not voice or not voice.channel:
            return None
        ch_data = self.service.get_channel(voice.channel.id)
        if not ch_data:
            return None
        return voice.channel, ch_data  # type: ignore[return-value]

    # ─────────────── 指令實作 ───────────────

    async def _cmd_help(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        embed = discord.Embed(
            title=tx("temp_voice.help_temporary_voice_channel_commands"),
            description=(
                tx("temp_voice.these_commands_apply_to_a_temporary", v0=(ENVC_PREFIX))
            ),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("temp_voice.basic_settings"),
            value=(
                tx(
                    "temp_voice.name_name_rename_the_channel_limit",
                    v0=(ENVC_PREFIX),
                    v1=(ENVC_PREFIX),
                    v2=(ENVC_PREFIX),
                )
            ),
            inline=False,
        )
        embed.add_field(
            name=tx("temp_voice.privacy_settings"),
            value=(
                tx(
                    "temp_voice.hide_hide_the_channel_unhide_make",
                    v0=(ENVC_PREFIX),
                    v1=(ENVC_PREFIX),
                    v2=(ENVC_PREFIX),
                    v3=(ENVC_PREFIX),
                )
            ),
            inline=False,
        )
        embed.add_field(
            name=tx("temp_voice.participant_management"),
            value=(
                tx(
                    "temp_voice.kick_member_disconnect_a_member_ban",
                    v0=(ENVC_PREFIX),
                    v1=(ENVC_PREFIX),
                    v2=(ENVC_PREFIX),
                )
            ),
            inline=False,
        )
        embed.add_field(
            name=tx("temp_voice.ownership_management"),
            value=(
                tx(
                    "temp_voice.transfer_member_transfer_ownership_to_a",
                    v0=(ENVC_PREFIX),
                    v1=(ENVC_PREFIX),
                )
            ),
            inline=False,
        )
        embed.set_footer(
            text=tx(
                "temp_voice.server_commands_apply_to_the_current",
                v0=(message.guild.name),
            )
        )
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_name(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not args:
            await message.reply(
                tx("temp_voice.failed_provide_a_new_name_for", v0=(ENVC_PREFIX)),
                mention_author=False,
            )
            return
        if len(args) > 100:
            await message.reply(
                tx("temp_voice.failed_the_channel_name_must_not"), mention_author=False
            )
            return

        try:
            await channel.edit(name=args)
            await message.reply(
                tx("temp_voice.success_channel_renamed_to", v0=(args)),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_lacks_permission_to"),
                mention_author=False,
            )
        except discord.HTTPException as e:
            await message.reply(
                tx("temp_voice.failed_update_failed_discord_error", v0=(e)),
                mention_author=False,
            )

    async def _cmd_limit(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not args.isdigit():
            await message.reply(
                tx("temp_voice.failed_enter_a_valid_number_for", v0=(ENVC_PREFIX)),
                mention_author=False,
            )
            return
        limit = int(args)
        if limit < 0 or limit > 99:
            await message.reply(
                tx("temp_voice.failed_the_member_limit_must_be"), mention_author=False
            )
            return

        try:
            await channel.edit(user_limit=limit)
            limit_text = (
                tx("anti_spam.members", v0=(limit))
                if limit > 0
                else tx("audit_log.unlimited")
            )
            await message.reply(
                tx("temp_voice.success_channel_member_limit", v0=(limit_text)),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_lacks_permission_to"),
                mention_author=False,
            )
        except discord.HTTPException as e:
            await message.reply(
                tx("temp_voice.failed_update_failed_discord_error", v0=(e)),
                mention_author=False,
            )

    async def _cmd_bitrate(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not args.isdigit():
            await message.reply(
                tx(
                    "temp_voice.failed_enter_a_valid_number_for_29f742",
                    v0=(ENVC_PREFIX),
                ),
                mention_author=False,
            )
            return
        bitrate = int(args)

        # 依伺服器加成等級決定上限
        max_bitrate = message.guild.bitrate_limit // 1000
        if bitrate < 8 or bitrate > max_bitrate:
            await message.reply(
                tx("temp_voice.failed_bitrate_must_be_between_8", v0=(max_bitrate)),
                mention_author=False,
            )
            return

        try:
            await channel.edit(bitrate=bitrate * 1000)
            await message.reply(
                tx("temp_voice.success_channel_bitrate_kbps", v0=(bitrate)),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_lacks_permission_to"),
                mention_author=False,
            )
        except discord.HTTPException as e:
            await message.reply(
                tx("temp_voice.failed_update_failed_discord_error", v0=(e)),
                mention_author=False,
            )

    async def _cmd_hide(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(
                message.guild.default_role, view_channel=False
            )
            await message.reply(
                tx("temp_voice.success_channel_hidden_from_other_members"),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_unhide(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(message.guild.default_role, view_channel=True)
            await message.reply(
                tx("temp_voice.success_channel_is_visible"), mention_author=False
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_lock(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(message.guild.default_role, connect=False)
            await message.reply(
                tx("temp_voice.success_channel_locked_only_invited_members"),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_unlock(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(message.guild.default_role, connect=True)
            await message.reply(
                tx("temp_voice.success_channel_unlocked_anyone_can_join"),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_kick(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                tx(
                    "temp_voice.failed_mention_the_member_to_disconnect",
                    v0=(ENVC_PREFIX),
                ),
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if not isinstance(target, discord.Member):
            await message.reply(
                tx("temp_voice.specify_a_member_of_this_server"), mention_author=False
            )
            return
        if target.id == message.author.id:
            await message.reply(
                tx("temp_voice.failed_self_kicking_is_not_allowed"),
                mention_author=False,
            )
            return

        if (
            target.voice
            and target.voice.channel
            and target.voice.channel.id == channel.id
        ):
            try:
                await target.move_to(
                    None,
                    reason=tx(
                        "temp_voice.temporary_voice_channel_kick_by",
                        v0=(message.author),
                        v1=(message.author.id),
                    ),
                )
                await message.reply(
                    tx(
                        "temp_voice.success_disconnected_from_the_channel",
                        v0=(target.mention),
                    ),
                    mention_author=False,
                )
            except discord.Forbidden:
                await message.reply(
                    tx("temp_voice.failed_the_bot_lacks_the_move"), mention_author=False
                )
        else:
            await message.reply(
                tx("temp_voice.failed_is_not_in_this_channel", v0=(target.mention)),
                mention_author=False,
            )

    async def _cmd_ban(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                tx("temp_voice.failed_mention_the_member_to_block", v0=(ENVC_PREFIX)),
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if not isinstance(target, discord.Member):
            await message.reply(
                tx("temp_voice.specify_a_member_of_this_server"), mention_author=False
            )
            return
        if target.id == message.author.id:
            await message.reply(
                tx("temp_voice.failed_self_blocking_is_not_allowed"),
                mention_author=False,
            )
            return

        await run_storage(self.service.add_ban, channel.id, target.id)
        try:
            await channel.set_permissions(target, connect=False, view_channel=False)
            # 若目標在頻道內，一併踢出
            if (
                target.voice
                and target.voice.channel
                and target.voice.channel.id == channel.id
            ):
                await target.move_to(
                    None,
                    reason=tx(
                        "temp_voice.temporary_voice_channel_block_by",
                        v0=(message.author),
                        v1=(message.author.id),
                    ),
                )
            await message.reply(
                tx(
                    "temp_voice.success_is_blocked_from_this_channel",
                    v0=(target.mention),
                ),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_unban(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                tx("temp_voice.failed_mention_the_member_to_unblock", v0=(ENVC_PREFIX)),
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if not isinstance(target, discord.Member):
            await message.reply(
                tx("temp_voice.specify_a_member_of_this_server"), mention_author=False
            )
            return
        await run_storage(self.service.remove_ban, channel.id, target.id)
        try:
            await channel.set_permissions(target, overwrite=None)
            await message.reply(
                tx(
                    "temp_voice.success_unblocked_and_able_to_join", v0=(target.mention)
                ),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_transfer(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_owned_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary"),
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                tx("temp_voice.failed_mention_the_new_owner_for", v0=(ENVC_PREFIX)),
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if not isinstance(target, discord.Member):
            await message.reply(
                tx("temp_voice.specify_a_member_of_this_server"), mention_author=False
            )
            return
        if target.id == message.author.id:
            await message.reply(
                tx("temp_voice.failed_this_account_already_owns_the"),
                mention_author=False,
            )
            return

        if not (
            target.voice
            and target.voice.channel
            and target.voice.channel.id == channel.id
        ):
            await message.reply(
                tx("temp_voice.failed_must_be_in_this_channel", v0=(target.mention)),
                mention_author=False,
            )
            return

        await run_storage(self.service.set_owner, channel.id, target.id)
        try:
            # 移除舊擁有者的額外權限
            await channel.set_permissions(message.author, overwrite=None)
            # 給新擁有者管理員權限
            await channel.set_permissions(
                target,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            await message.reply(
                tx(
                    "temp_voice.success_channel_ownership_transferred_to",
                    v0=(target.mention),
                ),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )

    async def _cmd_claim(self, message: discord.Message, args: str) -> None:
        if message.guild is None or not isinstance(message.author, discord.Member):
            return
        result = await run_storage(self._get_user_in_temp_channel, message.author)
        if not result:
            await message.reply(
                tx("temp_voice.failed_this_command_requires_a_temporary_ea06f2"),
                mention_author=False,
            )
            return
        channel, ch_data = result

        current_owner_id = ch_data["owner_id"]
        if current_owner_id == message.author.id:
            await message.reply(
                tx("temp_voice.info_this_account_already_owns_the"),
                mention_author=False,
            )
            return

        # 確認原擁有者已不在頻道內
        owner_in_channel = any(m.id == current_owner_id for m in channel.members)
        if owner_in_channel:
            await message.reply(
                tx("temp_voice.failed_the_original_owner_is_still"),
                mention_author=False,
            )
            return

        await run_storage(self.service.set_owner, channel.id, message.author.id)
        try:
            await channel.set_permissions(
                message.author,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            await message.reply(
                tx("temp_voice.success_temporary_voice_channel_ownership_claimed"),
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply(
                tx("temp_voice.failed_the_bot_cannot_change_channel"),
                mention_author=False,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TempVoice(bot))
