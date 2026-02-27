import asyncio
import contextlib
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Union


class DatabaseConnectionPool:
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created_connections = 0

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _initialize_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp REAL,
                    ttl REAL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    value REAL,
                    timestamp REAL,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    user_id TEXT,
                    guild_id TEXT,
                    timestamp REAL,
                    details TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_timestamp ON cache_entries(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)
            """)

            conn.commit()

    async def get_connection(self) -> sqlite3.Connection:
        try:
            conn = self._pool.get_nowait()
            return conn
        except asyncio.QueueEmpty:
            with self._lock:
                if self._created_connections < self.max_connections:
                    self._created_connections += 1
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    return conn
                else:
                    conn = await self._pool.get()
                    return conn

    async def return_connection(self, conn: sqlite3.Connection):
        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            conn.close()
            with self._lock:
                self._created_connections -= 1


class DatabaseManager:
    def __init__(self, db_path: str = "data/storage/bot_database.db"):
        self.pool = DatabaseConnectionPool(db_path)
        self._cleanup_task = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup_task:
            self._cleanup_task.cancel()

    @contextlib.asynccontextmanager
    async def get_connection(self):
        conn = await self.pool.get_connection()
        try:
            yield conn
        finally:
            await self.pool.return_connection(conn)

    async def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                value_json = json.dumps(value, default=str)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries (key, value, timestamp, ttl)
                    VALUES (?, ?, ?, ?)
                """,
                    (key, value_json, timestamp, ttl),
                )

                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Cache set error: {e}")
            return False

    async def cache_get(self, key: str) -> Optional[Any]:
        try:
            async with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT value, timestamp, ttl FROM cache_entries
                    WHERE key = ?
                """,
                    (key,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                current_time = time.time()
                if current_time - row["timestamp"] > row["ttl"]:
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return None

                return json.loads(row["value"])
        except Exception as e:
            print(f"[Database] Cache get error: {e}")
            return None

    async def cache_delete(self, key: str) -> bool:
        try:
            async with self.get_connection() as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Cache delete error: {e}")
            return False

    async def cache_clear_pattern(self, pattern: str) -> int:
        try:
            async with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM cache_entries WHERE key LIKE ?
                """,
                    (f"%{pattern}%",),
                )

                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"[Database] Cache clear pattern error: {e}")
            return 0

    async def store_metric(
        self, metric_name: str, value: float, metadata: Dict = None
    ) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                metadata_json = json.dumps(metadata or {})

                conn.execute(
                    """
                    INSERT INTO metrics (metric_name, value, timestamp, metadata)
                    VALUES (?, ?, ?, ?)
                """,
                    (metric_name, value, timestamp, metadata_json),
                )

                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Store metric error: {e}")
            return False

    async def get_metrics(
        self, metric_name: str = None, limit: int = 100
    ) -> List[Dict]:
        try:
            async with self.get_connection() as conn:
                if metric_name:
                    cursor = conn.execute(
                        """
                        SELECT * FROM metrics
                        WHERE metric_name = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (metric_name, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM metrics
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (limit,),
                    )

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[Database] Get metrics error: {e}")
            return []

    async def log_audit(
        self,
        action: str,
        user_id: str = None,
        guild_id: str = None,
        details: Dict = None,
    ) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                details_json = json.dumps(details or {})

                conn.execute(
                    """
                    INSERT INTO audit_logs (action, user_id, guild_id, timestamp, details)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (action, user_id, guild_id, timestamp, details_json),
                )

                conn.commit()
                return True
        except Exception as e:
            print(f"[Database] Audit log error: {e}")
            return False

    async def cleanup_expired_cache(self) -> int:
        try:
            async with self.get_connection() as conn:
                current_time = time.time()
                cursor = conn.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE timestamp + ttl < ?
                """,
                    (current_time,),
                )

                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"[Database] Cleanup expired cache error: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, int]:
        try:
            async with self.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as total FROM cache_entries")
                total = cursor.fetchone()["total"]

                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as expired FROM cache_entries
                    WHERE timestamp + ttl < ?
                """,
                    (time.time(),),
                )
                expired = cursor.fetchone()["expired"]

                return {
                    "total_entries": total,
                    "expired_entries": expired,
                    "valid_entries": total - expired,
                }
        except Exception as e:
            print(f"[Database] Get cache stats error: {e}")
            return {"total_entries": 0, "expired_entries": 0, "valid_entries": 0}

    async def start_cleanup_task(self, interval: int = 300):
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    cleaned = await self.cleanup_expired_cache()
                    if cleaned > 0:
                        print(f"[Database] Cleaned {cleaned} expired cache entries")
                except Exception as e:
                    print(f"[Database] Cleanup task error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())


database_manager = None


def init_database_manager():
    global database_manager
    database_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager:
    return database_manager
