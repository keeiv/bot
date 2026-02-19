"""Database migration scripts."""

import json
import os
from pathlib import Path

def migrate_config():
    """Migrate old config to new structure."""
    old_config = "config.json"
    new_config = "data/config/bot.json"
    
    if os.path.exists(old_config) and not os.path.exists(new_config):
        with open(old_config, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        os.makedirs(os.path.dirname(new_config), exist_ok=True)
        with open(new_config, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Migrated config to {new_config}")

def migrate_storage():
    """Migrate storage files to new structure."""
    storage_dir = Path("data/storage")
    old_data_dir = Path("data")
    
    storage_files = [
        "achievements.json",
        "blacklist.json", 
        "osu_links.json",
        "github_watch.json",
        "log_channels.json"
    ]
    
    for file in storage_files:
        old_path = old_data_dir / file
        new_path = storage_dir / file
        
        if old_path.exists() and not new_path.exists():
            import shutil
            shutil.move(str(old_path), str(new_path))
            print(f"Moved {file} to storage")

def migrate_logs():
    """Migrate log files to new structure."""
    logs_dir = Path("data/logs/messages")
    old_data_dir = Path("data")
    
    log_files = list(old_data_dir.glob("guild_*.json")) + [old_data_dir / "message_log.json"]
    
    for file in log_files:
        if file.exists():
            import shutil
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
