#!/usr/bin/env python3
"""
给指定用户解锁所有成就的脚本
"""

import json
import os
from datetime import datetime, timezone, timedelta


#!/usr/bin/env python3
"""為指定使用者解鎖所有成就。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# 使用 UTC+8
TZ_OFFSET = timezone(timedelta(hours=8))

# 成就清單（與主程式共用識別碼）
ACHIEVEMENTS: Dict[str, Dict[str, object]] = {
    "first_edit": {"name": "首次編輯", "rarity": "common"},
    "editor": {"name": "編輯者", "rarity": "uncommon"},
    "message_organizer": {"name": "訊息整理者", "rarity": "rare"},
    "first_delete": {"name": "訊息撤回", "rarity": "common"},
    "content_manager": {"name": "內容管理者", "rarity": "uncommon"},
    "active_participant": {"name": "活躍參與者", "rarity": "uncommon"},
    "halo_broken": {"name": "光環破裂", "rarity": "uncommon"},
    "halo_damage": {"name": "光環損傷", "rarity": "rare"},
    "probability_challenger": {"name": "機率挑戰者", "rarity": "rare"},
    "kursk_sinking": {"name": "庫爾斯克號", "rarity": "uncommon"},
    "depth_tracking": {"name": "沉沒追蹤", "rarity": "rare"},
    "deep_sea_explorer": {"name": "深海探險家", "rarity": "rare"},
    "server_newcomer": {"name": "伺服器新人", "rarity": "common"},
    "active_member": {"name": "活躍成員", "rarity": "uncommon"},
    "info_explorer": {"name": "資訊查詢者", "rarity": "common"},
    "server_analyst": {"name": "伺服器分析者", "rarity": "common"},
    "first_interaction": {"name": "首次互動", "rarity": "common"},
    "morinoyado_tearoom": {"name": "森之宿茶室", "rarity": "legendary", "developer_only": True},
    "achievement_explorer": {"name": "窺探者", "rarity": "uncommon"},
}


def load_achievements() -> Dict[str, object]:
    """讀取 `data/achievements.json`，若無返回空 dict。"""
    data_file = PathHolder = "data/achievements.json"
    if not os.path.exists(data_file):
        return {}
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[錯誤] 無法載入成就資料: {e}")
        return {}


def save_achievements(data: Dict[str, object]) -> None:
    """將成就資料寫回檔案。"""
    data_file = "data/achievements.json"
    try:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[錯誤] 無法保存成就資料: {e}")


def unlock_all_achievements(user_id: str, guild_id: str) -> List[str]:
    """為指定使用者解鎖所有尚未解鎖的成就，回傳新解鎖的 id 列表。"""
    achievements = load_achievements()
    if user_id not in achievements:
        achievements[user_id] = {}
    if guild_id not in achievements[user_id]:
        achievements[user_id][guild_id] = {"unlocked": []}

    user_data = achievements[user_id][guild_id]
    current_unlocked = set(user_data.get("unlocked", []))

    newly_unlocked: List[str] = []
    for achievement_id in ACHIEVEMENTS.keys():
        if achievement_id not in current_unlocked:
            user_data.setdefault("unlocked", []).append(achievement_id)
            user_data[f"unlocked_at_{achievement_id}"] = datetime.now(TZ_OFFSET).isoformat()
            newly_unlocked.append(achievement_id)

    save_achievements(achievements)
    return newly_unlocked


def main() -> None:
    user_id = "241619561760292866"
    guild_id = "1367102094917763204"
    print(f"為使用者 {user_id} 解鎖所有成就...")
    newly_unlocked = unlock_all_achievements(user_id, guild_id)
    if newly_unlocked:
        print(f"成功解鎖 {len(newly_unlocked)} 個成就:")
        for achievement_id in newly_unlocked:
            achievement_data = ACHIEVEMENTS[achievement_id]
            print(f"  - {achievement_data['name']} ({achievement_id})")
    else:
        print("使用者已擁有所有成就")
    print("完成")


if __name__ == "__main__":
    main()
