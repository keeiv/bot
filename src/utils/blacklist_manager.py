import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import asyncio
import aiohttp

TZ_OFFSET = timezone(timedelta(hours=8))


class BlacklistManager:
    def __init__(self, api_key: str = None, api_base: str = None):
        self.appeals_file = "data/storage/appeals.json"
        if not os.path.exists("data/storage"):
            os.makedirs("data/storage")
        self.api_key = api_key
        self.api_base = api_base
        self._blacklist_cache = {}
        self._blacklist_cache_time = {}
        self._rate_limit_lock = asyncio.Lock()
        self.session: aiohttp.ClientSession | None = None

    async def setup(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def check(self, user_id: int):
        now = asyncio.get_event_loop().time()
        if user_id in self._blacklist_cache:
            if now - self._blacklist_cache_time.get(user_id, 0) < 10:
                return self._blacklist_cache[user_id]
        url = f"{self.api_base}?id={user_id}"
        headers = {"X-API-Key": self.api_key}
        async with self._rate_limit_lock:
            try:
                async with self.session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
            except Exception:
                return None
        if not data.get("users"):
            result = None
        else:
            result = data["entries"].get(str(user_id))
        self._blacklist_cache[user_id] = result
        self._blacklist_cache_time[user_id] = now
        return result

    def load_appeals(self) -> Dict:
        if os.path.exists(self.appeals_file):
            with open(self.appeals_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_appeals(self, appeals: Dict):
        with open(self.appeals_file, "w", encoding="utf-8") as f:
            json.dump(appeals, f, ensure_ascii=False, indent=2)

    def add_appeal(self, user_id: int, reason: str) -> bool:
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str in appeals and appeals[user_id_str]["status"] == "待處理":
            return False

        appeals[user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "status": "待處理",
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
        }

        self.save_appeals(appeals)
        return True

    def get_appeal(self, user_id: int) -> Optional[Dict]:
        appeals = self.load_appeals()
        return appeals.get(str(user_id))

    def update_appeal(self, user_id: int, status: str, reviewer_id: int = None) -> bool:
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str not in appeals:
            return False

        appeals[user_id_str]["status"] = status
        appeals[user_id_str]["reviewed_at"] = datetime.now(TZ_OFFSET).isoformat()
        appeals[user_id_str]["reviewed_by"] = reviewer_id

        self.save_appeals(appeals)
        return True

    def get_pending_appeals(self) -> list:
        appeals = self.load_appeals()
        return [
            appeal for appeal in appeals.values()
            if appeal.get("status") == "待處理"
        ]


blacklist_manager = BlacklistManager()