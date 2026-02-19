import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import timedelta
import sys
import msvcrt  # Windows 文件鎖定

from utils.config_manager import (
    ensure_data_dir
)
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
        ("cogs.anti_spam", "anti_spam")
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


@bot.tree.command(name="clear", description="清除指定數量的訊息")
@discord.app_commands.describe(amount="要清除的訊息數量 (1-100)")
@discord.app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    """清除訊息"""
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("[失敗] 你需要管理訊息權限", ephemeral=True)
        return
    
    if amount < 1 or amount > 100:
        await interaction.response.send_message("[失敗] 數量必須在 1-100 之間", ephemeral=True)
        return
    
    await interaction.response.defer()
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"[成功] 已清除 {len(deleted)} 條訊息", ephemeral=True)

@bot.tree.command(name="kick", description="踢出成員")
@discord.app_commands.describe(user="要踢出的成員", reason="原因")
@discord.app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "無"):
    """踢出成員"""
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("[失敗] 你需要踢出成員權限", ephemeral=True)
        return
    
    if user == interaction.user:
        await interaction.response.send_message("[失敗] 你不能踢出你自己", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role:
        await interaction.response.send_message("[失敗] 你的權限不足以踢出此成員", ephemeral=True)
        return
    
    try:
        await user.kick(reason=reason)
        embed = discord.Embed(
            title="[成功] 已踢出成員",
            description=f"成員: {user.mention}\n原因: {reason}",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"[失敗] 無法踢出成員: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="封禁成員")
@discord.app_commands.describe(user="要封禁的成員", reason="原因")
@discord.app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "無"):
    """封禁成員"""
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("[失敗] 你需要封禁成員權限", ephemeral=True)
        return
    
    if user == interaction.user:
        await interaction.response.send_message("[失敗] 你不能封禁你自己", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role:
        await interaction.response.send_message("[失敗] 你的權限不足以封禁此成員", ephemeral=True)
        return
    
    try:
        await user.ban(reason=reason)
        embed = discord.Embed(
            title="[成功] 已封禁成員",
            description=f"成員: {user.mention}\n原因: {reason}",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"[失敗] 無法封禁成員: {str(e)}", ephemeral=True)

@bot.tree.command(name="mute", description="禁言成員")
@discord.app_commands.describe(user="要禁言的成員", duration="禁言時長(分鐘)", reason="原因")
@discord.app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, user: discord.Member, duration: int = 60, reason: str = "無"):
    """禁言成員"""
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("[失敗] 你需要管理成員權限", ephemeral=True)
        return
    
    if user == interaction.user:
        await interaction.response.send_message("[失敗] 你不能禁言你自己", ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role:
        await interaction.response.send_message("[失敗] 你的權限不足以禁言此成員", ephemeral=True)
        return
    
    try:
        await user.timeout(timedelta(minutes=duration), reason=reason)
        embed = discord.Embed(
            title="[成功] 已禁言成員",
            description=f"成員: {user.mention}\n時長: {duration} 分鐘\n原因: {reason}",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"[失敗] 無法禁言成員: {str(e)}", ephemeral=True)

@bot.tree.command(name="warn", description="警告成員")
@discord.app_commands.describe(user="要警告的成員", reason="原因")
@discord.app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str = "無"):
    """警告成員"""
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("[失敗] 你需要管理成員權限", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="[警告] 警告",
        description=f"{user.mention} 因為以下原因被警告:\n{reason}",
        color=discord.Color.from_rgb(241, 196, 15)
    )
    
    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"[成功] 已警告 {user.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"[警告] 已警告成員，但無法發送私訊: {str(e)}", ephemeral=True)

@bot.tree.command(name="anti_spam_set", description="設置防炸群功能")
@discord.app_commands.describe(
    enabled="是否啟用 (true/false)",
    messages_per_window="時間視窗內最多訊息數 (預設10)",
    window_seconds="時間視窗大小(秒) (預設10)",
    action="觸發時的動作 (mute/delete) (預設 mute)"
)
@discord.app_commands.default_permissions(administrator=True)
async def anti_spam_set(interaction: discord.Interaction, enabled: bool = True, messages_per_window: int = 10, window_seconds: int = 10, action: str = "mute"):
    """設置防炸群功能"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("[失敗] 你需要管理員權限", ephemeral=True)
            return
        
        if action not in ["mute", "delete"]:
            await interaction.response.send_message("[失敗] 可選的動作: mute 或 delete", ephemeral=True)
            return
        
        if messages_per_window < 1 or window_seconds < 1:
            await interaction.response.send_message("[失敗] 數量必須大於 0", ephemeral=True)
            return
        
        settings = {
            'enabled': enabled,
            'messages_per_window': messages_per_window,
            'window_seconds': window_seconds,
            'action': action
        }
        
        anti_spam_manager.update_settings(interaction.guild_id, settings)
        
        status = "[已啟用]" if enabled else "[已禁用]"
        embed = discord.Embed(
            title="[設置] 防炸群設置完成",
            description=f"{status} 防炸群功能",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        embed.add_field(name="[時間視窗]", value=f"{window_seconds} 秒", inline=True)
        embed.add_field(name="[訊息限制]", value=f"{messages_per_window} 條", inline=True)
        embed.add_field(name="[動作]", value=action, inline=True)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"[防炸群設置] 錯誤: {type(e).__name__}: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"[失敗] 錯誤: {str(e)}", ephemeral=True)

@bot.tree.command(name="anti_spam_status", description="查看防炸群狀態")
@discord.app_commands.default_permissions(administrator=True)
async def anti_spam_status(interaction: discord.Interaction):
    """查看防炸群狀態"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("[失敗] 你需要管理員權限", ephemeral=True)
            return
        
        settings = anti_spam_manager.get_settings(interaction.guild_id)
        
        status = "[已啟用]" if settings['enabled'] else "[已禁用]"
        
        embed = discord.Embed(
            title="[查詢] 防炸群設置狀態",
            color=discord.Color.blue()
        )
        embed.add_field(name="[是否啟用]", value=status, inline=False)
        embed.add_field(name="[時間視窗]", value=f"{settings['window_seconds']} 秒", inline=True)
        embed.add_field(name="[訊息限制]", value=f"{settings['messages_per_window']} 條", inline=True)
        embed.add_field(name="[動作]", value=settings['action'], inline=True)
        print(f"[查詢防炸群設置] 錯誤: {type(e).__name__}: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)


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
