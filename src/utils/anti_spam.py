from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict, Tuple

import discord

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


class AntiSpamManager:
    """防刷屏管理器"""

    def __init__(self):
        # 儲存用戶在時間視窗內的訊息記錄
        # { guild_id: { user_id: [(timestamp, message_count)] } }
        self.message_log: Dict[int, Dict[int, list]] = defaultdict(
            lambda: defaultdict(list)
        )

        # 防刷屏設置: { guild_id: { 'enabled': bool, 'messages_per_window': int, 'window_seconds': int, 'action': str } }
        self.spam_settings: Dict[int, dict] = {}

    def init_guild_settings(self, guild_id: int):
        """初始化伺服器防刷屏設置"""
        if guild_id not in self.spam_settings:
            self.spam_settings[guild_id] = {
                "enabled": True,
                "messages_per_window": 10,  # 時間視窗內最多訊息數
                "window_seconds": 10,  # 時間視窗（秒）
                "action": "mute",  # 'mute' 或 'delete'
            }

    def get_settings(self, guild_id: int) -> dict:
        """取得伺服器設置"""
        self.init_guild_settings(guild_id)
        return self.spam_settings[guild_id]

    def update_settings(self, guild_id: int, settings: dict):
        """更新伺服器設置"""
        self.init_guild_settings(guild_id)
        self.spam_settings[guild_id].update(settings)

    def check_spam(self, guild_id: int, user_id: int) -> Tuple[bool, int]:
        """
        檢查是否觸發防刷屏

        回傳: (是否為垃圾訊息, 該時間視窗內的訊息數)
        """
        self.init_guild_settings(guild_id)
        settings = self.spam_settings[guild_id]

        if not settings["enabled"]:
            return False, 0

        now = datetime.now(TZ_OFFSET).timestamp()
        window_seconds = settings["window_seconds"]
        messages_per_window = settings["messages_per_window"]

        # 清理超出時間視窗的舊訊息記錄
        if user_id in self.message_log[guild_id]:
            self.message_log[guild_id][user_id] = [
                timestamp
                for timestamp in self.message_log[guild_id][user_id]
                if now - timestamp < window_seconds
            ]

        # 新增當前訊息
        self.message_log[guild_id][user_id].append(now)

        # 計算該時間視窗內的訊息數
        current_messages = len(self.message_log[guild_id][user_id])

        # 檢查是否超過限制
        is_spam = current_messages > messages_per_window

        return is_spam, current_messages

    def reset_user(self, guild_id: int, user_id: int):
        """重設用戶的訊息記錄"""
        if guild_id in self.message_log and user_id in self.message_log[guild_id]:
            self.message_log[guild_id][user_id] = []


def create_anti_spam_log_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    message_count: int,
    threshold: int,
    action: str,
) -> discord.Embed:
    """建立防刷屏日誌 Embed"""
    embed = discord.Embed(
        title="[防刷屏] 檢測到垃圾訊息",
        color=discord.Color.from_rgb(255, 165, 0),
        timestamp=datetime.now(TZ_OFFSET),
    )

    # 新增基本資訊
    embed.add_field(name="[用戶]", value=f"<@{user_id}> ({user_id})", inline=False)
    embed.add_field(name="[用戶名]", value=user_name, inline=False)
    embed.add_field(name="[伺服器]", value=f"{guild_name} ({guild_id})", inline=False)
    embed.add_field(
        name="[頻道]", value=f"<#{channel_id}> ({channel_id})", inline=False
    )

    # 新增統計資訊
    embed.add_field(name="[訊息數]", value=str(message_count), inline=True)
    embed.add_field(name="[閾值]", value=str(threshold), inline=True)

    # 新增執行的動作
    action_text = "禁言 1 小時" if action == "mute" else "刪除訊息"
    embed.add_field(name="[動作]", value=action_text, inline=False)

    embed.add_field(
        name="[時間]",
        value=datetime.now(TZ_OFFSET).strftime("%m/%d %H:%M"),
        inline=True,
    )

    return embed
