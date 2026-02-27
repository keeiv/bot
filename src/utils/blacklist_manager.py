import json
import os
from typing import Set, Dict, Optional
from datetime import datetime, timezone, timedelta

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

class BlacklistManager:
    """黑名單管理器"""

    def __init__(self):
        self.blacklist_file = "data/storage/blacklist.json"
        self.appeals_file = "data/storage/appeals.json"
        self.ensure_data_dir()
        self._blacklist_cache = None
        self._last_load_time = None

    def ensure_data_dir(self):
        """確保數據目錄存在"""
        if not os.path.exists("data/storage"):
            os.makedirs("data/storage")

    def load_blacklist(self) -> Set[int]:
        """載入黑名單（帶緩存）"""
        try:
            # 檢查緩存是否需要更新
            current_time = os.path.getmtime(self.blacklist_file) if os.path.exists(self.blacklist_file) else 0

            if self._blacklist_cache is None or self._last_load_time != current_time:
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._blacklist_cache = set(data.get("blacklisted_users", []))
                    self._last_load_time = current_time

            return self._blacklist_cache or set()
        except Exception as e:
            print(f"[錯誤] 無法載入黑名單: {e}")
            return set()

    def is_blacklisted(self, user_id: int) -> bool:
        """檢查用戶是否在黑名單中"""
        return user_id in self.load_blacklist()

    def add_to_blacklist(self, user_id: int):
        """添加用戶到黑名單"""
        blacklist = self.load_blacklist()
        blacklist.add(user_id)
        self.save_blacklist(blacklist)

    def remove_from_blacklist(self, user_id: int):
        """從黑名單移除用戶"""
        blacklist = self.load_blacklist()
        blacklist.discard(user_id)
        self.save_blacklist(blacklist)

    def save_blacklist(self, blacklist: Set[int]):
        """保存黑名單"""
        try:
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump({"blacklisted_users": list(blacklist)}, f, ensure_ascii=False, indent=2)
            self._blacklist_cache = blacklist  # 更新緩存
        except Exception as e:
            print(f"[錯誤] 無法保存黑名單: {e}")

    def load_appeals(self) -> Dict:
        """載入申訴記錄"""
        try:
            if os.path.exists(self.appeals_file):
                with open(self.appeals_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"[錯誤] 無法載入申訴記錄: {e}")
            return {}

    def save_appeals(self, appeals: Dict):
        """保存申訴記錄"""
        try:
            with open(self.appeals_file, 'w', encoding='utf-8') as f:
                json.dump(appeals, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[錯誤] 無法保存申訴記錄: {e}")

    def add_appeal(self, user_id: int, reason: str) -> bool:
        """新增申訴"""
        if not self.is_blacklisted(user_id):
            return False

        appeals = self.load_appeals()
        user_id_str = str(user_id)

        # 檢查是否已有待處理的申訴
        if user_id_str in appeals and appeals[user_id_str]["status"] == "待處理":
            return False

        appeals[user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "status": "待處理",
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None
        }

        self.save_appeals(appeals)
        return True

    def get_appeal(self, user_id: int) -> Optional[Dict]:
        """取得特定用戶的申訴記錄"""
        appeals = self.load_appeals()
        return appeals.get(str(user_id))

    def update_appeal(self, user_id: int, status: str, reviewer_id: int = None) -> bool:
        """更新申訴狀態（accepted/rejected）"""
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str not in appeals:
            return False

        appeals[user_id_str]["status"] = status
        appeals[user_id_str]["reviewed_at"] = datetime.now(TZ_OFFSET).isoformat()
        appeals[user_id_str]["reviewed_by"] = reviewer_id

        # 如果申訴被接受，從黑名單移除用戶
        if status == "接受":
            self.remove_from_blacklist(user_id)

        self.save_appeals(appeals)
        return True

    def get_pending_appeals(self) -> list:
        """獲取所有待處理的申訴"""
        appeals = self.load_appeals()
        return [appeal for appeal in appeals.values() if appeal.get("status") == "待處理"]

# 全局黑名單管理器實例
blacklist_manager = BlacklistManager()
