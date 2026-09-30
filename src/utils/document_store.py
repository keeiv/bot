"""Transactional MySQL document storage with an explicit legacy JSON backend.

MySQL failures never fall back to stale JSON. Original JSON is not modified in
MySQL mode. Paths remain distinct keys, including historical file locations.
"""

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pymysql


class StorageError(RuntimeError):
    """Storage failed; callers must not replace data with empty defaults."""


def using_mysql() -> bool:
    backend = os.getenv("STORAGE_BACKEND", "json").lower()
    if backend not in ("json", "mysql"):
        raise StorageError("Unknown STORAGE_BACKEND")
    return backend == "mysql"


def connect_mysql(database: str | None = None, dict_rows: bool = False):
    try:
        return pymysql.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3307")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=database or os.environ["MYSQL_DATABASE"],
            charset="utf8mb4",
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            cursorclass=(
                pymysql.cursors.DictCursor if dict_rows else pymysql.cursors.Cursor
            ),
            autocommit=False,
        )
    except (pymysql.MySQLError, KeyError, ValueError) as exc:
        raise StorageError(
            "MySQL connection failed; JSON fallback is disabled"
        ) from exc


def document_key(path: str | Path) -> str:
    root = Path(os.getenv("STORAGE_ROOT", str(Path.cwd()))).resolve()
    target = Path(path).resolve()
    try:
        return target.relative_to(root).as_posix()
    except ValueError as exc:
        raise StorageError("Document path is outside STORAGE_ROOT") from exc


def canonical(data: Any) -> str:
    # JSON object keys are strings; normalize before sorting and hashing so
    # integer-keyed in-memory settings survive a round-trip with the same hash.
    data = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(data: Any) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def document_exists(path: str | Path) -> bool:
    if not using_mysql():
        return Path(path).exists()
    with connect_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM documents WHERE path=%s", (document_key(path),))
            return cur.fetchone() is not None


def read_document(path: str | Path) -> Any:
    if not using_mysql():
        with open(path, encoding="utf-8-sig") as stream:
            return json.load(stream)
    with connect_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload, checksum FROM documents WHERE path=%s",
                (document_key(path),),
            )
            row = cur.fetchone()
    if row is None:
        raise FileNotFoundError(str(path))
    data = json.loads(row[0])
    if digest(data) != row[1]:
        raise StorageError("Stored document checksum mismatch")
    return data


def write_document(path: str | Path, data: Any) -> None:
    payload = canonical(data)
    if using_mysql():
        try:
            with connect_mysql() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents(path,payload,checksum) VALUES (%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE payload=VALUES(payload), checksum=VALUES(checksum)",
                        (document_key(path), payload, digest(data)),
                    )
                conn.commit()
        except pymysql.MySQLError as exc:
            raise StorageError(
                "MySQL write failed; original JSON remains unchanged"
            ) from exc
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=target.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def open_document(path, mode="r", encoding="utf-8"):
    """Compatibility stream for services while keeping all I/O centralized."""
    if mode not in ("r", "w"):
        raise ValueError("Only read/write document modes are supported")
    stream = io.StringIO(
        json.dumps(read_document(path), ensure_ascii=False) if mode == "r" else ""
    )
    try:
        yield stream
        if mode == "w":
            write_document(path, json.loads(stream.getvalue()))
    finally:
        stream.close()


def initialize_schema() -> None:
    statements = [
        "CREATE TABLE IF NOT EXISTS documents (path VARCHAR(512) COLLATE utf8mb4_bin PRIMARY KEY, payload LONGTEXT NOT NULL, checksum CHAR(64) NOT NULL, CHECK(JSON_VALID(payload))) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS migration_sources (path VARCHAR(512) COLLATE utf8mb4_bin PRIMARY KEY, source_sha256 CHAR(64) NOT NULL, content LONGBLOB NOT NULL) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS migration_state (id INT PRIMARY KEY, manifest_sha256 CHAR(64) NOT NULL, verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS samples (timestamp BIGINT PRIMARY KEY, online INT NOT NULL, latency DOUBLE) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS cache_entries (`key` VARCHAR(512) COLLATE utf8mb4_bin PRIMARY KEY, value LONGTEXT, timestamp DOUBLE, ttl DOUBLE) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS metrics (id BIGINT PRIMARY KEY AUTO_INCREMENT, metric_name TEXT, value DOUBLE, timestamp DOUBLE, metadata LONGTEXT, INDEX(timestamp)) ENGINE=InnoDB",
        "CREATE TABLE IF NOT EXISTS audit_logs (id BIGINT PRIMARY KEY AUTO_INCREMENT, action TEXT, user_id TEXT, guild_id TEXT, timestamp DOUBLE, details LONGTEXT, INDEX(timestamp)) ENGINE=InnoDB",
    ]
    with connect_mysql() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


def require_migration() -> None:
    if using_mysql():
        with connect_mysql() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM migration_state WHERE id=1")
                if cur.fetchone() is None:
                    raise StorageError("Storage migration has not been verified")
