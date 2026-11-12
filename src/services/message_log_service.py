"""Message log business logic."""

import copy
from datetime import datetime
from datetime import timedelta
import threading
import time
from typing import Any, Optional

import discord

from src.services.message_log_store import MessageLogStore
from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.i18n import text as tx
from src.utils.message_cache import get_message_cache
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET

_CHANNELS_FILE = "data/storage/log_channels.json"
_CHANNELS_TTL = 60.0
LOG_RETENTION_DAYS = 30
_MESSAGE_LOCK = threading.RLock()


class MessageLogService:
    """Message log data access and business logic."""

    def __init__(self) -> None:
        self.store = MessageLogStore()
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

    def add_record(
        self,
        guild_id: int,
        message_id: int,
        content: str,
        author_id: int,
        channel_id: int,
        attachments: Optional[list[Any]] = None,
    ) -> None:
        """Add a message record; a repeated delivery keeps the first one."""
        record = {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "author_id": author_id,
            "original_content": content,
            "attachments": [a.url for a in attachments] if attachments else [],
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
        }
        with _MESSAGE_LOCK:
            with self.store.transaction(write=True) as db:
                self.store.insert(db, record)
                stored = self.store.read(db, guild_id, message_id)
            # The cache only learns what was committed.
            self.message_cache.set(guild_id, message_id, stored)

    def record_edit(self, guild_id: int, message_id: int, new_content: str) -> bool:
        """Record a message edit; return whether the original record was found."""
        with _MESSAGE_LOCK:
            with self.store.transaction(write=True) as db:
                if not self.store.lock_row(db, guild_id, message_id):
                    return False
                at = datetime.now(TZ_OFFSET).isoformat()
                self.store.append_edit(db, guild_id, message_id, new_content, at)
                stored = self.store.read(db, guild_id, message_id)
            self.message_cache.set(guild_id, message_id, stored)
            return True

    def mark_deleted(self, guild_id: int, message_id: int) -> bool:
        """Mark a message deleted; return whether the original record was found."""
        with _MESSAGE_LOCK:
            with self.store.transaction(write=True) as db:
                at = datetime.now(TZ_OFFSET).isoformat()
                if not self.store.mark_deleted(db, guild_id, message_id, at):
                    return False
                stored = self.store.read(db, guild_id, message_id)
            self.message_cache.set(guild_id, message_id, stored)
            return True

    def get_record(self, guild_id: int, message_id: int) -> Optional[dict[Any, Any]]:
        """Get a message record (from the cache first); the caller gets its own copy."""
        with _MESSAGE_LOCK:
            cached = self.message_cache.get(guild_id, message_id)
            if cached is not None:
                return copy.deepcopy(cached)
            with self.store.transaction() as db:
                record = self.store.read(db, guild_id, message_id)
            if record:
                self.message_cache.set(guild_id, message_id, record)
            return copy.deepcopy(record)

    def cleanup_old_logs(self) -> int:
        """Remove records past the retention period, or from servers without a log channel."""
        with _MESSAGE_LOCK:
            cutoff = (
                datetime.now(TZ_OFFSET) - timedelta(days=LOG_RETENTION_DAYS)
            ).isoformat()
            logging = [int(g) for g in self.load_log_channels() if str(g).isdigit()]
            with self.store.transaction(write=True) as db:
                gone = self.store.expired(db, cutoff, logging)
                self.store.remove(db, gone)
            for guild_id, message_id in gone:
                self.message_cache.delete(guild_id, message_id)
            return len(gone)

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
