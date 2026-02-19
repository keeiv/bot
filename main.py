import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import timedelta
import sys
import msvcrt  # Windows 文件鎖定

from utils.config_manager import ensure_data_dir
from utils.blacklist_manager import blacklist_manager

# 加載環境變數
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 設置bot
intents = discord.Intents.default()
intents.message_content = True  # 讀取訊息內容
intents.guilds = True  # 伺服器事件
intents.guild_messages = True  # 伺服器訊息事件（必需用于編輯/刪除）
intents.members = True  # 成員事件

bot = commands.Bot(command_prefix=["/", "!"], intents=intents)

ensure_data_dir()

async def load_cogs():
    """加載所有 Cog"""
    print("[Cog] 開始加載 Cog...")
    
    cogs_to_load = [
        ("cogs.message_logger", "message_logger"),
        ("cogs.developer", "developer"),
        ("cogs.admin", "admin"),
        ("cogs.anti_spam", "anti_spam"),
        ("cogs.russian_roulette", "russian_roulette"),
        ("cogs.deep_sea_oxygen", "deep_sea_oxygen"),
        ("cogs.cross_dressing_petition", "cross_dressing_petition"),
        ("cogs.user_server_info", "user_server_info"),
        ("cogs.achievements", "achievements"),
        ("cogs.osu_info", "osu_info"),
        ("cogs.github_watch", "github_watch")
    ]
    
    for cog_path, cog_name in cogs_to_load:
        try:
            await bot.load_extension(cog_path)
            print(f"[Cog] ✓ 已加載 {cog_name}")
        except Exception as e:
            print(f"[Cog] ✗ 加載 {cog_name} 失敗: {e}")
    
    print(f"[Cog] Cog 加載完成")

@bot.event
async def on_ready():
    """Bot準備就緒"""
    print(f'{bot.user} 已登入')
    print(f"[DEBUG] Bot Process ID: {os.getpid()}")
    print(f"[Intents] message_content: {bot.intents.message_content}")
    print(f"[Intents] guilds: {bot.intents.guilds}")
    print(f"[Intents] guild_messages: {bot.intents.guild_messages}")
    print(f"[Intents] members: {bot.intents.members}")
    
    # 加載 Cog
    await load_cogs()
    
    try:
        synced = await bot.tree.sync()
        print(f"同步了 {len(synced)} 個斜杠指令")
    except Exception as e:
        print(f"同步指令時出錯: {e}")

# 啟動bot
if __name__ == "__main__":
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
    
    try:
        bot.run(TOKEN)
    finally:
        # 清理 lock 文件
        if os.path.exists(lock_file):
            os.remove(lock_file)
