import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import os

from src.utils.config_manager import ensure_data_dir

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

class MessageLogger(commands.Cog):
    """訊息編輯和刪除日誌 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/logs/messages/message_log.json"
        self.config_file = "data/storage/log_channels.json"
        ensure_data_dir()
        
    def get_current_time_str(self) -> str:
        """獲取格式化的當前時間 (月/日 時:分)"""
        now = datetime.now(TZ_OFFSET)
        return now.strftime("%m/%d %H:%M")
    
    def load_log_channels(self) -> dict:
        """載入日誌頻道設置"""
        if not os.path.exists(self.config_file):
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[錯誤] 無法載入日誌頻道設置: {e}")
            return {}
    
    def save_log_channels(self, data: dict):
        """保存日誌頻道設置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[錯誤] 無法保存日誌頻道設置: {e}")
    
    def get_log_channel_id(self, guild_id: int) -> Optional[int]:
        """獲取伺服器的日誌頻道 ID"""
        channels = self.load_log_channels()
        return channels.get(str(guild_id))
    
    def set_log_channel_id(self, guild_id: int, channel_id: int):
        """設置伺服器的日誌頻道 ID"""
        channels = self.load_log_channels()
        channels[str(guild_id)] = channel_id
        self.save_log_channels(channels)
    
    def load_message_log(self) -> dict:
        """載入訊息日誌"""
        if not os.path.exists(self.data_file):
            return {}
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[錯誤] 無法載入訊息日誌: {e}")
            return {}
    
    def save_message_log(self, data: dict):
        """保存訊息日誌"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[錯誤] 無法保存訊息日誌: {e}")
    
    def add_message_record(self, guild_id: int, message_id: int, content: str, author_id: int, channel_id: int, attachments: list = None):
        """添加訊息記錄"""
        logs = self.load_message_log()
        msg_key = f"{guild_id}_{message_id}"
        
        # 提取附件URL
        attachment_urls = []
        if attachments:
            for attachment in attachments:
                attachment_urls.append(attachment.url)
        
        logs[msg_key] = {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "author_id": author_id,
            "original_content": content,
            "edit_history": [],
            "deleted": False,
            "attachments": attachment_urls,
            "created_at": datetime.now(TZ_OFFSET).isoformat()
        }
        
        self.save_message_log(logs)
    
    def update_message_edit(self, guild_id: int, message_id: int, new_content: str):
        """更新訊息編輯歷史"""
        logs = self.load_message_log()
        msg_key = f"{guild_id}_{message_id}"
        
        if msg_key in logs:
            logs[msg_key]["edit_history"].append(new_content)
            logs[msg_key]["last_edited_at"] = datetime.now(TZ_OFFSET).isoformat()
            self.save_message_log(logs)
            return True
        else:
            print(f"[警告] 未找到訊息記錄: {msg_key}")
            return False
    
    def mark_message_deleted(self, guild_id: int, message_id: int):
        """標記訊息為已刪除"""
        logs = self.load_message_log()
        msg_key = f"{guild_id}_{message_id}"
        
        if msg_key in logs:
            logs[msg_key]["deleted"] = True
            logs[msg_key]["deleted_at"] = datetime.now(TZ_OFFSET).isoformat()
            self.save_message_log(logs)
            return True
        else:
            print(f"[警告] 未找到訊息記錄: {msg_key}")
            return False
    
    def get_message_record(self, guild_id: int, message_id: int) -> Optional[dict]:
        """獲取訊息記錄"""
        logs = self.load_message_log()
        msg_key = f"{guild_id}_{message_id}"
        return logs.get(msg_key)
    
    def is_image_or_gif(self, url: str) -> bool:
        """檢查連結是否為圖片或GIF"""
        if not url:
            return False
        url_lower = url.lower()
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')
        return any(url_lower.endswith(ext) for ext in image_extensions) or \
               any(ext in url_lower for ext in ('media', 'image', 'cdn'))
    
    def get_first_image_url(self, attachment_urls: list) -> Optional[str]:
        """從附件URL列表中獲取第一個圖片或GIF的URL"""
        if not attachment_urls:
            return None
        for url in attachment_urls:
            if self.is_image_or_gif(url):
                return url
        return None
    
    def create_edit_embed(self, guild_id: int, channel_id: int, message_id: int, user_id: int, user_name: str, guild_name: str, before_content: str, after_content: str, edit_count: int, before_attachments: list = None, after_attachments: list = None) -> discord.Embed:
        """建立編輯訊息的 embed"""
        embed = discord.Embed(
            title="[編輯] 訊息已編輯",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET)
        )
        
        # 添加基本信息
        embed.add_field(name="用戶ID", value=f"{user_id}", inline=True)
        embed.add_field(name="原始頻道ID", value=f"{channel_id}", inline=True)
        embed.add_field(name="伺服器名稱", value=f"{guild_name} ({guild_id})", inline=False)
        embed.add_field(name="訊息ID", value=str(message_id), inline=False)
        embed.add_field(name="時間", value=self.get_current_time_str(), inline=True)
        
        # 檢查編輯前的附件
        before_image_url = self.get_first_image_url(before_attachments) if before_attachments else None
        
        # 添加編輯前內容
        if before_image_url:
            # 如果有圖片，不用代碼框
            before_text = before_content[:1024] if before_content else "(空)"
            if before_text and before_text != "(空)":
                embed.add_field(name="編輯前 (文字)", value=before_text, inline=False)
        else:
            # 如果沒有圖片，用代碼框包裹文字
            before_text = before_content[:1024] if before_content else "(空)"
            embed.add_field(name="編輯前", value=f"```\n{before_text}\n```", inline=False)
        
        # 檢查編輯後的附件
        after_image_url = self.get_first_image_url(after_attachments) if after_attachments else None
        
        # 添加編輯後內容
        if after_image_url:
            # 如果有圖片，不用代碼框
            after_text = after_content[:1024] if after_content else "(空)"
            if after_text and after_text != "(空)":
                embed.add_field(name="編輯後 (文字)", value=after_text, inline=False)
        else:
            # 如果沒有圖片，用代碼框包裹文字
            after_text = after_content[:1024] if after_content else "(空)"
            embed.add_field(name="編輯後", value=f"```\n{after_text}\n```", inline=False)
        
        # 如果有編輯後的圖片，添加到embed
        if after_image_url:
            embed.set_image(url=after_image_url)
        
        embed.add_field(name="編輯次數", value=str(edit_count), inline=True)
        
        embed.set_footer(text=f"用戶 {user_name}")
        
        return embed
    
    def create_delete_embed(self, guild_id: int, channel_id: int, message_id: int, user_id: int, user_name: str, guild_name: str, content: str, attachments: list = None) -> discord.Embed:
        """建立刪除訊息的 embed"""
        embed = discord.Embed(
            title="[刪除] 訊息已刪除",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET)
        )
        
        # 添加基本信息
        embed.add_field(name="用戶ID", value=f"{user_id}", inline=True)
        embed.add_field(name="原始頻道ID", value=f"{channel_id}", inline=True)
        embed.add_field(name="伺服器名稱", value=f"{guild_name} ({guild_id})", inline=False)
        embed.add_field(name="訊息ID", value=str(message_id), inline=False)
        embed.add_field(name="時間", value=self.get_current_time_str(), inline=True)
        
        # 檢查是否有圖片附件
        image_url = self.get_first_image_url(attachments) if attachments else None
        
        # 添加刪除前的訊息內容
        if image_url:
            # 如果有圖片，不用代碼框
            content_text = content[:1024] if content else "(空)"
            if content_text and content_text != "(空)":
                embed.add_field(name="刪除前的訊息 (文字)", value=content_text, inline=False)
        else:
            # 如果沒有圖片，用代碼框包裹文字
            content_text = content[:1024] if content else "(空)"
            embed.add_field(name="刪除前的訊息", value=f"```\n{content_text}\n```", inline=False)
        
        # 如果有圖片，添加到embed
        if image_url:
            embed.set_image(url=image_url)
        
        embed.set_footer(text=f"用戶 {user_name}")
        
        return embed
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽所有訊息 - 記錄內容以備後用"""
        # 忽略bot訊息
        if message.author.bot:
            return
        
        # 忽略私人訊息
        if message.guild is None:
            return
        
        # 記錄訊息內容
        record = self.get_message_record(message.guild.id, message.id)
        if not record:
            self.add_message_record(
                message.guild.id,
                message.id,
                message.content,
                message.author.id,
                message.channel.id,
                message.attachments if message.attachments else None
            )
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """監聽訊息編輯"""
        # 忽略bot訊息
        if before.author.bot:
            return
        
        # 內容相同，忽略
        if before.content == after.content:
            return
        
        try:
            guild_id = before.guild.id
            channel_id = before.channel.id
            message_id = before.id
            user_id = before.author.id
            user_name = str(before.author)
            
            # 獲取或創建記錄
            record = self.get_message_record(guild_id, message_id)
            if not record:
                # 如果沒有記錄，先創建
                self.add_message_record(guild_id, message_id, before.content, user_id, channel_id, before.attachments if before.attachments else None)
                before_content = before.content
                before_attachments = before.attachments if before.attachments else None
                edit_count = 1
            else:
                before_content = record.get("original_content", before.content)
                before_attachments = record.get("attachments", [])
                edit_count = 1 + len(record.get("edit_history", []))
            
            # 更新編輯歷史
            self.update_message_edit(guild_id, message_id, after.content)
            
            # 獲取日誌頻道
            log_channel_id = self.get_log_channel_id(guild_id)
            if not log_channel_id:
                return
            
            try:
                log_channel = await self.bot.fetch_channel(log_channel_id)
                if not isinstance(log_channel, discord.TextChannel):
                    return
                
                # 創建並發送 embed
                embed = self.create_edit_embed(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name,
                    guild_name=before.guild.name,
                    before_content=before_content,
                    after_content=after.content,
                    edit_count=edit_count,
                    before_attachments=before_attachments,
                    after_attachments=after.attachments if after.attachments else None
                )
                
                await log_channel.send(embed=embed)
                print(f"[✓] 編輯日誌已發送到頻道 {log_channel_id}")
                
                # 觸發成就
                try:
                    achievements_cog = self.bot.get_cog("Achievements")
                    if achievements_cog:
                        achievements_cog.trigger_edit_achievement(user_id, guild_id)
                except Exception as e:
                    print(f"[成就] 編輯成就觸發失敗: {e}")
                
            except Exception as e:
                print(f"[✗] 發送編輯日誌失敗: {e}")
                
        except Exception as e:
            print(f"[✗] 編輯監聽出錯: {e}")
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """監聽訊息刪除"""
        # 忽略bot訊息
        if message.author.bot:
            return
        
        try:
            guild_id = message.guild.id
            channel_id = message.channel.id
            message_id = message.id
            user_id = message.author.id
            user_name = str(message.author)
            
            # 獲取訊息記錄
            record = self.get_message_record(guild_id, message_id)
            if record:
                original_content = record.get("original_content", message.content)
                attachments = record.get("attachments", [])
            else:
                original_content = message.content
                attachments = [attachment.url for attachment in message.attachments] if message.attachments else []
                # 如果沒有記錄，創建一個
                self.add_message_record(guild_id, message_id, original_content, user_id, channel_id, message.attachments if message.attachments else None)
            
            # 標記為已刪除
            self.mark_message_deleted(guild_id, message_id)
            
            # 獲取日誌頻道
            log_channel_id = self.get_log_channel_id(guild_id)
            if not log_channel_id:
                return
            
            try:
                log_channel = await self.bot.fetch_channel(log_channel_id)
                if not isinstance(log_channel, discord.TextChannel):
                    return
                
                # 創建並發送 embed
                embed = self.create_delete_embed(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    user_id=user_id,
                    user_name=user_name,
                    guild_name=message.guild.name,
                    content=original_content,
                    attachments=attachments
                )
                
                await log_channel.send(embed=embed)
                print(f"[✓] 刪除日誌已發送到頻道 {log_channel_id}")
                
                # 觸發成就
                try:
                    achievements_cog = self.bot.get_cog("Achievements")
                    if achievements_cog:
                        achievements_cog.trigger_delete_achievement(user_id, guild_id)
                except Exception as e:
                    print(f"[成就] 刪除成就觸發失敗: {e}")
                
            except Exception as e:
                print(f"[✗] 發送刪除日誌失敗: {e}")
                
        except Exception as e:
            print(f"[✗] 刪除監聽出錯: {e}")
    
    @discord.app_commands.command(name="編刪紀錄設定", description="設置訊息編輯/刪除的日誌頻道")
    @discord.app_commands.describe(channel="要發送日誌的頻道")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """設置日誌頻道"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("[失敗] 你需要管理員權限才能使用此命令", ephemeral=True)
                return
            
            # 設置日誌頻道
            self.set_log_channel_id(interaction.guild_id, channel.id)
            
            embed = discord.Embed(
                title="[成功] 設置成功",
                description=f"訊息編輯/刪除的日誌將發送到 {channel.mention}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"[設置日誌頻道] 錯誤: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"[失敗] 錯誤: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(MessageLogger(bot))
