import asyncio
from dataclasses import dataclass
import hashlib
import socket
import ssl
import struct
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import aiohttp


@dataclass
class NetworkConfig:
    max_connections: int = 100
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    use_http2: bool = True
    verify_ssl: bool = True
    dns_cache_ttl: int = 300
    connection_pool_size: int = 10


class DNSCache:
    def __init__(self, ttl: int = 300):
        self._cache: Dict[str, Dict] = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def resolve(self, hostname: str) -> List[str]:
        current_time = time.time()

        async with self._lock:
            if hostname in self._cache:
                entry = self._cache[hostname]
                if current_time - entry["timestamp"] < self._ttl:
                    return entry["ips"]

        try:
            loop = asyncio.get_event_loop()
            ips = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
            ip_addresses = [info[4][0] for info in ips]

            async with self._lock:
                self._cache[hostname] = {"ips": ip_addresses, "timestamp": current_time}

            return ip_addresses
        except Exception as e:
            print(f"[DNS Cache] Error resolving {hostname}: {e}")
            return []

    def clear(self, hostname: str = None):
        if hostname:
            self._cache.pop(hostname, None)
        else:
            self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


class ConnectionPool:
    def __init__(self, config: NetworkConfig):
        self.config = config
        self._pools: Dict[str, aiohttp.TCPConnector] = {}
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, base_url: str) -> aiohttp.ClientSession:
        parsed = urlparse(base_url)
        key = f"{parsed.scheme}://{parsed.netloc}"

        async with self._lock:
            if key not in self._sessions or self._sessions[key].closed:
                if key in self._pools:
                    await self._pools[key].close()

                connector = aiohttp.TCPConnector(
                    limit=self.config.max_connections,
                    limit_per_host=self.config.connection_pool_size,
                    ttl_dns_cache=self.config.dns_cache_ttl,
                    use_dns_cache=True,
                    ssl=self.config.verify_ssl,
                    enable_cleanup_closed=True,
                )

                self._pools[key] = connector

                timeout = aiohttp.ClientTimeout(
                    total=self.config.read_timeout, connect=self.config.connect_timeout
                )

                headers = {
                    "User-Agent": "Discord-Bot/1.0 (Network-Optimized)",
                    "Connection": "keep-alive",
                    "Accept-Encoding": "gzip, deflate",
                }

                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=headers,
                    version=(
                        aiohttp.HttpVersion11
                        if not self.config.use_http2
                        else aiohttp.HttpVersion20
                    ),
                )

                self._sessions[key] = session

            return self._sessions[key]

    async def close_all(self):
        async with self._lock:
            for session in self._sessions.values():
                if not session.closed:
                    await session.close()

            for pool in self._pools.values():
                await pool.close()

            self._sessions.clear()
            self._pools.clear()


