from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
import time

import discord
from discord.ext import commands

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


class AuditLog(commands.Cog):
    """伺服器審計日誌 Cog — 記錄成員、語音、角色、暱稱、頻道事件"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_file = "data/storage/log_channels.json"
        # 記憶體快取：避免每個事件都讀磁碟
        self._channel_cache: dict = {}
        self._cache_time: float = 0
        self._CACHE_TTL: float = 60.0  # 60 秒 TTL

    def get_current_time_str(self) -> str:
        """取得格式化的當前時間 (月/日 時:分)"""
        now = datetime.now(TZ_OFFSET)
        return now.strftime("%m/%d %H:%M")

    def _load_all_log_channels(self) -> dict:
        """載入所有日誌頻道設定 (帶記憶體快取)"""
        now = time.monotonic()
        if self._channel_cache and (now - self._cache_time) < self._CACHE_TTL:
            return self._channel_cache

        if not os.path.exists(self.config_file):
            self._channel_cache = {}
            self._cache_time = now
            return self._channel_cache

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._channel_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._channel_cache = {}
        self._cache_time = now
        return self._channel_cache

    def get_log_channel_id(self, guild_id: int):
        """取得伺服器的日誌頻道 ID (從快取)"""
        channels = self._load_all_log_channels()
        return channels.get(str(guild_id))

    async def send_log_embed(self, guild_id: int, embed: discord.Embed):
        """發送日誌 Embed 到設定的日誌頻道"""
        log_channel_id = self.get_log_channel_id(guild_id)
        if not log_channel_id:
            return

        try:
            # 優先用 get_channel (記憶體) 避免 API 呼叫
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel is None:
                log_channel = await self.bot.fetch_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[✗] 審計日誌發送失敗: {e}")

    # ===== 成員加入 / 離開 =====

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """成員加入伺服器"""
        if member.bot:
            return

        embed = discord.Embed(
            title="[加入] 成員加入伺服器",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="用戶",
            value=f"{member.mention} ({member.id})",
            inline=False,
        )
        embed.add_field(
            name="帳號建立時間",
            value=member.created_at.astimezone(TZ_OFFSET).strftime(
                "%Y/%m/%d %H:%M"
            ),
            inline=True,
        )
        embed.add_field(
            name="目前伺服器人數",
            value=str(member.guild.member_count),
            inline=True,
        )
        embed.add_field(
            name="時間", value=self.get_current_time_str(), inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"用戶 {member}")

        await self.send_log_embed(member.guild.id, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
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
                stay_text = f"{days // 365} 年 {days % 365} 天"
            elif days >= 1:
                stay_text = f"{days} 天"
            else:
                hours = stay_duration.seconds // 3600
                stay_text = f"{hours} 小時"
        else:
            stay_text = "未知"

        embed = discord.Embed(
            title="[離開] 成員離開伺服器",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="用戶",
            value=f"{member.mention} ({member.id})",
            inline=False,
        )

        # 列出離開前的角色
        roles = [
            role.mention for role in member.roles if role != member.guild.default_role
        ]
        roles_text = ", ".join(roles) if roles else "無"
        embed.add_field(name="擁有角色", value=roles_text[:1024], inline=False)

        embed.add_field(name="待了多久", value=stay_text, inline=True)
        embed.add_field(
            name="目前伺服器人數",
            value=str(member.guild.member_count),
            inline=True,
        )
        embed.add_field(
            name="時間", value=self.get_current_time_str(), inline=True
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"用戶 {member}")

        await self.send_log_embed(member.guild.id, embed)

    # ===== 語音頻道加入 / 離開 / 移動 =====

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """語音狀態變更"""
        if member.bot:
            return

        guild_id = member.guild.id

        # 加入語音頻道
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="[語音] 加入語音頻道",
                color=discord.Color.from_rgb(52, 152, 219),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name="用戶",
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name="頻道",
                value=f"{after.channel.mention} ({after.channel.id})",
                inline=False,
            )
            embed.add_field(
                name="時間", value=self.get_current_time_str(), inline=True
            )
            embed.set_footer(text=f"用戶 {member}")
            await self.send_log_embed(guild_id, embed)

        # 離開語音頻道
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="[語音] 離開語音頻道",
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name="用戶",
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name="頻道",
                value=f"{before.channel.mention} ({before.channel.id})",
                inline=False,
            )
            embed.add_field(
                name="時間", value=self.get_current_time_str(), inline=True
            )
            embed.set_footer(text=f"用戶 {member}")
            await self.send_log_embed(guild_id, embed)

        # 移動語音頻道
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            embed = discord.Embed(
                title="[語音] 移動語音頻道",
                color=discord.Color.from_rgb(241, 196, 15),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name="用戶",
                value=f"{member.mention} ({member.id})",
                inline=False,
            )
            embed.add_field(
                name="移動前",
                value=f"{before.channel.mention} ({before.channel.id})",
                inline=True,
            )
            embed.add_field(
                name="移動後",
                value=f"{after.channel.mention} ({after.channel.id})",
                inline=True,
            )
            embed.add_field(
                name="時間", value=self.get_current_time_str(), inline=True
            )
            embed.set_footer(text=f"用戶 {member}")
            await self.send_log_embed(guild_id, embed)

    # ===== 角色變更 / 暱稱變更 =====

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
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
                    title="[角色] 角色新增",
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="用戶",
                    value=f"{after.mention} ({after.id})",
                    inline=False,
                )
                embed.add_field(
                    name="新增角色", value=roles_text[:1024], inline=False
                )
                embed.add_field(
                    name="時間",
                    value=self.get_current_time_str(),
                    inline=True,
                )
                embed.set_footer(text=f"用戶 {after}")
                await self.send_log_embed(guild_id, embed)

            if removed:
                roles_text = ", ".join(role.mention for role in removed)
                embed = discord.Embed(
                    title="[角色] 角色移除",
                    color=discord.Color.from_rgb(231, 76, 60),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="用戶",
                    value=f"{after.mention} ({after.id})",
                    inline=False,
                )
                embed.add_field(
                    name="移除角色", value=roles_text[:1024], inline=False
                )
                embed.add_field(
                    name="時間",
                    value=self.get_current_time_str(),
                    inline=True,
                )
                embed.set_footer(text=f"用戶 {after}")
                await self.send_log_embed(guild_id, embed)

        # 暱稱變更
        if before.nick != after.nick:
            embed = discord.Embed(
                title="[暱稱] 暱稱變更",
                color=discord.Color.from_rgb(155, 89, 182),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name="用戶",
                value=f"{after.mention} ({after.id})",
                inline=False,
            )
            embed.add_field(
                name="變更前",
                value=f"```\n{before.nick or '(無暱稱)'}\n```",
                inline=True,
            )
            embed.add_field(
                name="變更後",
                value=f"```\n{after.nick or '(無暱稱)'}\n```",
                inline=True,
            )
            embed.add_field(
                name="時間", value=self.get_current_time_str(), inline=True
            )
            embed.set_footer(text=f"用戶 {after}")
            await self.send_log_embed(guild_id, embed)

    # ===== 頻道建立 / 刪除 / 修改 =====

    def _channel_type_name(self, channel: discord.abc.GuildChannel) -> str:
        """取得頻道類型的中文名稱"""
        type_map = {
            discord.ChannelType.text: "文字頻道",
            discord.ChannelType.voice: "語音頻道",
            discord.ChannelType.category: "分類",
            discord.ChannelType.news: "公告頻道",
            discord.ChannelType.stage_voice: "舞台頻道",
            discord.ChannelType.forum: "論壇頻道",
        }
        return type_map.get(channel.type, "未知類型")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """頻道建立"""
        embed = discord.Embed(
            title="[頻道] 頻道建立",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="頻道名稱",
            value=f"{channel.mention} ({channel.id})",
            inline=False,
        )
        embed.add_field(
            name="類型",
            value=self._channel_type_name(channel),
            inline=True,
        )
        if channel.category:
            embed.add_field(
                name="分類", value=channel.category.name, inline=True
            )
        embed.add_field(
            name="時間", value=self.get_current_time_str(), inline=True
        )
        embed.set_footer(text=f"伺服器 {channel.guild.name}")

        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """頻道刪除"""
        embed = discord.Embed(
            title="[頻道] 頻道刪除",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="頻道名稱",
            value=f"#{channel.name} ({channel.id})",
            inline=False,
        )
        embed.add_field(
            name="類型",
            value=self._channel_type_name(channel),
            inline=True,
        )
        if channel.category:
            embed.add_field(
                name="分類", value=channel.category.name, inline=True
            )
        embed.add_field(
            name="時間", value=self.get_current_time_str(), inline=True
        )
        embed.set_footer(text=f"伺服器 {channel.guild.name}")

        await self.send_log_embed(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ):
        """頻道修改"""
        changes = []

        # 名稱變更
        if before.name != after.name:
            changes.append(("名稱", before.name, after.name))

        # 分類變更
        before_category = before.category.name if before.category else "(無)"
        after_category = after.category.name if after.category else "(無)"
        if before_category != after_category:
            changes.append(("分類", before_category, after_category))

        # 文字頻道特有屬性
        if isinstance(before, discord.TextChannel) and isinstance(
            after, discord.TextChannel
        ):
            if before.topic != after.topic:
                before_topic = before.topic or "(無)"
                after_topic = after.topic or "(無)"
                changes.append(("主題", before_topic[:200], after_topic[:200]))

            if before.slowmode_delay != after.slowmode_delay:
                changes.append(
                    (
                        "慢速模式",
                        f"{before.slowmode_delay} 秒",
                        f"{after.slowmode_delay} 秒",
                    )
                )

            if before.is_nsfw() != after.is_nsfw():
                changes.append(
                    (
                        "NSFW",
                        "[是]" if before.is_nsfw() else "[否]",
                        "[是]" if after.is_nsfw() else "[否]",
                    )
                )

        # 語音頻道特有屬性
        if isinstance(before, discord.VoiceChannel) and isinstance(
            after, discord.VoiceChannel
        ):
            if before.bitrate != after.bitrate:
                changes.append(
                    (
                        "位元率",
                        f"{before.bitrate // 1000} kbps",
                        f"{after.bitrate // 1000} kbps",
                    )
                )

            if before.user_limit != after.user_limit:
                before_limit = str(before.user_limit) if before.user_limit else "無限制"
                after_limit = str(after.user_limit) if after.user_limit else "無限制"
                changes.append(("人數上限", before_limit, after_limit))

        if not changes:
            return

        embed = discord.Embed(
            title="[頻道] 頻道修改",
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="頻道",
            value=f"{after.mention} ({after.id})",
            inline=False,
        )

        for field_name, old_val, new_val in changes:
            embed.add_field(
                name=f"{field_name} 變更",
                value=f"```\n{old_val}\n```->```\n{new_val}\n```",
                inline=False,
            )

        embed.add_field(
            name="時間", value=self.get_current_time_str(), inline=True
        )
        embed.set_footer(text=f"伺服器 {after.guild.name}")

        await self.send_log_embed(after.guild.id, embed)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(AuditLog(bot))
