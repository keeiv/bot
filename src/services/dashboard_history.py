"""Bounded, persistent observations; missing samples are never counted as uptime."""

from pathlib import Path
import sqlite3
import time


class StatusHistory:
    def __init__(self, path="data/storage/dashboard_history.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS samples "
                "(timestamp INTEGER PRIMARY KEY, online INTEGER NOT NULL, latency REAL)"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def record(self, online, latency, now=None):
        now = int(time.time() if now is None else now)
        timestamp = now // 60 * 60
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO samples VALUES (?, ?, ?)",
                (timestamp, int(online), latency if online else None),
            )
            connection.execute(
                "DELETE FROM samples WHERE timestamp < ?", (now - 604800,)
            )

    def read(self, hours=24, now=None):
        now = int(time.time() if now is None else now)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT timestamp, online, latency FROM samples "
                "WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
                (now - hours * 3600, now),
            ).fetchall()
        return {
            "samples": [
                {"timestamp": row[0], "online": bool(row[1]), "latencyMs": row[2]}
                for row in rows
            ],
            "intervalSeconds": 60,
            "retentionDays": 7,
            "from": now - hours * 3600,
            "to": now,
        }
