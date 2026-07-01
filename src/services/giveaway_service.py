"""抽獎業務邏輯服務"""

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
import random
import re
import time
from typing import Optional

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/giveaways.json"


class GiveawayService:
    """抽獎資料存取與業務邏輯"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cache: Optional[dict] = None

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                    return self._cache
            except (json.JSONDecodeError, OSError):
                pass
        self._cache = {}
        return self._cache

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._cache = data

    # ─────────────── 查詢 ───────────────

    def get(self, giveaway_id: str) -> Optional[dict]:
        """取得單筆抽獎資料"""
        return self._load().get(giveaway_id)

    def list_active(self, guild_id: int) -> list[tuple[str, dict]]:
        """列出伺服器所有進行中的抽獎"""
        data = self._load()
        return [
            (gid, ga)
            for gid, ga in data.items()
            if ga.get("guild_id") == guild_id and not ga.get("ended")
        ]

    def list_all_active(self) -> list[tuple[str, dict]]:
        """列出所有進行中的抽獎 (跨伺服器，供定時檢查用)"""
        data = self._load()
        return [(gid, ga) for gid, ga in data.items() if not ga.get("ended")]

    # ─────────────── 建立 ───────────────

    def create(self, giveaway_id: str, giveaway_data: dict) -> None:
        """建立新抽獎記錄"""
        data = self._load()
        data[giveaway_id] = giveaway_data
        self._save(data)

    # ─────────────── 參加 / 退出 ───────────────

    @property
    def lock(self) -> asyncio.Lock:
        """取得並發鎖 (供 View 使用)"""
        return self._lock

    def toggle_participant(
        self, giveaway_id: str, user_id: str
    ) -> tuple[Optional[str], int]:
        """切換參與狀態，回傳 (action, count)，action 為 'joined'/'left'/None"""
        data = self._load()
        ga = data.get(giveaway_id)
        if not ga or ga.get("ended"):
            return None, 0

        participants: list = ga.setdefault("participants", [])
        if user_id in participants:
            participants.remove(user_id)
            action = "left"
        else:
            participants.append(user_id)
            action = "joined"

        self._save(data)
        return action, len(participants)

    # ─────────────── 結算 ───────────────

    def pick_winners(self, giveaway_id: str) -> list[str]:
        """隨機選出得獎者 ID 列表，不修改狀態"""
        ga = self.get(giveaway_id)
        if not ga:
            return []
        participants = ga.get("participants", [])
        num_winners = min(ga.get("winners", 1), len(participants))
        if not participants:
            return []
        return random.sample(participants, num_winners)

    def mark_ended(self, giveaway_id: str, winner_ids: list[str]) -> None:
        """標記抽獎為已結束並記錄得獎者"""
        data = self._load()
        ga = data.get(giveaway_id)
        if ga:
            ga["ended"] = True
            ga["winner_ids"] = winner_ids
            self._save(data)

    def reroll(self, giveaway_id: str, num_winners: int) -> list[str]:
        """重新抽獎，回傳新得獎者 ID 列表"""
        data = self._load()
        ga = data.get(giveaway_id)
        if not ga:
            return []
        participants = ga.get("participants", [])
        if not participants:
            return []
        winner_ids = random.sample(participants, min(num_winners, len(participants)))
        ga["winner_ids"] = winner_ids
        self._save(data)
        return winner_ids

    def check_expired(self) -> list[tuple[str, dict]]:
        """找出所有已到期但尚未結束的抽獎，並標記為結束 (不選得獎者)"""
        now = datetime.now(TZ_OFFSET).timestamp()
        expired: list[tuple[str, dict]] = []
        data = self._load()
        changed = False

        for gid, ga in list(data.items()):
            if ga.get("ended"):
                continue
            if now >= ga.get("end_time", float("inf")):
                expired.append((gid, dict(ga)))
                ga["ended"] = True
                changed = True

        if changed:
            self._save(data)
        return expired

    # ─────────────── 工具 ───────────────

    @staticmethod
    def parse_duration(duration: str) -> Optional[int]:
        """解析時長字串 (如 1h, 30m, 1d, 2d6h)，回傳秒數"""
        pattern = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?", re.IGNORECASE)
        match = pattern.fullmatch(duration.strip())
        if not match:
            return None
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        total = days * 86400 + hours * 3600 + minutes * 60
        return total if total > 0 else None
