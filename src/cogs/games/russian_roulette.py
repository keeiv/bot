import random
from typing import Any, Dict, List

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.services.game_service import RouletteGame
from src.utils.domain_text import item_name
from src.utils.domain_text import items_text
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView


class RussianRoulette(commands.Cog):
    """極限籌碼：紅黑左輪 - 俄羅斯輪盤遊戲"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: Dict[int, "RouletteGame"] = {}  # channel_id -> game
        self.player_data: Dict[int, Dict[Any, Any]] = {}  # user_id -> player stats

    class GameView(LocalizedView):
        """遊戲主視圖"""

        i18n = {
            "pull_trigger.label": "russian_roulette.pull_trigger",
            "use_item.label": "deep_sea_oxygen.use_item",
        }

        def __init__(self, game: "RouletteGame", cog: "RussianRoulette") -> None:
            super().__init__(timeout=180)  # 3分鐘超時
            self.game = game
            self.cog = cog

        @localized()
        async def on_timeout(self) -> None:
            """超時處理"""
            if self.game.game_active:
                self.game.game_active = False
                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.game_ended_timed_out"),
                    description=tx("deep_sea_oxygen.the_game_ended_due_to_inactivity"),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await self.game.channel.send(embed=embed)
                if self.game.channel.id in self.cog.active_games:
                    del self.cog.active_games[self.game.channel.id]

        @ui.button(label="Pull trigger", style=discord.ButtonStyle.danger)
        @localized("interaction")
        async def pull_trigger(
            self, interaction: discord.Interaction, button: ui.Button[Any]
        ) -> None:
            """扣動扳機"""
            if not self.game.game_active:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.the_game_has_ended"), ephemeral=True
                )
                return

            if interaction.user != self.game.current_player:
                await interaction.response.send_message(
                    tx("russian_roulette.it_is_another_player_s_turn"), ephemeral=True
                )
                return

            # 執行開槍
            is_hit = self.game.current_chamber == self.game.bullet_position

            if is_hit:
                # 中彈
                damage = self.game.calculate_damage()
                player, chips, items = self.game.get_current_player_data()

                # 檢查是否有空包彈
                if interaction.user.id in self.game.blank_round_players:
                    damage = damage // 2
                    self.game.blank_round_players.remove(interaction.user.id)
                elif "空包彈" in items:
                    damage = damage // 2
                    items.remove("空包彈")

                # 扣除籌碼
                if self.game.current_player == self.game.player1:
                    self.game.player1_chips -= damage
                else:
                    self.game.player2_chips -= damage

                embed = discord.Embed(
                    title=tx("russian_roulette.hit_round_result"),
                    description=tx(
                        "russian_roulette.pulls_the_trigger_bang_ct_lost",
                        v0=(interaction.user.mention),
                        v1=(damage),
                    ),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await interaction.response.send_message(embed=embed)

                # 檢查是否結束遊戲
                if (
                    self.game.round >= self.game.max_rounds
                    or self.game.player1_chips <= 0
                    or self.game.player2_chips <= 0
                ):
                    await self._end_game()
                else:
                    self.game.next_round()
                    await self._show_game_status()
            else:
                # 空槍
                self.game.empty_shots_this_round += 1
                self.game.current_chamber += 1

                embed = discord.Embed(
                    title=tx("russian_roulette.empty_shot_safe"),
                    description=tx(
                        "russian_roulette.pulls_the_trigger_click_safe_this",
                        v0=(interaction.user.mention),
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                )
                await interaction.response.send_message(embed=embed)

                # 切換玩家
                self.game.switch_player()
                await self._show_game_status()

        @ui.button(label="Use item", style=discord.ButtonStyle.primary)
        @localized("interaction")
        async def use_item(
            self, interaction: discord.Interaction, button: ui.Button[Any]
        ) -> None:
            """使用道具"""
            if not self.game.game_active:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.the_game_has_ended"), ephemeral=True
                )
                return

            if interaction.user != self.game.current_player:
                await interaction.response.send_message(
                    tx("russian_roulette.it_is_another_player_s_turn"), ephemeral=True
                )
                return

            player, chips, items = self.game.get_current_player_data()

            if not items:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.no_items_are_available"), ephemeral=True
                )
                return

            # 創建道具選擇視圖
            view = self.cog.ItemSelectView(self.game, self.cog, items)
            embed = discord.Embed(
                title=tx("russian_roulette.items_choose_an_item"),
                description=tx("russian_roulette.choose_an_item_to_use"),
                color=discord.Color.from_rgb(52, 152, 219),
            )
            for i, item in enumerate(items, 1):
                embed.add_field(
                    name=f"{i}. {item_name(item)}",
                    value=self._get_item_description(item),
                    inline=False,
                )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        def _get_item_description(self, item: str) -> str:
            """獲取道具描述"""
            descriptions = {
                "透視眼鏡": tx(
                    "russian_roulette.check_whether_the_next_chamber_contains"
                ),
                "命運洗牌": tx("russian_roulette.spin_the_cylinder_again_to_move"),
                "空包彈": tx("russian_roulette.halve_the_damage_if_the_next"),
                "強制轉向": tx("russian_roulette.force_the_opponent_to_take_this"),
                "加倍賭注": tx("russian_roulette.double_the_damage_for_this_round"),
            }
            return descriptions.get(item, tx("russian_roulette.unknown_item"))

        async def _show_game_status(self) -> None:
            """顯示遊戲狀態"""
            embed = discord.Embed(
                title=tx(
                    "russian_roulette.round_red_and_black_roulette",
                    v0=(self.game.round),
                ),
                description=tx(
                    "russian_roulette.current_player",
                    v0=(self.game.current_player.mention),
                ),
                color=discord.Color.from_rgb(155, 89, 182),
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=tx(
                    "deep_sea_oxygen.ct_items",
                    v0=(self.game.player1_chips),
                    v1=(items_text(self.game.player1_items)),
                ),
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=tx(
                    "deep_sea_oxygen.ct_items",
                    v0=(self.game.player2_chips),
                    v1=(items_text(self.game.player2_items)),
                ),
                inline=True,
            )

            embed.add_field(
                name=tx("russian_roulette.cylinder_status"),
                value=tx(
                    "russian_roulette.current_chamber_6_empty_shots",
                    v0=(self.game.current_chamber),
                    v1=(self.game.empty_shots_this_round),
                ),
                inline=False,
            )

            if self.game.double_bet_active:
                embed.add_field(
                    name=tx("russian_roulette.special_status"),
                    value=tx("russian_roulette.double_stakes_active"),
                    inline=False,
                )

            await self.game.channel.send(embed=embed, view=self)

        async def _end_game(self) -> None:
            """結束遊戲"""
            self.game.game_active = False

            winner = (
                self.game.player1
                if self.game.player1_chips > self.game.player2_chips
                else self.game.player2
            )
            winner_chips = max(self.game.player1_chips, self.game.player2_chips)

            embed = discord.Embed(
                title=tx("deep_sea_oxygen.game_ended_final_results"),
                color=discord.Color.from_rgb(241, 196, 15),
            )

            embed.add_field(
                name=tx("russian_roulette.winner"),
                value=f"{winner.mention} ({winner_chips} CT)",
                inline=False,
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=tx("russian_roulette.final_ct", v0=(self.game.player1_chips)),
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=tx("russian_roulette.final_ct", v0=(self.game.player2_chips)),
                inline=True,
            )

            await self.game.channel.send(embed=embed)

            if self.game.channel.id in self.cog.active_games:
                del self.cog.active_games[self.game.channel.id]

    class ItemSelectView(LocalizedView):
        """道具選擇視圖"""

        def __init__(
            self, game: "RouletteGame", cog: "RussianRoulette", items: List[str]
        ) -> None:
            super().__init__(timeout=180)
            self.game = game
            self.cog = cog
            self.items = items

            # 為每個道具創建按鈕
            for item in items:
                button = ui.Button[Any](
                    label=item_name(item), style=discord.ButtonStyle.secondary
                )
                button.callback = self._create_item_callback(item)  # type: ignore[method-assign]  # discord.py supports callback assignment
                self.add_item(button)

        def _create_item_callback(self, item: str) -> Any:
            """創建道具回調函數"""

            @localized("interaction")
            async def callback(interaction: discord.Interaction) -> None:
                if interaction.user != self.game.current_player:
                    await interaction.response.send_message(
                        tx("russian_roulette.it_is_another_player_s_turn"),
                        ephemeral=True,
                    )
                    return

                await self._use_item(interaction, item)

            return callback

        async def _use_item(self, interaction: discord.Interaction, item: str) -> None:
            """使用道具"""
            player, chips, items = self.game.get_current_player_data()

            if item not in items:
                await interaction.response.send_message(
                    tx("russian_roulette.this_item_is_not_in_the"), ephemeral=True
                )
                return

            # 移除使用的道具
            items.remove(item)

            if item == "透視眼鏡":
                # 偷看下一發
                next_chamber = self.game.current_chamber
                is_bullet = next_chamber == self.game.bullet_position

                result = (
                    tx("russian_roulette.bullet")
                    if is_bullet
                    else tx("russian_roulette.empty_chamber")
                )
                embed = discord.Embed(
                    title=tx("russian_roulette.x_ray_glasses_peek_result"),
                    description=tx("russian_roulette.next_chamber", v0=(result)),
                    color=discord.Color.from_rgb(52, 152, 219),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif item == "命運洗牌":
                # 重新洗牌
                self.game.bullet_position = random.randint(1, 6)
                embed = discord.Embed(
                    title=tx("russian_roulette.fate_shuffle_cylinder_spun"),
                    description=tx("russian_roulette.the_cylinder_was_spun_again_and"),
                    color=discord.Color.from_rgb(52, 152, 219),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "空包彈":
                if player.id in self.game.blank_round_players:
                    items.append(item)
                    await interaction.response.send_message(
                        tx("russian_roulette.blank_round_active"), ephemeral=True
                    )
                    return
                self.game.blank_round_players.add(player.id)
                embed = discord.Embed(
                    title=tx("russian_roulette.blank_round_ready"),
                    description=tx("russian_roulette.damage_is_halved_if_the_next"),
                    color=discord.Color.from_rgb(52, 152, 219),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "強制轉向":
                # 強制對手開槍
                if self.game.used_force_redirect[interaction.user.id]:
                    await interaction.response.send_message(
                        tx("russian_roulette.this_item_can_only_be_used"),
                        ephemeral=True,
                    )
                    items.append(item)  # 歸還道具
                    return

                self.game.used_force_redirect[interaction.user.id] = True
                opponent, _, _ = self.game.get_opponent_data()
                self.game.current_player = opponent

                embed = discord.Embed(
                    title=tx("russian_roulette.redirect_shot_transferred"),
                    description=tx(
                        "russian_roulette.must_take_this_shot_instead",
                        v0=(opponent.mention),
                    ),
                    color=discord.Color.from_rgb(52, 152, 219),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "加倍賭注":
                # 加倍賭注
                self.game.double_bet_active = True
                embed = discord.Embed(
                    title=tx("russian_roulette.double_stakes_active_36fac1"),
                    description=tx("russian_roulette.a_hit_this_round_costs_double"),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await interaction.response.send_message(embed=embed)

            # 關閉道具選擇視圖
            self.stop()

    @app_commands.command(
        name="russian-roulette", description="Start a game of Russian roulette"
    )
    @app_commands.describe(opponent="Your opponent")
    @localized("interaction")
    async def start_roulette(
        self, interaction: discord.Interaction, opponent: discord.Member
    ) -> None:
        """開始俄羅斯輪盤遊戲"""
        if not isinstance(interaction.channel, discord.TextChannel) or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                tx("deep_sea_oxygen.start_the_game_in_a_server"), ephemeral=True
            )
            return
        # 檢查是否已在遊戲中
        if interaction.channel.id in self.active_games:
            await interaction.response.send_message(
                tx("deep_sea_oxygen.a_game_is_already_running_in"), ephemeral=True
            )
            return

        # 檢查對手
        if opponent == interaction.user:
            await interaction.response.send_message(
                tx("deep_sea_oxygen.the_opponent_must_be_another_member"),
                ephemeral=True,
            )
            return

        if opponent.bot:
            await interaction.response.send_message(
                tx("deep_sea_oxygen.bots_cannot_be_opponents"), ephemeral=True
            )
            return

        # 創建遊戲
        game = RouletteGame(interaction.channel, interaction.user, opponent)
        self.active_games[interaction.channel.id] = game

        # 發送邀請
        view = GameInviteView(game, self, opponent)
        embed = discord.Embed(
            title=tx("russian_roulette.game_invite_red_and_black_roulette"),
            description=tx(
                "russian_roulette.invites_to_russian_roulette_rules_starting",
                v0=(interaction.user.mention),
                v1=(opponent.mention),
            ),
            color=discord.Color.from_rgb(155, 89, 182),
        )

        await interaction.response.send_message(embed=embed, view=view)


class GameInviteView(LocalizedView):
    """遊戲邀請視圖"""

    i18n = {
        "accept.label": "blacklist.accept",
        "decline.label": "bot_appearance.reject",
    }

    def __init__(
        self,
        game: RouletteGame,
        cog: RussianRoulette,
        opponent: discord.Member,
    ) -> None:
        super().__init__(timeout=180)  # 3分鐘超時
        self.game = game
        self.cog = cog
        self.opponent = opponent

    @localized()
    async def on_timeout(self) -> None:
        """超時處理"""
        if self.game.channel.id in self.cog.active_games:
            del self.cog.active_games[self.game.channel.id]

        embed = discord.Embed(
            title=tx("deep_sea_oxygen.invite_expired_game_cancelled"),
            description=tx("deep_sea_oxygen.the_game_invitation_expired"),
            color=discord.Color.from_rgb(231, 76, 60),
        )
        await self.game.channel.send(embed=embed)

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    @localized("interaction")
    async def accept(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """接受邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message(
                tx("deep_sea_oxygen.only_the_invited_player_can_accept"), ephemeral=True
            )
            return

        # 開始遊戲
        view = RussianRoulette.GameView(self.game, self.cog)

        embed = discord.Embed(
            title=tx("russian_roulette.game_started_red_and_black_roulette"),
            description=tx(
                "russian_roulette.game_started_takes_the_first_turn",
                v0=(self.game.current_player.mention),
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )

        embed.add_field(
            name=f"{self.game.player1.display_name}",
            value=tx(
                "deep_sea_oxygen.ct_items",
                v0=(self.game.player1_chips),
                v1=(items_text(self.game.player1_items)),
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{self.game.player2.display_name}",
            value=tx(
                "deep_sea_oxygen.ct_items",
                v0=(self.game.player2_chips),
                v1=(items_text(self.game.player2_items)),
            ),
            inline=True,
        )

        await interaction.response.send_message(embed=embed, view=view)
        self.stop()

    @ui.button(label="Reject", style=discord.ButtonStyle.danger)
    @localized("interaction")
    async def decline(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """拒絕邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message(
                tx("deep_sea_oxygen.only_the_invited_player_can_decline"),
                ephemeral=True,
            )
            return

        if self.game.channel.id in self.cog.active_games:
            del self.cog.active_games[self.game.channel.id]

        embed = discord.Embed(
            title=tx("deep_sea_oxygen.invite_declined_game_cancelled"),
            description=tx(
                "deep_sea_oxygen.declined_the_invitation", v0=(self.opponent.mention)
            ),
            color=discord.Color.from_rgb(231, 76, 60),
        )

        await interaction.response.send_message(embed=embed)
        self.stop()


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(RussianRoulette(bot))
