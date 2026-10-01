"""Copy and verify every legacy data file without deleting any source.

Run from the project root: python -m src.migrate_storage
The bot must be stopped. Conflicting destination data aborts the transaction.
"""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from dotenv import load_dotenv
import psutil

from src.utils.document_store import canonical
from src.utils.document_store import connect_mysql
from src.utils.document_store import digest
from src.utils.document_store import initialize_schema

TABLES = {
    "samples": ("timestamp", "online", "latency"),
    "sample_health": ("timestamp", "database_online"),
    "cache_entries": ("key", "value", "timestamp", "ttl"),
    "metrics": ("id", "metric_name", "value", "timestamp", "metadata"),
    "audit_logs": ("id", "action", "user_id", "guild_id", "timestamp", "details"),
}


SELECT_SQL = {
    "samples": "SELECT * FROM samples ORDER BY timestamp",
    "sample_health": "SELECT * FROM sample_health ORDER BY timestamp",
    "cache_entries": "SELECT * FROM cache_entries ORDER BY `key`",
    "metrics": "SELECT * FROM metrics ORDER BY id",
    "audit_logs": "SELECT * FROM audit_logs ORDER BY id",
}
INSERT_SQL = {
    "samples": "INSERT INTO samples(timestamp,online,latency) VALUES (%s,%s,%s)",
    "sample_health": "INSERT INTO sample_health(timestamp,database_online) VALUES (%s,%s)",
    "cache_entries": "INSERT INTO cache_entries(`key`,value,timestamp,ttl) VALUES (%s,%s,%s,%s)",
    "metrics": "INSERT INTO metrics(id,metric_name,value,timestamp,metadata) VALUES (%s,%s,%s,%s,%s)",
    "audit_logs": "INSERT INTO audit_logs(id,action,user_id,guild_id,timestamp,details) VALUES (%s,%s,%s,%s,%s,%s)",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; manual review required")
        result[key] = value
    return result


def stopped_bot(root):
    lock = root / "bot.lock"
    if lock.exists():
        pid = int(lock.read_text().strip())
        if psutil.pid_exists(pid):
            raise RuntimeError(
                "Migration blocked by a running bot instance; data unchanged"
            )


def migrate(root: Path, backup: Path):
    stopped_bot(root)
    paths = sorted(
        p
        for p in (root / "data").rglob("*")
        if p.is_file() and p.suffix in (".json", ".db", ".sqlite3")
    )
    if not paths:
        raise RuntimeError("No legacy data found")
    backup.mkdir(parents=True, exist_ok=False)
    if (root / ".env").exists():
        shutil.copy2(root / ".env", backup / ".env")
    documents, tables, archives, original_hashes = {}, {}, {}, {}
    for path in paths:
        key = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        original_hashes[key] = hashlib.sha256(raw).hexdigest()
        destination = backup / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        if path.suffix == ".json":
            documents[key] = json.loads(
                raw.decode("utf-8-sig"), object_pairs_hook=unique_object
            )
            canonical(documents[key])  # Reject non-finite numbers before writes.
        else:
            with sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True
            ) as source:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite integrity check failed: " + key)
                with sqlite3.connect(destination) as copy:
                    source.backup(copy)
                for (table,) in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ):
                    if table == "sqlite_sequence":
                        continue
                    if table not in TABLES or table in tables:
                        raise RuntimeError(
                            "Unexpected or duplicate SQLite table: " + table
                        )
                    columns = tuple(
                        r[1] for r in source.execute(f"PRAGMA table_info(`{table}`)")
                    )
                    if columns != TABLES[table]:
                        raise RuntimeError("Unexpected SQLite columns: " + table)
                    tables[table] = source.execute(SELECT_SQL[table]).fetchall()
        archives[key] = destination.read_bytes()

    initialize_schema()
    report = {"documents": {}, "tables": {}, "source_sha256": original_hashes}
    with connect_mysql() as connection:
        try:
            with connection.cursor() as cursor:
                for key, raw in archives.items():
                    sha = hashlib.sha256(raw).hexdigest()
                    cursor.execute(
                        "SELECT source_sha256 FROM migration_sources WHERE path=%s",
                        (key,),
                    )
                    previous = cursor.fetchone()
                    if previous and previous[0] != sha:
                        raise RuntimeError("Previous migration source differs: " + key)
                    if not previous:
                        cursor.execute(
                            "INSERT INTO migration_sources VALUES (%s,%s,%s)",
                            (key, sha, raw),
                        )
                    cursor.execute(
                        "SELECT content FROM migration_sources WHERE path=%s", (key,)
                    )
                    if hashlib.sha256(cursor.fetchone()[0]).hexdigest() != sha:
                        raise RuntimeError("Source archive verification failed: " + key)
                for key, data in documents.items():
                    sha = digest(data)
                    cursor.execute(
                        "SELECT payload FROM documents WHERE path=%s", (key,)
                    )
                    previous = cursor.fetchone()
                    if previous and digest(json.loads(previous[0])) != sha:
                        raise RuntimeError(
                            "Destination document differs; refusing overwrite: " + key
                        )
                    if not previous:
                        cursor.execute(
                            "INSERT INTO documents VALUES (%s,%s,%s)",
                            (key, canonical(data), sha),
                        )
                    cursor.execute(
                        "SELECT payload,checksum FROM documents WHERE path=%s", (key,)
                    )
                    payload, checksum = cursor.fetchone()
                    if digest(json.loads(payload)) != sha or checksum != sha:
                        raise RuntimeError("Document verification failed: " + key)
                    report["documents"][key] = {
                        "checksum": sha,
                        "entries": len(data) if isinstance(data, (list, dict)) else 1,
                    }
                for table, rows in tables.items():
                    cursor.execute(SELECT_SQL[table])
                    existing = cursor.fetchall()
                    if existing and canonical(existing) != canonical(rows):
                        raise RuntimeError("Destination SQL table differs: " + table)
                    if not existing and rows:
                        for index in range(0, len(rows), 1000):
                            cursor.executemany(
                                INSERT_SQL[table],
                                rows[index : index + 1000],
                            )
                    cursor.execute(SELECT_SQL[table])
                    restored = cursor.fetchall()
                    if canonical(restored) != canonical(rows):
                        raise RuntimeError("SQL row verification failed: " + table)
                    report["tables"][table] = {
                        "rows": len(rows),
                        "checksum": digest(rows),
                    }
                stopped_bot(root)
                for path in paths:
                    key = path.relative_to(root).as_posix()
                    if (
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        != original_hashes[key]
                    ):
                        raise RuntimeError("Source changed during migration: " + key)
                cursor.execute(
                    "INSERT INTO migration_state(id,manifest_sha256) VALUES (1,%s) ON DUPLICATE KEY UPDATE manifest_sha256=VALUES(manifest_sha256), verified_at=CURRENT_TIMESTAMP",
                    (digest(report),),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    (backup / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main():
    load_dotenv(".env")
    root = Path.cwd()
    location = Path(os.environ["LOCALAPPDATA"]) / "NewBotMySQL" / "backups"
    backup = location / datetime.now().strftime("%Y%m%d-%H%M%S")
    report = migrate(root, backup)
    print("Verified JSON documents:", len(report["documents"]))
    print("Verified SQL rows:", {k: v["rows"] for k, v in report["tables"].items()})
    print("Backup:", backup)
    print(
        "Original JSON and SQLite files have been preserved. Backend not switched automatically."
    )


if __name__ == "__main__":
    main()
