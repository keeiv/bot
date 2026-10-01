"""Public service health uses real observations and preserves old history."""

import asyncio
import copy
import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient
from aiohttp.test_utils import TestServer
import pytest

from src.cogs.core.dashboard_api import DashboardAPI
from src.services import dashboard_health
from src.services.dashboard_health import check_storage
from src.services.dashboard_health import StorageHealth
from src.services.dashboard_history import StatusHistory


def test_mysql_health_executes_read_only_query_and_sanitizes_errors(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)
    factory = MagicMock(return_value=connection)
    monkeypatch.setattr(dashboard_health, "connect_mysql", factory)
    result = check_storage()
    assert result["online"] is True
    assert result["backend"] == "mysql"
    cursor.execute.assert_called_once_with("SELECT 1")
    connection.commit.assert_not_called()
    factory.side_effect = RuntimeError("private password and hostname")
    failed = check_storage()
    assert failed["online"] is False
    assert set(failed) == {"online", "backend", "checkedAt"}
    assert "private" not in str(failed)


async def test_health_probe_is_coalesced_nonblocking_and_refreshes_after_expiry(
    monkeypatch,
):
    clock = [30.0]
    calls = []
    entered = threading.Event()
    release = threading.Event()

    def probe():
        calls.append(len(calls))
        entered.set()
        assert release.wait(2)
        return {"online": len(calls) == 1, "checkedAt": "2026-10-01T00:00:00Z"}

    monkeypatch.setattr(dashboard_health, "check_storage", probe)
    monkeypatch.setattr(dashboard_health.time, "monotonic", lambda: clock[0])
    health = StorageHealth()
    first = asyncio.create_task(health.read())
    second = asyncio.create_task(health.read())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(0)
        assert not first.done()  # The event loop still runs while the probe waits.
    finally:
        release.set()
    observed, duplicate = await asyncio.gather(first, second)
    assert len(calls) == 1
    observed["online"] = False
    assert duplicate["online"] is True
    clock[0] += 31
    assert (await health.read())["online"] is False
    assert len(calls) == 2


def test_history_adds_health_without_replacing_legacy_samples(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE samples(timestamp INTEGER PRIMARY KEY, online INT, latency REAL)"
        )
        connection.execute("INSERT INTO samples VALUES(6000,1,42)")
    history = StatusHistory(path)
    assert history.read(now=6000)["samples"] == [
        {"timestamp": 6000, "online": True, "latencyMs": 42, "databaseOnline": None}
    ]
    history.record(True, 20, now=6060, database_online=True)
    history.record(False, None, now=6120, database_online=False)
    restarted = StatusHistory(path).read(now=6120)["samples"]
    assert [row["databaseOnline"] for row in restarted] == [None, True, False]
    history.record(True, 10, now=6121, database_online=True)
    assert history.read(now=6180)["samples"][-1]["databaseOnline"] is True


def test_failed_health_record_rolls_back_the_heartbeat(tmp_path):
    path = tmp_path / "history.sqlite3"
    history = StatusHistory(path)
    history.record(True, 42, now=6000, database_online=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_health BEFORE INSERT ON sample_health "
            "WHEN NEW.timestamp=6060 BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        history.record(False, None, now=6060, database_online=False)
    rows = history.read(now=6120)["samples"]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == 6000
    assert rows[0]["databaseOnline"] is True


async def test_status_exposes_independent_components_without_credentials(monkeypatch):
    bot = SimpleNamespace(
        latency=0.042,
        guilds=[],
        shard_count=None,
        is_ready=lambda: True,
    )
    api = DashboardAPI(bot)
    observation = {
        "online": False,
        "backend": "mysql",
        "checkedAt": "2026-10-01T00:00:00Z",
    }
    monkeypatch.setattr(
        dashboard_health, "check_storage", lambda: copy.deepcopy(observation)
    )
    async with TestClient(TestServer(api.create_app("test-status-secret"))) as client:
        assert (await client.get("/status")).status == 401
        response = await client.get(
            "/status", headers={"Authorization": "Bearer test-status-secret"}
        )
        data = await response.json()
        assert response.status == 200
        assert data["online"] is True
        assert data["heartbeatAt"]
        assert data["heartbeatTimeoutSeconds"] == 90
        assert data["components"]["database"] == observation
        assert data["components"]["discord"]["online"] is True
        assert data["components"]["api"]["online"] is True
        assert "password" not in str(data)
        bot.is_ready = lambda: False
        offline = await (
            await client.get(
                "/status", headers={"Authorization": "Bearer test-status-secret"}
            )
        ).json()
        assert offline["online"] is False
        assert offline["components"]["api"]["online"] is True
