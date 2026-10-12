"""抽獎系統 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands
from discord.ext import tasks

from src.services.giveaway_service import GiveawayService
from src.utils.i18n import language_scope
from src.utils.i18n import t
from src.utils.i18n import text as tx
from src.utils.lang_context import guild_language
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage

TZ_OFFSET = timezone(timedelta(hours=8))
GIVEAWAY_EMOJI = "\U0001f389"

# 模組級別單例 - GiveawayView 與 Giveaway Cog 共用同一個鎖
_service = GiveawayService()


class GiveawayView(LocalizedView):
    """抽獎按鈕視圖 (持久化)"""

    i18n = {"enter_button.label": "giveaway.enter_giveaway"}

    def __init__(self, giveaway_id: str) -> None:
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @ui.button(
        label="Enter giveaway",
        style=discord.ButtonStyle.primary,
        emoji=GIVEAWAY_EMOJI,
        custom_id="giveaway_enter",
    )
    @localized("interaction")
    async def enter_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """參加抽獎 (使用鎖防止競態條件)"""
        await interaction.response.defer(thinking=True, ephemeral=True)
        async with _service.lock:
            action, count = await run_storage(
                _service.toggle_participant, self.giveaway_id, str(interaction.user.id)
            )

        if action is None:
            await interaction.followup.send(
                tx("giveaway.info_this_giveaway_has_ended"), ephemeral=True
            )
            return

        if action == "left":
            await interaction.followup.send(
                tx("giveaway.info_entry_withdrawn"), ephemeral=True
            )
        else:
            await interaction.followup.send(
                tx("giveaway.success_giveaway_entered_participants", v0=(count)),
                ephemeral=True,
            )

        try:
            if interaction.message is None:
                return
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
            if field.name in {
                t(lang, "giveaway.participants") for lang in ("en", "zh")
            }:
                new_embed.add_field(
                    name=tx("giveaway.participants"),
                    value=tx("anti_spam.members", v0=(count)),
                    inline=field.inline,
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

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = _service
        self.check_giveaways.start()

    async def cog_unload(self) -> None:
        self.check_giveaways.cancel()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """重新載入進行中抽獎的視圖"""
        active = await run_storage(self.service.list_all_active)
        for gid, ga in active:
            self.bot.add_view(GiveawayView(gid), message_id=ga["message_id"])

    # ───────────── 定時檢查 ─────────────

    @tasks.loop(seconds=30)
    async def check_giveaways(self) -> None:
        """檢查並結算到期的抽獎"""
        await self.bot.wait_until_ready()
        expired = await run_storage(self.service.check_expired)
        for gid, ga in expired:
            await self._end_giveaway(gid, ga)

    # ───────────── 指令群組 ─────────────

    giveaway_group = app_commands.Group(
        name="giveaway",
        description="Giveaways",
        default_permissions=discord.Permissions(administrator=True),
    )

    @giveaway_group.command(name="start", description="Start a giveaway")
    @app_commands.describe(
        prize="The prize",
        duration="How long it runs (for example 1h, 30m, 1d, 1d12h)",
        winners="Number of winners",
        channel="The giveaway channel (defaults to this one)",
        description="Prize description (optional)",
    )
    @localized("interaction")
    async def start_cmd(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: int = 1,
        channel: discord.TextChannel | None = None,
        description: str | None = None,
    ) -> None:
        """建立新抽獎"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        total_seconds = self.service.parse_duration(duration)
        if total_seconds is None or total_seconds < 60:
            await interaction.response.send_message(
                tx("giveaway.failed_invalid_duration_examples_1h_30m"),
                ephemeral=True,
            )
            return

        if winners < 1 or winners > 50:
            await interaction.response.send_message(
                tx("giveaway.failed_winner_count_must_be_between"), ephemeral=True
            )
            return

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                tx("giveaway.select_a_text_channel_or_thread"), ephemeral=True
            )
            return
        now = datetime.now(TZ_OFFSET)
        end_dt = now + timedelta(seconds=total_seconds)
        giveaway_id = f"{interaction.guild_id}_{int(now.timestamp())}"

        embed = discord.Embed(
            title=tx("giveaway.giveaway", v0=(GIVEAWAY_EMOJI)),
            description=f"**{prize}**",
            color=discord.Color.from_rgb(255, 215, 0),
            timestamp=end_dt,
        )
        if description:
            embed.add_field(
                name=tx("giveaway.prize_details"), value=description, inline=False
            )
        embed.add_field(
            name=tx("giveaway.winner_count"),
            value=tx("anti_spam.members", v0=(winners)),
            inline=True,
        )
        embed.add_field(
            name=tx("giveaway.ends_at"),
            value=f"<t:{int(end_dt.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name=tx("giveaway.participants"),
            value=tx("giveaway.0_members"),
            inline=True,
        )
        embed.add_field(
            name=tx("giveaway.hosted_by"), value=interaction.user.mention, inline=True
        )
        embed.set_footer(text=tx("giveaway.id_ends_at", v0=(giveaway_id)))

        view = GiveawayView(giveaway_id)
        await interaction.response.defer()
        msg = await target_channel.send(embed=embed, view=view)

        await run_storage(
            self.service.create,
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
        self.bot.add_view(view, message_id=msg.id)

        confirm = discord.Embed(
            title=tx("giveaway.success_giveaway_created"),
            description=tx(
                "giveaway.prize_channel_ends_t_r",
                v0=(prize),
                v1=(target_channel.mention),
                v2=(int(end_dt.timestamp())),
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=confirm, ephemeral=True)

    @giveaway_group.command(name="end", description="End a giveaway early")
    @app_commands.describe(giveaway_id="Giveaway ID (shown in the embed footer)")
    @localized("interaction")
    async def end_cmd(self, interaction: discord.Interaction, giveaway_id: str) -> None:
        """提前結束抽獎"""
        ga = await run_storage(self.service.get, giveaway_id)
        if not ga:
            await interaction.response.send_message(
                tx("giveaway.failed_giveaway_not_found"), ephemeral=True
            )
            return
        if ga.get("ended"):
            await interaction.response.send_message(
                tx("giveaway.failed_this_giveaway_has_ended"), ephemeral=True
            )
            return

        await interaction.response.defer()
        await self._end_giveaway(giveaway_id, ga)
        await interaction.followup.send(
            tx("giveaway.success_giveaway_ended_early_and_winners"), ephemeral=True
        )

    @giveaway_group.command(name="reroll", description="Draw new winners")
    @app_commands.describe(
        giveaway_id="Giveaway ID",
        winners="How many to draw (defaults to the original number)",
    )
    @localized("interaction")
    async def reroll_cmd(
        self,
        interaction: discord.Interaction,
        giveaway_id: str,
        winners: int | None = None,
    ) -> None:
        """重新抽取得獎者"""
        ga = await run_storage(self.service.get, giveaway_id)
        if not ga or not ga.get("ended"):
            await interaction.response.send_message(
                tx("giveaway.failed_finished_giveaway_not_found"), ephemeral=True
            )
            return

        num_winners = winners or ga["winners"]
        winner_ids = await run_storage(self.service.reroll, giveaway_id, num_winners)

        if not winner_ids:
            await interaction.response.send_message(
                tx("giveaway.failed_no_participants"), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
        try:
            ch = self.bot.get_channel(ga["channel_id"])
            if isinstance(ch, discord.abc.Messageable):
                reroll_embed = discord.Embed(
                    title=tx("giveaway.redraw_results", v0=(GIVEAWAY_EMOJI)),
                    description=tx(
                        "giveaway.prize_new_winners", v0=(ga["prize"]), v1=(mentions)
                    ),
                    color=discord.Color.from_rgb(255, 215, 0),
                )
                await ch.send(embed=reroll_embed)
        except Exception:
            pass

        await interaction.followup.send(
            tx("giveaway.success_winners_redrawn", v0=(mentions)), ephemeral=True
        )

    @giveaway_group.command(name="list", description="Show running giveaways")
    @localized("interaction")
    async def list_cmd(self, interaction: discord.Interaction) -> None:
        """列出伺服器所有進行中的抽獎"""
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
        active = await run_storage(self.service.list_active, interaction.guild_id)

        if not active:
            await interaction.followup.send(
                tx("giveaway.info_no_active_giveaways"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("giveaway.active_giveaways", v0=(GIVEAWAY_EMOJI)),
            color=discord.Color.from_rgb(255, 215, 0),
        )
        for gid, ga in active[:10]:
            participants = len(ga.get("participants", []))
            end_ts = int(ga["end_time"])
            embed.add_field(
                name=ga["prize"],
                value=(
                    tx(
                        "giveaway.id_winners_participants_ends_t_r",
                        v0=(gid),
                        v1=(ga["winners"]),
                        v2=(participants),
                        v3=(end_ts),
                    )
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ───────────── 內部方法 ─────────────

    async def _end_giveaway(self, giveaway_id: str, ga: dict[Any, Any]) -> None:
        """結算抽獎並發送結果"""
        lang = await guild_language(ga["guild_id"])
        with language_scope(lang):
            winner_ids = await run_storage(self.service.pick_winners, giveaway_id)
            await run_storage(self.service.mark_ended, giveaway_id, winner_ids)

            participants_count = len(ga.get("participants", []))
            if winner_ids:
                mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
                result_embed = discord.Embed(
                    title=tx("giveaway.giveaway_ended", v0=(GIVEAWAY_EMOJI)),
                    description=tx(
                        "giveaway.prize_winners", v0=(ga["prize"]), v1=(mentions)
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.now(TZ_OFFSET),
                )
            else:
                mentions = None
                result_embed = discord.Embed(
                    title=tx("giveaway.giveaway_ended_9e59c1", v0=(GIVEAWAY_EMOJI)),
                    description=tx(
                        "giveaway.prize_not_enough_participants", v0=(ga["prize"])
                    ),
                    color=discord.Color.from_rgb(231, 76, 60),
                    timestamp=datetime.now(TZ_OFFSET),
                )
            result_embed.add_field(
                name=tx("giveaway.participants"),
                value=tx("anti_spam.members", v0=(participants_count)),
                inline=True,
            )
            result_embed.set_footer(text=f"ID: {giveaway_id}")

            try:
                ch = self.bot.get_channel(ga["channel_id"])
                if not isinstance(
                    ch,
                    (
                        discord.TextChannel,
                        discord.Thread,
                        discord.VoiceChannel,
                        discord.StageChannel,
                    ),
                ):
                    ch = await self.bot.fetch_channel(ga["channel_id"])

                try:
                    msg = await ch.fetch_message(ga["message_id"])
                    ended_embed = discord.Embed(
                        title=tx("giveaway.giveaway_has_ended", v0=(GIVEAWAY_EMOJI)),
                        description=f"**{ga['prize']}**",
                        color=discord.Color.from_rgb(128, 128, 128),
                    )
                    ended_embed.add_field(
                        name=tx("giveaway.winners"),
                        value=(
                            mentions if winner_ids else tx("giveaway.no_participants")
                        ),
                        inline=False,
                    )
                    ended_embed.add_field(
                        name=tx("giveaway.participants"),
                        value=tx("anti_spam.members", v0=(participants_count)),
                        inline=True,
                    )
                    ended_embed.set_footer(
                        text=tx("giveaway.id_ended", v0=(giveaway_id))
                    )
                    await msg.edit(embed=ended_embed, view=None)
                except Exception:
                    pass

                await ch.send(embed=result_embed)

                if winner_ids:
                    await ch.send(
                        tx(
                            "giveaway.congratulations_on_winning_contact_to_claim",
                            v0=(mentions),
                            v1=(ga["prize"]),
                            v2=(ga["host_id"]),
                        )
                    )
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(Giveaway(bot))
