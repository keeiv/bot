import asyncio
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.services.osu_service import OsuService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage


class OsuInfo(commands.Cog):
    """OSU! 用戶資訊查詢"""

    # Personal tool: also usable in DMs and servers without the bot.
    osu = app_commands.Group(
        name="osu",
        description="osu!",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = OsuService()

    @app_commands.command(name="user_info_osu", description="Look up an osu! player")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(username="osu! username")
    @localized("interaction")
    async def user_info_osu(
        self, interaction: discord.Interaction, username: str
    ) -> None:
        """查詢 osu! 用戶資訊"""
        try:
            await interaction.response.defer()

            self.service.ensure_api()

            # 抓取玩家資料
            user = await asyncio.wait_for(
                asyncio.to_thread(self.service.api.user, username), timeout=10
            )

            # 創建嵌入消息
            embed = discord.Embed(
                title=tx("osu_info.osu_user_info", v0=(user.username)),
                color=discord.Color.from_rgb(255, 105, 180),
                url=f"https://osu.ppy.sh/users/{user.id}",
            )

            # 設置頭像
            if user.avatar_url:
                embed.set_thumbnail(url=user.avatar_url)

            # 基本資訊欄位
            basic_info = tx("osu_info.username", v0=(user.username))
            basic_info += tx("osu_info.level", v0=(user.statistics.level.current))
            basic_info += (
                tx("osu_info.global_rank", v0=(user.statistics.global_rank))
                if user.statistics.global_rank
                else tx("osu_info.global_rank_unranked")
            )
            basic_info += (
                tx("osu_info.country_rank", v0=(user.statistics.country_rank))
                if user.statistics.country_rank
                else tx("osu_info.country_rank_unranked")
            )
            basic_info += f"**PP**: {user.statistics.pp:,.2f}\n"
            basic_info += tx("osu_info.accuracy", v0=(user.statistics.hit_accuracy))
            basic_info += tx(
                "osu_info.play_time",
                v0=(OsuService.format_playtime(user.statistics.play_time)),
            )
            basic_info += tx(
                "osu_info.supporter",
                v0=(tx("anti_spam.yes") if user.is_supporter else tx("anti_spam.no")),
            )

            embed.add_field(
                name=tx("osu_info.basic_info"), value=basic_info, inline=False
            )

            # 成績統計
            counts = user.statistics.grade_counts
            grades_info = tx("osu_info.ss_gold", v0=(counts.ss))
            grades_info += tx("osu_info.ss_silver_platinum", v0=(counts.ssh))
            grades_info += tx("osu_info.s_gold", v0=(counts.s))
            grades_info += tx("osu_info.s_silver_platinum", v0=(counts.sh))
            grades_info += tx("osu_info.a_ranks", v0=(counts.a))

            embed.add_field(
                name=tx("osu_info.rank_statistics"), value=grades_info, inline=True
            )

            # 遊戲統計
            stats = user.statistics
            play_count = self._get_first_attr(stats, "play_count", "playcount")
            total_score = self._get_first_attr(stats, "total_score")
            ranked_score = self._get_first_attr(stats, "ranked_score")
            maximum_combo = self._get_first_attr(stats, "maximum_combo", "max_combo")
            total_hits = self._get_first_attr(stats, "total_hits")

            playcount_info = tx("osu_info.play_count", v0=(self._fmt_int(play_count)))
            playcount_info += tx(
                "osu_info.total_score", v0=(self._fmt_int(total_score))
            )
            playcount_info += tx(
                "osu_info.ranked_score", v0=(self._fmt_int(ranked_score))
            )
            playcount_info += tx(
                "osu_info.maximum_combo", v0=(self._fmt_int(maximum_combo))
            )
            playcount_info += tx("osu_info.total_hits", v0=(self._fmt_int(total_hits)))

            embed.add_field(
                name=tx("osu_info.play_statistics"), value=playcount_info, inline=True
            )

            # 附加資訊
            if user.cover_url:
                embed.set_image(url=user.cover_url)

            embed.set_footer(
                text=tx(
                    "osu_info.user_id_joined",
                    v0=(user.id),
                    v1=(
                        user.join_date.strftime("%Y-%m-%d")
                        if user.join_date
                        else tx("audit_log.unknown")
                    ),
                )
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            error_msg = tx(
                "osu_info.user_was_not_found_or_an", v0=(username), v1=(str(e))
            )
            await interaction.followup.send(error_msg, ephemeral=True)

    @osu.command(name="bind", description="Link your osu! account")
    @app_commands.describe(username="osu! username")
    @localized("interaction")
    async def osu_bind(self, interaction: discord.Interaction, username: str) -> None:
        try:
            await interaction.response.defer(ephemeral=True)

            self.service.ensure_api()

            osu_user = await asyncio.wait_for(
                asyncio.to_thread(self.service.api.user, username), timeout=10
            )
            await run_storage(self.service.bind, interaction.user.id, osu_user.username)

            await interaction.followup.send(
                tx("osu_info.osu_account_linked", v0=(osu_user.username)),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                tx("osu_info.linking_failed", v0=(str(e))), ephemeral=True
            )

    @osu.command(name="unbind", description="Unlink your osu! account")
    @localized("interaction")
    async def osu_unbind(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        unbound_username = self.service.get_bound_username(interaction.user.id)
        if not (await run_storage(self.service.unbind, interaction.user.id)):
            await interaction.followup.send(
                tx("osu_info.no_osu_account_is_linked"), ephemeral=True
            )
            return

        await interaction.followup.send(
            tx(
                "osu_info.osu_account_unlinked",
                v0=(unbound_username or tx("audit_log.unknown")),
            ),
            ephemeral=True,
        )

    @osu.command(name="best", description="Show best osu! plays")
    @app_commands.describe(
        username="osu! username (defaults to your linked account)",
        limit="How many to show (1-10)",
    )
    @localized("interaction")
    async def osu_best(
        self,
        interaction: discord.Interaction,
        username: str | None = None,
        limit: int = 5,
    ) -> None:
        try:
            await interaction.response.defer()

            self.service.ensure_api()

            limit = max(1, min(10, limit))
            username = self._resolve_username(interaction.user.id, username)

            osu_user = await asyncio.wait_for(
                asyncio.to_thread(self.service.api.user, username), timeout=10
            )
            scores = await asyncio.wait_for(
                asyncio.to_thread(
                    self.service.api.user_scores, osu_user.id, type="best", limit=limit
                ),
                timeout=10,
            )

            embed = discord.Embed(
                title=f"osu! BP - {osu_user.username}",
                color=discord.Color.from_rgb(52, 152, 219),
                url=f"https://osu.ppy.sh/users/{osu_user.id}",
            )

            if osu_user.avatar_url:
                embed.set_thumbnail(url=osu_user.avatar_url)

            lines = []
            for i, s in enumerate(scores or [], start=1):
                lines.append(self._format_score_line(i, s))

            embed.add_field(
                name=tx("osu_info.scores"),
                value="\n".join(lines) if lines else tx("osu_info.no_data"),
                inline=False,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                tx("osu_info.query_failed", v0=(str(e))), ephemeral=True
            )

    @osu.command(name="recent", description="Show recent osu! plays")
    @app_commands.describe(
        username="osu! username (defaults to your linked account)",
        limit="How many to show (1-10)",
    )
    @localized("interaction")
    async def osu_recent(
        self,
        interaction: discord.Interaction,
        username: str | None = None,
        limit: int = 5,
    ) -> None:
        try:
            await interaction.response.defer()

            self.service.ensure_api()

            limit = max(1, min(10, limit))
            username = self._resolve_username(interaction.user.id, username)

            osu_user = await asyncio.wait_for(
                asyncio.to_thread(self.service.api.user, username), timeout=10
            )
            scores = await asyncio.wait_for(
                asyncio.to_thread(
                    self.service.api.user_scores,
                    osu_user.id,
                    type="recent",
                    limit=limit,
                ),
                timeout=10,
            )

            embed = discord.Embed(
                title=tx("osu_info.osu_recent_plays", v0=(osu_user.username)),
                color=discord.Color.from_rgb(46, 204, 113),
                url=f"https://osu.ppy.sh/users/{osu_user.id}",
            )

            if osu_user.avatar_url:
                embed.set_thumbnail(url=osu_user.avatar_url)

            lines = []
            for i, s in enumerate(scores or [], start=1):
                lines.append(self._format_score_line(i, s))

            embed.add_field(
                name=tx("osu_info.scores"),
                value="\n".join(lines) if lines else tx("osu_info.no_data"),
                inline=False,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                tx("osu_info.query_failed", v0=(str(e))), ephemeral=True
            )

    def _get_first_attr(self, obj: Any, *names: Any) -> Any:
        """按順序嘗試多個屬性名，取到第一個存在且不為 None 的值。"""
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value is not None:
                    return value
        return None

    def _fmt_int(self, value: Any) -> str:
        """安全格式化整數（含千分位），空值顯示為未知。"""
        if value is None:
            return tx("audit_log.unknown")
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)

    def _resolve_username(self, discord_user_id: int, username: Optional[str]) -> str:
        if username:
            return username
        bound = self.service.get_bound_username(discord_user_id)
        if not bound:
            raise ValueError(tx("osu_info.no_osu_account_is_linked_use"))
        return bound

    def _format_score_line(self, index: int, score: Any) -> str:
        beatmap = getattr(score, "beatmap", None)
        beatmapset = getattr(score, "beatmapset", None)

        title = None
        if beatmapset and hasattr(beatmapset, "title"):
            artist = getattr(beatmapset, "artist", "")
            title = (
                f"{artist} - {beatmapset.title}" if artist else str(beatmapset.title)
            )
        elif beatmap and hasattr(beatmap, "id"):
            title = f"Beatmap {beatmap.id}"
        else:
            title = tx("osu_info.unknown_beatmap")

        version = getattr(beatmap, "version", None)
        version_text = f"[{version}]" if version else ""

        rank = getattr(score, "rank", None)
        rank_text = str(rank) if rank else tx("audit_log.unknown")

        pp = getattr(score, "pp", None)
        pp_text = (
            f"{pp:.2f}pp" if isinstance(pp, (int, float)) else tx("osu_info.unknown_pp")
        )

        acc = getattr(score, "accuracy", None)
        if isinstance(acc, (int, float)):
            acc_text = f"{acc * 100:.2f}%" if acc <= 1 else f"{acc:.2f}%"
        else:
            acc_text = tx("osu_info.unknown")

        miss = getattr(score, "statistics", None)
        miss_count = None
        if miss and hasattr(miss, "count_miss"):
            miss_count = miss.count_miss

        miss_text = f"Miss {miss_count}" if miss_count is not None else ""
        parts = [f"{index}. {title} {version_text}", f"{rank_text}", pp_text, acc_text]
        if miss_text:
            parts.append(miss_text)

        return " | ".join([p for p in parts if p])


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(OsuInfo(bot))
