import asyncio
import time
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands


class APIOptimizer:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.request_queue: List[Dict] = []
        self.batch_size = 10
        self.batch_interval = 1.0
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300
        self.rate_limits: Dict[str, Dict] = {}
        self.last_request_time: Dict[str, float] = {}

    async def batch_requests(self, requests: List[Dict]) -> List[Any]:
        results = []
        for i in range(0, len(requests), self.batch_size):
            batch = requests[i : i + self.batch_size]
            batch_results = await asyncio.gather(
                *[req["func"](*req["args"], **req["kwargs"]) for req in batch],
                return_exceptions=True,
            )
            results.extend(batch_results)

            if i + self.batch_size < len(requests):
                await asyncio.sleep(self.batch_interval)

        return results

    def get_cache_key(self, method: str, *args, **kwargs) -> str:
        key_parts = (
            [method]
            + [str(arg) for arg in args]
            + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        )
        return "|".join(key_parts)

    def get_cached(self, cache_key: str) -> Optional[Any]:
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
            else:
                del self.cache[cache_key]
        return None

    def set_cache(self, cache_key: str, data: Any) -> None:
        self.cache[cache_key] = (data, time.time())

    async def check_rate_limit(self, endpoint: str) -> bool:
        current_time = time.time()

        if endpoint in self.rate_limits:
            limit_info = self.rate_limits[endpoint]
            if current_time - limit_info["reset_time"] < limit_info["reset_after"]:
                if limit_info["remaining"] <= 0:
                    wait_time = limit_info["reset_after"] - (
                        current_time - limit_info["reset_time"]
                    )
                    await asyncio.sleep(wait_time)
                    return False

        return True

    def update_rate_limit(self, endpoint: str, headers: Dict) -> None:
        if "X-RateLimit-Remaining" in headers and "X-RateLimit-Reset-After" in headers:
            self.rate_limits[endpoint] = {
                "remaining": int(headers["X-RateLimit-Remaining"]),
                "reset_after": float(headers["X-RateLimit-Reset-After"]),
                "reset_time": time.time(),
            }

    async def optimized_get_channel(
        self, channel_id: int
    ) -> Optional[discord.TextChannel]:
        cache_key = f"channel_{channel_id}"
        cached_channel = self.get_cached(cache_key)

        if cached_channel:
            return cached_channel

        channel = self.bot.get_channel(channel_id)
        if channel:
            self.set_cache(cache_key, channel)

        return channel

    async def optimized_get_user(self, user_id: int) -> Optional[discord.User]:
        cache_key = f"user_{user_id}"
        cached_user = self.get_cached(cache_key)

        if cached_user:
            return cached_user

        user = self.bot.get_user(user_id)
        if user:
            self.set_cache(cache_key, user)

        return user

    async def optimized_get_guild(self, guild_id: int) -> Optional[discord.Guild]:
        cache_key = f"guild_{guild_id}"
        cached_guild = self.get_cached(cache_key)

        if cached_guild:
            return cached_guild

        guild = self.bot.get_guild(guild_id)
        if guild:
            self.set_cache(cache_key, guild)

        return guild

    async def optimized_send_message(
        self, channel: discord.TextChannel, content: str = None, **kwargs
    ) -> discord.Message:
        if not await self.check_rate_limit("send_message"):
            raise discord.HTTPException("Rate limited")

        message = await channel.send(content, **kwargs)

        cache_key = f"last_message_{channel.id}"
        self.set_cache(cache_key, message)

        return message

    async def bulk_fetch_members(
        self, guild: discord.Guild, member_ids: List[int]
    ) -> List[Optional[discord.Member]]:
        members = []

        for member_id in member_ids:
            cache_key = f"member_{guild.id}_{member_id}"
            cached_member = self.get_cached(cache_key)

            if cached_member:
                members.append(cached_member)
            else:
                try:
                    member = await guild.fetch_member(member_id)
                    if member:
                        self.set_cache(cache_key, member)
                        members.append(member)
                    else:
                        members.append(None)
                except discord.NotFound:
                    members.append(None)
                except discord.HTTPException as e:
                    if e.status == 429:
                        await asyncio.sleep(1)
                        member = await guild.fetch_member(member_id)
                        if member:
                            self.set_cache(cache_key, member)
                            members.append(member)
                        else:
                            members.append(None)
                    else:
                        members.append(None)

        return members

    def clear_cache(self, pattern: str = None) -> None:
        if pattern:
            keys_to_remove = [key for key in self.cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self.cache[key]
        else:
            self.cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        current_time = time.time()
        valid_entries = sum(
            1
            for _, (_, timestamp) in self.cache.items()
            if current_time - timestamp < self.cache_ttl
        )

        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.cache) - valid_entries,
            "cache_ttl": self.cache_ttl,
        }


class ConnectionManager:
    def __init__(self):
        self.connection_pool_size = 100
        self.max_retries = 3
        self.retry_delay = 1.0
        self.connection_timeout = 30.0

    async def execute_with_retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(
                        e.response.headers.get("Retry-After", self.retry_delay)
                    )
                    await asyncio.sleep(retry_after)
                elif e.status in [500, 502, 503, 504]:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                else:
                    raise e
            except (discord.ConnectionClosed, discord.GatewayNotFound) as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                else:
                    raise e
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise e

        raise Exception("Max retries exceeded")


class PerformanceMonitor:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.alert_threshold = 5.0

    def start_timing(self, operation: str) -> str:
        timing_id = f"{operation}_{time.time()}"
        return timing_id

    def end_timing(self, timing_id: str) -> float:
        parts = timing_id.split("_")
        operation = "_".join(parts[:-1])
        start_time = float(parts[-1])

        duration = time.time() - start_time

        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(duration)

        if duration > self.alert_threshold:
            print(f"Performance alert: {operation} took {duration:.2f}s")

        return duration

    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        stats = {}

        for operation, times in self.metrics.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "total": sum(times),
                }

        return stats

    def clear_metrics(self) -> None:
        self.metrics.clear()


api_optimizer = None
connection_manager = ConnectionManager()
performance_monitor = PerformanceMonitor()


def init_api_optimizer(bot: commands.Bot):
    global api_optimizer
    api_optimizer = APIOptimizer(bot)


def get_api_optimizer() -> APIOptimizer:
    return api_optimizer
