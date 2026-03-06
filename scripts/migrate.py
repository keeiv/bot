"""資料遷移腳本

負責將舊版資料與設定移到新的目錄結構。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


def migrate_config() -> None:
    """將舊的 `config.json` 移至 `data/config/bot.json`（若尚未存在）。"""
    old_config = "config.json"
    new_config = "data/config/bot.json"
    if os.path.exists(old_config) and not os.path.exists(new_config):
        with open(old_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        os.makedirs(os.path.dirname(new_config), exist_ok=True)
        with open(new_config, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Migrated config to {new_config}")


def migrate_storage() -> None:
    """將若干舊資料檔移至 `data/storage/`。"""
    storage_dir = Path("data/storage")
    old_data_dir = Path("data")
    storage_files: Iterable[str] = [
        "achievements.json",
        "blacklist.json",
        "osu_links.json",
        "github_watch.json",
        "log_channels.json",
    ]
    for file in storage_files:
        old_path = old_data_dir / file
        new_path = storage_dir / file
        if old_path.exists() and not new_path.exists():
            import shutil

            os.makedirs(new_path.parent, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            print(f"Moved {file} to storage")


def migrate_logs() -> None:
    """將日誌檔案移至 `data/logs/messages/`。"""
    logs_dir = Path("data/logs/messages")
    old_data_dir = Path("data")
    log_files = list(old_data_dir.glob("guild_*.json")) + [old_data_dir / "message_log.json"]
    for file in log_files:
        if file.exists():
            import shutil
            os.makedirs(logs_dir, exist_ok=True)
            new_path = logs_dir / file.name
            if not new_path.exists():
                shutil.move(str(file), str(new_path))
                print(f"Moved {file.name} to logs")


if __name__ == "__main__":
    print("Starting migration...")
    migrate_config()
    migrate_storage()
    migrate_logs()
    print("Migration completed!")
