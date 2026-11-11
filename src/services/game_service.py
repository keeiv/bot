"""Game state business logic (deep-sea oxygen and Russian roulette)."""

import random
from typing import Dict, List, Optional, Tuple

import discord

# ── Deep-sea oxygen ───────────────────────────────────────────────


class OxygenGame:
    """The state of a deep-sea oxygen game."""

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

        # Oxygen
        self.total_oxygen = 10000
        self.round_oxygen_usage: Dict[int, int] = {}
        self.round_choices: Dict[int, int] = {}

        # CT rewards
        self.player1_coins = 0
        self.player2_coins = 0

        # Items
        self.player1_items: List[str] = ["側錄器", "漏氣針"]
        self.player2_items: List[str] = ["側錄器", "漏氣針"]

        # Game state
        self.game_active = True
        self.eliminated_player: Optional[discord.Member] = None
        self.current_phase = "waiting"

    def calculate_coins(self, oxygen_amount: int) -> int:
        """Work out the CT reward from the oxygen taken."""
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
        """How much oxygen a player took last round."""
        if self.round <= 1:
            return 0
        return self.round_oxygen_usage.get(player.id, 0)

    def get_player_items(self, player: discord.Member) -> List[str]:
        """A player's items."""
        return self.player1_items if player == self.player1 else self.player2_items


# ── Russian roulette ──────────────────────────────────────────────


class RouletteGame:
    """The state of a Russian roulette game."""

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
        self.blank_round_players: set[int] = set()

    @staticmethod
    def _random_items() -> List[str]:
        """Make a random set of items."""
        pool = ["透視眼鏡", "命運洗牌", "空包彈", "強制轉向", "加倍賭注"]
        return random.sample(pool, 3)

    def get_current_player_data(
        self,
    ) -> Tuple[discord.Member, int, List[str]]:
        """The current player's data."""
        if self.current_player == self.player1:
            return self.player1, self.player1_chips, self.player1_items
        return self.player2, self.player2_chips, self.player2_items

    def get_opponent_data(
        self,
    ) -> Tuple[discord.Member, int, List[str]]:
        """The opponent's data."""
        if self.current_player == self.player1:
            return self.player2, self.player2_chips, self.player2_items
        return self.player1, self.player1_chips, self.player1_items

    def switch_player(self) -> None:
        """Switch the current player."""
        self.current_player = (
            self.player2 if self.current_player == self.player1 else self.player1
        )

    def calculate_damage(self) -> int:
        """Work out the damage this time."""
        base = 2000 if self.empty_shots_this_round >= 3 else 1500
        return base * 2 if self.double_bet_active else base

    def next_round(self) -> None:
        """Move to the next turn."""
        self.round += 1
        self.bullet_position = random.randint(1, 6)
        self.current_chamber = 1
        self.empty_shots_this_round = 0
        self.double_bet_active = False
        self.current_player = self.player1 if self.round % 2 == 1 else self.player2

    @staticmethod
    def get_item_description(item: str) -> str:
        """The description of an item."""
        return RouletteGame.ITEM_DESCRIPTIONS.get(item, "未知道具")
