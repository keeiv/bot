from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Protocol
from typing import Sequence
from typing import Tuple
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Container
from discord.ui import LayoutView
from discord.ui import MediaGallery
from discord.ui import Section
from discord.ui import Separator
from discord.ui import TextDisplay
from discord.ui import Thumbnail

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


class AchievementsCogProtocol(Protocol):
    def get_progress(self, user_id: int, guild_id: Optional[int]) -> Mapping[str, Any]:
        ...

    def get_progress_bar(self, percentage: Any, length: int) -> str:
        ...

    def unlock_achievement(
        self, user_id: int, guild_id: Optional[int], achievement: str
    ) -> None:
        ...


class OsuInfoCogProtocol(Protocol):
    api: Any

    def get_bound_osu_username(self, user_id: int) -> Optional[str]:
        ...


class UserServerInfo(commands.Cog):
    """用戶和伺服器資訊Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def format_time(self, dt: datetime) -> str:
        """格式化時間為 年/月/日 時:分:秒"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(TZ_OFFSET)
        return local_dt.strftime("%Y/%m/%d %H:%M:%S")

    def truncate_text(self, text: str, limit: int = 4000) -> str:
        """限制文字長度"""
        if len(text) <= limit:
            return text
        if limit <= 3:
            return text[:limit]
        return f"{text[: limit - 3]}..."

    async def get_member(
        self, guild: Optional[discord.Guild], user_id: int
    ) -> Optional[discord.Member]:
        """快取"""
        if guild is None:
            return None

        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None

    def format_text_block(
        self, title: str, lines: Sequence[str], limit: int = 4000
    ) -> str:
        """將多行內容整理成TextDisplay可用的markdown區塊。"""
        content_lines = [line for line in lines if line]
        body = "\n".join(content_lines) if content_lines else "無"
        return self.truncate_text(f"### {title}\n{body}", limit)

    def format_field_block(
        self, title: str, fields: Sequence[Tuple[str, str]], limit: int = 4000
    ) -> str:
        lines = []
        for label, value in fields:
            if "\n" in value:
                lines.append(f"**{label}**")
                lines.append(value)
            else:
                lines.append(f"**{label}**: {value}")
        return self.format_text_block(title, lines, limit)

    def add_separator(
        self,
        container: Container,
        spacing: discord.SeparatorSpacing = discord.SeparatorSpacing.small,
    ) -> None:
        """分隔線"""
        container.add_item(Separator(visible=True, spacing=spacing))

    def build_user_info_view(
        self,
        user: discord.abc.User,
        display_name: str,
        created_time: str,
        joined_time: str,
        status: str,
        roles_text: Optional[str],
        achievement_text: Optional[str],
        osu_text: Optional[str],
        queried_at: str,
    ) -> LayoutView:
        """建立戶資訊畫面。"""
        view = LayoutView(timeout=None)
        container = Container(accent_color=discord.Color.from_rgb(52, 152, 219))

        container.add_item(
            Section(
                TextDisplay("## 用戶資訊"),
                TextDisplay(
                    self.truncate_text(
                        "\n".join(
                            (
                                f"目標：{user.mention}",
                                f"狀態：{status}",
                                f"查詢時間：{queried_at}",
                            )
                        )
                    )
                ),
                accessory=Thumbnail(
                    user.display_avatar.url,
                    description="用戶頭像",
                ),
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    "基本資料",
                    (
                        ("用戶ID", f"`{user.id}`"),
                        ("用戶名", f"@{user.name}"),
                        ("顯示名稱", display_name),
                        ("帳號創立時間", created_time),
                        ("加入伺服器時間", joined_time),
                        ("帳號狀態", status),
                    ),
                )
            )
        )

        if roles_text is not None:
            self.add_separator(container)
            container.add_item(
                TextDisplay(self.format_text_block("角色", (roles_text,), 3500))
            )

        if achievement_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(
                    self.format_text_block("成就進度", (achievement_text,), 3500)
                )
            )

        if osu_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(self.format_text_block("osu! 資訊", (osu_text,), 3500))
            )

        banner = getattr(user, "banner", None)
        if banner:
            self.add_separator(container, discord.SeparatorSpacing.large)
            gallery = MediaGallery()
            gallery.add_item(media=banner.url, description="用戶橫幅")
            container.add_item(gallery)

        view.add_item(container)
        return view

    def build_server_info_view(
        self,
        guild: discord.Guild,
        owner_text: str,
        created_time: str,
        member_stats_text: str,
        channel_stats_text: str,
        role_count: int,
        verification_level: str,
        boost_text: str,
        description_text: Optional[str],
        queried_at: str,
    ) -> LayoutView:
        """建立伺服器資訊畫面。"""
        view = LayoutView(timeout=None)
        container = Container(accent_color=discord.Color.from_rgb(46, 204, 113))

        summary_lines = (
            f"伺服器：**{self.truncate_text(guild.name, 200)}**",
            f"成員總數：{guild.member_count or 0}",
            f"查詢時間：{queried_at}",
        )

        if guild.icon:
            container.add_item(
                Section(
                    TextDisplay("## 伺服器資訊"),
                    TextDisplay(self.truncate_text("\n".join(summary_lines))),
                    accessory=Thumbnail(
                        guild.icon.url,
                        description="伺服器圖標",
                    ),
                )
            )
        else:
            container.add_item(
                TextDisplay(self.format_text_block("伺服器資訊", summary_lines))
            )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    "基本資料",
                    (
                        ("伺服器名稱", guild.name),
                        ("伺服器ID", f"`{guild.id}`"),
                        ("創建時間", created_time),
                        ("擁有者", owner_text),
                    ),
                )
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(self.format_text_block("成員統計", member_stats_text.split("\n")))
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(self.format_text_block("頻道統計", channel_stats_text.split("\n")))
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    "伺服器設定",
                    (
                        ("角色數量", str(role_count)),
                        ("驗證等級", verification_level),
                        ("Boost 資訊", boost_text),
                    ),
                )
            )
        )

        if description_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(self.format_text_block("描述", (description_text,), 3500))
            )

        if guild.banner:
            self.add_separator(container, discord.SeparatorSpacing.large)
            gallery = MediaGallery()
            gallery.add_item(media=guild.banner.url, description="伺服器橫幅")
            container.add_item(gallery)

        view.add_item(container)
        return view

    @app_commands.command(name="user_info", description="顯示用戶資訊")
    @app_commands.describe(user="要查詢的用戶 (不填默認為自己)")
    async def user_info(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        """顯示用戶資訊"""
        try:
            target_user = user or interaction.user
            member = await self.get_member(interaction.guild, target_user.id)

            display_name = target_user.display_name
            if member and member.nick:
                display_name = f"{member.nick} ({target_user.display_name})"

            created_time = self.format_time(target_user.created_at)
            joined_time = (
                self.format_time(member.joined_at)
                if member and member.joined_at
                else "無法獲取或不在伺服器內"
            )
            status = "機器人" if target_user.bot else "普通用戶"
            queried_at = self.format_time(datetime.now(TZ_OFFSET))

            roles_text = None
            if member:
                default_role = member.guild.default_role
                roles = [
                    role.mention
                    for role in member.roles
                    if role != default_role
                ]
                roles_text = " ".join(roles) if roles else "無"
                roles_text = self.truncate_text(roles_text, 3500)

            achievement_text = None
            if interaction.guild and not target_user.bot:
                try:
                    achievements_cog = cast(
                        Optional[AchievementsCogProtocol],
                        self.bot.get_cog("Achievements"),
                    )
                    if achievements_cog:
                        progress = achievements_cog.get_progress(
                            target_user.id, interaction.guild_id
                        )
                        progress_bar = achievements_cog.get_progress_bar(
                            progress["percentage"], 15
                        )
                        achievement_text = (
                            f"{progress_bar}\n"
                            f"{progress['unlocked']}/{progress['total']} "
                            f"({progress['percentage']}%)"
                        )
                        achievements_cog.unlock_achievement(
                            target_user.id, interaction.guild_id, "info_explorer"
                        )
                except Exception as e:
                    print(f"[成就] 顯示進度失敗: {e}")

            osu_text = None
            if not target_user.bot:
                try:
                    osu_cog = cast(
                        Optional[OsuInfoCogProtocol],
                        self.bot.get_cog("OsuInfo"),
                    )
                    if osu_cog:
                        if getattr(osu_cog, "api", None) is None:
                            raise RuntimeError("osu 功能尚未啟用")

                        bound_username = osu_cog.get_bound_osu_username(target_user.id)
                        if bound_username:
                            osu_user = osu_cog.api.user(bound_username)
                            stats = osu_user.statistics

                            global_rank = getattr(stats, "global_rank", None)
                            country_rank = getattr(stats, "country_rank", None)
                            pp = getattr(stats, "pp", None)
                            accuracy = getattr(stats, "hit_accuracy", None)

                            osu_lines = [
                                f"用戶名: {osu_user.username}",
                                (
                                    f"全球排名: #{global_rank:,}"
                                    if isinstance(global_rank, int)
                                    else "全球排名: 未排名"
                                ),
                                (
                                    f"國家排名: #{country_rank:,}"
                                    if isinstance(country_rank, int)
                                    else "國家排名: 未排名"
                                ),
                                (
                                    f"PP: {pp:,.2f}"
                                    if isinstance(pp, (int, float))
                                    else "PP: 未知"
                                ),
                                (
                                    f"準確度: {accuracy:.2f}%"
                                    if isinstance(accuracy, (int, float))
                                    else "準確度: 未知"
                                ),
                                f"連結: https://osu.ppy.sh/users/{osu_user.id}",
                            ]
                            osu_text = self.truncate_text("\n".join(osu_lines), 3500)
                except Exception as e:
                    print(f"[osu] 顯示綁定資訊失敗: {e}")

            view = self.build_user_info_view(
                target_user,
                display_name,
                created_time,
                joined_time,
                status,
                roles_text,
                achievement_text,
                osu_text,
                queried_at,
            )
            await interaction.response.send_message(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except Exception as e:
            print(f"[user_info] 錯誤: {e}")
            await interaction.response.send_message(
                f"[錯誤] 無法獲取用戶資訊: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="server_info", description="顯示伺服器資訊")
    async def server_info(self, interaction: discord.Interaction):
        """顯示伺服器資訊"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "[失敗] 此命令只能在伺服器中使用", ephemeral=True
                )
                return

            created_time = self.format_time(guild.created_at)
            queried_at = self.format_time(datetime.now(TZ_OFFSET))

            owner = guild.owner
            owner_text = f"{owner.mention} ({owner.name})" if owner else "無法獲取"

            total_members = guild.member_count or 0
            bot_count = sum(1 for member in guild.members if member.bot)
            human_count = total_members - bot_count
            member_stats_text = (
                f"總計: {total_members}\n"
                f"人類: {human_count}\n"
                f"Bot: {bot_count}"
            )

            text_channels = len(
                [
                    channel
                    for channel in guild.channels
                    if isinstance(channel, discord.TextChannel)
                ]
            )
            voice_channels = len(
                [
                    channel
                    for channel in guild.channels
                    if isinstance(channel, discord.VoiceChannel)
                ]
            )
            categories = len(
                [
                    channel
                    for channel in guild.channels
                    if isinstance(channel, discord.CategoryChannel)
                ]
            )
            channel_stats_text = (
                f"文字: {text_channels}\n"
                f"語音: {voice_channels}\n"
                f"分類: {categories}"
            )

            role_count = len(guild.roles)
            verification_level = str(guild.verification_level).capitalize()
            boost_text = (
                f"等級: {guild.premium_tier}\n"
                f"Boosts: {guild.premium_subscription_count}"
            )
            description_text = (
                self.truncate_text(guild.description, 3500)
                if guild.description
                else None
            )

            view = self.build_server_info_view(
                guild,
                owner_text,
                created_time,
                member_stats_text,
                channel_stats_text,
                role_count,
                verification_level,
                boost_text,
                description_text,
                queried_at,
            )
            await interaction.response.send_message(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

            try:
                achievements_cog = cast(
                    Optional[AchievementsCogProtocol],
                    self.bot.get_cog("Achievements"),
                )
                if achievements_cog:
                    achievements_cog.unlock_achievement(
                        interaction.user.id, guild.id, "server_analyst"
                    )
            except Exception as e:
                print(f"[成就] 伺服器分析成就觸發失敗: {e}")

        except Exception as e:
            print(f"[server_info] 錯誤: {e}")
            await interaction.response.send_message(
                f"[錯誤] 無法獲取伺服器資訊: {str(e)}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(UserServerInfo(bot))
