"""Message log business logic."""

import copy
from datetime import datetime
from datetime import timedelta
import threading
import time
from typing import Any, Optional

import discord

from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.i18n import text as tx
from src.utils.message_cache import get_message_cache
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET

_LOG_FILE = "data/logs/messages/message_log.json"
_CHANNELS_FILE = "data/storage/log_channels.json"
_CACHE_TTL = 120.0
_CHANNELS_TTL = 60.0
LOG_RETENTION_DAYS = 30
_MESSAGE_LOCK = threading.RLock()


class MessageLogService:
    """Message log data access and business logic."""

    def __init__(self) -> None:
        self._msg_cache: Optional[dict[Any, Any]] = None
        self._msg_cache_time: float = 0.0
        self._ch_cache: dict[Any, Any] = {}
        self._ch_cache_time: float = 0.0
        self.message_cache = get_message_cache()

    # ── Channel setting ───────────────────────────────────────────────

    def load_log_channels(self, force=False) -> dict[Any, Any]:
        """Read a detached snapshot; failed reads do not clear valid cache."""
        now = time.monotonic()
        if not force and self._ch_cache and (now - self._ch_cache_time) < _CHANNELS_TTL:
            return copy.deepcopy(self._ch_cache)
        try:
            data = read_document(_CHANNELS_FILE)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            raise TypeError("Channel configuration must be an object")
        self._ch_cache = data
        self._ch_cache_time = now
        return copy.deepcopy(data)

    def save_log_channels(self, data: dict[Any, Any]) -> None:
        """Publish a detached channel snapshot only after persistence succeeds."""
        write_document(_CHANNELS_FILE, data)
        self._ch_cache = copy.deepcopy(data)
        self._ch_cache_time = time.monotonic()

    def invalidate_log_channels(self):
        """Reload shared channel configuration on the next lookup."""
        self._ch_cache_time = 0.0

    def get_log_channel_id(self, guild_id: int) -> Optional[int]:
        """The ID of the server's log channel."""
        return self.load_log_channels().get(str(guild_id))

    def set_log_channel_id(self, guild_id: int, channel_id: int) -> None:
        """Set the ID of the server's log channel."""
        channels = self.load_log_channels(force=True)
        channels[str(guild_id)] = channel_id
        self.save_log_channels(channels)

    # ── Message log ───────────────────────────────────────────────────

    def load_message_log(self, force: bool = False) -> dict[Any, Any]:
        """Load an independent copy; a failed read does not empty a valid cache."""
        with _MESSAGE_LOCK:
            now = time.monotonic()
            if (
                not force
                and self._msg_cache is not None
                and (now - self._msg_cache_time) < _CACHE_TTL
            ):
                return copy.deepcopy(self._msg_cache)
            try:
                data = read_document(_LOG_FILE)
            except FileNotFoundError:
                data = {}
            if not isinstance(data, dict):
                raise TypeError("Message log must be an object")
            self._msg_cache = copy.deepcopy(data)
            self._msg_cache_time = now
            return copy.deepcopy(data)

    def save_message_log(self, data: dict[Any, Any]) -> None:
        """Publish to the cache only after saving succeeds; the caller handles a failure."""
        with _MESSAGE_LOCK:
            if not isinstance(data, dict):
                raise TypeError("Message log must be an object")
            snapshot = copy.deepcopy(data)
            write_document(_LOG_FILE, snapshot)
            self._msg_cache = snapshot
            self._msg_cache_time = time.monotonic()
            self.message_cache.clear_all()

    def add_record(
        self,
        guild_id: int,
        message_id: int,
        content: str,
        author_id: int,
        channel_id: int,
        attachments: Optional[list[Any]] = None,
    ) -> None:
        """Add a message record."""
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
        with _MESSAGE_LOCK:
            logs = self.load_message_log(force=True)
            key = f"{guild_id}_{message_id}"
            if key in logs:
                self.message_cache.set(guild_id, message_id, logs[key])
                return
            logs[key] = record
            self.save_message_log(logs)
            self.message_cache.set(guild_id, message_id, record)

    def record_edit(self, guild_id: int, message_id: int, new_content: str) -> bool:
        """Record a message edit; return whether the original record was found."""
        with _MESSAGE_LOCK:
            logs = self.load_message_log(force=True)
            key = f"{guild_id}_{message_id}"
            if key not in logs:
                return False
            logs[key]["edit_history"].append(new_content)
            logs[key]["last_edited_at"] = datetime.now(TZ_OFFSET).isoformat()
            self.save_message_log(logs)
            self.message_cache.set(guild_id, message_id, logs[key])
            return True

    def mark_deleted(self, guild_id: int, message_id: int) -> bool:
        """Mark a message deleted; return whether the original record was found."""
        with _MESSAGE_LOCK:
            logs = self.load_message_log(force=True)
            key = f"{guild_id}_{message_id}"
            if key not in logs:
                return False
            logs[key]["deleted"] = True
            logs[key]["deleted_at"] = datetime.now(TZ_OFFSET).isoformat()
            self.save_message_log(logs)
            self.message_cache.set(guild_id, message_id, logs[key])
            return True

    def get_record(self, guild_id: int, message_id: int) -> Optional[dict[Any, Any]]:
        """Get a message record (from the cache first)."""
        with _MESSAGE_LOCK:
            cached = self.message_cache.get(guild_id, message_id)
            if cached is not None:
                return copy.deepcopy(cached)
            record = self.load_message_log(force=True).get(f"{guild_id}_{message_id}")
            if record:
                self.message_cache.set(guild_id, message_id, record)
            return copy.deepcopy(record)

    def cleanup_old_logs(self) -> int:
        """Remove records older than the retention period; return how many were removed."""
        with _MESSAGE_LOCK:
            logs = self.load_message_log(force=True)
            if not logs:
                return 0
            cutoff = (
                datetime.now(TZ_OFFSET) - timedelta(days=LOG_RETENTION_DAYS)
            ).isoformat()
            logging = {str(g) for g in self.load_log_channels()}
            # Too old, or from a server that has no log channel (any more): gone.
            to_remove = [
                k
                for k, v in logs.items()
                if v.get("created_at", "") < cutoff
                or str(v.get("guild_id")) not in logging
            ]
            for key in to_remove:
                del logs[key]
            if to_remove:
                self.save_message_log(logs)
                for key in to_remove:
                    guild_id, _, message_id = key.partition("_")
                    if guild_id.isdigit() and message_id.isdigit():
                        self.message_cache.delete(int(guild_id), int(message_id))
            return len(to_remove)

    # ── Tools ─────────────────────────────────────────────────────────

    @staticmethod
    def get_current_time_str() -> str:
        """The current time, formatted (month/day hour:minute)."""
        return datetime.now(TZ_OFFSET).strftime("%m/%d %H:%M")

    @staticmethod
    def _get_first_image_url(urls: list[str]) -> Optional[str]:
        """The first image URL in a list of attachment URLs."""
        exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
        for url in urls:
            ul = url.lower()
            if any(ul.endswith(e) for e in exts) or any(
                k in ul for k in ("media", "image", "cdn")
            ):
                return url
        return None

    # ── Embed building ────────────────────────────────────────────────

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
        """Build the embed for an edited message."""
        embed = discord.Embed(
            title=tx("message_log_service.edited_message_edited"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("message_log_service.user_id"), value=str(user_id), inline=True
        )
        embed.add_field(
            name=tx("message_log_service.channel_id"),
            value=str(channel_id),
            inline=True,
        )
        embed.add_field(
            name=tx("bot_appearance.server"),
            value=f"{guild_name} ({guild_id})",
            inline=False,
        )
        embed.add_field(
            name=tx("message_log_service.message_id"),
            value=str(message_id),
            inline=False,
        )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )

        before_image = self._get_first_image_url(before_attachments or [])
        before_text = (
            before_content[:1024] if before_content else tx("message_log_service.empty")
        )
        if before_image:
            if before_text and before_text != tx("message_log_service.empty"):
                embed.add_field(
                    name=tx("message_log_service.before_edit_text"),
                    value=before_text,
                    inline=False,
                )
        else:
            embed.add_field(
                name=tx("message_log_service.before_edit"),
                value=f"```\n{before_text}\n```",
                inline=False,
            )

        after_image = self._get_first_image_url(after_attachments or [])
        after_text = (
            after_content[:1024] if after_content else tx("message_log_service.empty")
        )
        if after_image:
            if after_text and after_text != tx("message_log_service.empty"):
                embed.add_field(
                    name=tx("message_log_service.after_edit_text"),
                    value=after_text,
                    inline=False,
                )
            embed.set_image(url=after_image)
        else:
            embed.add_field(
                name=tx("message_log_service.after_edit"),
                value=f"```\n{after_text}\n```",
                inline=False,
            )

        embed.add_field(
            name=tx("message_log_service.edit_count"),
            value=str(edit_count),
            inline=True,
        )
        embed.set_footer(text=tx("audit_log.user_941f2d", v0=(user_name)))
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
        """Build the embed for a deleted message."""
        embed = discord.Embed(
            title=tx("message_log_service.deleted_message_deleted"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("message_log_service.user_id"), value=str(user_id), inline=True
        )
        embed.add_field(
            name=tx("message_log_service.channel_id"),
            value=str(channel_id),
            inline=True,
        )
        embed.add_field(
            name=tx("bot_appearance.server"),
            value=f"{guild_name} ({guild_id})",
            inline=False,
        )
        embed.add_field(
            name=tx("message_log_service.message_id"),
            value=str(message_id),
            inline=False,
        )
        embed.add_field(
            name=tx("audit_log.time"), value=get_current_time_str(), inline=True
        )

        image_url = self._get_first_image_url(attachments or [])
        content_text = content[:1024] if content else tx("message_log_service.empty")
        if image_url:
            if content_text and content_text != "(空)":
                embed.add_field(
                    name=tx("message_log_service.before_deletion_text"),
                    value=content_text,
                    inline=False,
                )
            embed.set_image(url=image_url)
        else:
            embed.add_field(
                name=tx("message_log_service.message_before_deletion"),
                value=f"```\n{content_text}\n```",
                inline=False,
            )

        embed.set_footer(text=tx("audit_log.user_941f2d", v0=(user_name)))
        return embed
