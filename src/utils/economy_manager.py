from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple

DATA_PATH = Path(__file__).parents[1].joinpath("data", "storage", "economy.json")


class EconomyManager:
    """簡單的經濟管理器：持久化至 data/storage/economy.json

    提供 async 方法以便在 cog 中直接呼叫。
    """

    def __init__(self):
        self._path = DATA_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def _read(self) -> Dict[str, int]:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write(self, data: Dict[str, int]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    async def get_balance(self, user_id: int) -> int:
        data = self._read()
        return int(data.get(str(user_id), 0))

    async def add_balance(self, user_id: int, amount: int) -> int:
        if amount == 0:
            return await self.get_balance(user_id)
        data = self._read()
        key = str(user_id)
        current = int(data.get(key, 0))
        new = current + int(amount)
        data[key] = new
        self._write(data)
        return new

    async def deduct_balance(self, user_id: int, amount: int) -> Tuple[bool, int]:
        """Attempt to deduct amount from user. Returns (success, new_balance)."""
        if amount <= 0:
            return False, await self.get_balance(user_id)
        data = self._read()
        key = str(user_id)
        current = int(data.get(key, 0))
        if current < amount:
            return False, current
        new = current - int(amount)
        data[key] = new
        self._write(data)
        return True, new

    async def transfer(self, from_id: int, to_id: int, amount: int) -> Tuple[bool, int, int]:
        if amount <= 0:
            return False, await self.get_balance(from_id), await self.get_balance(to_id)
        data = self._read()
        f = str(from_id)
        t = str(to_id)
        if int(data.get(f, 0)) < amount:
            return False, int(data.get(f, 0)), int(data.get(t, 0))
        data[f] = int(data.get(f, 0)) - amount
        data[t] = int(data.get(t, 0)) + amount
        self._write(data)
        return True, int(data[f]), int(data[t])

    async def leaderboard(self, limit: int = 10) -> List[Tuple[int, int]]:
        data = self._read()
        items = sorted(((int(k), int(v)) for k, v in data.items()), key=lambda x: x[1], reverse=True)
        return items[:limit]


# module-level singleton
economy_manager = EconomyManager()
