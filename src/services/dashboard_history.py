from src.utils.document_store import using_mysql
from src.utils.mysql_compat import MySQLConnection

"""Bounded, persistent observations; missing samples are never counted as uptime."""

from pathlib import Path
import sqlite3
import time


class StatusHistory:
    def __init__(self, path="data/storage/dashboard_history.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            if not using_mysql():
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS samples "
                    "(timestamp INTEGER PRIMARY KEY, online INTEGER NOT NULL, latency REAL)"
                )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sample_health "
                "(timestamp BIGINT PRIMARY KEY, database_online INTEGER)"
            )

    def connect(self):
        if using_mysql():
            return MySQLConnection()
        return sqlite3.connect(self.path, timeout=5)

    def record(self, online, latency, now=None, database_online=None):
        now = int(time.time() if now is None else now)
        timestamp = now // 60 * 60
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO samples VALUES (?, ?, ?)",
                (timestamp, int(online), latency if online else None),
            )
            connection.execute(
                "INSERT OR REPLACE INTO sample_health VALUES (?, ?)",
                (
                    timestamp,
                    None if database_online is None else int(database_online),
                ),
            )
            connection.execute(
                "DELETE FROM samples WHERE timestamp < ?", (now - 604800,)
            )
            connection.execute(
                "DELETE FROM sample_health WHERE timestamp < ?", (now - 604800,)
            )

    def read(self, hours=24, now=None):
        now = int(time.time() if now is None else now)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT s.timestamp, s.online, s.latency, h.database_online "
                "FROM samples s LEFT JOIN sample_health h ON h.timestamp=s.timestamp "
                "WHERE s.timestamp >= ? AND s.timestamp <= ? ORDER BY s.timestamp",
                (now - hours * 3600, now),
            ).fetchall()
        return {
            "samples": [
                {
                    "timestamp": row[0],
                    "online": bool(row[1]),
                    "latencyMs": row[2],
                    "databaseOnline": None if row[3] is None else bool(row[3]),
                }
                for row in rows
            ],
            "intervalSeconds": 60,
            "storageBackend": "mysql" if using_mysql() else "json",
            "retentionDays": 7,
            "from": now - hours * 3600,
            "to": now,
        }
