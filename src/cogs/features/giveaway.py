import asyncio
import json
import os
import random
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands
from discord.ext import tasks

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# 資料檔案路徑
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "storage",
)
GIVEAWAY_FILE = os.path.join(DATA_DIR, "giveaways.json")

# 抽獎表情
GIVEAWAY_EMOJI = "\U0001f389"  # 🎉

# 全域鎖：防止並發讀寫競態條件
_giveaway_lock = asyncio.Lock()

# 記憶體快取
_giveaway_cache: Optional[dict] = None


def _load_giveaways() -> dict:
    """載入抽獎資料 (優先讀取快取)"""
    global _giveaway_cache
    if _giveaway_cache is not None:
        return _giveaway_cache

    if os.path.exists(GIVEAWAY_FILE):
        try:
            with open(GIVEAWAY_FILE, "r", encoding="utf-8") as f:
                _giveaway_cache = json.load(f)
                return _giveaway_cache
        except (json.JSONDecodeError, OSError):
            pass
    _giveaway_cache = {}
    return _giveaway_cache


def _save_giveaways(data: dict):
    """儲存抽獎資料並更新快取"""
    global _giveaway_cache
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(GIVEAWAY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _giveaway_cache = data


class GiveawayView(ui.View):
    """抽獎按鈕視圖"""

    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @ui.button(
        label="參加抽獎",
        style=discord.ButtonStyle.primary,
        emoji=GIVEAWAY_EMOJI,
        custom_id="giveaway_enter",
    )
    async def enter_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """參加抽獎 (使用鎖防止競態條件)"""
        async with _giveaway_lock:
            data = _load_giveaways()
            ga = data.get(self.giveaway_id)

            if not ga or ga.get("ended"):
                await interaction.response.send_message(
                    "[提示] 此抽獎已結束", ephemeral=True
                )
                return

            user_id = str(interaction.user.id)
            participants = ga.setdefault("participants", [])

            if user_id in participants:
                participants.remove(user_id)
                _save_giveaways(data)
                await interaction.response.send_message(
                    "[提示] 你已退出抽獎", ephemeral=True
                )
            else:
                participants.append(user_id)
                _save_giveaways(data)
                await interaction.response.send_message(
                    f"[成功] 你已參加抽獎! 目前共 {len(participants)} 位參與者",
                    ephemeral=True,
                )

        # 更新 Embed 上的參與人數 (鎖外操作，減少持鎖時間)
        try:
            embed = interaction.message.embeds[0] if interaction.message.embeds else None
            if embed:
                new_embed = self._update_participant_count(embed, len(participants))
                await interaction.message.edit(embed=new_embed)
        except Exception:
            pass

    @staticmethod
    def _update_participant_count(
        embed: discord.Embed, count: int
    ) -> discord.Embed:
        """更新 Embed 上的參與人數"""
        new_embed = discord.Embed(
            title=embed.title,
            description=embed.description,
            color=embed.color,
            timestamp=embed.timestamp,
        )
        for field in embed.fields:
            if field.name == "參與人數":
                new_embed.add_field(
                    name="參與人數", value=f"{count} 人", inline=field.inline
                )
            else:
                new_embed.add_field(
                    name=field.name, value=field.value, inline=field.inline
                )
        if embed.footer:
            new_embed.set_footer(text=embed.footer.text)
        return new_embed


class Giveaway(commands.Cog):
    """抽獎系統 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """重新載入進行中抽獎的視圖"""
        data = _load_giveaways()
        for gid, ga in data.items():
            if not ga.get("ended"):
                self.bot.add_view(GiveawayView(gid))

    # ───────────── 定時檢查 ─────────────

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        """檢查並結算到期的抽獎"""
        await self.bot.wait_until_ready()

        data = _load_giveaways()
        now = datetime.now(TZ_OFFSET).timestamp()
        changed = False

        for gid, ga in list(data.items()):
            if ga.get("ended"):
                continue
            if now >= ga["end_time"]:
                await self._end_giveaway(gid, ga)
                ga["ended"] = True
                changed = True

        if changed:
            _save_giveaways(data)

    # ───────────── 指令群組 ─────────────

    giveaway_group = app_commands.Group(
        name="giveaway",
        description="抽獎系統",
        default_permissions=discord.Permissions(administrator=True),
    )

    @giveaway_group.command(name="start", description="建立新的抽獎活動")
    @app_commands.describe(
        prize="獎品名稱",
        duration="持續時間 (例: 1h, 30m, 1d, 1d12h)",
        winners="得獎人數",
        channel="抽獎頻道 (預設為當前頻道)",
        description="獎品描述 (選填)",
    )
    async def start_cmd(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: int = 1,
        channel: discord.TextChannel = None,
        description: str = None,
    ):
        """建立新抽獎"""
        # 解析時長
        total_seconds = self._parse_duration(duration)
        if total_seconds is None or total_seconds < 60:
            await interaction.response.send_message(
                "[失敗] 無效時長格式 (例: 1h, 30m, 1d, 2d6h)，最短 1 分鐘",
                ephemeral=True,
            )
            return

        if winners < 1 or winners > 50:
            await interaction.response.send_message(
                "[失敗] 得獎人數必須在 1~50 之間", ephemeral=True
            )
            return

        target_channel = channel or interaction.channel
        now = datetime.now(TZ_OFFSET)
        end_dt = now + timedelta(seconds=total_seconds)

        # 建立唯一 ID
        giveaway_id = f"{interaction.guild_id}_{int(now.timestamp())}"

        # 建立 Embed
        embed = discord.Embed(
            title=f"{GIVEAWAY_EMOJI} 抽獎活動",
            description=f"**{prize}**",
            color=discord.Color.from_rgb(255, 215, 0),
            timestamp=end_dt,
        )
        if description:
            embed.add_field(name="獎品說明", value=description, inline=False)
        embed.add_field(
            name="得獎人數", value=f"{winners} 人", inline=True
        )
        embed.add_field(
            name="結束時間",
            value=f"<t:{int(end_dt.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(name="參與人數", value="0 人", inline=True)
        embed.add_field(
            name="主辦者",
            value=f"{interaction.user.mention}",
            inline=True,
        )
        embed.set_footer(text=f"ID: {giveaway_id} | 結束於")

        view = GiveawayView(giveaway_id)
        await interaction.response.defer()

        msg = await target_channel.send(embed=embed, view=view)

        # 儲存資料
        data = _load_giveaways()
        data[giveaway_id] = {
            "guild_id": interaction.guild_id,
            "channel_id": target_channel.id,
            "message_id": msg.id,
            "prize": prize,
            "description": description,
            "winners": winners,
            "host_id": interaction.user.id,
            "end_time": end_dt.timestamp(),
            "participants": [],
            "ended": False,
            "winner_ids": [],
        }
        _save_giveaways(data)

        self.bot.add_view(view)

        confirm_embed = discord.Embed(
            title="[成功] 抽獎已建立",
            description=f"獎品: **{prize}**\n頻道: {target_channel.mention}\n結束: <t:{int(end_dt.timestamp())}:R>",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

    @giveaway_group.command(name="end", description="提前結束抽獎")
    @app_commands.describe(giveaway_id="抽獎 ID (可從 Embed footer 查看)")
    async def end_cmd(
        self, interaction: discord.Interaction, giveaway_id: str
    ):
        """提前結束抽獎"""
        data = _load_giveaways()
        ga = data.get(giveaway_id)

        if not ga:
            await interaction.response.send_message(
                "[失敗] 找不到此抽獎", ephemeral=True
            )
            return

        if ga.get("ended"):
            await interaction.response.send_message(
                "[失敗] 此抽獎已結束", ephemeral=True
            )
            return

        await interaction.response.defer()
        await self._end_giveaway(giveaway_id, ga)
        ga["ended"] = True
        _save_giveaways(data)

        await interaction.followup.send(
            "[成功] 抽獎已提前結束並抽出得獎者", ephemeral=True
        )

    @giveaway_group.command(name="reroll", description="重新抽取得獎者")
    @app_commands.describe(
        giveaway_id="抽獎 ID",
        winners="重新抽取的人數 (預設為原始設定)",
    )
    async def reroll_cmd(
        self,
        interaction: discord.Interaction,
        giveaway_id: str,
        winners: int = None,
    ):
        """重新抽取得獎者"""
        data = _load_giveaways()
        ga = data.get(giveaway_id)

        if not ga or not ga.get("ended"):
            await interaction.response.send_message(
                "[失敗] 找不到已結束的抽獎", ephemeral=True
            )
            return

        num_winners = winners or ga["winners"]
        participants = ga.get("participants", [])

        if not participants:
            await interaction.response.send_message(
                "[失敗] 沒有參與者", ephemeral=True
            )
            return

        winner_ids = random.sample(
            participants, min(num_winners, len(participants))
        )
        ga["winner_ids"] = winner_ids
        _save_giveaways(data)

        mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)

        # 在原頻道公告
        try:
            ch = self.bot.get_channel(ga["channel_id"])
            if ch:
                reroll_embed = discord.Embed(
                    title=f"{GIVEAWAY_EMOJI} 重新抽獎結果",
                    description=f"獎品: **{ga['prize']}**\n新得獎者: {mentions}",
                    color=discord.Color.from_rgb(255, 215, 0),
                )
                await ch.send(embed=reroll_embed)
        except Exception:
            pass

        await interaction.response.send_message(
            f"[成功] 重新抽取完成! 得獎者: {mentions}", ephemeral=True
        )

    @giveaway_group.command(name="list", description="查看進行中的抽獎")
    async def list_cmd(self, interaction: discord.Interaction):
        """列出伺服器所有進行中的抽獎"""
        await interaction.response.defer()

        data = _load_giveaways()
        guild_id = interaction.guild_id

        active = [
            (gid, ga)
            for gid, ga in data.items()
            if ga["guild_id"] == guild_id and not ga.get("ended")
        ]

        if not active:
            await interaction.followup.send(
                "[提示] 目前沒有進行中的抽獎", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{GIVEAWAY_EMOJI} 進行中的抽獎",
            color=discord.Color.from_rgb(255, 215, 0),
        )

        for gid, ga in active[:10]:
            participants = len(ga.get("participants", []))
            end_ts = int(ga["end_time"])
            embed.add_field(
                name=ga["prize"],
                value=(
                    f"ID: `{gid}`\n"
                    f"得獎人數: {ga['winners']} | 參與: {participants} 人\n"
                    f"結束: <t:{end_ts}:R>"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ───────────── 內部方法 ─────────────

    async def _end_giveaway(self, giveaway_id: str, ga: dict):
        """結算抽獎並發送結果"""
        participants = ga.get("participants", [])
        num_winners = ga["winners"]

        if participants:
            winner_ids = random.sample(
                participants, min(num_winners, len(participants))
            )
        else:
            winner_ids = []

        ga["winner_ids"] = winner_ids

        # 建立結果 Embed
        if winner_ids:
            mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            result_embed = discord.Embed(
                title=f"{GIVEAWAY_EMOJI} 抽獎結束!",
                description=f"獎品: **{ga['prize']}**\n\n得獎者: {mentions}",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
        else:
            result_embed = discord.Embed(
                title=f"{GIVEAWAY_EMOJI} 抽獎結束",
                description=f"獎品: **{ga['prize']}**\n\n沒有足夠的參與者",
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )

        result_embed.add_field(
            name="參與人數", value=f"{len(participants)} 人", inline=True
        )
        result_embed.set_footer(text=f"ID: {giveaway_id}")

        try:
            ch = self.bot.get_channel(ga["channel_id"])
            if not ch:
                ch = await self.bot.fetch_channel(ga["channel_id"])

            # 更新原始訊息
            try:
                msg = await ch.fetch_message(ga["message_id"])
                ended_embed = discord.Embed(
                    title=f"{GIVEAWAY_EMOJI} 抽獎已結束",
                    description=f"**{ga['prize']}**",
                    color=discord.Color.from_rgb(128, 128, 128),
                )
                ended_embed.add_field(
                    name="得獎者",
                    value=mentions if winner_ids else "無人參與",
                    inline=False,
                )
                ended_embed.add_field(
                    name="參與人數",
                    value=f"{len(participants)} 人",
                    inline=True,
                )
                ended_embed.set_footer(text=f"ID: {giveaway_id} | 已結束")
                await msg.edit(embed=ended_embed, view=None)
            except Exception:
                pass

            # 發送結果公告
            await ch.send(embed=result_embed)

            # @得獎者
            if winner_ids:
                await ch.send(
                    f"恭喜 {mentions} 獲得 **{ga['prize']}**! "
                    f"請聯繫 <@{ga['host_id']}> 領取獎品"
                )

        except Exception:
            pass

    @staticmethod
    def _parse_duration(text: str) -> Optional[int]:
        """解析時長字串，回傳總秒數"""
        text = text.strip().lower()
        total = 0
        current = ""

        for char in text:
            if char.isdigit():
                current += char
            elif char in ("d", "h", "m", "s"):
                if not current:
                    return None
                num = int(current)
                if char == "d":
                    total += num * 86400
                elif char == "h":
                    total += num * 3600
                elif char == "m":
                    total += num * 60
                elif char == "s":
                    total += num
                current = ""
            else:
                return None

        # 純數字視為秒
        if current:
            total += int(current)

        return total if total > 0 else None


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Giveaway(bot))
