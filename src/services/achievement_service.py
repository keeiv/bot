"""成就業務邏輯服務"""

import json
import os
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional

TZ_OFFSET = timezone(timedelta(hours=8))
_DATA_FILE = "data/storage/achievements.json"

# 成就定義 (從 cog 搬移至此，cog 透過 service 取得)
ACHIEVEMENTS: dict[str, dict] = {
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
        self._cache: dict | None = None
        self._cache_time: float = 0.0

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict:
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self._CACHE_TTL:
            return self._cache
        if not os.path.exists(_DATA_FILE):
            self._cache = {}
            self._cache_time = now
            return self._cache
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        self._cache_time = now
        return self._cache

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        try:
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._cache = data
            self._cache_time = time.monotonic()
        except OSError as e:
            print(f"[錯誤] 無法儲存成就數據: {e}")

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
            return user_data.get(str(guild_id), {}).get("unlocked", [])
        all_unlocked: list[str] = []
        for guild_val in user_data.values():
            all_unlocked.extend(guild_val.get("unlocked", []))
        return list(set(all_unlocked))

    def get_progress(
        self, user_id: int, guild_id: Optional[int] = None
    ) -> dict:
        """取得用戶成就進度"""
        unlocked = self.get_user_achievements(user_id, guild_id)
        regular = {
            k: v for k, v in ACHIEVEMENTS.items() if not v.get("developer_only")
        }
        total = len(regular) if guild_id is not None else len(ACHIEVEMENTS)
        pct = round(len(unlocked) / total * 100, 1) if total else 0.0
        return {
            "unlocked": len(unlocked),
            "total": total,
            "percentage": pct,
        }

    def get_achievement_info(self, achievement_id: str) -> Optional[dict]:
        """取得單一成就定義"""
        return ACHIEVEMENTS.get(achievement_id)

    # ─────────────── 解鎖 ───────────────

    def unlock(
        self, user_id: int, guild_id: int, achievement_id: str
    ) -> bool:
        """解鎖成就，回傳是否為新解鎖"""
        if achievement_id not in ACHIEVEMENTS:
            return False
        data = self._load()
        user_key = str(user_id)
        guild_key = str(guild_id)
        data.setdefault(user_key, {}).setdefault(guild_key, {"unlocked": []})
        guild_data = data[user_key][guild_key]
        if achievement_id in guild_data["unlocked"]:
            return False
        guild_data["unlocked"].append(achievement_id)
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
