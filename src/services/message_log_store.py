"""The message log as rows: one per kept message, one per edit.

The log used to be one JSON document that every new message rewrote whole. Here
each message is a row and each edit is a row of its own, so recording an edit is
an insert, not a rewrite of every server's history. The same SQL runs on SQLite
(data/storage/message_log.sqlite3) in JSON mode and on MySQL in MySQL mode.

The first time a store opens, records from the old JSON document are copied in
once; the document itself is left as it was.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator, Optional

from src.utils.document_store import read_document
from src.utils.document_store import using_mysql
from src.utils.mysql_compat import MySQLConnection

LEGACY_FILE = "data/logs/messages/message_log.json"
SQLITE_FILE = "data/storage/message_log.sqlite3"

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS message_log (guild_id BIGINT NOT NULL, message_id BIGINT NOT NULL, channel_id BIGINT NOT NULL, author_id BIGINT NOT NULL, original_content TEXT NOT NULL, attachments TEXT NOT NULL, created_at VARCHAR(40) NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, deleted_at VARCHAR(40), last_edited_at VARCHAR(40), extra TEXT, PRIMARY KEY (guild_id, message_id))",
    "CREATE TABLE IF NOT EXISTS message_edits (guild_id BIGINT NOT NULL, message_id BIGINT NOT NULL, seq INTEGER NOT NULL, content TEXT NOT NULL, edited_at VARCHAR(40) NOT NULL, PRIMARY KEY (guild_id, message_id, seq))",
    "CREATE TABLE IF NOT EXISTS message_log_meta (name VARCHAR(64) PRIMARY KEY, value TEXT NOT NULL)",
)
# Column order as created above; the storage migrator checks SQLite files against it.
COLUMNS = {
    "message_log": (
        "guild_id",
        "message_id",
        "channel_id",
        "author_id",
        "original_content",
        "attachments",
        "created_at",
        "deleted",
        "deleted_at",
        "last_edited_at",
        "extra",
    ),
    "message_edits": ("guild_id", "message_id", "seq", "content", "edited_at"),
    "message_log_meta": ("name", "value"),
}
_KNOWN = {
    "message_id",
    "guild_id",
    "channel_id",
    "author_id",
    "original_content",
    "edit_history",
    "deleted",
    "deleted_at",
    "attachments",
    "created_at",
    "last_edited_at",
}
_LEGACY_MARK = "legacy_json_imported"
_ready: set[str] = set()
_ready_lock = threading.Lock()


def mysql_schema() -> tuple[str, ...]:
    return tuple(f"{sql} ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" for sql in SCHEMA)


class MessageLogStore:
    """Row storage for the message log. Callers hold their own lock for ordering."""

    def __init__(self) -> None:
        self.mysql = using_mysql()
        root = Path(os.getenv("STORAGE_ROOT", str(Path.cwd()))).resolve()
        self.path = root / SQLITE_FILE
        self._key = "mysql" if self.mysql else str(self.path)

    # ── Connections ───────────────────────────────────────────────────

    def _connect(self) -> Any:
        if self.mysql:
            return MySQLConnection()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path, timeout=10)

    @contextmanager
    def transaction(self, write: bool = False) -> Iterator[Any]:
        """One transaction; with `write`, writers queue instead of interleaving."""
        self._ensure()
        db = self._connect()
        try:
            if write and not self.mysql:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            try:
                db.rollback()
            except Exception:
                pass  # the error that brought us here is the one to report
            raise
        finally:
            db.close()

    def _ensure(self) -> None:
        if self._key in _ready:
            return
        with _ready_lock:
            if self._key in _ready:
                return
            db = self._connect()
            try:
                if not self.mysql:
                    db.execute("BEGIN IMMEDIATE")
                for sql in mysql_schema() if self.mysql else SCHEMA:
                    db.execute(sql)
                self._import_legacy(db)
                db.commit()
            except BaseException:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise
            finally:
                db.close()
            _ready.add(self._key)

    def _import_legacy(self, db: Any) -> None:
        if db.execute(
            "SELECT value FROM message_log_meta WHERE name=?", (_LEGACY_MARK,)
        ).fetchone():
            return
        try:
            legacy = read_document(LEGACY_FILE)
        except FileNotFoundError:
            legacy = {}
        if not isinstance(legacy, dict):
            raise TypeError("Message log must be an object")
        ignore = "INSERT IGNORE" if self.mysql else "INSERT OR IGNORE"
        imported = 0
        for record in legacy.values():
            if not isinstance(record, dict):
                continue
            try:
                guild_id, message_id = int(record["guild_id"]), int(
                    record["message_id"]
                )
            except (KeyError, TypeError, ValueError):
                continue
            extra = {key: value for key, value in record.items() if key not in _KNOWN}
            db.execute(
                f"{ignore} INTO message_log (guild_id, message_id, channel_id, author_id, original_content, attachments, created_at, deleted, deleted_at, last_edited_at, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    guild_id,
                    message_id,
                    int(record.get("channel_id") or 0),
                    int(record.get("author_id") or 0),
                    str(record.get("original_content") or ""),
                    json.dumps(record.get("attachments") or [], ensure_ascii=False),
                    str(record.get("created_at") or ""),
                    1 if record.get("deleted") else 0,
                    record.get("deleted_at"),
                    record.get("last_edited_at"),
                    json.dumps(extra, ensure_ascii=False) if extra else None,
                ),
            )
            for seq, content in enumerate(record.get("edit_history") or [], start=1):
                db.execute(
                    f"{ignore} INTO message_edits (guild_id, message_id, seq, content, edited_at) VALUES (?,?,?,?,?)",
                    (
                        guild_id,
                        message_id,
                        seq,
                        str(content),
                        str(
                            record.get("last_edited_at")
                            or record.get("created_at")
                            or ""
                        ),
                    ),
                )
            imported += 1
        db.execute(
            f"{ignore} INTO message_log_meta (name, value) VALUES (?, ?)",
            (_LEGACY_MARK, str(imported)),
        )

    # ── Records ───────────────────────────────────────────────────────

    def insert(self, db: Any, record: dict[str, Any]) -> bool:
        """Add a record unless one exists; return whether it was added."""
        ignore = "INSERT IGNORE" if self.mysql else "INSERT OR IGNORE"
        result = db.execute(
            f"{ignore} INTO message_log (guild_id, message_id, channel_id, author_id, original_content, attachments, created_at, deleted) VALUES (?,?,?,?,?,?,?,0)",
            (
                record["guild_id"],
                record["message_id"],
                record["channel_id"],
                record["author_id"],
                record["original_content"],
                json.dumps(record["attachments"], ensure_ascii=False),
                record["created_at"],
            ),
        )
        return bool(result.rowcount)

    def lock_row(self, db: Any, guild_id: int, message_id: int) -> bool:
        """Whether the record exists; on MySQL its row stays locked until commit."""
        suffix = " FOR UPDATE" if self.mysql else ""
        row = db.execute(
            # The suffix is one of two fixed strings; the ids are bound.
            f"SELECT 1 FROM message_log WHERE guild_id=? AND message_id=?{suffix}",  # nosec B608
            (guild_id, message_id),
        ).fetchone()
        return row is not None

    def append_edit(
        self, db: Any, guild_id: int, message_id: int, content: str, at: str
    ) -> None:
        row = db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM message_edits WHERE guild_id=? AND message_id=?",
            (guild_id, message_id),
        ).fetchone()
        db.execute(
            "INSERT INTO message_edits (guild_id, message_id, seq, content, edited_at) VALUES (?,?,?,?,?)",
            (guild_id, message_id, int(row[0]) + 1, content, at),
        )
        db.execute(
            "UPDATE message_log SET last_edited_at=? WHERE guild_id=? AND message_id=?",
            (at, guild_id, message_id),
        )

    def mark_deleted(self, db: Any, guild_id: int, message_id: int, at: str) -> bool:
        result = db.execute(
            "UPDATE message_log SET deleted=1, deleted_at=? WHERE guild_id=? AND message_id=?",
            (at, guild_id, message_id),
        )
        return bool(result.rowcount)

    def read(self, db: Any, guild_id: int, message_id: int) -> Optional[dict[str, Any]]:
        row = db.execute(
            "SELECT guild_id, message_id, channel_id, author_id, original_content, attachments, created_at, deleted, deleted_at, last_edited_at, extra FROM message_log WHERE guild_id=? AND message_id=?",
            (guild_id, message_id),
        ).fetchone()
        if row is None:
            return None
        edits = db.execute(
            "SELECT content FROM message_edits WHERE guild_id=? AND message_id=? ORDER BY seq",
            (guild_id, message_id),
        ).fetchall()
        record: dict[str, Any] = json.loads(row[10]) if row[10] else {}
        record.update(
            {
                "message_id": int(row[1]),
                "guild_id": int(row[0]),
                "channel_id": int(row[2]),
                "author_id": int(row[3]),
                "original_content": row[4],
                "edit_history": [edit[0] for edit in edits],
                "deleted": bool(row[7]),
                "attachments": json.loads(row[5]),
                "created_at": row[6],
            }
        )
        if row[8]:
            record["deleted_at"] = row[8]
        if row[9]:
            record["last_edited_at"] = row[9]
        return record

    def expired(
        self, db: Any, cutoff: str, logging: list[int]
    ) -> list[tuple[int, int]]:
        """Records older than `cutoff`, or from servers not in `logging`."""
        if logging:
            marks = ",".join("?" for _ in logging)
            # Only placeholders are joined in; the server ids are bound.
            sql = f"SELECT guild_id, message_id FROM message_log WHERE created_at < ? OR guild_id NOT IN ({marks})"  # nosec B608
            rows = db.execute(sql, (cutoff, *logging)).fetchall()
        else:
            rows = db.execute("SELECT guild_id, message_id FROM message_log").fetchall()
        return [(int(row[0]), int(row[1])) for row in rows]

    def remove(self, db: Any, keys: list[tuple[int, int]]) -> None:
        for guild_id, message_id in keys:
            db.execute(
                "DELETE FROM message_edits WHERE guild_id=? AND message_id=?",
                (guild_id, message_id),
            )
            db.execute(
                "DELETE FROM message_log WHERE guild_id=? AND message_id=?",
                (guild_id, message_id),
            )


def forget_ready() -> None:
    """Tests that swap STORAGE_ROOT or the backend start from a fresh check."""
    with _ready_lock:
        _ready.clear()
