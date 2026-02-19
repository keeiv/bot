import os
import asyncio
import discord
from dotenv import load_dotenv
import sys

from src.bot import Bot
from src.utils.config_manager import ensure_data_dir
from src.utils.blacklist_manager import blacklist_manager

# 加載環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

def main():
    """Main entry point for the bot."""
    if not TOKEN:
        print("錯誤: 未設置 DISCORD_TOKEN 環境變數")
        exit(1)
    
    # 檢查是否已有 bot 實例在運行
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        print("[警告] 檢測到 lock 文件，可能已有 bot 實例在運行")
        try:
            with open(lock_file, 'r') as f:
                old_pid = f.read().strip()
            print(f"[警告] 舊實例 PID: {old_pid}")
            # 檢查進程是否還在運行
            try:
                os.kill(int(old_pid), 0)  # 檢查進程是否存在
                print("[錯誤] Bot 已在運行中，請先停止舊實例")
                exit(1)
            except OSError:
                print("[信息] 舊實例已停止，繼續啟動")
        except:
            pass
    
    # 創建 lock 文件
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    
    # 初始化數據目錄
    ensure_data_dir()
    
    # 創建並運行 bot
    bot = Bot()
    
    try:
        bot.run(TOKEN)
    finally:
        # 清理 lock 文件
        if os.path.exists(lock_file):
            os.remove(lock_file)

if __name__ == "__main__":
    main()
