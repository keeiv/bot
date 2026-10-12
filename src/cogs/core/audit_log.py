from datetime import datetime

import discord
from discord.ext import commands

from src.services.audit_log_service import AuditLogService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET


class AuditLog(commands.Cog):
    """伺服器審計日誌 Cog — 記錄成員、語音、角色、暱稱、頻道事件"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AuditLogService()

    async def send_log_embed(self, guild_id: int, embed: discord.Embed) -> None:
        """發送日誌 Embed 到設定的日誌頻道"""
        log_channel_id = await run_storage(self.service.get_channel_id, guild_id)
        if not log_channel_id:
            return
        try:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel is None:
                log_channel = await self.bot.fetch_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[失敗] 審計日誌發送失敗: {e}")

    # ===== 成員加入 / 離開 =====

    @commands.Cog.listener()
    @localized("member")
    async def on_member_join(self, member: discord.Member) -> None:
        """成員加入伺服器"""
        if member.bot:
            return

        embed = discord.Embed(
            title=tx("audit_log.joined_member_joined_the_server"),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.user"),
            value=f"{member.mention} ({member.id})",
            inline=False,
        )
        embed.add_field(
            name=tx("audit_log.account_created"),
            value=member.created_at.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M"),
            inline=True,
        )
        embed.add_field(
            name=tx("audit_log.server_member_count"),
            value=str(member.guild.member_count),
            inline=True,
        )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=tx("audit_log.user_941f2d", v0=(member)))

        await self.send_log_embed(member.guild.id, embed)

    @commands.Cog.listener()
    @localized("member")
    async def on_member_remove(self, member: discord.Member) -> None:
        """成員離開伺服器"""
        if member.bot:
            return

        # 計算在伺服器待了多久
        if member.joined_at:
            stay_duration = datetime.now(TZ_OFFSET) - member.joined_at.astimezone(
                TZ_OFFSET
            )
            days = stay_duration.days
            if days >= 365:
                stay_text = tx(
                    "audit_log.years_days", v0=(days // 365), v1=(days % 365)
                )
            elif days >= 1:
                stay_text = tx("audit_log.days", v0=(days))
            else:
                hours = stay_duration.seconds // 3600
                stay_text = tx("audit_log.hours", v0=(hours))
        else:
            stay_text = tx("audit_log.unknown")

        embed = discord.Embed(
            title=tx("audit_log.left_member_left_the_server"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.user"),
            value=f"{member.mention} ({member.id})",
            inline=False,
        )

        # 列出離開前的角色
        roles = [
            role.mention for role in member.roles if role != member.guild.default_role
        ]
        roles_text = ", ".join(roles) if roles else tx("audit_log.none")
        embed.add_field(
            name=tx("audit_log.roles"), value=roles_text[:1024], inline=False
        )

        embed.add_field(
            name=tx("audit_log.time_in_server"), value=stay_text, inline=True
        )
        embed.add_field(
            name=tx("audit_log.server_member_count"),
            value=str(member.guild.member_count),
            inline=True,
        )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=tx("audit_log.user_941f2d", v0=(member)))

        await self.send_log_embed(member.guild.id, embed)

    # ===== 語音頻道加入 / 離開 / 移動 =====

    @commands.Cog.listener()
    @localized("member")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """語音狀態變更"""
        if member.bot:
            return

        guild_id = member.guild.id

        # 加入語音頻道
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title=tx("audit_log.voice_joined_a_voice_channel"),
                color=discord.Color.from_rgb(52, 152, 219),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name=tx("audit_log.user"),
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.channel"),
                value=f"{after.channel.mention} ({after.channel.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.time"), value=get_current_time_str(), inline=True
            )
            embed.set_footer(text=tx("audit_log.user_941f2d", v0=(member)))
            await self.send_log_embed(guild_id, embed)

        # 離開語音頻道
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title=tx("audit_log.voice_left_a_voice_channel"),
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name=tx("audit_log.user"),
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.channel"),
                value=f"{before.channel.mention} ({before.channel.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.time"), value=get_current_time_str(), inline=True
            )
            embed.set_footer(text=tx("audit_log.user_941f2d", v0=(member)))
            await self.send_log_embed(guild_id, embed)

        # 移動語音頻道
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            embed = discord.Embed(
                title=tx("audit_log.voice_moved_between_voice_channels"),
                color=discord.Color.from_rgb(241, 196, 15),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name=tx("audit_log.user"),
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.from"),
                value=f"{before.channel.mention} ({before.channel.id})",
                inline=True,
            )
            embed.add_field(
                name=tx("audit_log.to"),
                value=f"{after.channel.mention} ({after.channel.id})",
                inline=True,
            )
            embed.add_field(
                name=tx("audit_log.time"), value=get_current_time_str(), inline=True
            )
            embed.set_footer(text=tx("audit_log.user_941f2d", v0=(member)))
            await self.send_log_embed(guild_id, embed)

    # ===== 角色變更 / 暱稱變更 =====

    @commands.Cog.listener()
    @localized("after")
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """成員資料更新（角色、暱稱）"""
        if before.bot:
            return

        guild_id = before.guild.id

        # 角色變更
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)

            if added:
                roles_text = ", ".join(role.mention for role in added)
                embed = discord.Embed(
                    title=tx("audit_log.role_role_added"),
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("audit_log.user"),
                    value=f"{after.mention} ({after.id})",
                    inline=False,
                )
                embed.add_field(
                    name=tx("audit_log.added_roles"),
                    value=roles_text[:1024],
                    inline=False,
                )
                embed.add_field(
                    name=tx("audit_log.time"),
                    value=get_current_time_str(),
                    inline=True,
                )
                embed.set_footer(text=tx("audit_log.user_941f2d", v0=(after)))
                await self.send_log_embed(guild_id, embed)

            if removed:
                roles_text = ", ".join(role.mention for role in removed)
                embed = discord.Embed(
                    title=tx("audit_log.role_role_removed"),
                    color=discord.Color.from_rgb(231, 76, 60),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("audit_log.user"),
                    value=f"{after.mention} ({after.id})",
                    inline=False,
                )
                embed.add_field(
                    name=tx("audit_log.removed_roles"),
                    value=roles_text[:1024],
                    inline=False,
                )
                embed.add_field(
                    name=tx("audit_log.time"),
                    value=get_current_time_str(),
                    inline=True,
                )
                embed.set_footer(text=tx("audit_log.user_941f2d", v0=(after)))
                await self.send_log_embed(guild_id, embed)

        # 暱稱變更
        if before.nick != after.nick:
            embed = discord.Embed(
                title=tx("audit_log.nickname_nickname_changed"),
                color=discord.Color.from_rgb(155, 89, 182),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name=tx("audit_log.user"),
                value=f"{after.mention} ({after.id})",
                inline=False,
            )
            embed.add_field(
                name=tx("audit_log.before"),
                value=tx(
                    "audit_log.value", v0=(before.nick or tx("audit_log.no_nickname"))
                ),
                inline=True,
            )
            embed.add_field(
                name=tx("audit_log.after"),
                value=tx(
                    "audit_log.value", v0=(after.nick or tx("audit_log.no_nickname"))
                ),
                inline=True,
            )
            embed.add_field(
                name=tx("audit_log.time"), value=get_current_time_str(), inline=True
            )
            embed.set_footer(text=tx("audit_log.user_941f2d", v0=(after)))
            await self.send_log_embed(guild_id, embed)

    # ===== 頻道建立 / 刪除 / 修改 =====

    def _channel_type_name(self, channel: discord.abc.GuildChannel) -> str:
        """取得頻道類型的中文名稱"""
        type_map = {
            discord.ChannelType.text: tx("audit_log.text_channel"),
            discord.ChannelType.voice: tx("audit_log.voice_channel"),
            discord.ChannelType.category: tx("audit_log.category"),
            discord.ChannelType.news: tx("audit_log.announcement_channel"),
            discord.ChannelType.stage_voice: tx("audit_log.stage_channel"),
            discord.ChannelType.forum: tx("audit_log.forum_channel"),
        }
        return type_map.get(channel.type, tx("audit_log.unknown_type"))

    @commands.Cog.listener()
    @localized("channel")
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """頻道建立"""
        embed = discord.Embed(
            title=tx("audit_log.channel_channel_created"),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.channel_name"),
            value=f"{channel.mention} ({channel.id})",
            inline=False,
        )
        embed.add_field(
            name=tx("audit_log.type"),
            value=self._channel_type_name(channel),
            inline=True,
        )
        if channel.category:
            embed.add_field(
                name=tx("audit_log.category"), value=channel.category.name, inline=True
            )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )
        embed.set_footer(text=tx("audit_log.server", v0=(channel.guild.name)))

        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    @localized("channel")
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        """頻道刪除"""
        embed = discord.Embed(
            title=tx("audit_log.channel_channel_deleted"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.channel_name"),
            value=f"#{channel.name} ({channel.id})",
            inline=False,
        )
        embed.add_field(
            name=tx("audit_log.type"),
            value=self._channel_type_name(channel),
            inline=True,
        )
        if channel.category:
            embed.add_field(
                name=tx("audit_log.category"), value=channel.category.name, inline=True
            )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )
        embed.set_footer(text=tx("audit_log.server", v0=(channel.guild.name)))

        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    @localized("after")
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        """頻道修改"""
        changes = []

        # 名稱變更
        if before.name != after.name:
            changes.append((tx("audit_log.name"), before.name, after.name))

        # 分類變更
        before_category = (
            before.category.name if before.category else tx("audit_log.none_a6cdc8")
        )
        after_category = (
            after.category.name if after.category else tx("audit_log.none_a6cdc8")
        )
        if before_category != after_category:
            changes.append((tx("audit_log.category"), before_category, after_category))

        # 文字頻道特有屬性
        if isinstance(before, discord.TextChannel) and isinstance(
            after, discord.TextChannel
        ):
            if before.topic != after.topic:
                before_topic = before.topic or tx("audit_log.none_a6cdc8")
                after_topic = after.topic or tx("audit_log.none_a6cdc8")
                changes.append(
                    (tx("audit_log.topic"), before_topic[:200], after_topic[:200])
                )

            if before.slowmode_delay != after.slowmode_delay:
                changes.append(
                    (
                        tx("audit_log.slow_mode"),
                        tx("audit_log.seconds", v0=(before.slowmode_delay)),
                        tx("audit_log.seconds", v0=(after.slowmode_delay)),
                    )
                )

            if before.is_nsfw() != after.is_nsfw():
                changes.append(
                    (
                        "NSFW",
                        tx("audit_log.yes") if before.is_nsfw() else tx("audit_log.no"),
                        tx("audit_log.yes") if after.is_nsfw() else tx("audit_log.no"),
                    )
                )

        # 語音頻道特有屬性
        if isinstance(before, discord.VoiceChannel) and isinstance(
            after, discord.VoiceChannel
        ):
            if before.bitrate != after.bitrate:
                changes.append(
                    (
                        tx("audit_log.bitrate"),
                        f"{before.bitrate // 1000} kbps",
                        f"{after.bitrate // 1000} kbps",
                    )
                )

            if before.user_limit != after.user_limit:
                before_limit = (
                    str(before.user_limit)
                    if before.user_limit
                    else tx("audit_log.unlimited")
                )
                after_limit = (
                    str(after.user_limit)
                    if after.user_limit
                    else tx("audit_log.unlimited")
                )
                changes.append(
                    (tx("audit_log.member_limit"), before_limit, after_limit)
                )

        if not changes:
            return

        embed = discord.Embed(
            title=tx("audit_log.channel_channel_updated"),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("audit_log.channel"),
            value=f"{after.mention} ({after.id})",
            inline=False,
        )

        for field_name, old_val, new_val in changes:
            embed.add_field(
                name=tx("audit_log.changed", v0=(field_name)),
                value=f"```\n{old_val}\n```->```\n{new_val}\n```",
                inline=False,
            )

        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )
        embed.set_footer(text=tx("audit_log.server", v0=(after.guild.name)))

        await self.send_log_embed(after.guild.id, embed)


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(AuditLog(bot))
