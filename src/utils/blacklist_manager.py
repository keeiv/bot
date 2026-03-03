import asyncio
import json
import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict
from typing import Optional

import aiohttp

TZ_OFFSET = timezone(timedelta(hours=8))

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "storage",
)
LOCAL_BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
APPEALS_FILE = os.path.join(DATA_DIR, "appeals.json")


def _load_json(path: str) -> Dict:
    """讀取 JSON 檔案"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: str, data: Dict):
    """寫入 JSON 檔案"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BlacklistManager:
    """黑名單管理器 (本地 + CatHome API 雙軌)"""

    def __init__(self, api_key: str = None, api_base: str = None):
        self.api_key = api_key
        self.api_base = api_base
        self._api_cache: Dict[int, Optional[Dict]] = {}
        self._api_cache_time: Dict[int, float] = {}
        self._rate_limit_lock = asyncio.Lock()
        self.session: aiohttp.ClientSession | None = None

    async def setup(self):
        """初始化 HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """關閉 HTTP session"""
        if self.session:
            await self.session.close()

    # ==================== 本地黑名單 ====================

    def local_check(self, user_id: int) -> Optional[Dict]:
        """檢查本地黑名單 (同步, 零延遲)"""
        data = _load_json(LOCAL_BLACKLIST_FILE)
        users = data.get("users", {})
        entry = users.get(str(user_id))
        if not entry:
            return None
        # 檢查是否過期
        expires_at = entry.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.now(TZ_OFFSET) >= exp_dt:
                    self.local_remove(user_id)
                    return None
            except ValueError:
                pass
        return entry

    def local_add(
        self,
        user_id: int,
        reason: str,
        mode: str = "block",
        added_by: int = None,
        expires_at: str = None,
        note: str = None,
    ) -> bool:
        """新增本地黑名單"""
        data = _load_json(LOCAL_BLACKLIST_FILE)
        data.setdefault("users", {})
        user_id_str = str(user_id)

        data["users"][user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "mode": mode,
            "added_by": added_by,
            "added_at": datetime.now(TZ_OFFSET).isoformat(),
            "expires_at": expires_at,
            "note": note,
        }

        _save_json(LOCAL_BLACKLIST_FILE, data)
        return True

    def local_remove(self, user_id: int) -> bool:
        """移除本地黑名單"""
        data = _load_json(LOCAL_BLACKLIST_FILE)
        users = data.get("users", {})
        user_id_str = str(user_id)

        if user_id_str not in users:
            return False

        del users[user_id_str]
        _save_json(LOCAL_BLACKLIST_FILE, data)
        return True

    def local_list(self) -> Dict[str, Dict]:
        """取得所有本地黑名單"""
        data = _load_json(LOCAL_BLACKLIST_FILE)
        return data.get("users", {})

    # ==================== CatHome API ====================

    async def api_check(self, user_id: int) -> Optional[Dict]:
        """檢查 CatHome API 黑名單 (非同步)"""
        if not self.api_key or not self.api_base:
            return None

        now = asyncio.get_event_loop().time()
        if user_id in self._api_cache:
            if now - self._api_cache_time.get(user_id, 0) < 10:
                return self._api_cache[user_id]

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

        users_list = data.get("users", [])
        if not users_list:
            result = None
        else:
            entries = data.get("entries", {})
            result = entries.get(str(user_id))

        self._api_cache[user_id] = result
        self._api_cache_time[user_id] = now
        return result

    async def check(self, user_id: int) -> Optional[Dict]:
        """雙軌檢查: 本地優先, 再查 API

        回傳 dict 含 "source" 鍵標記來源 ("local" / "api")
        """
        local_entry = self.local_check(user_id)
        if local_entry:
            local_entry["source"] = "local"
            return local_entry

        api_entry = await self.api_check(user_id)
        if api_entry:
            api_entry["source"] = "api"
            return api_entry

        return None

    # ==================== 申訴系統 ====================

    def load_appeals(self) -> Dict:
        """讀取申訴資料"""
        return _load_json(APPEALS_FILE)

    def save_appeals(self, appeals: Dict):
        """儲存申訴資料"""
        _save_json(APPEALS_FILE, appeals)

    def add_appeal(self, user_id: int, reason: str, source: str = "local") -> bool:
        """提交申訴"""
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str in appeals and appeals[user_id_str].get("status") == "待處理":
            return False

        appeals[user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "source": source,
            "status": "待處理",
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "review_reason": None,
        }

        self.save_appeals(appeals)
        return True

    def get_appeal(self, user_id: int) -> Optional[Dict]:
        """查詢申訴"""
        appeals = self.load_appeals()
        return appeals.get(str(user_id))

    def update_appeal(
        self,
        user_id: int,
        status: str,
        reviewer_id: int = None,
        review_reason: str = None,
    ) -> bool:
        """更新申訴狀態"""
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str not in appeals:
            return False

        appeals[user_id_str]["status"] = status
        appeals[user_id_str]["reviewed_at"] = datetime.now(TZ_OFFSET).isoformat()
        appeals[user_id_str]["reviewed_by"] = reviewer_id
        appeals[user_id_str]["review_reason"] = review_reason

        self.save_appeals(appeals)
        return True

    def get_pending_appeals(self) -> list:
        """取得所有待處理申訴"""
        appeals = self.load_appeals()
        return [
            appeal for appeal in appeals.values()
            if appeal.get("status") == "待處理"
        ]
