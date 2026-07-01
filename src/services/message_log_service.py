"""訊息日誌業務邏輯服務"""

from datetime import datetime
import json
import os
import time
from typing import Optional

import discord

from src.utils.message_cache import get_message_cache
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET

_LOG_FILE = "data/logs/messages/message_log.json"
_CHANNELS_FILE = "data/storage/log_channels.json"
_CACHE_TTL = 120.0
_CHANNELS_TTL = 60.0
LOG_RETENTION_DAYS = 30


class MessageLogService:
    """訊息日誌資料存取與業務邏輯"""

    def __init__(self) -> None:
        self._msg_cache: Optional[dict] = None
        self._msg_cache_time: float = 0.0
        self._ch_cache: dict = {}
        self._ch_cache_time: float = 0.0
        self.message_cache = get_message_cache()

    # ─────────────── 頻道設定 ───────────────

    def load_log_channels(self) -> dict:
        """載入日誌頻道設定 (帶快取)"""
        now = time.monotonic()
        if self._ch_cache and (now - self._ch_cache_time) < _CHANNELS_TTL:
            return self._ch_cache
        if not os.path.exists(_CHANNELS_FILE):
            self._ch_cache = {}
            self._ch_cache_time = now
            return self._ch_cache
        try:
            with open(_CHANNELS_FILE, "r", encoding="utf-8") as f:
                self._ch_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._ch_cache = {}
        self._ch_cache_time = now
        return self._ch_cache

    def save_log_channels(self, data: dict) -> None:
        """儲存日誌頻道設定"""
        try:
            with open(_CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._ch_cache = data
            self._ch_cache_time = time.monotonic()
        except OSError as e:
            print(f"[錯誤] 無法儲存日誌頻道設定: {e}")

    def get_log_channel_id(self, guild_id: int) -> Optional[int]:
        """取得伺服器的日誌頻道 ID"""
        return self.load_log_channels().get(str(guild_id))

    def set_log_channel_id(self, guild_id: int, channel_id: int) -> None:
        """設定伺服器的日誌頻道 ID"""
        channels = self.load_log_channels()
        channels[str(guild_id)] = channel_id
        self.save_log_channels(channels)

    # ─────────────── 訊息日誌 ───────────────

    def load_message_log(self) -> dict:
        """載入訊息日誌 (帶快取)"""
        now = time.monotonic()
        if self._msg_cache is not None and (now - self._msg_cache_time) < _CACHE_TTL:
            return self._msg_cache
        if not os.path.exists(_LOG_FILE):
            self._msg_cache = {}
            self._msg_cache_time = now
            return self._msg_cache
        try:
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                self._msg_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._msg_cache = {}
        self._msg_cache_time = now
        return self._msg_cache

    def save_message_log(self, data: dict) -> None:
        """儲存訊息日誌"""
        os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)
        try:
            with open(_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._msg_cache = data
            self._msg_cache_time = time.monotonic()
        except OSError as e:
            print(f"[錯誤] 無法儲存訊息日誌: {e}")

    def add_record(
        self,
        guild_id: int,
        message_id: int,
        content: str,
        author_id: int,
        channel_id: int,
        attachments: Optional[list] = None,
    ) -> None:
        """新增訊息記錄"""
        attachment_urls = [a.url for a in attachments] if attachments else []
        record = {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "author_id": author_id,
            "original_content": content,
            "edit_history": [],
            "deleted": False,
            "attachments": attachment_urls,
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
        }
        logs = self.load_message_log()
        logs[f"{guild_id}_{message_id}"] = record
        self.save_message_log(logs)
        self.message_cache.set(guild_id, message_id, record)

    def record_edit(self, guild_id: int, message_id: int, new_content: str) -> bool:
        """記錄訊息編輯，回傳是否找到原始記錄"""
        logs = self.load_message_log()
        key = f"{guild_id}_{message_id}"
        if key not in logs:
            return False
        logs[key]["edit_history"].append(new_content)
        logs[key]["last_edited_at"] = datetime.now(TZ_OFFSET).isoformat()
        self.save_message_log(logs)
        self.message_cache.update(
            guild_id,
            message_id,
            {
                "edit_history": logs[key]["edit_history"],
                "last_edited_at": logs[key]["last_edited_at"],
            },
        )
        return True

    def mark_deleted(self, guild_id: int, message_id: int) -> bool:
        """標記訊息為已刪除，回傳是否找到原始記錄"""
        logs = self.load_message_log()
        key = f"{guild_id}_{message_id}"
        if key not in logs:
            return False
        logs[key]["deleted"] = True
        logs[key]["deleted_at"] = datetime.now(TZ_OFFSET).isoformat()
        self.save_message_log(logs)
        self.message_cache.update(
            guild_id,
            message_id,
            {"deleted": True, "deleted_at": logs[key]["deleted_at"]},
        )
        return True

    def get_record(self, guild_id: int, message_id: int) -> Optional[dict]:
        """取得訊息記錄 (優先快取)"""
        cached = self.message_cache.get(guild_id, message_id)
        if cached is not None:
            return cached
        record = self.load_message_log().get(f"{guild_id}_{message_id}")
        if record:
            self.message_cache.set(guild_id, message_id, record)
        return record

    def cleanup_old_logs(self) -> int:
        """清理超過保留天數的舊記錄，回傳刪除筆數"""
        logs = self.load_message_log()
        if not logs:
            return 0
        cutoff = (
            datetime.now(TZ_OFFSET) - timedelta(days=LOG_RETENTION_DAYS)
        ).isoformat()
        to_remove = [k for k, v in logs.items() if v.get("created_at", "") < cutoff]
        for k in to_remove:
            del logs[k]
        if to_remove:
            self.save_message_log(logs)
        return len(to_remove)

    # ─────────────── 工具 ───────────────

    @staticmethod
    def get_current_time_str() -> str:
        """取得格式化當前時間 (月/日 時:分)"""
        return datetime.now(TZ_OFFSET).strftime("%m/%d %H:%M")

    @staticmethod
    def _get_first_image_url(urls: list[str]) -> Optional[str]:
        """從附件 URL 列表中取得第一個圖片 URL"""
        exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
        for url in urls:
            ul = url.lower()
            if any(ul.endswith(e) for e in exts) or any(
                k in ul for k in ("media", "image", "cdn")
            ):
                return url
        return None

    # ─────────────── Embed 產生 ───────────────

    def build_edit_embed(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        user_id: int,
        user_name: str,
        guild_name: str,
        before_content: str,
        after_content: str,
        edit_count: int,
        before_attachments: Optional[list[str]] = None,
        after_attachments: Optional[list[str]] = None,
    ) -> discord.Embed:
        """建立訊息編輯 Embed"""
        embed = discord.Embed(
            title="[編輯] 訊息已編輯",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="用戶ID", value=str(user_id), inline=True)
        embed.add_field(name="頻道ID", value=str(channel_id), inline=True)
        embed.add_field(name="伺服器", value=f"{guild_name} ({guild_id})", inline=False)
        embed.add_field(name="訊息ID", value=str(message_id), inline=False)
        embed.add_field(name="時間", value=get_current_time_str(), inline=True)

        before_image = self._get_first_image_url(before_attachments or [])
        before_text = before_content[:1024] if before_content else "(空)"
        if before_image:
            if before_text and before_text != "(空)":
                embed.add_field(name="編輯前 (文字)", value=before_text, inline=False)
        else:
            embed.add_field(
                name="編輯前", value=f"```\n{before_text}\n```", inline=False
            )

        after_image = self._get_first_image_url(after_attachments or [])
        after_text = after_content[:1024] if after_content else "(空)"
        if after_image:
            if after_text and after_text != "(空)":
                embed.add_field(name="編輯後 (文字)", value=after_text, inline=False)
            embed.set_image(url=after_image)
        else:
            embed.add_field(
                name="編輯後", value=f"```\n{after_text}\n```", inline=False
            )

        embed.add_field(name="編輯次數", value=str(edit_count), inline=True)
        embed.set_footer(text=f"用戶 {user_name}")
        return embed

    def build_delete_embed(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        user_id: int,
        user_name: str,
        guild_name: str,
        content: str,
        attachments: Optional[list[str]] = None,
    ) -> discord.Embed:
        """建立訊息刪除 Embed"""
        embed = discord.Embed(
            title="[刪除] 訊息已刪除",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="用戶ID", value=str(user_id), inline=True)
        embed.add_field(name="頻道ID", value=str(channel_id), inline=True)
        embed.add_field(name="伺服器", value=f"{guild_name} ({guild_id})", inline=False)
        embed.add_field(name="訊息ID", value=str(message_id), inline=False)
        embed.add_field(name="時間", value=get_current_time_str(), inline=True)

        image_url = self._get_first_image_url(attachments or [])
        content_text = content[:1024] if content else "(空)"
        if image_url:
            if content_text and content_text != "(空)":
                embed.add_field(
                    name="刪除前的訊息 (文字)", value=content_text, inline=False
                )
            embed.set_image(url=image_url)
        else:
            embed.add_field(
                name="刪除前的訊息",
                value=f"```\n{content_text}\n```",
                inline=False,
            )

        embed.set_footer(text=f"用戶 {user_name}")
        return embed
