"""遊戲狀態業務邏輯服務 (深海氧氣瓶 / 俄羅斯輪盤)"""

import random
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import discord


# ═══════════════════════════════════════════
#  深海氧氣瓶
# ═══════════════════════════════════════════


class OxygenGame:
    """深海氧氣瓶遊戲狀態"""

    def __init__(
        self,
        channel: discord.TextChannel,
        player1: discord.Member,
        player2: discord.Member,
    ) -> None:
        self.channel = channel
        self.player1 = player1
        self.player2 = player2
        self.round = 1
        self.max_rounds = 5

        # 氧氣系統
        self.total_oxygen = 10000
        self.round_oxygen_usage: Dict[int, int] = {}
        self.round_choices: Dict[int, int] = {}

        # CT 獎勵
        self.player1_coins = 0
        self.player2_coins = 0

        # 道具
        self.player1_items: List[str] = ["側錄器", "漏氣針"]
        self.player2_items: List[str] = ["側錄器", "漏氣針"]

        # 遊戲狀態
        self.game_active = True
        self.eliminated_player: Optional[discord.Member] = None
        self.current_phase = "waiting"

    def calculate_coins(self, oxygen_amount: int) -> int:
        """依吸氧量計算 CT 獎勵"""
        if oxygen_amount <= 500:
            return 2000
        if oxygen_amount <= 800:
            return 1500
        if oxygen_amount <= 1200:
            return 1000
        if oxygen_amount <= 1500:
            return 500
        if oxygen_amount <= 1800:
            return 200
        return 0

    def get_last_round_oxygen(self, player: discord.Member) -> int:
        """取得玩家上一輪吸氧量"""
        if self.round <= 1:
            return 0
        return self.round_oxygen_usage.get(player.id, 0)

    def get_player_items(self, player: discord.Member) -> List[str]:
        """取得玩家道具列表"""
        return self.player1_items if player == self.player1 else self.player2_items


# ═══════════════════════════════════════════
#  俄羅斯輪盤
# ═══════════════════════════════════════════


class RouletteGame:
    """俄羅斯輪盤遊戲狀態"""

    ITEM_DESCRIPTIONS: Dict[str, str] = {
        "透視眼鏡": "偷看彈巢中的下一發是否為子彈",
        "命運洗牌": "強制重新旋轉彈巢，改變子彈位置",
        "空包彈": "若下一發是子彈，傷害減半",
        "強制轉向": "強制對手替你開這一槍",
        "加倍賭注": "這局擊中金額翻倍",
    }

    def __init__(
        self,
        channel: discord.TextChannel,
        player1: discord.Member,
        player2: discord.Member,
    ) -> None:
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

        self.player1_chips = 5000
        self.player2_chips = 5000

        self.player1_items: List[str] = self._random_items()
        self.player2_items: List[str] = self._random_items()

        self.used_force_redirect: Dict[int, bool] = {
            player1.id: False,
            player2.id: False,
        }
        self.double_bet_active = False

    @staticmethod
    def _random_items() -> List[str]:
        """產生隨機道具組"""
        pool = ["透視眼鏡", "命運洗牌", "空包彈", "強制轉向", "加倍賭注"]
        return random.sample(pool, 3)

    def get_current_player_data(
        self,
    ) -> Tuple[discord.Member, int, List[str]]:
        """取得當前玩家資料"""
        if self.current_player == self.player1:
            return self.player1, self.player1_chips, self.player1_items
        return self.player2, self.player2_chips, self.player2_items

    def get_opponent_data(
        self,
    ) -> Tuple[discord.Member, int, List[str]]:
        """取得對手資料"""
        if self.current_player == self.player1:
            return self.player2, self.player2_chips, self.player2_items
        return self.player1, self.player1_chips, self.player1_items

    def switch_player(self) -> None:
        """切換當前玩家"""
        self.current_player = (
            self.player2 if self.current_player == self.player1 else self.player1
        )

    def calculate_damage(self) -> int:
        """計算本次傷害"""
        base = 2000 if self.empty_shots_this_round >= 3 else 1500
        return base * 2 if self.double_bet_active else base

    def next_round(self) -> None:
        """進入下一回合"""
        self.round += 1
        self.bullet_position = random.randint(1, 6)
        self.current_chamber = 1
        self.empty_shots_this_round = 0
        self.double_bet_active = False
        self.current_player = self.player1 if self.round % 2 == 1 else self.player2

    @staticmethod
    def get_item_description(item: str) -> str:
        """取得道具說明"""
        return RouletteGame.ITEM_DESCRIPTIONS.get(item, "未知道具")
