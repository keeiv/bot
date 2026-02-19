import discord
from discord.ext import commands
from discord import ui, app_commands
import random
from typing import Dict, List, Tuple
from datetime import datetime

class DeepSeaOxygen(commands.Cog):
    """深海氧氣瓶 - 耐力與貪婪的遊戲"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, 'OxygenGame'] = {}  # channel_id -> game
    
    class OxygenGame:
        """遊戲實例"""
        
        def __init__(self, channel: discord.TextChannel, player1: discord.Member, player2: discord.Member):
            self.channel = channel
            self.player1 = player1
            self.player2 = player2
            self.round = 1
            self.max_rounds = 5
            
            # 氧氣系統
            self.total_oxygen = 10000  # 共享氧氣瓶
            self.round_oxygen_usage = {}  # 每輪玩家吸氧量
            self.round_choices = {}  # 每輪玩家選擇（隱藏）
            
            # CT 獎勵系統
            self.player1_coins = 0
            self.player2_coins = 0
            
            # 道具系統
            self.player1_items = ["側錄器", "漏氣針"]
            self.player2_items = ["側錄器", "漏氣針"]
            
            # 遊戲狀態
            self.game_active = True
            self.eliminated_player = None
            self.current_phase = "waiting"  # waiting, choosing, reveal
            
        def calculate_coins(self, oxygen_amount: int) -> int:
            """計算 CT 獎勵"""
            # 吸得越少，獎勵越高
            if oxygen_amount <= 500:
                return 2000
            elif oxygen_amount <= 800:
                return 1500
            elif oxygen_amount <= 1200:
                return 1000
            elif oxygen_amount <= 1500:
                return 500
            elif oxygen_amount <= 1800:
                return 200
            else:
                return 0
        
        def get_last_round_oxygen(self, player: discord.Member) -> int:
            """獲取玩家上一輪吸氧量"""
            if self.round <= 1:
                return 0
            
            # 返回上一輪的吸氧量
            return self.round_oxygen_usage.get(player.id, 0)
    
    class GameView(ui.View):
        """遊戲主視圖"""
        
        def __init__(self, game: 'OxygenGame', cog: 'DeepSeaOxygen'):
            super().__init__(timeout=300)  # 5分鐘超時
            self.game = game
            self.cog = cog
            
        async def on_timeout(self):
            """超時處理"""
            if self.game.game_active:
                self.game.game_active = False
                embed = discord.Embed(
                    title="[遊戲結束] 超時",
                    description="遊戲因超時而結束",
                    color=discord.Color.red()
                )
                await self.game.channel.send(embed=embed)
                if self.game.channel.id in self.cog.active_games:
                    del self.cog.active_games[self.game.channel.id]
        
        @ui.button(label="選擇吸氧量", style=discord.ButtonStyle.primary)
        async def choose_oxygen(self, interaction: discord.Interaction, button: ui.Button):
            """選擇吸氧量"""
            if not self.game.game_active:
                await interaction.response.send_message("遊戲已結束", ephemeral=True)
                return
            
            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message("你不是遊戲玩家", ephemeral=True)
                return
            
            if interaction.user.id in self.game.round_choices:
                await interaction.response.send_message("你已經選擇了這輪的吸氧量", ephemeral=True)
                return
            
            # 創建吸氧量選擇視圖
            view = self.cog.OxygenSelectView(self.game, self.cog, interaction.user)
            embed = discord.Embed(
                title="[選擇吸氧量] 深海抉擇",
                description=f"{interaction.user.mention} 請選擇這輪要吸多少氧氣\n"
                          f"範圍：500~2000 單位\n"
                          f"吸得越少，CT 獎勵越高",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="獎勵表",
                value="• 500 單位 = 2000 CT\n"
                      "• 800 單位 = 1500 CT\n"
                      "• 1200 單位 = 1000 CT\n"
                      "• 1500 單位 = 500 CT\n"
                      "• 1800 單位 = 200 CT\n"
                      "• 2000 單位 = 0 CT",
                inline=False
            )
            
            embed.add_field(
                name="當前狀態",
                value=f"剩餘氧氣：{self.game.total_oxygen} 單位\n"
                      f"第 {self.game.round}/{self.game.max_rounds} 輪",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        @ui.button(label="使用道具", style=discord.ButtonStyle.secondary)
        async def use_item(self, interaction: discord.Interaction, button: ui.Button):
            """使用道具"""
            if not self.game.game_active:
                await interaction.response.send_message("遊戲已結束", ephemeral=True)
                return
            
            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message("你不是遊戲玩家", ephemeral=True)
                return
            
            # 獲取玩家道具
            if interaction.user == self.game.player1:
                items = self.game.player1_items
            else:
                items = self.game.player2_items
            
            if not items:
                await interaction.response.send_message("你沒有道具可用", ephemeral=True)
                return
            
            # 創建道具選擇視圖
            view = self.cog.ItemSelectView(self.game, self.cog, interaction.user)
            embed = discord.Embed(
                title="[道具選擇] 深海工具",
                description=f"{interaction.user.mention} 請選擇要使用的道具",
                color=discord.Color.purple()
            )
            
            for item in items:
                if item == "側錄器":
                    embed.add_field(
                        name="側錄器",
                        value="得知對方上一輪吸了多少氧氣",
                        inline=False
                    )
                elif item == "漏氣針":
                    embed.add_field(
                        name="漏氣針", 
                        value="強制讓本輪共享氧氣額外損耗 1000 單位",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        @ui.button(label="查看狀態", style=discord.ButtonStyle.success)
        async def check_status(self, interaction: discord.Interaction, button: ui.Button):
            """查看遊戲狀態"""
            if not self.game.game_active:
                await interaction.response.send_message("遊戲已結束", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="[遊戲狀態] 深海氧氣瓶",
                description=f"第 {self.game.round}/{self.game.max_rounds} 輪",
                color=discord.Color.teal()
            )
            
            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=f"CT: {self.game.player1_coins}\n道具: {', '.join(self.game.player1_items)}",
                inline=True
            )
            
            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=f"CT: {self.game.player2_coins}\n道具: {', '.join(self.game.player2_items)}",
                inline=True
            )
            
            embed.add_field(
                name="氧氣狀態",
                value=f"剩餘氧氣：{self.game.total_oxygen} 單位\n"
                      f"已選擇：{len(self.game.round_choices)}/2 人",
                inline=False
            )
            
            if self.game.eliminated_player:
                embed.add_field(
                    name="淘汰玩家",
                    value=f"{self.game.eliminated_player.mention} 已因缺氧出局",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    class OxygenSelectView(ui.View):
        """吸氧量選擇視圖"""
        
        def __init__(self, game: 'OxygenGame', cog: 'DeepSeaOxygen', player: discord.Member):
            super().__init__(timeout=120)  # 2分鐘超時
            self.game = game
            self.cog = cog
            self.player = player
            
            # 創建吸氧量選項按鈕
            oxygen_options = [
                (500, 2000), (800, 1500), (1200, 1000),
                (1500, 500), (1800, 200), (2000, 0)
            ]
            
            for oxygen, coins in oxygen_options:
                button = ui.Button(
                    label=f"{oxygen} 單位 ({coins} CT)",
                    style=discord.ButtonStyle.primary
                )
                button.callback = self._create_callback(oxygen, coins)
                self.add_item(button)
        
        def _create_callback(self, oxygen: int, coins: int):
            """創建按鈕回調"""
            async def callback(interaction: discord.Interaction):
                if interaction.user != self.player:
                    await interaction.response.send_message("這不是你的選擇", ephemeral=True)
                    return
                
                # 記錄玩家選擇
                self.game.round_choices[self.player.id] = oxygen
                
                embed = discord.Embed(
                    title="[選擇確認] 氧氣抉擇",
                    description=f"你選擇了吸 {oxygen} 單位氧氣\n將獲得 {coins} CT",
                    color=discord.Color.green()
                )
                
                await interaction.response.edit_message(embed=embed, view=None)
                
                # 檢查是否兩人都已選擇
                if len(self.game.round_choices) == 2:
                    await self._reveal_round_results()
                
                self.stop()
            return callback
        
        async def _reveal_round_results(self):
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
                title=f"[第 {self.game.round} 輪結果] 氧氣抉擇",
                description=f"本輪總消耗：{total_used} 單位",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=f"吸氧：{p1_oxygen} 單位\n獲得：{p1_coins} CT",
                inline=True
            )
            
            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=f"吸氧：{p2_oxygen} 單位\n獲得：{p2_coins} CT",
                inline=True
            )
            
            embed.add_field(
                name="剩餘氧氣",
                value=f"{self.game.total_oxygen} 單位",
                inline=False
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
        
        async def _check_death_condition(self):
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
                    self.game.eliminated_player = random.choice([self.game.player1, self.game.player2])
                
                embed = discord.Embed(
                    title="[缺氧死亡] 深海悲劇",
                    description=f"氧氣瓶見底！{self.game.eliminated_player.mention} 因吸氧最少而缺氧出局",
                    color=discord.Color.red()
                )
                await self.game.channel.send(embed=embed)
        
        async def _end_game(self):
            """結束遊戲"""
            self.game.game_active = False
            
            # 判定勝負
            if self.game.eliminated_player:
                # 有人被淘汰，另一人直接獲勝
                winner = self.game.player1 if self.game.eliminated_player == self.game.player2 else self.game.player2
                winner_coins = self.game.player1_coins if winner == self.game.player1 else self.game.player2_coins
                
                embed = discord.Embed(
                    title="[遊戲結束] 深海倖存者",
                    description=f"{winner.mention} 獲勝！\n對手因缺氧出局",
                    color=discord.Color.gold()
                )
            else:
                # 無人被淘汰，比較 CT
                if self.game.player1_coins > self.game.player2_coins:
                    winner = self.game.player1
                    winner_coins = self.game.player1_coins
                elif self.game.player2_coins > self.game.player1_coins:
                    winner = self.game.player2
                    winner_coins = self.game.player2_coins
                else:
                    winner = None
                    winner_coins = self.game.player1_coins
                
                embed = discord.Embed(
                    title="[遊戲結束] 最終結果",
                    description=f"遊戲結束！{'平局' if winner is None else f'{winner.mention} 獲勝！'}",
                    color=discord.Color.gold()
                )
            
            # 顯示最終結果
            embed.add_field(
                name=f"{self.game.player1.display_name}",
                value=f"最終 CT：{self.game.player1_coins}",
                inline=True
            )
            
            embed.add_field(
                name=f"{self.game.player2.display_name}",
                value=f"最終 CT：{self.game.player2_coins}",
                inline=True
            )
            
            await self.game.channel.send(embed=embed)
            
            if self.game.channel.id in self.cog.active_games:
                del self.cog.active_games[self.game.channel.id]
    
    class ItemSelectView(ui.View):
        """道具選擇視圖"""
        
        def __init__(self, game: 'OxygenGame', cog: 'DeepSeaOxygen', player: discord.Member):
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
                button = ui.Button(label=item, style=discord.ButtonStyle.secondary)
                button.callback = self._create_item_callback(item)
                self.add_item(button)
        
        def _create_item_callback(self, item: str):
            """創建道具回調"""
            async def callback(interaction: discord.Interaction):
                if interaction.user != self.player:
                    await interaction.response.send_message("這不是你的道具", ephemeral=True)
                    return
                
                await self._use_item(interaction, item)
            return callback
        
        async def _use_item(self, interaction: discord.Interaction, item: str):
            """使用道具"""
            if item == "側錄器":
                # 顯示對方上一輪吸氧量
                opponent = self.game.player2 if self.player == self.game.player1 else self.game.player1
                last_oxygen = self.game.get_last_round_oxygen(opponent)
                
                embed = discord.Embed(
                    title="[側錄器] 氧氣記錄",
                    description=f"{opponent.mention} 上一輪吸了 {last_oxygen} 單位氧氣",
                    color=discord.Color.blue()
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
                    title="[漏氣針] 氧氣洩漏",
                    description="共享氧氣瓶額外損耗 1000 單位！\n氧氣正在快速減少...",
                    color=discord.Color.red()
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
        
        async def _check_immediate_death(self):
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
                        self.game.eliminated_player = random.choice([self.game.player1, self.game.player2])
                    
                    embed = discord.Embed(
                        title="[緊急死亡] 氧氣耗盡",
                        description=f"氧氣瓶完全見底！{self.game.eliminated_player.mention} 因吸氧最少而立即出局",
                        color=discord.Color.red()
                    )
                    await self.game.channel.send(embed=embed)
                    
                    # 立即結束遊戲
                    self.game.game_active = False
                    
                    if self.game.channel.id in self.cog.active_games:
                        del self.cog.active_games[self.game.channel.id]
    
    @app_commands.command(name="deep-sea-oxygen", description="開始深海氧氣瓶遊戲")
    @app_commands.describe(opponent="選擇一個對手")
    async def start_oxygen_game(self, interaction: discord.Interaction, opponent: discord.Member):
        """開始深海氧氣瓶遊戲"""
        
        # 檢查是否已在遊戲中
        if interaction.channel.id in self.active_games:
            await interaction.response.send_message("此頻道已有遊戲進行中", ephemeral=True)
            return
        
        # 檢查對手
        if opponent == interaction.user:
            await interaction.response.send_message("不能選擇自己作為對手", ephemeral=True)
            return
        
        if opponent.bot:
            await interaction.response.send_message("不能選擇機器人作為對手", ephemeral=True)
            return
        
        # 創建遊戲
        game = self.OxygenGame(interaction.channel, interaction.user, opponent)
        self.active_games[interaction.channel.id] = game
        
        # 發送邀請
        view = GameInviteView(game, self, opponent)
        embed = discord.Embed(
            title="[遊戲邀請] 深海氧氣瓶",
            description=f"{interaction.user.mention} 邀請 {opponent.mention} 進行深海氧氣瓶遊戲\n\n"
                       f"遊戲規則：\n"
                       f"• 共享氧氣瓶：10,000 單位\n"
                       f"• 遊戲輪數：5 輪\n"
                       f"• 每輪秘密選擇吸氧量（500~2000）\n"
                       f"• 吸得越少，CT 獎勵越高\n"
                       f"• 氧氣見底時，吸最少者出局",
            color=discord.Color.teal()
        )
        
        await interaction.response.send_message(embed=embed, view=view)

class GameInviteView(ui.View):
    """遊戲邀請視圖"""
    
    def __init__(self, game: DeepSeaOxygen.OxygenGame, cog: DeepSeaOxygen, opponent: discord.Member):
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
            color=discord.Color.red()
        )
        await self.game.channel.send(embed=embed)
    
    @ui.button(label="接受", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        """接受邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message("只有被邀請者可以接受", ephemeral=True)
            return
        
        # 開始遊戲
        view = DeepSeaOxygen.GameView(self.game, self.cog)
        
        embed = discord.Embed(
            title="[遊戲開始] 深海氧氣瓶",
            description="遊戲開始！兩位深海潛水員必須在氧氣耗盡前做出抉擇\n"
                      "每輪秘密選擇吸氧量，平衡生存與貪婪",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{self.game.player1.display_name}",
            value=f"CT: 0\n道具: {', '.join(self.game.player1_items)}",
            inline=True
        )
        
        embed.add_field(
            name=f"{self.game.player2.display_name}",
            value=f"CT: 0\n道具: {', '.join(self.game.player2_items)}",
            inline=True
        )
        
        embed.add_field(
            name="初始狀態",
            value=f"共享氧氣：{self.game.total_oxygen} 單位\n"
                  f"遊戲輪數：{self.game.max_rounds} 輪",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()
    
    @ui.button(label="拒絕", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        """拒絕邀請"""
        if interaction.user != self.opponent:
            await interaction.response.send_message("只有被邀請者可以拒絕", ephemeral=True)
            return
        
        if self.game.channel.id in self.cog.active_games:
            del self.cog.active_games[self.game.channel.id]
        
        embed = discord.Embed(
            title="[邀請拒絕] 遊戲取消",
            description=f"{self.opponent.mention} 拒絕了遊戲邀請",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
        self.stop()

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(DeepSeaOxygen(bot))
