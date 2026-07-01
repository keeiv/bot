"""抽獎系統 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands
from discord.ext import tasks

from src.services.giveaway_service import GiveawayService

TZ_OFFSET = timezone(timedelta(hours=8))
GIVEAWAY_EMOJI = "\U0001f389"

# 模組級別單例 - GiveawayView 與 Giveaway Cog 共用同一個鎖
_service = GiveawayService()


class GiveawayView(ui.View):
    """抽獎按鈕視圖 (持久化)"""

    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @ui.button(
        label="參加抽獎",
        style=discord.ButtonStyle.primary,
        emoji=GIVEAWAY_EMOJI,
        custom_id="giveaway_enter",
    )
    async def enter_button(self, interaction: discord.Interaction, button: ui.Button):
        """參加抽獎 (使用鎖防止競態條件)"""
        async with _service.lock:
            action, count = _service.toggle_participant(
                self.giveaway_id, str(interaction.user.id)
            )

        if action is None:
            await interaction.response.send_message(
                "[提示] 此抽獎已結束", ephemeral=True
            )
            return

        if action == "left":
            await interaction.response.send_message(
                "[提示] 你已退出抽獎", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"[成功] 你已參加抽獎！目前共 {count} 位參與者", ephemeral=True
            )

        try:
            embed = (
                interaction.message.embeds[0] if interaction.message.embeds else None
            )
            if embed:
                new_embed = self._update_participant_count(embed, count)
                await interaction.message.edit(embed=new_embed)
        except Exception:
            pass

    @staticmethod
    def _update_participant_count(embed: discord.Embed, count: int) -> discord.Embed:
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
        self.service = _service
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """重新載入進行中抽獎的視圖"""
        data = self.service._load()
        for gid, ga in data.items():
            if not ga.get("ended"):
                self.bot.add_view(GiveawayView(gid))

    # ───────────── 定時檢查 ─────────────

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        """檢查並結算到期的抽獎"""
        await self.bot.wait_until_ready()
        expired = self.service.check_expired()
        for gid, ga in expired:
            await self._end_giveaway(gid, ga)

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
        total_seconds = self.service.parse_duration(duration)
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
        giveaway_id = f"{interaction.guild_id}_{int(now.timestamp())}"

        embed = discord.Embed(
            title=f"{GIVEAWAY_EMOJI} 抽獎活動",
            description=f"**{prize}**",
            color=discord.Color.from_rgb(255, 215, 0),
            timestamp=end_dt,
        )
        if description:
            embed.add_field(name="獎品說明", value=description, inline=False)
        embed.add_field(name="得獎人數", value=f"{winners} 人", inline=True)
        embed.add_field(
            name="結束時間", value=f"<t:{int(end_dt.timestamp())}:R>", inline=True
        )
        embed.add_field(name="參與人數", value="0 人", inline=True)
        embed.add_field(name="主辦者", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"ID: {giveaway_id} | 結束於")

        view = GiveawayView(giveaway_id)
        await interaction.response.defer()
        msg = await target_channel.send(embed=embed, view=view)

        self.service.create(
            giveaway_id,
            {
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
            },
        )
        self.bot.add_view(view)

        confirm = discord.Embed(
            title="[成功] 抽獎已建立",
            description=f"獎品: **{prize}**\n頻道: {target_channel.mention}\n結束: <t:{int(end_dt.timestamp())}:R>",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=confirm, ephemeral=True)

    @giveaway_group.command(name="end", description="提前結束抽獎")
    @app_commands.describe(giveaway_id="抽獎 ID (可從 Embed footer 查看)")
    async def end_cmd(self, interaction: discord.Interaction, giveaway_id: str):
        """提前結束抽獎"""
        ga = self.service.get(giveaway_id)
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
        ga = self.service.get(giveaway_id)
        if not ga or not ga.get("ended"):
            await interaction.response.send_message(
                "[失敗] 找不到已結束的抽獎", ephemeral=True
            )
            return

        num_winners = winners or ga["winners"]
        winner_ids = self.service.reroll(giveaway_id, num_winners)

        if not winner_ids:
            await interaction.response.send_message("[失敗] 沒有參與者", ephemeral=True)
            return

        mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
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
            f"[成功] 重新抽取完成！得獎者: {mentions}", ephemeral=True
        )

    @giveaway_group.command(name="list", description="查看進行中的抽獎")
    async def list_cmd(self, interaction: discord.Interaction):
        """列出伺服器所有進行中的抽獎"""
        await interaction.response.defer()
        active = self.service.list_active(interaction.guild_id)

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
        winner_ids = self.service.pick_winners(giveaway_id)
        self.service.mark_ended(giveaway_id, winner_ids)

        participants_count = len(ga.get("participants", []))
        if winner_ids:
            mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            result_embed = discord.Embed(
                title=f"{GIVEAWAY_EMOJI} 抽獎結束！",
                description=f"獎品: **{ga['prize']}**\n\n得獎者: {mentions}",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
        else:
            mentions = None
            result_embed = discord.Embed(
                title=f"{GIVEAWAY_EMOJI} 抽獎結束",
                description=f"獎品: **{ga['prize']}**\n\n沒有足夠的參與者",
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.now(TZ_OFFSET),
            )
        result_embed.add_field(
            name="參與人數", value=f"{participants_count} 人", inline=True
        )
        result_embed.set_footer(text=f"ID: {giveaway_id}")

        try:
            ch = self.bot.get_channel(ga["channel_id"])
            if not ch:
                ch = await self.bot.fetch_channel(ga["channel_id"])

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
                    name="參與人數", value=f"{participants_count} 人", inline=True
                )
                ended_embed.set_footer(text=f"ID: {giveaway_id} | 已結束")
                await msg.edit(embed=ended_embed, view=None)
            except Exception:
                pass

            await ch.send(embed=result_embed)

            if winner_ids:
                await ch.send(
                    f"恭喜 {mentions} 獲得 **{ga['prize']}**！"
                    f"請聯繫 <@{ga['host_id']}> 領取獎品"
                )
        except Exception:
            pass


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Giveaway(bot))
