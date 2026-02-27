import asyncio
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from typing import Any, Dict, Optional

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


class MessageCache:
    """訊息內存緩存 - LRU 策略，提升查詢速度（支援同步和異步操作）"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        初始化訊息緩存

        Args:
            max_size: 最大緩存訊息數 (超過時退出最舊的)
            ttl_seconds: 緩存生命週期 (秒)
        """
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.cache_timestamp: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _get_cache_key(self, guild_id: int, message_id: int) -> str:
        """生成快取键"""
        return f"{guild_id}_{message_id}"

    def _is_expired(self, cache_key: str) -> bool:
        """檢查快取是否過期"""
        if cache_key not in self.cache_timestamp:
            return True

        elapsed = datetime.now(TZ_OFFSET).timestamp() - self.cache_timestamp[cache_key]
        return elapsed > self.ttl_seconds

    def get(self, guild_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """
        從緩存中獲取訊息（同步版本）

        Args:
            guild_id: 伺服器ID
            message_id: 訊息ID

        Returns:
            訊息記錄 或 None
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        # 檢查快取存在且未過期
        if cache_key in self.cache and not self._is_expired(cache_key):
            # LRU：移到末尾
            self.cache.move_to_end(cache_key)
            self.hits += 1
            return self.cache[cache_key].copy()

        # 快取不存在或已過期
        if cache_key in self.cache:
            del self.cache[cache_key]
            if cache_key in self.cache_timestamp:
                del self.cache_timestamp[cache_key]

        self.misses += 1
        return None

    def set(self, guild_id: int, message_id: int, data: Dict[str, Any]) -> None:
        """
        將訊息保存到緩存（同步版本）

        Args:
            guild_id: 伺服器ID
            message_id: 訊息ID
            data: 訊息記錄
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        # 如果已存在，先移除
        if cache_key in self.cache:
            del self.cache[cache_key]

        # 檢查是否超過容量
        if len(self.cache) >= self.max_size:
            # 移除最舊的（第一個）
            oldest_key, _ = self.cache.popitem(last=False)
            if oldest_key in self.cache_timestamp:
                del self.cache_timestamp[oldest_key]

        # 添加新項目
        self.cache[cache_key] = data.copy()
        self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()

    def batch_set(self, messages: Dict[str, Dict[str, Any]]) -> None:
        """
        批量設置快取（同步版本）

        Args:
            messages: {cache_key: message_data} 字典
        """
        for cache_key, data in messages.items():
            if len(self.cache) >= self.max_size:
                oldest_key, _ = self.cache.popitem(last=False)
                if oldest_key in self.cache_timestamp:
                    del self.cache_timestamp[oldest_key]

            self.cache[cache_key] = data.copy()
            self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()

    def update(self, guild_id: int, message_id: int, data: Dict[str, Any]) -> None:
        """
        更新緩存中的訊息（同步版本）

        Args:
            guild_id: 伺服器ID
            message_id: 訊息ID
            data: 新的訊息記錄
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        if cache_key in self.cache:
            # 合併更新
            self.cache[cache_key].update(data)
            self.cache_timestamp[cache_key] = datetime.now(TZ_OFFSET).timestamp()
            # 移到末尾（LRU）
            self.cache.move_to_end(cache_key)

    def delete(self, guild_id: int, message_id: int) -> None:
        """
        從緩存中刪除訊息（同步版本）

        Args:
            guild_id: 伺服器ID
            message_id: 訊息ID
        """
        cache_key = self._get_cache_key(guild_id, message_id)

        if cache_key in self.cache:
            del self.cache[cache_key]
        if cache_key in self.cache_timestamp:
            del self.cache_timestamp[cache_key]

    def clear_guild(self, guild_id: int) -> None:
        """
        清除某個伺服器的所有快取

        Args:
            guild_id: 伺服器ID
        """
        keys_to_delete = [
            key for key in self.cache.keys() if key.startswith(f"{guild_id}_")
        ]

        for key in keys_to_delete:
            del self.cache[key]
            if key in self.cache_timestamp:
                del self.cache_timestamp[key]

    def clear_all(self) -> None:
        """清除所有快取"""
        self.cache.clear()
        self.cache_timestamp.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        獲取快取統計信息

        Returns:
            統計信息字典
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
        """重置統計信息"""
        self.hits = 0
        self.misses = 0


# 全局訊息快取實例
_global_message_cache: Optional[MessageCache] = None


def get_message_cache(max_size: int = 1000, ttl_seconds: int = 3600) -> MessageCache:
    """
    獲取全局訊息快取實例（單例模式）

    Args:
        max_size: 最大緩存訊息數
        ttl_seconds: 快取過期時間（秒）

    Returns:
        MessageCache 實例
    """
    global _global_message_cache

    if _global_message_cache is None:
        _global_message_cache = MessageCache(max_size=max_size, ttl_seconds=ttl_seconds)

    return _global_message_cache
