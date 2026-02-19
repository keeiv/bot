import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import json
import os

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# 成就定義
ACHIEVEMENTS = {
    # 聊天互動成就
    "first_edit": {
        "name": "首次編輯",
        "description": "在伺服器中編輯一條訊息",
        "rarity": "common"
    },
    "editor": {
        "name": "編輯者",
        "description": "累計編輯訊息 50 次",
        "rarity": "uncommon"
    },
    "message_organizer": {
        "name": "訊息整理者",
        "description": "編輯訊息達 100 次",
        "rarity": "rare"
    },
    "first_delete": {
        "name": "信息撤回",
        "description": "首次刪除一條訊息",
        "rarity": "common"
    },
    "content_manager": {
        "name": "內容管理者",
        "description": "刪除訊息 50 次",
        "rarity": "uncommon"
    },
    "active_participant": {
        "name": "活躍參與者",
        "description": "在伺服器發送 100 條訊息",
        "rarity": "uncommon"
    },
    
    # 遊戲成就
    "halo_broken": {
        "name": "光環破裂",
        "description": "首次在俄羅斯輪盤中失敗",
        "rarity": "uncommon"
    },
    "halo_damage": {
        "name": "光環損傷",
        "description": "在俄羅斯輪盤中失敗 5 次",
        "rarity": "rare"
    },
    "probability_challenger": {
        "name": "概率挑戰者",
        "description": "在俄羅斯輪盤中獲勝 5 次",
        "rarity": "rare"
    },
    "kursk_sinking": {
        "name": "庫爾斯克號",
        "description": "首次在潛艇遊戲中失敗",
        "rarity": "uncommon"
    },
    "depth_tracking": {
        "name": "沉沒追蹤",
        "description": "在潛艇遊戲中失敗 5 次",
        "rarity": "rare"
    },
    "deep_sea_explorer": {
        "name": "深海探險家",
        "description": "在潛艇遊戲中獲勝 5 次",
        "rarity": "rare"
    },
    
    # 社交成就
    "server_newcomer": {
        "name": "伺服器新人",
        "description": "加入伺服器",
        "rarity": "common"
    },
    "active_member": {
        "name": "活躍成員",
        "description": "在伺服器活動滿 7 天",
        "rarity": "uncommon"
    },
    "info_explorer": {
        "name": "資訊查詢者",
        "description": "使用 /user_info 查詢用戶 5 次",
        "rarity": "common"
    },
    "server_analyst": {
        "name": "伺服器分析者",
        "description": "查詢 /server_info 3 次",
        "rarity": "common"
    },
    
    # 特殊成就
    "first_interaction": {
        "name": "首次互動",
        "description": "在伺服器中執行第一個操作",
        "rarity": "common"
    },
    
    # 開發者特殊成就
    "morinoyado_tearoom": {
        "name": "森之宿茶室",
        "description": "從虛無中破殼而出",
        "rarity": "legendary",
        "developer_only": True
    },
    
    # 探索者成就
    "achievement_explorer": {
        "name": "窺探者",
        "description": "查看成就圖鑑",
        "rarity": "uncommon"
    }
}

