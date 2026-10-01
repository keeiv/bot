"""成就業務邏輯服務"""

import copy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import threading
import time
from typing import Any, Optional

from src.utils.document_store import read_document
from src.utils.document_store import write_document

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/achievements.json"
_DATA_LOCK = threading.RLock()

# 成就定義 (從 cog 搬移至此，cog 透過 service 取得)
ACHIEVEMENTS: dict[str, dict[Any, Any]] = {
    # 聊天互動成就
    "first_edit": {
        "name": "首次編輯",
        "description": "在伺服器中編輯一條訊息",
        "rarity": "common",
    },
    "editor": {
        "name": "編輯者",
        "description": "累計編輯訊息 50 次",
        "rarity": "uncommon",
    },
    "message_organizer": {
        "name": "訊息整理者",
        "description": "編輯訊息達 100 次",
        "rarity": "rare",
    },
    "first_delete": {
        "name": "訊息撤回",
        "description": "首次刪除一條訊息",
        "rarity": "common",
    },
    "content_manager": {
        "name": "內容管理者",
        "description": "刪除訊息 50 次",
        "rarity": "uncommon",
    },
    "active_participant": {
        "name": "活躍參與者",
        "description": "在伺服器發送 100 條訊息",
        "rarity": "uncommon",
    },
    # 遊戲成就
    "halo_broken": {
        "name": "光環破裂",
        "description": "首次在俄羅斯輪盤中失敗",
        "rarity": "uncommon",
    },
    "halo_damage": {
        "name": "光環損傷",
        "description": "在俄羅斯輪盤中失敗 5 次",
        "rarity": "rare",
    },
    "probability_challenger": {
        "name": "概率挑戰者",
        "description": "在俄羅斯輪盤中獲勝 5 次",
        "rarity": "rare",
    },
    "kursk_sinking": {
        "name": "庫爾斯克號",
        "description": "首次在潛艇遊戲中失敗",
        "rarity": "uncommon",
    },
    "depth_tracking": {
        "name": "沉沒追蹤",
        "description": "在潛艇遊戲中失敗 5 次",
        "rarity": "rare",
    },
    "deep_sea_explorer": {
        "name": "深海探險家",
        "description": "在潛艇遊戲中獲勝 5 次",
        "rarity": "rare",
    },
    # 社交成就
    "server_newcomer": {
        "name": "伺服器新人",
        "description": "加入伺服器",
        "rarity": "common",
    },
    "active_member": {
        "name": "活躍成員",
        "description": "在伺服器活動滿 7 天",
        "rarity": "uncommon",
    },
    "info_explorer": {
        "name": "資訊查詢者",
        "description": "使用 /user_info 查詢用戶 5 次",
        "rarity": "common",
    },
    "server_analyst": {
        "name": "伺服器分析者",
        "description": "查詢 /server_info 3 次",
        "rarity": "common",
    },
    # 特殊成就
    "first_interaction": {
        "name": "首次互動",
        "description": "在伺服器中執行第一個操作",
        "rarity": "common",
    },
    # 探索者成就
    "achievement_explorer": {
        "name": "窺探者",
        "description": "查看成就圖鑑",
        "rarity": "uncommon",
    },
}

RARITY_LABELS = {
    "common": "[普通]",
    "uncommon": "[少見]",
    "rare": "[稀有]",
    "epic": "[史詩]",
    "legendary": "[傳說]",
}


