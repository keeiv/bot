import asyncio
from datetime import datetime
from datetime import timedelta
import random
from typing import Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands


class RussianRoulette(commands.Cog):
    """極限籌碼：紅黑左輪 - 俄羅斯輪盤遊戲"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, "RouletteGame"] = {}  # channel_id -> game
        self.player_data: Dict[int, Dict] = {}  # user_id -> player stats

    class RouletteGame:
        """遊戲實例"""

        def __init__(
            self,
            channel: discord.TextChannel,
            player1: discord.Member,
            player2: discord.Member,
        ):
            self.channel = channel
            self.player1 = player1
            self.player2 = player2
            self.current_player = player1
            self.round = 1
            self.max_rounds = 5
            self.bullet_position = random.randint(1, 6)
            self.current_chamber = 1
            self.empty_shots_this_round = 0
            self.game_active = True

            # 玩家資產
            self.player1_chips = 5000
            self.player2_chips = 5000

            # 道具系統
            self.player1_items = self._generate_random_items()
            self.player2_items = self._generate_random_items()

            # 遊戲狀態
            self.used_force_redirect = {player1.id: False, player2.id: False}
            self.double_bet_active = False

        def _generate_random_items(self) -> List[str]:
            """生成隨機道具"""
            all_items = ["透視眼鏡", "命運洗牌", "空包彈", "強制轉向", "加倍賭注"]
            return random.sample(all_items, 3)

        def get_current_player_data(self) -> Tuple[discord.Member, int, List[str]]:
            """獲取當前玩家數據"""
            if self.current_player == self.player1:
                return self.player1, self.player1_chips, self.player1_items
            else:
                return self.player2, self.player2_chips, self.player2_items

        def get_opponent_data(self) -> Tuple[discord.Member, int, List[str]]:
            """獲取對手數據"""
            if self.current_player == self.player1:
                return self.player2, self.player2_chips, self.player2_items
            else:
                return self.player1, self.player1_chips, self.player1_items

        def switch_player(self):
            """切換當前玩家"""
            self.current_player = (
                self.player2 if self.current_player == self.player1 else self.player1
            )

        def calculate_damage(self) -> int:
            """計算傷害"""
            base_damage = 1500
            if self.empty_shots_this_round >= 3:
                base_damage = 2000

            if self.double_bet_active:
                base_damage *= 2

            return base_damage

        def next_round(self):
            """進入下一回合"""
            self.round += 1
            self.bullet_position = random.randint(1, 6)
            self.current_chamber = 1
            self.empty_shots_this_round = 0
            self.double_bet_active = False
            self.current_player = self.player1 if self.round % 2 == 1 else self.player2

    class GameView(ui.View):
        """遊戲主視圖"""

        def __init__(self, game: "RouletteGame", cog: "RussianRoulette"):
            super().__init__(timeout=180)  # 3分鐘超時
            self.game = game
            self.cog = cog

        async def on_timeout(self):
            """超時處理"""
            if self.game.game_active:
                self.game.game_active = False
                embed = discord.Embed(
                    title="[遊戲結束] 超時",
                    description="遊戲因超時而結束",
                    color=discord.Color.red(),
                )
                await self.game.channel.send(embed=embed)
                if self.game.channel.id in self.cog.active_games:
                    del self.cog.active_games[self.game.channel.id]

        @ui.button(label="扣動扳機", style=discord.ButtonStyle.danger)
        async def pull_trigger(
            self, interaction: discord.Interaction, button: ui.Button
        ):
            """扣動扳機"""
            if not self.game.game_active:
                await interaction.response.send_message("遊戲已結束", ephemeral=True)
                return

            if interaction.user != self.game.current_player:
                await interaction.response.send_message("不是你的回合", ephemeral=True)
                return

            # 執行開槍
            is_hit = self.game.current_chamber == self.game.bullet_position

            if is_hit:
                # 中彈
                damage = self.game.calculate_damage()
                player, chips, items = self.game.get_current_player_data()

                # 檢查是否有空包彈
                if "空包彈" in items:
                    damage = damage // 2
                    items.remove("空包彈")

                # 扣除籌碼
                if self.game.current_player == self.game.player1:
                    self.game.player1_chips -= damage
                else:
                    self.game.player2_chips -= damage

                embed = discord.Embed(
                    title="[中彈] 遊戲結束",
                    description=f"{interaction.user.mention} 扣動扳機...砰！\n扣除 {damage} CT",
                    color=discord.Color.red(),
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
                    title="[空槍] 安全通過",
                    description=f"{interaction.user.mention} 扣動扳機...咔嚓！\n安全通過",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed)

                # 切換玩家
                self.game.switch_player()
                await self._show_game_status()

        @ui.button(label="使用道具", style=discord.ButtonStyle.primary)
        async def use_item(self, interaction: discord.Interaction, button: ui.Button):
            """使用道具"""
            if not self.game.game_active:
                await interaction.response.send_message("遊戲已結束", ephemeral=True)
                return

            if interaction.user != self.game.current_player:
                await interaction.response.send_message("不是你的回合", ephemeral=True)
                return

            player, chips, items = self.game.get_current_player_data()

            if not items:
                await interaction.response.send_message(
                    "你沒有道具可用", ephemeral=True
                )
                return

            # 創建道具選擇視圖
            view = self.cog.ItemSelectView(self.game, self.cog, items)
            embed = discord.Embed(
                title="[道具] 選擇要使用的道具",
                description="選擇一個道具來使用",
                color=discord.Color.blue(),
            )
            for i, item in enumerate(items, 1):
                embed.add_field(
                    name=f"{i}. {item}",
                    value=self._get_item_description(item),
                    inline=False,
                )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        def _get_item_description(self, item: str) -> str:
            """獲取道具描述"""
            descriptions = {
                "透視眼鏡": "偷看彈巢中的下一發是否為子彈",
                "命運洗牌": "強制重新旋轉彈巢，改變子彈位置",
                "空包彈": "若下一發是子彈，傷害減半",
                "強制轉向": "強制對手替你開這一槍",
                "加倍賭注": "這局擊中金額翻倍",
            }
            return descriptions.get(item, "未知道具")

        async def _show_game_status(self):
            """顯示遊戲狀態"""
            embed = discord.Embed(
                title=f"[第 {self.game.round} 局] 極限籌碼：紅黑左輪",
                description=f"當前玩家：{self.game.current_player.mention}",
                color=discord.Color.purple(),
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=f"CT: {self.game.player1_chips}\n道具: {', '.join(self.game.player1_items)}",
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=f"CT: {self.game.player2_chips}\n道具: {', '.join(self.game.player2_items)}",
                inline=True,
            )

            embed.add_field(
                name="彈巢狀態",
                value=f"當前位置: {self.game.current_chamber}/6\n空槍次數: {self.game.empty_shots_this_round}",
                inline=False,
            )

            if self.game.double_bet_active:
                embed.add_field(name="特殊狀態", value="加倍賭注已啟動", inline=False)

            await self.game.channel.send(embed=embed, view=self)

        async def _end_game(self):
            """結束遊戲"""
            self.game.game_active = False

            winner = (
                self.game.player1
                if self.game.player1_chips > self.game.player2_chips
                else self.game.player2
            )
            winner_chips = max(self.game.player1_chips, self.game.player2_chips)

            embed = discord.Embed(
                title="[遊戲結束] 最終結果", color=discord.Color.gold()
            )

            embed.add_field(
                name="勝利者",
                value=f"{winner.mention} ({winner_chips} CT)",
                inline=False,
            )

            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=f"最終 CT: {self.game.player1_chips}",
                inline=True,
            )

            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=f"最終 CT: {self.game.player2_chips}",
                inline=True,
            )

            await self.game.channel.send(embed=embed)

            if self.game.channel.id in self.cog.active_games:
                del self.cog.active_games[self.game.channel.id]

    class ItemSelectView(ui.View):
        """道具選擇視圖"""

        def __init__(
            self, game: "RouletteGame", cog: "RussianRoulette", items: List[str]
        ):
            super().__init__(timeout=180)
            self.game = game
            self.cog = cog
            self.items = items

            # 為每個道具創建按鈕
            for item in items:
                button = ui.Button(label=item, style=discord.ButtonStyle.secondary)
                button.callback = self._create_item_callback(item)
                self.add_item(button)

        def _create_item_callback(self, item: str):
            """創建道具回調函數"""

            async def callback(interaction: discord.Interaction):
                if interaction.user != self.game.current_player:
                    await interaction.response.send_message(
                        "不是你的回合", ephemeral=True
                    )
                    return

                await self._use_item(interaction, item)

            return callback

        async def _use_item(self, interaction: discord.Interaction, item: str):
            """使用道具"""
            player, chips, items = self.game.get_current_player_data()

            if item not in items:
                await interaction.response.send_message(
                    "你沒有這個道具", ephemeral=True
                )
                return

            # 移除使用的道具
            items.remove(item)

            if item == "透視眼鏡":
                # 偷看下一發
                next_chamber = self.game.current_chamber
                is_bullet = next_chamber == self.game.bullet_position

                result = "子彈" if is_bullet else "空槍"
                embed = discord.Embed(
                    title="[透視眼鏡] 偷看結果",
                    description=f"下一發是：{result}",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif item == "命運洗牌":
                # 重新洗牌
                self.game.bullet_position = random.randint(1, 6)
                embed = discord.Embed(
                    title="[命運洗牌] 重新洗牌",
                    description="彈巢已重新洗牌，子彈位置改變",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "空包彈":
                # 空包彈效果（實際使用時才生效）
                embed = discord.Embed(
                    title="[空包彈] 已準備",
                    description="若下一發是子彈，傷害將減半",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "強制轉向":
                # 強制對手開槍
                if self.game.used_force_redirect[interaction.user.id]:
                    await interaction.response.send_message(
                        "此道具每場遊戲限用一次", ephemeral=True
                    )
                    items.append(item)  # 歸還道具
                    return

                self.game.used_force_redirect[interaction.user.id] = True
                opponent, _, _ = self.game.get_opponent_data()
                self.game.current_player = opponent

                embed = discord.Embed(
                    title="[強制轉向] 轉移開槍",
                    description=f"強制 {opponent.mention} 替你開這一槍",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)

            elif item == "加倍賭注":
                # 加倍賭注
                self.game.double_bet_active = True
                embed = discord.Embed(
                    title="[加倍賭注] 已啟動",
                    description="這局擊中金額將翻倍",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)

            # 關閉道具選擇視圖
            self.stop()

    @app_commands.command(name="russian-roulette", description="開始俄羅斯輪盤遊戲")
    @app_commands.describe(opponent="選擇一個對手")
    async def start_roulette(
        self, interaction: discord.Interaction, opponent: discord.Member
    ):
        """開始俄羅斯輪盤遊戲"""

        # 檢查是否已在遊戲中
        if interaction.channel.id in self.active_games:
            await interaction.response.send_message(
                "此頻道已有遊戲進行中", ephemeral=True
            )
            return

        # 檢查對手
        if opponent == interaction.user:
            await interaction.response.send_message(
                "不能選擇自己作為對手", ephemeral=True
            )
            return

        if opponent.bot:
            await interaction.response.send_message(
                "不能選擇機器人作為對手", ephemeral=True
            )
            return

        # 創建遊戲
        game = self.RouletteGame(interaction.channel, interaction.user, opponent)
        self.active_games[interaction.channel.id] = game

        # 發送邀請
        view = GameInviteView(game, self, opponent)
        embed = discord.Embed(
            title="[遊戲邀請] 極限籌碼：紅黑左輪",
            description=f"{interaction.user.mention} 邀請 {opponent.mention} 進行俄羅斯輪盤遊戲\n\n"
            f"遊戲規則：\n"
            f"• 初始資產：5,000 CT\n"
            f"• 總局數：5 局\n"
            f"• 每局隨機放入 1 顆子彈\n"
            f"• 中彈扣除 1,500 CT（連續空槍3次後增至 2,000 CT）\n"
            f"• 每人隨機獲得 3 個道具",
            color=discord.Color.purple(),
        )

        await interaction.response.send_message(embed=embed, view=view)


class GameInviteView(ui.View):
    """遊戲邀請視圖"""

    def __init__(
        self,
        game: RussianRoulette.RouletteGame,
        cog: RussianRoulette,
        opponent: discord.Member,
    ):
        super().__init__(timeout=180)  # 3分鐘超時
        self.game = game
        self.cog = cog
        self.opponent = opponent

    async def on_timeout(self):
        """超時處理"""
        if self.game.channel.id in self.cog.active_games:
            del self.cog.active_games[self.game.channel.id]

        embed = discord.Embed(
            title="[邀請過期] 遊戲取消",
            description="遊戲邀請已過期",
            color=discord.Color.red(),
        )
        await self.game.channel.send(embed=embed)

    @ui.button(label="接受", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        """接受邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message(
                "只有被邀請者可以接受", ephemeral=True
            )
            return

        # 開始遊戲
        view = RussianRoulette.GameView(self.game, self.cog)

        embed = discord.Embed(
            title="[遊戲開始] 極限籌碼：紅黑左輪",
            description=f"遊戲開始！{self.game.current_player.mention} 先手",
            color=discord.Color.green(),
        )

        embed.add_field(
            name=f"{self.game.player1.display_name}",
            value=f"CT: {self.game.player1_chips}\n道具: {', '.join(self.game.player1_items)}",
            inline=True,
        )

        embed.add_field(
            name=f"{self.game.player2.display_name}",
            value=f"CT: {self.game.player2_chips}\n道具: {', '.join(self.game.player2_items)}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, view=view)
        self.stop()

    @ui.button(label="拒絕", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        """拒絕邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message(
                "只有被邀請者可以拒絕", ephemeral=True
            )
            return

        if self.game.channel.id in self.cog.active_games:
            del self.cog.active_games[self.game.channel.id]

        embed = discord.Embed(
            title="[邀請拒絕] 遊戲取消",
            description=f"{self.opponent.mention} 拒絕了遊戲邀請",
            color=discord.Color.red(),
        )

        await interaction.response.send_message(embed=embed)
        self.stop()


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(RussianRoulette(bot))
