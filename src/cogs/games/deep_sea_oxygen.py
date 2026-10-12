import random
from typing import Any, Dict

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.services.game_service import OxygenGame
from src.utils.domain_text import item_name
from src.utils.domain_text import items_text
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView


class DeepSeaOxygen(commands.Cog):
    """深海氧氣瓶 - 耐力與貪婪的遊戲"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_games: Dict[int, "OxygenGame"] = {}  # channel_id -> game

    class GameView(LocalizedView):
        """遊戲主視圖"""

        i18n = {
            "choose_oxygen.label": "deep_sea_oxygen.choose_oxygen_intake",
            "use_item.label": "deep_sea_oxygen.use_item",
            "check_status.label": "deep_sea_oxygen.view_status",
        }

        def __init__(self, game: "OxygenGame", cog: "DeepSeaOxygen") -> None:
            super().__init__(timeout=300)  # 5分鐘超時
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

        @ui.button(label="Choose oxygen intake", style=discord.ButtonStyle.primary)
        @localized("interaction")
        async def choose_oxygen(
            self, interaction: discord.Interaction, button: ui.Button[Any]
        ) -> None:
            """選擇吸氧量"""
            if not self.game.game_active:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.the_game_has_ended"), ephemeral=True
                )
                return

            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.this_account_is_not_a_player"), ephemeral=True
                )
                return

            if interaction.user.id in self.game.round_choices:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.an_oxygen_choice_has_already_been"),
                    ephemeral=True,
                )
                return

            # 創建吸氧量選擇視圖
            view = self.cog.OxygenSelectView(self.game, self.cog, interaction.user)
            embed = discord.Embed(
                title=tx("deep_sea_oxygen.oxygen_intake_a_deep_sea_choice"),
                description=tx(
                    "deep_sea_oxygen.choose_oxygen_intake_for_this_round",
                    v0=(interaction.user.mention),
                ),
                color=discord.Color.from_rgb(52, 152, 219),
            )

            embed.add_field(
                name=tx("deep_sea_oxygen.rewards"),
                value=tx("deep_sea_oxygen.500_units_2000_ct_800_units"),
                inline=False,
            )

            embed.add_field(
                name=tx("deep_sea_oxygen.current_status"),
                value=tx(
                    "deep_sea_oxygen.remaining_oxygen_units_round",
                    v0=(self.game.total_oxygen),
                    v1=(self.game.round),
                    v2=(self.game.max_rounds),
                ),
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        @ui.button(label="Use item", style=discord.ButtonStyle.secondary)
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

            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.this_account_is_not_a_player"), ephemeral=True
                )
                return

            # 獲取玩家道具
            if interaction.user == self.game.player1:
                items = self.game.player1_items
            else:
                items = self.game.player2_items

            if not items:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.no_items_are_available"), ephemeral=True
                )
                return

            # 創建道具選擇視圖
            view = self.cog.ItemSelectView(self.game, self.cog, interaction.user)
            embed = discord.Embed(
                title=tx("deep_sea_oxygen.item_selection_diving_tools"),
                description=tx(
                    "deep_sea_oxygen.choose_an_item_to_use",
                    v0=(interaction.user.mention),
                ),
                color=discord.Color.from_rgb(155, 89, 182),
            )

            for item in items:
                if item == "側錄器":
                    embed.add_field(
                        name="側錄器",
                        value=tx("deep_sea_oxygen.reveal_the_opponent_s_oxygen_intake"),
                        inline=False,
                    )
                elif item == "漏氣針":
                    embed.add_field(
                        name="漏氣針",
                        value=tx("deep_sea_oxygen.drain_an_extra_1000_oxygen_units"),
                        inline=False,
                    )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        @ui.button(label="View status", style=discord.ButtonStyle.success)
        @localized("interaction")
        async def check_status(
            self, interaction: discord.Interaction, button: ui.Button[Any]
        ) -> None:
            """查看遊戲狀態"""
            if not self.game.game_active:
                await interaction.response.send_message(
                    tx("deep_sea_oxygen.the_game_has_ended"), ephemeral=True
                )
                return

            embed = discord.Embed(
                title=tx("deep_sea_oxygen.game_status_deep_sea_oxygen"),
                description=tx(
                    "deep_sea_oxygen.round",
                    v0=(self.game.round),
                    v1=(self.game.max_rounds),
                ),
                color=discord.Color.from_rgb(26, 188, 156),
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=tx(
                    "deep_sea_oxygen.ct_items",
                    v0=(self.game.player1_coins),
                    v1=(items_text(self.game.player1_items)),
                ),
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=tx(
                    "deep_sea_oxygen.ct_items",
                    v0=(self.game.player2_coins),
                    v1=(items_text(self.game.player2_items)),
                ),
                inline=True,
            )

            embed.add_field(
                name=tx("deep_sea_oxygen.oxygen_status"),
                value=tx(
                    "deep_sea_oxygen.remaining_oxygen_units_choices_submitted_2",
                    v0=(self.game.total_oxygen),
                    v1=(len(self.game.round_choices)),
                ),
                inline=False,
            )

            if self.game.eliminated_player:
                embed.add_field(
                    name=tx("deep_sea_oxygen.eliminated_player"),
                    value=tx(
                        "deep_sea_oxygen.was_eliminated_due_to_oxygen_deprivation",
                        v0=(self.game.eliminated_player.mention),
                    ),
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    class OxygenSelectView(LocalizedView):
        """吸氧量選擇視圖"""

        def __init__(
            self, game: "OxygenGame", cog: "DeepSeaOxygen", player: discord.Member
        ) -> None:
            super().__init__(timeout=120)  # 2分鐘超時
            self.game = game
            self.cog = cog
            self.player = player

            # 創建吸氧量選項按鈕
            oxygen_options = [
                (500, 2000),
                (800, 1500),
                (1200, 1000),
                (1500, 500),
                (1800, 200),
                (2000, 0),
            ]

            for oxygen, coins in oxygen_options:
                button = ui.Button[Any](
                    label=tx("deep_sea_oxygen.units_ct", v0=(oxygen), v1=(coins)),
                    style=discord.ButtonStyle.primary,
                )
                button.callback = self._create_callback(oxygen, coins)  # type: ignore[method-assign]  # discord.py supports callback assignment
                self.add_item(button)

        def _create_callback(self, oxygen: int, coins: int) -> Any:
            """創建按鈕回調"""

            @localized("interaction")
            async def callback(interaction: discord.Interaction) -> None:
                if interaction.user != self.player:
                    await interaction.response.send_message(
                        tx("deep_sea_oxygen.this_choice_belongs_to_another_player"),
                        ephemeral=True,
                    )
                    return

                # 記錄玩家選擇
                self.game.round_choices[self.player.id] = oxygen

                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.choice_confirmed_oxygen_intake"),
                    description=tx(
                        "deep_sea_oxygen.selected_oxygen_intake_units_reward_ct",
                        v0=(oxygen),
                        v1=(coins),
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                )

                await interaction.response.edit_message(embed=embed, view=None)

                # 檢查是否兩人都已選擇
                if len(self.game.round_choices) == 2:
                    await self._reveal_round_results()

                self.stop()

            return callback

        async def _reveal_round_results(self) -> None:
            """揭示本輪結果"""
            # 獲取兩位玩家的選擇
            p1_oxygen = self.game.round_choices.get(self.game.player1.id, 0)
            p2_oxygen = self.game.round_choices.get(self.game.player2.id, 0)

            # 計算 CT 獎勵
            p1_coins = self.game.calculate_coins(p1_oxygen)
            p2_coins = self.game.calculate_coins(p2_oxygen)

            # 更新 CT
            self.game.player1_coins += p1_coins
            self.game.player2_coins += p2_coins

            # 記錄本輪吸氧量
            self.game.round_oxygen_usage[self.game.player1.id] = p1_oxygen
            self.game.round_oxygen_usage[self.game.player2.id] = p2_oxygen

            # 扣除氧氣
            total_used = p1_oxygen + p2_oxygen
            self.game.total_oxygen -= total_used

            # 創建結果 embed
            embed = discord.Embed(
                title=tx(
                    "deep_sea_oxygen.round_results_oxygen_choices", v0=(self.game.round)
                ),
                description=tx(
                    "deep_sea_oxygen.total_oxygen_consumed_this_round_units",
                    v0=(total_used),
                ),
                color=discord.Color.from_rgb(230, 126, 34),
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=tx(
                    "deep_sea_oxygen.oxygen_units_earned_ct",
                    v0=(p1_oxygen),
                    v1=(p1_coins),
                ),
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=tx(
                    "deep_sea_oxygen.oxygen_units_earned_ct",
                    v0=(p2_oxygen),
                    v1=(p2_coins),
                ),
                inline=True,
            )

            embed.add_field(
                name=tx("deep_sea_oxygen.remaining_oxygen"),
                value=tx("deep_sea_oxygen.units", v0=(self.game.total_oxygen)),
                inline=False,
            )

            await self.game.channel.send(embed=embed)

            # 檢查死亡條件
            await self._check_death_condition()

            # 準備下一輪
            if self.game.game_active:
                self.game.round += 1
                self.game.round_choices.clear()

                if self.game.round > self.game.max_rounds:
                    await self._end_game()

        async def _check_death_condition(self) -> None:
            """檢查死亡條件"""
            if self.game.total_oxygen <= 0 and not self.game.eliminated_player:
                # 氧氣見底，吸最少的人出局
                p1_oxygen = self.game.round_oxygen_usage.get(self.game.player1.id, 0)
                p2_oxygen = self.game.round_oxygen_usage.get(self.game.player2.id, 0)

                if p1_oxygen < p2_oxygen:
                    self.game.eliminated_player = self.game.player1
                elif p2_oxygen < p1_oxygen:
                    self.game.eliminated_player = self.game.player2
                else:
                    # 平局，隨機淘汰一人
                    self.game.eliminated_player = random.choice(
                        [self.game.player1, self.game.player2]
                    )

                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.eliminated_oxygen_deprivation"),
                    description=tx(
                        "deep_sea_oxygen.the_tank_is_empty_had_the",
                        v0=(self.game.eliminated_player.mention),
                    ),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await self.game.channel.send(embed=embed)

        async def _end_game(self) -> None:
            """結束遊戲"""
            self.game.game_active = False

            # 判定勝負
            if self.game.eliminated_player:
                # 有人被淘汰，另一人直接獲勝
                winner = (
                    self.game.player1
                    if self.game.eliminated_player == self.game.player2
                    else self.game.player2
                )
                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.game_ended_deep_sea_survivor"),
                    description=tx(
                        "deep_sea_oxygen.wins_the_opponent_was_eliminated_due",
                        v0=(winner.mention),
                    ),
                    color=discord.Color.from_rgb(241, 196, 15),
                )
            else:
                # 無人被淘汰，比較 CT
                if self.game.player1_coins > self.game.player2_coins:
                    winner = self.game.player1
                elif self.game.player2_coins > self.game.player1_coins:
                    winner = self.game.player2
                else:
                    winner = None

                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.game_ended_final_results"),
                    description=tx(
                        "deep_sea_oxygen.game_over",
                        v0=(
                            tx("deep_sea_oxygen.draw")
                            if winner is None
                            else tx("deep_sea_oxygen.wins", v0=(winner.mention))
                        ),
                    ),
                    color=discord.Color.from_rgb(241, 196, 15),
                )

            # 顯示最終結果
            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=tx("deep_sea_oxygen.final_ct", v0=(self.game.player1_coins)),
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=tx("deep_sea_oxygen.final_ct", v0=(self.game.player2_coins)),
                inline=True,
            )

            await self.game.channel.send(embed=embed)

            if self.game.channel.id in self.cog.active_games:
                del self.cog.active_games[self.game.channel.id]

    class ItemSelectView(LocalizedView):
        """道具選擇視圖"""

        def __init__(
            self, game: "OxygenGame", cog: "DeepSeaOxygen", player: discord.Member
        ) -> None:
            super().__init__(timeout=120)  # 2分鐘超時
            self.game = game
            self.cog = cog
            self.player = player

            # 獲取玩家道具
            if player == game.player1:
                items = game.player1_items
            else:
                items = game.player2_items

            for item in items:
                button = ui.Button[Any](
                    label=item_name(item), style=discord.ButtonStyle.secondary
                )
                button.callback = self._create_item_callback(item)  # type: ignore[method-assign]  # discord.py supports callback assignment
                self.add_item(button)

        def _create_item_callback(self, item: str) -> Any:
            """創建道具回調"""

            @localized("interaction")
            async def callback(interaction: discord.Interaction) -> None:
                if interaction.user != self.player:
                    await interaction.response.send_message(
                        tx("deep_sea_oxygen.this_item_belongs_to_another_player"),
                        ephemeral=True,
                    )
                    return

                await self._use_item(interaction, item)

            return callback

        async def _use_item(self, interaction: discord.Interaction, item: str) -> None:
            """使用道具"""
            if item == "側錄器":
                # 顯示對方上一輪吸氧量
                opponent = (
                    self.game.player2
                    if self.player == self.game.player1
                    else self.game.player1
                )
                last_oxygen = self.game.get_last_round_oxygen(opponent)

                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.recorder_oxygen_log"),
                    description=tx(
                        "deep_sea_oxygen.consumed_oxygen_units_in_the_last",
                        v0=(opponent.mention),
                        v1=(last_oxygen),
                    ),
                    color=discord.Color.from_rgb(52, 152, 219),
                )
                await interaction.response.edit_message(embed=embed, view=None)

                # 移除道具
                if self.player == self.game.player1:
                    self.game.player1_items.remove(item)
                else:
                    self.game.player2_items.remove(item)

            elif item == "漏氣針":
                # 額外損耗 1000 單位氧氣
                self.game.total_oxygen -= 1000

                embed = discord.Embed(
                    title=tx("deep_sea_oxygen.leak_needle_oxygen_leak"),
                    description=tx(
                        "deep_sea_oxygen.the_shared_tank_loses_another_1000"
                    ),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await interaction.response.edit_message(embed=embed, view=None)

                # 移除道具
                if self.player == self.game.player1:
                    self.game.player1_items.remove(item)
                else:
                    self.game.player2_items.remove(item)

                # 檢查是否立即觸發死亡
                if self.game.total_oxygen <= 0:
                    await self._check_immediate_death()

            self.stop()

        async def _check_immediate_death(self) -> None:
            """檢查立即死亡"""
            if self.game.total_oxygen <= 0 and not self.game.eliminated_player:
                # 如果當前輪已經有選擇，比較當前輪的吸氧量
                current_p1 = self.game.round_choices.get(self.game.player1.id, 0)
                current_p2 = self.game.round_choices.get(self.game.player2.id, 0)

                if current_p1 > 0 and current_p2 > 0:
                    # 兩人都已選擇，比較吸氧量
                    if current_p1 < current_p2:
                        self.game.eliminated_player = self.game.player1
                    elif current_p2 < current_p1:
                        self.game.eliminated_player = self.game.player2
                    else:
                        self.game.eliminated_player = random.choice(
                            [self.game.player1, self.game.player2]
                        )

                    embed = discord.Embed(
                        title=tx("deep_sea_oxygen.eliminated_oxygen_depleted"),
                        description=tx(
                            "deep_sea_oxygen.the_tank_is_empty_had_the_531c14",
                            v0=(self.game.eliminated_player.mention),
                        ),
                        color=discord.Color.from_rgb(231, 76, 60),
                    )
                    await self.game.channel.send(embed=embed)

                    # 立即結束遊戲
                    self.game.game_active = False

                    if self.game.channel.id in self.cog.active_games:
                        del self.cog.active_games[self.game.channel.id]

    @app_commands.command(
        name="deep-sea-oxygen", description="Start a deep-sea oxygen game"
    )
    @app_commands.describe(opponent="Your opponent")
    @localized("interaction")
    async def start_oxygen_game(
        self, interaction: discord.Interaction, opponent: discord.Member
    ) -> None:
        """開始深海氧氣瓶遊戲"""
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
        game = OxygenGame(interaction.channel, interaction.user, opponent)
        self.active_games[interaction.channel.id] = game

        # 發送邀請
        view = GameInviteView(game, self, opponent)
        embed = discord.Embed(
            title=tx("deep_sea_oxygen.game_invite_deep_sea_oxygen"),
            description=tx(
                "deep_sea_oxygen.invites_to_deep_sea_oxygen_rules",
                v0=(interaction.user.mention),
                v1=(opponent.mention),
            ),
            color=discord.Color.from_rgb(26, 188, 156),
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
        game: OxygenGame,
        cog: DeepSeaOxygen,
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
        view = DeepSeaOxygen.GameView(self.game, self.cog)

        embed = discord.Embed(
            title=tx("deep_sea_oxygen.game_started_deep_sea_oxygen"),
            description=tx("deep_sea_oxygen.two_divers_must_make_their_choices"),
            color=discord.Color.from_rgb(46, 204, 113),
        )

        embed.add_field(
            name=f"{self.game.player1.display_name}",
            value=tx(
                "deep_sea_oxygen.ct_0_items", v0=(items_text(self.game.player1_items))
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{self.game.player2.display_name}",
            value=tx(
                "deep_sea_oxygen.ct_0_items", v0=(items_text(self.game.player2_items))
            ),
            inline=True,
        )

        embed.add_field(
            name=tx("deep_sea_oxygen.initial_status"),
            value=tx(
                "deep_sea_oxygen.shared_oxygen_units_rounds",
                v0=(self.game.total_oxygen),
                v1=(self.game.max_rounds),
            ),
            inline=False,
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
    await bot.add_cog(DeepSeaOxygen(bot))
