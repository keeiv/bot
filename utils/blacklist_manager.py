import json
import os
from typing import Set

class BlacklistManager:
    """黑名單管理器"""
    
    def __init__(self):
        self.blacklist_file = "data/blacklist.json"
        self.ensure_data_dir()
        self._blacklist_cache = None
        self._last_load_time = None
    
    def ensure_data_dir(self):
        """確保數據目錄存在"""
        if not os.path.exists("data"):
            os.makedirs("data")
    
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

# 全局黑名單管理器實例
blacklist_manager = BlacklistManager()