class Achievements(commands.Cog):
    """成就系統 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/storage/achievements.json"
        self.ensure_data_dir()
    
    def ensure_data_dir(self):
        """確保資料目錄存在"""
        os.makedirs("data/storage", exist_ok=True)
    
    def load_achievements(self) -> dict:
        """載入成就數據"""
        if not os.path.exists(self.data_file):
            return {}
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[錯誤] 無法載入成就數據: {e}")
            return {}
    
    def save_achievements(self, data: dict):
        """保存成就數據"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[錯誤] 無法保存成就數據: {e}")
    
    def get_user_achievements(self, user_id: int, guild_id: int = None) -> list:
        """獲取用戶成就列表"""
        achievements = self.load_achievements()
        user_key = str(user_id)
        
        if user_key not in achievements:
            return []
        
        user_data = achievements[user_key]
        
        if guild_id:
            guild_key = str(guild_id)
            if guild_key not in user_data:
                return []
            return user_data[guild_key].get("unlocked", [])
        
        # 返回所有成就
        all_achievements = []
        for guild_key in user_data:
            all_achievements.extend(user_data[guild_key].get("unlocked", []))
        
        return list(set(all_achievements))
    
    def unlock_achievement(self, user_id: int, guild_id: int, achievement_id: str) -> bool:
        """解鎖成就，返回是否為新解鎖"""
        achievements = self.load_achievements()
        user_key = str(user_id)
        guild_key = str(guild_id)
        
        if user_key not in achievements:
            achievements[user_key] = {}
        
        if guild_key not in achievements[user_key]:
            achievements[user_key][guild_key] = {"unlocked": []}
        
        if achievement_id not in achievements[user_key][guild_key]["unlocked"]:
            achievements[user_key][guild_key]["unlocked"].append(achievement_id)
            achievements[user_key][guild_key]["unlocked_at_" + achievement_id] = datetime.now(TZ_OFFSET).isoformat()
            self.save_achievements(achievements)
            return True
        
        return False
    
    def get_progress(self, user_id: int, guild_id: int = None) -> dict:
        """獲取用戶成就進度"""
        unlocked = self.get_user_achievements(user_id, guild_id)
        total = len(ACHIEVEMENTS)
        
        # 如果查詢特定伺服器，只統計該伺服器的成就
        if guild_id is None:
            percentage = round((len(unlocked) / total) * 100, 1) if total > 0 else 0
            return {
                "unlocked": len(unlocked),
                "total": total,
                "percentage": percentage
            }
        
        # 不考慮開發者成就在計算中
        regular_achievements = {k: v for k, v in ACHIEVEMENTS.items() if not v.get("developer_only", False)}
        total_regular = len(regular_achievements)
        
        percentage = round((len(unlocked) / total_regular) * 100, 1) if total_regular > 0 else 0
        return {
            "unlocked": len(unlocked),
            "total": total_regular,
            "percentage": percentage
        }
    
    @app_commands.command(name="achievements", description="查看成就")
    @app_commands.describe(user="要查詢的用戶 (不填默認為自己)")
    async def achievements_command(self, interaction: discord.Interaction, user: discord.User = None):
        """查看成就命令"""
        try:
            if user is None:
                user = interaction.user
            
            unlocked_achievements = self.get_user_achievements(user.id, interaction.guild_id)
            progress = self.get_progress(user.id, interaction.guild_id)
            
            embed = discord.Embed(
                title="成就收集",
                color=discord.Color.from_rgb(52, 152, 219),
                timestamp=datetime.now(TZ_OFFSET)
            )
            
            # 用戶信息
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.add_field(name="用戶", value=f"{user.mention} ({user.name})", inline=False)
            
            # 進度條
            progress_bar = self.get_progress_bar(progress["percentage"])
            embed.add_field(
                name="成就進度",
                value=f"{progress_bar}\n{progress['unlocked']}/{progress['total']} ({progress['percentage']}%)",
                inline=False
            )
            
            # 已解鎖成就
            if unlocked_achievements:
                achievement_list = []
                for ach_id in unlocked_achievements:
                    if ach_id in ACHIEVEMENTS:
                        ach = ACHIEVEMENTS[ach_id]
                        rarity_emoji = self.get_rarity_emoji(ach["rarity"])
                        achievement_list.append(f"{rarity_emoji} {ach['name']}")
                
                if achievement_list:
                    # 分頁顯示（每頁 10 個）
                    for i in range(0, len(achievement_list), 10):
                        chunk = achievement_list[i:i+10]
                        embed.add_field(
                            name=f"已解鎖成就 (第 {i//10 + 1} 頁)",
                            value="\n".join(chunk),
                            inline=False
                        )
            else:
                embed.add_field(name="已解鎖成就", value="尚未解鎖任何成就", inline=False)
            
            embed.set_footer(text=f"更新於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"[achievements_command] 錯誤: {e}")
            await interaction.response.send_message(f"[錯誤] 無法獲取成就信息: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="achievement_codex", description="查看成就圖鑑")
    async def achievement_codex(self, interaction: discord.Interaction):
        """查看所有可用成就的圖鑑"""
        try:
            await interaction.response.defer()
            
            # 觸發窺探者成就
            self.unlock_achievement(interaction.user.id, interaction.guild.id, "achievement_explorer")
            
            # 按稀有度分類成就
            rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
            achievements_by_rarity = {rarity: [] for rarity in rarity_order}
            
            for ach_id, ach_data in ACHIEVEMENTS.items():
                # 隱藏開發者專用成就
                if ach_data.get("developer_only", False):
                    continue
                rarity = ach_data.get("rarity", "common")
                achievements_by_rarity[rarity].append((ach_id, ach_data))
            
            # 建立嵌入消息
            embeds = []
            
            # 標題頁面
            title_embed = discord.Embed(
                title=" 成就圖鑑",
                description="查看所有可解鎖的成就\n\n使用 `/achievement_info <成就ID>` 查看詳細信息",
                color=discord.Color.gold(),
                timestamp=datetime.now(TZ_OFFSET)
            )
            title_embed.add_field(
                name=" 統計",
                value=f"總成就數: {len([a for a in ACHIEVEMENTS.values() if not a.get('developer_only', False)])}\n稀有度: 通常 > 罕見 > 稀有 > 史詩 > 傳說",
                inline=False
            )
            embeds.append(title_embed)
            
            # 按稀有度添加成就
            for rarity in rarity_order:
                if not achievements_by_rarity[rarity]:
                    continue
                
                embed = discord.Embed(
                    title=f"{self.get_rarity_emoji(rarity)} 成就圖鑑",
                    color=self.get_rarity_color(rarity),
                    timestamp=datetime.now(TZ_OFFSET)
                )
                
                for ach_id, ach_data in achievements_by_rarity[rarity]:
                    achievement_text = f"**{ach_data['name']}**\n{ach_data['description']}"
                    embed.add_field(
                        name=achievement_text,
                        value=f"`{ach_id}`",
                        inline=False
                    )
                
                embeds.append(embed)
            
            # 發送所有嵌入
            await interaction.followup.send(embeds=embeds)
            
        except Exception as e:
            print(f"[achievement_codex] 錯誤: {e}")
            await interaction.followup.send(f"[錯誤] {str(e)}", ephemeral=True)
    
    @app_commands.command(name="achievement_info", description="查看成就詳細信息")
    @app_commands.describe(achievement="成就名稱或 ID")
    async def achievement_info(self, interaction: discord.Interaction, achievement: str):
        """查看成就詳細信息"""
        try:
            # 優先按 ID 查找，然後按名稱查找
            achievement_id = None
            achievement_data = None
            
            if achievement in ACHIEVEMENTS:
                achievement_id = achievement
                achievement_data = ACHIEVEMENTS[achievement]
            else:
                # 按名稱模糊查找
                for ach_id, ach_data in ACHIEVEMENTS.items():
                    if achievement.lower() in ach_data["name"].lower():
                        achievement_id = ach_id
                        achievement_data = ach_data
                        break
            
            if not achievement_data:
                await interaction.response.send_message("[失敗] 找不到該成就", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=achievement_data["name"],
                description=achievement_data["description"],
                color=self.get_rarity_color(achievement_data["rarity"]),
                timestamp=datetime.now(TZ_OFFSET)
            )
            
            embed.add_field(name="稀有度", value=self.get_rarity_display(achievement_data["rarity"]), inline=False)
            embed.add_field(name="成就 ID", value=f"`{achievement_id}`", inline=False)
            
            if achievement_data.get("developer_only", False):
                embed.add_field(name="類別", value="未知", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"[achievement_info] 錯誤: {e}")
            await interaction.response.send_message(f"[錯誤] {str(e)}", ephemeral=True)
    
    def get_progress_bar(self, percentage: float, length: int = 20) -> str:
        """生成進度條"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {percentage}%"
    
    def get_rarity_emoji(self, rarity: str) -> str:
        """獲取稀有度表情符號"""
        rarity_map = {
            "common": "[通常]",
            "uncommon": "[罕見]",
            "rare": "[稀有]",
            "epic": "[史詩]",
            "legendary": "[傳說]"
        }
        return rarity_map.get(rarity, "[不知]")
    
    def get_rarity_display(self, rarity: str) -> str:
        """獲取稀有度顯示名稱"""
        rarity_map = {
            "common": "通常",
            "uncommon": "罕見",
            "rare": "稀有",
            "epic": "史詩",
            "legendary": "傳說"
        }
        return rarity_map.get(rarity, "未知")
    
    def get_rarity_color(self, rarity: str) -> discord.Color:
        """獲取稀有度顏色"""
        color_map = {
            "common": discord.Color.from_rgb(128, 128, 128),  # 灰色
            "uncommon": discord.Color.from_rgb(0, 255, 0),    # 綠色
            "rare": discord.Color.from_rgb(0, 0, 255),        # 藍色
            "epic": discord.Color.from_rgb(128, 0, 128),      # 紫色
            "legendary": discord.Color.from_rgb(255, 215, 0)  # 金色
        }
        return color_map.get(rarity, discord.Color.greyple())
    
    # 事件監聽和成就觸發方法（後續整合）
    def trigger_edit_achievement(self, user_id: int, guild_id: int):
        """觸發編輯成就檢查"""
        self.unlock_achievement(user_id, guild_id, "first_edit")
    
    def trigger_delete_achievement(self, user_id: int, guild_id: int):
        """觸發刪除成就檢查"""
        self.unlock_achievement(user_id, guild_id, "first_delete")
    
    def trigger_interaction_achievement(self, user_id: int, guild_id: int):
        """觸發互動成就檢查"""
        self.unlock_achievement(user_id, guild_id, "first_interaction")
    
    def trigger_game_loss(self, user_id: int, guild_id: int, game_type: str):
        """觸發遊戲失敗成就"""
        if game_type == "russian_roulette":
            self.unlock_achievement(user_id, guild_id, "halo_broken")
        elif game_type == "submarine":
            self.unlock_achievement(user_id, guild_id, "kursk_sinking")
    
    def trigger_codex_achievement(self, user_id: int, guild_id: int):
        """觸發圖鑑成就檢查"""
        self.unlock_achievement(user_id, guild_id, "achievement_explorer")

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Achievements(bot))