class NetworkOptimizer:
    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()
        self.dns_cache = DNSCache(self.config.dns_cache_ttl)
        self.connection_pool = ConnectionPool(self.config)
        self._request_metrics: Dict[str, List[float]] = {}
        self._active_requests: Dict[str, int] = {}

    async def make_request(
        self,
        method: str,
        url: str,
        headers: Dict = None,
        params: Dict = None,
        data: Any = None,
        json_data: Dict = None,
        **kwargs,
    ) -> Dict:
        start_time = time.time()
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc

        self._active_requests[hostname] = self._active_requests.get(hostname, 0) + 1

        try:
            session = await self.connection_pool.get_session(url)

            for attempt in range(self.config.max_retries):
                try:
                    async with session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        data=data,
                        json=json_data,
                        **kwargs,
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            self._record_metric(hostname, time.time() - start_time)
                            return result
                        elif response.status in [429, 502, 503, 504]:
                            retry_after = float(
                                response.headers.get(
                                    "Retry-After", self.config.retry_delay
                                )
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP {response.status}: {error_text}")

                except asyncio.TimeoutError:
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2**attempt))
                        continue
                    else:
                        raise Exception("Request timeout after retries")

                except aiohttp.ClientError as e:
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2**attempt))
                        continue
                    else:
                        raise Exception(f"Network error: {e}")

            raise Exception(f"Max retries exceeded for {url}")

        finally:
            self._active_requests[hostname] = max(
                0, self._active_requests.get(hostname, 0) - 1
            )

    async def make_batch_requests(self, requests: List[Dict]) -> List[Dict]:
        tasks = []
        for req in requests:
            task = self.make_request(
                method=req.get("method", "GET"),
                url=req["url"],
                headers=req.get("headers"),
                params=req.get("params"),
                data=req.get("data"),
                json_data=req.get("json"),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def _record_metric(self, hostname: str, response_time: float):
        if hostname not in self._request_metrics:
            self._request_metrics[hostname] = []

        self._request_metrics[hostname].append(response_time)

        if len(self._request_metrics[hostname]) > 100:
            self._request_metrics[hostname] = self._request_metrics[hostname][-50:]

    def get_network_stats(self) -> Dict[str, Any]:
        stats = {
            "active_requests": dict(self._active_requests),
            "dns_cache_size": self.dns_cache.size(),
            "response_times": {},
        }

        for hostname, times in self._request_metrics.items():
            if times:
                stats["response_times"][hostname] = {
                    "count": len(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "last_10_avg": sum(times[-10:]) / min(10, len(times)),
                }

        return stats

    async def test_connectivity(self, urls: List[str] = None) -> Dict[str, Dict]:
        if urls is None:
            urls = [
                "https://httpbin.org/get",
                "https://api.github.com/rate_limit",
                "https://discord.com/api/v10/gateway",
            ]

        results = {}

        for url in urls:
            try:
                start_time = time.time()
                await self.make_request("GET", url)
                response_time = time.time() - start_time

                results[url] = {"status": "success", "response_time": response_time}
            except Exception as e:
                results[url] = {"status": "failed", "error": str(e)}

        return results

    async def optimize_connection(self, hostname: str) -> Dict[str, Any]:
        try:
            ips = await self.dns_cache.resolve(hostname)

            if not ips:
                return {"status": "failed", "error": "DNS resolution failed"}

            fastest_ip = None
            fastest_time = float("inf")

            for ip in ips[:5]:
                try:
                    start_time = time.time()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5.0)
                    result = sock.connect_ex((ip, 443))
                    sock.close()

                    if result == 0:
                        connect_time = time.time() - start_time
                        if connect_time < fastest_time:
                            fastest_time = connect_time
                            fastest_ip = ip

                except Exception:
                    continue

            if fastest_ip:
                return {
                    "status": "success",
                    "fastest_ip": fastest_ip,
                    "connect_time": fastest_time,
                    "all_ips": ips,
                }
            else:
                return {"status": "failed", "error": "No working IP found"}

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def clear_caches(self):
        self.dns_cache.clear()
        self._request_metrics.clear()

    async def close(self):
        await self.connection_pool.close_all()


class NetworkDiagnostics:
    def __init__(self, optimizer: NetworkOptimizer):
        self.optimizer = optimizer

    async def run_full_diagnostics(self) -> Dict[str, Any]:
        diagnostics = {
            "timestamp": time.time(),
            "network_stats": self.optimizer.get_network_stats(),
            "connectivity_test": await self.optimizer.test_connectivity(),
            "dns_resolution": {},
            "connection_optimization": {},
        }

        test_hosts = ["api.github.com", "discord.com", "httpbin.org"]

        for host in test_hosts:
            dns_result = await self.optimizer.dns_cache.resolve(host)
            diagnostics["dns_resolution"][host] = {
                "ips": dns_result,
                "count": len(dns_result),
            }

            opt_result = await self.optimizer.optimize_connection(host)
            diagnostics["connection_optimization"][host] = opt_result

        return diagnostics


network_optimizer = None


def init_network_optimizer(config: NetworkConfig = None):
    global network_optimizer
    network_optimizer = NetworkOptimizer(config)


def get_network_optimizer() -> NetworkOptimizer:
    return network_optimizer