class AchievementService:
    """成就資料存取與業務邏輯"""

    _CACHE_TTL: float = 60.0

    def __init__(self) -> None:
        self._cache: dict[Any, Any] | None = None
        self._cache_time: float = 0.0
        self._lock = _DATA_LOCK

    # ─────────────── 資料存取 ───────────────

    @staticmethod
    def _validate(data: Any) -> None:
        """Reject damaged records instead of replacing existing progress."""
        if not isinstance(data, dict):
            raise TypeError("Achievement data must be an object")
        for user_data in data.values():
            if not isinstance(user_data, dict):
                raise TypeError("User achievement data must be an object")
            for guild_data in user_data.values():
                if not isinstance(guild_data, dict):
                    raise TypeError("Guild achievement data must be an object")
                unlocked = guild_data.get("unlocked", [])
                if not isinstance(unlocked, list) or any(
                    not isinstance(achievement_id, str) for achievement_id in unlocked
                ):
                    raise TypeError("Unlocked achievements must be a list of IDs")

    def _load(self, force: bool = False) -> dict[Any, Any]:
        """Return a detached snapshot; failed reads preserve the valid cache."""
        with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._cache is not None
                and (now - self._cache_time) < self._CACHE_TTL
            ):
                return copy.deepcopy(self._cache)
            try:
                data = read_document(_DATA_FILE)
            except FileNotFoundError:
                data = {}
            self._validate(data)
            self._cache = copy.deepcopy(data)
            self._cache_time = now
            return copy.deepcopy(data)

    def _save(self, data: dict[Any, Any]) -> None:
        """Publish the proposed snapshot only after persistence succeeds."""
        with self._lock:
            proposed = copy.deepcopy(data)
            self._validate(proposed)
            write_document(_DATA_FILE, proposed)
            self._cache = proposed
            self._cache_time = time.monotonic()

    # ─────────────── 查詢 ───────────────

    def get_user_achievements(
        self, user_id: int, guild_id: Optional[int] = None
    ) -> list[str]:
        """取得用戶已解鎖的成就 ID 列表"""
        data = self._load()
        user_data = data.get(str(user_id))
        if not user_data:
            return []
        if guild_id is not None:
            result_value = user_data.get(str(guild_id), {}).get("unlocked", [])
            if not isinstance(result_value, list):
                raise TypeError("Unexpected stored or API value: expected list")
            return result_value
        all_unlocked: list[str] = []
        for guild_val in user_data.values():
            all_unlocked.extend(guild_val.get("unlocked", []))
        return list(set(all_unlocked))

    def get_progress(
        self, user_id: int, guild_id: Optional[int] = None
    ) -> dict[Any, Any]:
        """取得用戶成就進度"""
        unlocked = self.get_user_achievements(user_id, guild_id)
        regular = {k: v for k, v in ACHIEVEMENTS.items() if not v.get("developer_only")}
        total = len(regular) if guild_id is not None else len(ACHIEVEMENTS)
        pct = round(len(unlocked) / total * 100, 1) if total else 0.0
        return {
            "unlocked": len(unlocked),
            "total": total,
            "percentage": pct,
        }

    def get_achievement_info(self, achievement_id: str) -> Optional[dict[Any, Any]]:
        """取得單一成就定義"""
        return copy.deepcopy(ACHIEVEMENTS.get(achievement_id))

    # ─────────────── 解鎖 ───────────────

    def unlock(self, user_id: int, guild_id: int, achievement_id: str) -> bool:
        """解鎖成就，回傳是否為新解鎖"""
        if achievement_id not in ACHIEVEMENTS:
            return False
        # Refresh inside the shared lock so another service instance's successful
        # update cannot be overwritten by this instance's older TTL snapshot.
        with self._lock:
            data = self._load(force=True)
            user_key = str(user_id)
            guild_key = str(guild_id)
            data.setdefault(user_key, {}).setdefault(guild_key, {"unlocked": []})
            guild_data = data[user_key][guild_key]
            unlocked = guild_data.setdefault("unlocked", [])
            if achievement_id in unlocked:
                return False
            unlocked.append(achievement_id)
            guild_data[f"unlocked_at_{achievement_id}"] = datetime.now(
                TZ_OFFSET
            ).isoformat()
            self._save(data)
            return True

    # ─────────────── 顯示工具 ───────────────

    @staticmethod
    def get_rarity_label(rarity: str) -> str:
        """取得稀有度標籤"""
        return RARITY_LABELS.get(rarity, f"[{rarity}]")

    @staticmethod
    def get_progress_bar(percentage: float, length: int = 20) -> str:
        """產生文字進度條"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percentage}%"
