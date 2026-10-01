"""Opt-in integration test; requires a dedicated empty *_test database."""

import hashlib
import json
import os
import sqlite3

import pytest

from src.migrate_storage import migrate
from src.services.dashboard_history import StatusHistory
from src.services.osu_service import OsuService
from src.utils.database_manager import DatabaseManager
from src.utils.document_store import read_document
from src.utils.document_store import require_migration
from src.utils.document_store import write_document


@pytest.mark.skipif(
    os.getenv("MYSQL_INTEGRATION_TEST") != "1",
    reason="Requires isolated MySQL test database",
)
async def test_lossless_migration_and_live_storage(tmp_path, monkeypatch):
    database = os.environ.get("MYSQL_TEST_DATABASE", "")
    assert database.endswith("_test"), "Never run against production"
    monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    storage = tmp_path / "data/storage"
    storage.mkdir(parents=True)
    source = storage / "osu_links.json"
    source.write_text(
        json.dumps({"42": "中文 🎵", "large": 1461349028263497969}, ensure_ascii=False),
        encoding="utf-8",
    )
    original = source.read_bytes()
    legacy = DatabaseManager(str(storage / "bot_database.db"))
    await legacy.store_metric("migration-test", 1.25, {"text": "繁體中文"})
    await legacy.cache_set("sample", {"nested": [1, None, "🎵"]}, ttl=600)
    await legacy.log_audit("test", "1461349028263497969", "42", {"preserved": True})
    await legacy.close()
    history = StatusHistory(storage / "dashboard_history.sqlite3")
    history.record(True, 12.5, now=6000, database_online=True)
    report = migrate(tmp_path, tmp_path / "backup-one")
    assert len(report["documents"]) == 1
    assert report["tables"]["metrics"]["rows"] == 1
    assert report["tables"]["audit_logs"]["rows"] == 1
    # Idempotent re-run must not duplicate documents, metrics or history.
    repeated = migrate(tmp_path, tmp_path / "backup-two")
    assert report == repeated
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    require_migration()
    assert read_document(source)["large"] == 1461349028263497969
    osu = OsuService()
    assert osu.get_bound_username(42) == "中文 🎵"
    osu.bind(99, "new binding")
    assert OsuService().get_bound_username(99) == "new binding"
    assert source.read_bytes() == original
    # A stale source must not overwrite newer MySQL writes.
    with pytest.raises(RuntimeError, match="refusing overwrite"):
        migrate(tmp_path, tmp_path / "backup-three")
    assert read_document(source)["99"] == "new binding"
    history = StatusHistory(storage / "dashboard_history.sqlite3")
    assert len(history.read(now=6000)["samples"]) == 1
    assert history.read(now=6000)["samples"][0]["databaseOnline"] is True
    before = hashlib.sha256(
        (storage / "dashboard_history.sqlite3").read_bytes()
    ).hexdigest()
    history.record(False, None, now=6060, database_online=False)
    assert len(history.read(now=6060)["samples"]) == 2
    assert history.read(now=6060)["samples"][-1]["databaseOnline"] is False
    from src.services.dashboard_health import check_storage

    assert check_storage()["online"] is True
    assert (
        hashlib.sha256((storage / "dashboard_history.sqlite3").read_bytes()).hexdigest()
        == before
    )
    async with DatabaseManager() as manager:
        assert await manager.cache_get("sample") == {"nested": [1, None, "🎵"]}
        assert await manager.store_metric("mysql-test", 2.5)
        assert len(await manager.get_metrics()) == 2
        assert await manager.log_audit("mysql-test", "42")
        assert await manager.cache_set("new", {"preserved": True})
        assert await manager.cache_get("new") == {"preserved": True}
    write_document("data/new.json", {"list": ["a", "b"], "null": None})
    assert not (tmp_path / "data/new.json").exists()
    assert read_document("data/new.json")["list"] == ["a", "b"]
    with sqlite3.connect(storage / "bot_database.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 1


def test_json_writer_exception_does_not_truncate_source(tmp_path):
    from src.utils.document_store import open_document

    path = tmp_path / "existing.json"
    path.write_text('{"safe":true}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        with open_document(path, "w") as stream:
            stream.write('{"partial":')
            raise RuntimeError("interrupted")
    assert json.loads(path.read_text()) == {"safe": True}


def test_numeric_document_keys_have_stable_checksum():
    from src.utils.document_store import canonical
    from src.utils.document_store import digest

    data = {20: {100: "large"}, 3: "small"}
    assert digest(data) == digest(json.loads(canonical(data)))
