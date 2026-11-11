from collections import OrderedDict
import copy
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any, Dict, Optional

# The UTC+8 time zone
TZ_OFFSET = timezone(timedelta(hours=8))


class MessageCache:
    """In-memory message cache with an LRU policy, for faster lookups (synchronous and asynchronous use)."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        """Set up the message cache.

        Args:
            max_size: the most messages to cache (the oldest leave beyond that)
            ttl_seconds: how long an entry lives, in seconds
        """
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.cache_timestamp: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _get_cache_key(self, guild_id: int, message_id: int) -> str:
        """Build the cache key."""
        return f"{guild_id}_{message_id}"

    def _is_expired(self, cache_key: str) -> bool:
        """Check whether an entry has expired."""
        if cache_key not in self.cache_timestamp:
            return True

        elapsed = datetime.now(TZ_OFFSET).timestamp() - self.cache_timestamp[cache_key]
        return elapsed > self.ttl_seconds

    def get(self, guild_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """Get a message from the cache (synchronous).

        Args:
            guild_id: the server ID
            message_id: the message ID

        Returns:
            The message record, or None
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        # Check that the entry exists and has not expired
        if cache_key in self.cache and not self._is_expired(cache_key):
            # LRU: move to the end
            self.cache.move_to_end(cache_key)
            self.hits += 1
            return copy.deepcopy(self.cache[cache_key])

        # The entry is missing or expired
        if cache_key in self.cache:
            del self.cache[cache_key]
            if cache_key in self.cache_timestamp:
                del self.cache_timestamp[cache_key]

        self.misses += 1
        return None

    def set(self, guild_id: int, message_id: int, data: Dict[str, Any]) -> None:
        """Store a message in the cache (synchronous).

        Args:
            guild_id: the server ID
            message_id: the message ID
            data: the message record
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        # If it already exists, remove it first
        if cache_key in self.cache:
            del self.cache[cache_key]

        # Check whether it is over capacity
        if len(self.cache) >= self.max_size:
            # Remove the oldest (the first)
            oldest_key, _ = self.cache.popitem(last=False)
            if oldest_key in self.cache_timestamp:
                del self.cache_timestamp[oldest_key]

        # Add the new entry
        self.cache[cache_key] = copy.deepcopy(data)
        self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()

    def batch_set(self, messages: Dict[str, Dict[str, Any]]) -> None:
        """Store several entries (synchronous).

        Args:
            messages: a {cache_key: message_data} dict
        """
        for cache_key, data in messages.items():
            if len(self.cache) >= self.max_size:
                oldest_key, _ = self.cache.popitem(last=False)
                if oldest_key in self.cache_timestamp:
                    del self.cache_timestamp[oldest_key]

            self.cache[cache_key] = copy.deepcopy(data)
            self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()

    def update(self, guild_id: int, message_id: int, data: Dict[str, Any]) -> None:
        """Update a message in the cache (synchronous).

        Args:
            guild_id: the server ID
            message_id: the message ID
            data: the new message record
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        if cache_key in self.cache:
            # Merge the update
            self.cache[cache_key].update(copy.deepcopy(data))
            self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()
            # Move to the end (LRU)
            self.cache.move_to_end(cache_key)

    def delete(self, guild_id: int, message_id: int) -> None:
        """Delete a message from the cache (synchronous).

        Args:
            guild_id: the server ID
            message_id: the message ID
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        if cache_key in self.cache:
            del self.cache[cache_key]
        if cache_key in self.cache_timestamp:
            del self.cache_timestamp[cache_key]

    def clear_guild(self, guild_id: int) -> None:
        """Clear every entry of one server.

        Args:
            guild_id: the server ID
        """
        keys_to_delete = [
            key for key in self.cache.keys() if key.startswith(f"{guild_id}_")
        ]

        for key in keys_to_delete:
            del self.cache[key]
            if key in self.cache_timestamp:
                del self.cache_timestamp[key]

    def clear_all(self) -> None:
        """Clear every entry."""
        self.cache.clear()
        self.cache_timestamp.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Cache statistics.

        Returns:
            A dict of statistics
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "current_size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": f"{hit_rate:.2f}%",
            "ttl_seconds": self.ttl_seconds,
        }

    def reset_stats(self) -> None:
        """Reset the statistics."""
        self.hits = 0
        self.misses = 0


# The global message cache instance
_global_message_cache: Optional[MessageCache] = None


def get_message_cache(max_size: int = 1000, ttl_seconds: int = 3600) -> MessageCache:
    """The global message cache instance (a singleton).

    Args:
        max_size: the most messages to cache
        ttl_seconds: how long an entry lives, in seconds

    Returns:
        The MessageCache instance
    """
    global _global_message_cache

    if _global_message_cache is None:
        _global_message_cache = MessageCache(max_size=max_size, ttl_seconds=ttl_seconds)

    return _global_message_cache
