import asyncio
import contextlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional

from src.utils.document_store import StorageError
from src.utils.document_store import using_mysql
from src.utils.mysql_compat import MySQLConnection
from src.utils.storage_worker import run_blocking


class DatabaseConnectionPool:
    def __init__(
        self, db_path: str, max_connections: int = 10, acquire_timeout: float = 5
    ) -> None:
        if max_connections < 1:
            raise ValueError("max_connections must be positive")
        self.acquire_timeout = acquire_timeout
        self._slots = asyncio.Semaphore(max_connections)
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: asyncio.Queue[sqlite3.Connection] = asyncio.Queue(
            maxsize=max_connections
        )
        self._created_connections = 0
        self._closed = False

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        if not using_mysql():
            self._initialize_database()

    def _initialize_database(self) -> None:
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

    def _create_connection(self):
        if using_mysql():
            return MySQLConnection(dict_rows=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    async def _discard_connection(self, conn):
        try:
            with contextlib.suppress(Exception):
                await run_blocking(conn.close)
        finally:
            self._created_connections -= 1

    async def get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("Database pool is closed")
        try:
            await asyncio.wait_for(self._slots.acquire(), self.acquire_timeout)
        except asyncio.TimeoutError as exc:
            raise StorageError("Database connection acquisition timed out") from exc
        conn = None
        try:
            if self._closed:
                raise RuntimeError("Database pool is closed")
            try:
                conn = self._pool.get_nowait()
            except asyncio.QueueEmpty:
                pass
            if conn is not None:
                try:
                    await run_blocking(
                        (
                            conn.ping
                            if isinstance(conn, MySQLConnection)
                            else conn.execute
                        ),
                        *(() if isinstance(conn, MySQLConnection) else ("SELECT 1",)),
                    )
                except Exception:
                    await self._discard_connection(conn)
                    conn = None
            if conn is None:
                # Retain the result on cancellation to close it before releasing capacity.
                created = []

                def create():
                    result = self._create_connection()
                    created.append(result)
                    return result

                try:
                    conn = await run_blocking(create)
                except BaseException:
                    if created:
                        with contextlib.suppress(Exception):
                            await run_blocking(created[0].close)
                    raise
                self._created_connections += 1
            if self._closed:
                raise RuntimeError("Database pool is closed")
            return conn
        except BaseException:
            try:
                if conn is not None:
                    await self._discard_connection(conn)
            finally:
                self._slots.release()
            raise

    async def return_connection(
        self, conn: sqlite3.Connection, discard: bool = False
    ) -> None:
        try:
            if self._closed or discard:
                await self._discard_connection(conn)
            else:
                self._pool.put_nowait(conn)
        finally:
            self._slots.release()

    def close(self) -> None:
        self._closed = True
        while not self._pool.empty():
            try:
                with contextlib.suppress(Exception):
                    self._pool.get_nowait().close()
            finally:
                self._created_connections -= 1


class DatabaseManager:
    def __init__(self, db_path: str = "data/storage/bot_database.db") -> None:
        self.pool = DatabaseConnectionPool(db_path)
        self._cleanup_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        await run_blocking(self.pool.close)

    @contextlib.asynccontextmanager
    async def get_connection(self) -> Any:
        conn = await self.pool.get_connection()
        discard = False
        try:
            yield conn
            await run_blocking(conn.commit)
        except BaseException:
            discard = True
            try:
                await run_blocking(conn.rollback)
            except Exception:
                pass
            raise
        finally:
            await self.pool.return_connection(conn, discard=discard)

    async def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                value_json = json.dumps(value, default=str)

                await run_blocking(
                    conn.execute,
                    """
                    INSERT OR REPLACE INTO cache_entries (key, value, timestamp, ttl)
                    VALUES (?, ?, ?, ?)
                """,
                    (key, value_json, timestamp, ttl),
                )

                await run_blocking(conn.commit)
                return True
        except Exception as e:
            print(f"[Database] Cache set error: {e}")
            return False

    async def cache_get(self, key: str) -> Optional[Any]:
        try:
            async with self.get_connection() as conn:
                cursor = await run_blocking(
                    conn.execute,
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
                    await run_blocking(
                        conn.execute, "DELETE FROM cache_entries WHERE key = ?", (key,)
                    )
                    await run_blocking(conn.commit)
                    return None

                return json.loads(row["value"])
        except Exception as e:
            print(f"[Database] Cache get error: {e}")
            return None

    async def cache_delete(self, key: str) -> bool:
        try:
            async with self.get_connection() as conn:
                await run_blocking(
                    conn.execute, "DELETE FROM cache_entries WHERE key = ?", (key,)
                )
                await run_blocking(conn.commit)
                return True
        except Exception as e:
            print(f"[Database] Cache delete error: {e}")
            return False

    async def cache_clear_pattern(self, pattern: str) -> int:
        try:
            async with self.get_connection() as conn:
                cursor = await run_blocking(
                    conn.execute,
                    """
                    DELETE FROM cache_entries WHERE key LIKE ?
                """,
                    (f"%{pattern}%",),
                )

                await run_blocking(conn.commit)
                return int(cursor.rowcount)
        except Exception as e:
            print(f"[Database] Cache clear pattern error: {e}")
            return 0

    async def store_metric(
        self, metric_name: str, value: float, metadata: Dict[Any, Any] | None = None
    ) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                metadata_json = json.dumps(metadata or {})

                await run_blocking(
                    conn.execute,
                    """
                    INSERT INTO metrics (metric_name, value, timestamp, metadata)
                    VALUES (?, ?, ?, ?)
                """,
                    (metric_name, value, timestamp, metadata_json),
                )

                await run_blocking(conn.commit)
                return True
        except Exception as e:
            print(f"[Database] Store metric error: {e}")
            return False

    async def get_metrics(
        self, metric_name: str | None = None, limit: int = 100
    ) -> List[Dict[Any, Any]]:
        try:
            async with self.get_connection() as conn:
                if metric_name:
                    cursor = await run_blocking(
                        conn.execute,
                        """
                        SELECT * FROM metrics
                        WHERE metric_name = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (metric_name, limit),
                    )
                else:
                    cursor = await run_blocking(
                        conn.execute,
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
        user_id: str | None = None,
        guild_id: str | None = None,
        details: Dict[Any, Any] | None = None,
    ) -> bool:
        try:
            async with self.get_connection() as conn:
                timestamp = time.time()
                details_json = json.dumps(details or {})

                await run_blocking(
                    conn.execute,
                    """
                    INSERT INTO audit_logs (action, user_id, guild_id, timestamp, details)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (action, user_id, guild_id, timestamp, details_json),
                )

                await run_blocking(conn.commit)
                return True
        except Exception as e:
            print(f"[Database] Audit log error: {e}")
            return False

    async def cleanup_expired_cache(self) -> int:
        try:
            async with self.get_connection() as conn:
                current_time = time.time()
                cursor = await run_blocking(
                    conn.execute,
                    """
                    DELETE FROM cache_entries
                    WHERE timestamp + ttl < ?
                """,
                    (current_time,),
                )

                await run_blocking(conn.commit)
                return int(cursor.rowcount)
        except Exception as e:
            print(f"[Database] Cleanup expired cache error: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, int]:
        try:
            async with self.get_connection() as conn:
                cursor = await run_blocking(
                    conn.execute, "SELECT COUNT(*) as total FROM cache_entries"
                )
                total = cursor.fetchone()["total"]

                cursor = await run_blocking(
                    conn.execute,
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

    async def start_cleanup_task(self, interval: int = 300) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            return

        async def cleanup_loop() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    cleaned = await self.cleanup_expired_cache()
                    if cleaned > 0:
                        print(f"[Database] Cleaned {cleaned} expired cache entries")
                except Exception as e:
                    print(f"[Database] Cleanup task error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())


database_manager: DatabaseManager | None = None


def init_database_manager() -> None:
    global database_manager
    if database_manager is None or database_manager.pool._closed:
        database_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager | None:
    return database_manager
