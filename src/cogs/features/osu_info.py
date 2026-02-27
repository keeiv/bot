from datetime import datetime
import json
import os

import discord
from discord import app_commands
from discord.ext import commands
from ossapi import Ossapi


class OsuInfo(commands.Cog):
    """osu! 用戶信息查詢"""

    osu = app_commands.Group(name="osu", description="osu! 查詢")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/storage/osu_links.json"
        os.makedirs("data/storage", exist_ok=True)

        client_id = os.getenv("OSU_CLIENT_ID")
        client_secret = os.getenv("OSU_CLIENT_SECRET")
        self.api = None
        self._api_error = None
        if not client_id or not client_secret:
            self._api_error = "缺少 OSU_CLIENT_ID 或 OSU_CLIENT_SECRET 環境變數"
        else:
            self.api = Ossapi(int(client_id), client_secret)
        self._links = self._load_links()

    def _ensure_api(self):
        if self.api is None:
            raise RuntimeError(
                "osu 功能尚未啟用。請在專案根目錄的 .env 加上 OSU_CLIENT_ID 與 OSU_CLIENT_SECRET，然後重啟 bot。"
            )

    @app_commands.command(name="user_info_osu", description="查詢 osu! 用戶信息")
    @app_commands.describe(username="osu! 用戶名")
    async def user_info_osu(self, interaction: discord.Interaction, username: str):
        """查詢 osu! 用戶信息"""
        try:
            await interaction.response.defer()

            self._ensure_api()

            # 抓取玩家資料
            user = self.api.user(username)

            # 創建嵌入消息
            embed = discord.Embed(
                title=f"osu! 用戶信息 - {user.username}",
                color=discord.Color.pink(),
                url=f"https://osu.ppy.sh/users/{user.id}",
            )

            # 設置頭像
            if user.avatar_url:
                embed.set_thumbnail(url=user.avatar_url)

            # 基本信息欄位
            basic_info = f"**用戶名**: {user.username}\n"
            basic_info += f"**等級**: {user.statistics.level.current}\n"
            basic_info += (
                f"**全球排名**: #{user.statistics.global_rank:,}\n"
                if user.statistics.global_rank
                else "**全球排名**: 未排名\n"
            )
            basic_info += (
                f"**國家排名**: #{user.statistics.country_rank:,}\n"
                if user.statistics.country_rank
                else "**國家排名**: 未排名\n"
            )
            basic_info += f"**PP**: {user.statistics.pp:,.2f}\n"
            basic_info += f"**準確度**: {user.statistics.hit_accuracy:.2f}%\n"
            basic_info += (
                f"**遊戲時間**: {self._format_playtime(user.statistics.play_time)}\n"
            )
            basic_info += f"**是否為 Supporter**: {'是' if user.is_supporter else '否'}"

            embed.add_field(name="基本信息", value=basic_info, inline=False)

            # 成績統計
            counts = user.statistics.grade_counts
            grades_info = f"**SS (金)**: {counts.ss}\n"
            grades_info += f"**SS (銀/白金)**: {counts.ssh}\n"
            grades_info += f"**S (金)**: {counts.s}\n"
            grades_info += f"**S (銀/白金)**: {counts.sh}\n"
            grades_info += f"**A 等級**: {counts.a}"

            embed.add_field(name="成績統計", value=grades_info, inline=True)

            # 遊戲統計
            stats = user.statistics
            play_count = self._get_first_attr(stats, "play_count", "playcount")
            total_score = self._get_first_attr(stats, "total_score")
            ranked_score = self._get_first_attr(stats, "ranked_score")
            maximum_combo = self._get_first_attr(stats, "maximum_combo", "max_combo")
            total_hits = self._get_first_attr(stats, "total_hits")

            playcount_info = f"**遊戲次數**: {self._fmt_int(play_count)}\n"
            playcount_info += f"**總分**: {self._fmt_int(total_score)}\n"
            playcount_info += f"**排名後總分**: {self._fmt_int(ranked_score)}\n"
            playcount_info += f"**最高連擊**: {self._fmt_int(maximum_combo)}\n"
            playcount_info += f"**總命中**: {self._fmt_int(total_hits)}"

            embed.add_field(name="遊戲統計", value=playcount_info, inline=True)

            # 附加信息
            if user.cover_url:
                embed.set_image(url=user.cover_url)

            embed.set_footer(
                text=f"用戶 ID: {user.id} | 加入時間: {user.join_date.strftime('%Y-%m-%d') if user.join_date else '未知'}"
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            error_msg = f"無法找到用戶 '{username}' 或發生錯誤: {str(e)}"
            await interaction.followup.send(error_msg, ephemeral=True)

    @osu.command(name="bind", description="綁定你的 osu! 帳號")
    @app_commands.describe(username="osu! 用戶名")
    async def osu_bind(self, interaction: discord.Interaction, username: str):
        try:
            await interaction.response.defer(ephemeral=True)

            self._ensure_api()

            osu_user = self.api.user(username)
            self._links[str(interaction.user.id)] = {
                "username": osu_user.username,
                "osu_user_id": osu_user.id,
                "bound_at": datetime.utcnow().isoformat(),
            }
            self._save_links(self._links)

            await interaction.followup.send(
                f"已綁定 osu! 帳號: {osu_user.username}", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"綁定失敗: {str(e)}", ephemeral=True)

    @osu.command(name="unbind", description="解除綁定你的 osu! 帳號")
    async def osu_unbind(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        key = str(interaction.user.id)
        if key not in self._links:
            await interaction.followup.send("你尚未綁定 osu! 帳號", ephemeral=True)
            return

        old = self._links.pop(key)
        self._save_links(self._links)
        await interaction.followup.send(
            f"已解除綁定 osu! 帳號: {old.get('username', '未知')}", ephemeral=True
        )

    @osu.command(name="best", description="查看 osu! BP")
    @app_commands.describe(
        username="osu! 用戶名 (不填則使用你已綁定的帳號)", limit="顯示筆數 (1~10)"
    )
    async def osu_best(
        self, interaction: discord.Interaction, username: str = None, limit: int = 5
    ):
        try:
            await interaction.response.defer()

            self._ensure_api()

            limit = max(1, min(10, limit))
            username = self._resolve_username(interaction.user.id, username)

            osu_user = self.api.user(username)
            scores = self.api.user_scores(osu_user.id, type="best", limit=limit)

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
                name="成績", value="\n".join(lines) if lines else "無資料", inline=False
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"查詢失敗: {str(e)}", ephemeral=True)

    @osu.command(name="recent", description="查看 osu! 最近遊玩")
    @app_commands.describe(
        username="osu! 用戶名 (不填則使用你已綁定的帳號)", limit="顯示筆數 (1~10)"
    )
    async def osu_recent(
        self, interaction: discord.Interaction, username: str = None, limit: int = 5
    ):
        try:
            await interaction.response.defer()

            self._ensure_api()

            limit = max(1, min(10, limit))
            username = self._resolve_username(interaction.user.id, username)

            osu_user = self.api.user(username)
            scores = self.api.user_scores(osu_user.id, type="recent", limit=limit)

            embed = discord.Embed(
                title=f"osu! 最近遊玩 - {osu_user.username}",
                color=discord.Color.from_rgb(46, 204, 113),
                url=f"https://osu.ppy.sh/users/{osu_user.id}",
            )

            if osu_user.avatar_url:
                embed.set_thumbnail(url=osu_user.avatar_url)

            lines = []
            for i, s in enumerate(scores or [], start=1):
                lines.append(self._format_score_line(i, s))

            embed.add_field(
                name="成績", value="\n".join(lines) if lines else "無資料", inline=False
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"查詢失敗: {str(e)}", ephemeral=True)

    def _get_first_attr(self, obj, *names):
        """按順序嘗試多個屬性名，取到第一個存在且不為 None 的值。"""
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value is not None:
                    return value
        return None

    def _fmt_int(self, value) -> str:
        """安全格式化整數（含千分位），空值顯示為未知。"""
        if value is None:
            return "未知"
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)

    def _format_playtime(self, seconds: int) -> str:
        """格式化遊戲時間"""
        if seconds is None:
            return "未知"
        hours = seconds // 3600
        days = hours // 24
        remaining_hours = hours % 24

        if days > 0:
            return f"{days} 天 {remaining_hours} 小時"
        else:
            return f"{hours} 小時"

    def _load_links(self) -> dict:
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_links(self, data: dict):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_bound_osu_username(self, discord_user_id: int) -> str | None:
        bound = self._links.get(str(discord_user_id))
        if not bound:
            return None
        return bound.get("username")

    def _resolve_username(self, discord_user_id: int, username: str | None) -> str:
        if username:
            return username

        bound = self.get_bound_osu_username(discord_user_id)
        if not bound:
            raise ValueError("你尚未綁定 osu! 帳號，請先使用 /osu bind <username>")
        return bound

    def _format_score_line(self, index: int, score) -> str:
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
            title = "未知圖譜"

        version = getattr(beatmap, "version", None)
        version_text = f"[{version}]" if version else ""

        rank = getattr(score, "rank", None)
        rank_text = str(rank) if rank else "未知"

        pp = getattr(score, "pp", None)
        pp_text = f"{pp:.2f}pp" if isinstance(pp, (int, float)) else "未知pp"

        acc = getattr(score, "accuracy", None)
        if isinstance(acc, (int, float)):
            acc_text = f"{acc * 100:.2f}%" if acc <= 1 else f"{acc:.2f}%"
        else:
            acc_text = "未知%"

        miss = getattr(score, "statistics", None)
        miss_count = None
        if miss and hasattr(miss, "count_miss"):
            miss_count = getattr(miss, "count_miss")

        miss_text = f"Miss {miss_count}" if miss_count is not None else ""
        parts = [f"{index}. {title} {version_text}", f"{rank_text}", pp_text, acc_text]
        if miss_text:
            parts.append(miss_text)

        return " | ".join([p for p in parts if p])


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(OsuInfo(bot))
