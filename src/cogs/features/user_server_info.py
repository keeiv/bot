import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import logging
from typing import Any, cast, Optional, Protocol, Sequence, Tuple

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

from src.services.achievement_service import AchievementService
from src.services.osu_service import OsuService
from src.utils.i18n import from_locale
from src.utils.i18n import Lang
from src.utils.i18n import t
from src.utils.lang_context import interaction_lang
from src.utils.storage_worker import run_storage

log = logging.getLogger(__name__)

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


class AchievementsCogProtocol(Protocol):
    service: AchievementService

    def unlock_achievement(
        self, user_id: int, guild_id: Optional[int], achievement: str
    ) -> None: ...


class OsuInfoCogProtocol(Protocol):
    service: OsuService


class UserServerInfo(commands.Cog):
    """用戶和伺服器資訊Cog"""

    def __init__(self, bot: commands.Bot) -> None:
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
        self, title: str, lines: Sequence[str], limit: int = 4000, *, lang: Lang
    ) -> str:
        """將多行內容整理成TextDisplay可用的markdown區塊。"""
        content_lines = [line for line in lines if line]
        body = "\n".join(content_lines) if content_lines else t(lang, "info.none")
        return self.truncate_text(f"### {title}\n{body}", limit)

    def format_field_block(
        self,
        title: str,
        fields: Sequence[Tuple[str, str]],
        limit: int = 4000,
        *,
        lang: Lang,
    ) -> str:
        lines = []
        for label, value in fields:
            if "\n" in value:
                lines.append(f"**{label}**")
                lines.append(value)
            else:
                lines.append(f"**{label}**: {value}")
        return self.format_text_block(title, lines, limit, lang=lang)

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
        lang: Lang,
    ) -> LayoutView:
        """建立戶資訊畫面。"""
        view = LayoutView(timeout=None)
        container = Container[Any](accent_color=discord.Color.from_rgb(52, 152, 219))

        container.add_item(
            Section(
                TextDisplay(f"## {t(lang, 'info.user.title')}"),
                TextDisplay(
                    self.truncate_text(
                        "\n".join(
                            (
                                t(lang, "info.user.target", mention=user.mention),
                                t(lang, "info.user.status_line", status=status),
                                t(lang, "info.queried", time=queried_at),
                            )
                        )
                    )
                ),
                accessory=Thumbnail(
                    user.display_avatar.url,
                    description=t(lang, "info.user.avatar"),
                ),
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    t(lang, "info.user.basic"),
                    (
                        (t(lang, "info.user.id"), f"`{user.id}`"),
                        (t(lang, "info.user.username"), f"@{user.name}"),
                        (t(lang, "info.user.display_name"), display_name),
                        (t(lang, "info.user.created"), created_time),
                        (t(lang, "info.user.joined"), joined_time),
                        (t(lang, "info.user.account_status"), status),
                    ),
                    lang=lang,
                )
            )
        )

        if roles_text is not None:
            self.add_separator(container)
            container.add_item(
                TextDisplay(
                    self.format_text_block(
                        t(lang, "info.user.roles"), (roles_text,), 3500, lang=lang
                    )
                )
            )

        if achievement_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(
                    self.format_text_block(
                        t(lang, "info.user.achievements"),
                        (achievement_text,),
                        3500,
                        lang=lang,
                    )
                )
            )

        if osu_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(
                    self.format_text_block(
                        t(lang, "info.user.osu"), (osu_text,), 3500, lang=lang
                    )
                )
            )

        banner = getattr(user, "banner", None)
        if banner:
            self.add_separator(container, discord.SeparatorSpacing.large)
            gallery = MediaGallery[Any]()
            gallery.add_item(media=banner.url, description=t(lang, "info.user.banner"))
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
        lang: Lang,
    ) -> LayoutView:
        """建立伺服器資訊畫面。"""
        view = LayoutView(timeout=None)
        container = Container[Any](accent_color=discord.Color.from_rgb(46, 204, 113))

        summary_lines = (
            t(lang, "info.server.name_line", name=self.truncate_text(guild.name, 200)),
            t(lang, "info.server.member_total_line", count=guild.member_count or 0),
            t(lang, "info.queried", time=queried_at),
        )

        if guild.icon:
            container.add_item(
                Section(
                    TextDisplay(f"## {t(lang, 'info.server.title')}"),
                    TextDisplay(self.truncate_text("\n".join(summary_lines))),
                    accessory=Thumbnail(
                        guild.icon.url,
                        description=t(lang, "info.server.icon"),
                    ),
                )
            )
        else:
            container.add_item(
                TextDisplay(
                    self.format_text_block(
                        t(lang, "info.server.title"), summary_lines, lang=lang
                    )
                )
            )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    t(lang, "info.server.basic"),
                    (
                        (t(lang, "info.server.name"), guild.name),
                        (t(lang, "info.server.id"), f"`{guild.id}`"),
                        (t(lang, "info.server.created"), created_time),
                        (t(lang, "info.server.owner"), owner_text),
                    ),
                    lang=lang,
                )
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_text_block(
                    t(lang, "info.server.members"),
                    member_stats_text.split("\n"),
                    lang=lang,
                )
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_text_block(
                    t(lang, "info.server.channels"),
                    channel_stats_text.split("\n"),
                    lang=lang,
                )
            )
        )

        self.add_separator(container)
        container.add_item(
            TextDisplay(
                self.format_field_block(
                    t(lang, "info.server.settings"),
                    (
                        (t(lang, "info.server.role_count"), str(role_count)),
                        (t(lang, "info.server.verification"), verification_level),
                        (t(lang, "info.server.boost"), boost_text),
                    ),
                    lang=lang,
                )
            )
        )

        if description_text:
            self.add_separator(container)
            container.add_item(
                TextDisplay(
                    self.format_text_block(
                        t(lang, "info.server.description"),
                        (description_text,),
                        3500,
                        lang=lang,
                    )
                )
            )

        if guild.banner:
            self.add_separator(container, discord.SeparatorSpacing.large)
            gallery = MediaGallery[Any]()
            gallery.add_item(
                media=guild.banner.url, description=t(lang, "info.server.banner")
            )
            container.add_item(gallery)

        view.add_item(container)
        return view

    @app_commands.command(name="user_info", description="Look up a member")
    @app_commands.describe(user="The user to look up (defaults to you)")
    async def user_info(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ) -> None:
        """顯示用戶資訊"""
        lang: Lang = from_locale(interaction.locale)  # until the lookup below
        try:
            await interaction.response.defer(thinking=True)
            lang = await interaction_lang(interaction)
            target_user = user or interaction.user
            member = await self.get_member(interaction.guild, target_user.id)

            display_name = target_user.display_name
            if member and member.nick:
                display_name = f"{member.nick} ({target_user.display_name})"

            created_time = self.format_time(target_user.created_at)
            joined_time = (
                self.format_time(member.joined_at)
                if member and member.joined_at
                else t(lang, "info.user.joined_unknown")
            )
            status = t(
                lang, "info.user.bot" if target_user.bot else "info.user.regular"
            )
            queried_at = self.format_time(datetime.now(TZ_OFFSET))

            roles_text = None
            if member:
                default_role = member.guild.default_role
                roles = [role.mention for role in member.roles if role != default_role]
                roles_text = " ".join(roles) if roles else t(lang, "info.none")
                roles_text = self.truncate_text(roles_text, 3500)

            achievement_text = None
            if interaction.guild and not target_user.bot:
                try:
                    achievements_cog = cast(
                        Optional[AchievementsCogProtocol],
                        self.bot.get_cog("Achievements"),
                    )
                    if achievements_cog:
                        progress = await run_storage(
                            achievements_cog.service.get_progress,
                            target_user.id,
                            interaction.guild_id,
                        )
                        progress_bar = achievements_cog.service.get_progress_bar(
                            progress["percentage"], 15
                        )
                        achievement_text = (
                            f"{progress_bar}\n"
                            f"{progress['unlocked']}/{progress['total']} "
                            f"({progress['percentage']}%)"
                        )
                        await run_storage(
                            achievements_cog.unlock_achievement,
                            target_user.id,
                            interaction.guild_id,
                            "info_explorer",
                        )
                except Exception as e:
                    log.warning("[成就] 顯示進度失敗: %s", type(e).__name__)

            osu_text = None
            if not target_user.bot:
                try:
                    osu_cog = cast(
                        Optional[OsuInfoCogProtocol],
                        self.bot.get_cog("OsuInfo"),
                    )
                    if osu_cog:
                        service = osu_cog.service
                        bound_username = service.get_bound_username(target_user.id)
                        if bound_username:
                            osu_text = t(
                                lang, "info.user.osu_linked", name=bound_username
                            )
                            service.ensure_api()
                            osu_user = await asyncio.wait_for(
                                asyncio.to_thread(service.api.user, bound_username),
                                timeout=10,
                            )
                            stats = osu_user.statistics

                            global_rank = getattr(stats, "global_rank", None)
                            country_rank = getattr(stats, "country_rank", None)
                            pp = getattr(stats, "pp", None)
                            accuracy = getattr(stats, "hit_accuracy", None)

                            unranked = t(lang, "info.user.osu_unranked")
                            unknown = t(lang, "info.user.osu_unknown")
                            osu_lines = [
                                t(
                                    lang,
                                    "info.user.osu_username",
                                    value=osu_user.username,
                                ),
                                t(
                                    lang,
                                    "info.user.osu_global_rank",
                                    value=(
                                        f"#{global_rank:,}"
                                        if isinstance(global_rank, int)
                                        else unranked
                                    ),
                                ),
                                t(
                                    lang,
                                    "info.user.osu_country_rank",
                                    value=(
                                        f"#{country_rank:,}"
                                        if isinstance(country_rank, int)
                                        else unranked
                                    ),
                                ),
                                t(
                                    lang,
                                    "info.user.osu_pp",
                                    value=(
                                        f"{pp:,.2f}"
                                        if isinstance(pp, (int, float))
                                        else unknown
                                    ),
                                ),
                                t(
                                    lang,
                                    "info.user.osu_accuracy",
                                    value=(
                                        f"{accuracy:.2f}%"
                                        if isinstance(accuracy, (int, float))
                                        else unknown
                                    ),
                                ),
                                t(
                                    lang,
                                    "info.user.osu_link",
                                    value=f"https://osu.ppy.sh/users/{osu_user.id}",
                                ),
                            ]
                            osu_text = self.truncate_text("\n".join(osu_lines), 3500)
                except Exception as e:
                    log.warning("[osu] 即時資料取得失敗: %s", type(e).__name__)

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
                lang,
            )
            await interaction.followup.send(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except discord.NotFound as exc:
            if exc.code != 10062:
                raise
            log.warning("[user_info] 互動已過期，無法回覆；請重新執行指令")
        except Exception:
            log.exception("[user_info] 查詢失敗")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        t(lang, "info.user.error"), ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        t(lang, "info.user.error"), ephemeral=True
                    )
            except discord.HTTPException:
                log.warning("[user_info] 無法傳送錯誤回覆")

    @app_commands.command(name="server_info", description="Look up this server")
    async def server_info(self, interaction: discord.Interaction) -> None:
        """顯示伺服器資訊"""
        await interaction.response.defer(thinking=True, ephemeral=False)
        lang = await interaction_lang(interaction)
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send(
                    t(lang, "info.server.only_in_server"), ephemeral=True
                )
                return

            created_time = self.format_time(guild.created_at)
            queried_at = self.format_time(datetime.now(TZ_OFFSET))

            owner = guild.owner
            owner_text = (
                f"{owner.mention} ({owner.name})"
                if owner
                else t(lang, "info.unavailable")
            )

            total_members = guild.member_count or 0
            bot_count = sum(1 for member in guild.members if member.bot)
            human_count = total_members - bot_count
            member_stats_text = "\n".join(
                (
                    t(lang, "info.server.members_total", count=total_members),
                    t(lang, "info.server.members_humans", count=human_count),
                    t(lang, "info.server.members_bots", count=bot_count),
                )
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
            channel_stats_text = "\n".join(
                (
                    t(lang, "info.server.channels_text", count=text_channels),
                    t(lang, "info.server.channels_voice", count=voice_channels),
                    t(lang, "info.server.channels_categories", count=categories),
                )
            )

            role_count = len(guild.roles)
            verification_level = str(guild.verification_level).capitalize()
            boost_text = "\n".join(
                (
                    t(lang, "info.server.boost_tier", tier=guild.premium_tier),
                    t(
                        lang,
                        "info.server.boost_count",
                        count=guild.premium_subscription_count,
                    ),
                )
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
                lang,
            )
            await interaction.followup.send(
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

            try:
                achievements_cog = cast(
                    Optional[AchievementsCogProtocol],
                    self.bot.get_cog("Achievements"),
                )
                if achievements_cog:
                    await run_storage(
                        achievements_cog.unlock_achievement,
                        interaction.user.id,
                        guild.id,
                        "server_analyst",
                    )
            except Exception as e:
                print(f"[成就] 伺服器分析成就觸發失敗: {e}")

        except Exception as e:
            print(f"[server_info] 錯誤: {e}")
            await interaction.followup.send(
                t(lang, "info.server.error", error=str(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(UserServerInfo(bot))
