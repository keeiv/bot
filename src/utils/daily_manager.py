from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

DATA_PATH = Path(__file__).parents[1].joinpath("data", "storage", "daily.json")


class DailyManager:
    """管理每日/每小時簽到資訊，持久化於 data/storage/daily.json"""

    def __init__(self):
        self._path = DATA_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def _read(self) -> Dict[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    async def get_info(self, user_id: int) -> Dict[str, Any]:
        data = self._read()
        return data.get(str(user_id), {})

    async def claim_daily(self, user_id: int) -> Dict[str, Any]:
        data = self._read()
        key = str(user_id)
        now = datetime.utcnow()
        info = data.get(key, {})
        last_daily = None
        if info.get("last_daily"):
            last_daily = datetime.fromisoformat(info["last_daily"])

        # check if already claimed today (UTC day)
        if last_daily and last_daily.date() == now.date():
            return {"claimed": False, "reason": "already"}

        # streak handling: if last_daily yesterday -> streak+1 else reset
        streak = int(info.get("streak", 0))
        if last_daily and (now.date() - last_daily.date()).days == 1:
            streak += 1
        else:
            streak = 1

        # reward calculation
        base = 100
        bonus = min(50, (streak - 1) * 10)
        reward = base + bonus

        info.update({"last_daily": now.isoformat(), "streak": streak})
        data[key] = info
        self._write(data)
        return {"claimed": True, "reward": reward, "streak": streak}

    async def claim_hourly(self, user_id: int) -> Dict[str, Any]:
        data = self._read()
        key = str(user_id)
        now = datetime.utcnow()
        info = data.get(key, {})
        last_hour = None
        if info.get("last_hourly"):
            last_hour = datetime.fromisoformat(info["last_hourly"])

        if last_hour and (now - last_hour) < timedelta(hours=1):
            remaining = timedelta(hours=1) - (now - last_hour)
            return {"claimed": False, "reason": "cooldown", "remaining_seconds": int(remaining.total_seconds())}

        reward = 20
        info.update({"last_hourly": now.isoformat()})
        data[key] = info
        self._write(data)
        return {"claimed": True, "reward": reward}


# module singleton
daily_manager = DailyManager()
