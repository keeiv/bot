"""Storage failure, cancellation and moderation authorization regressions."""

import asyncio
import copy
import os
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pytest

from src.services.genshin_service import GenshinService
from src.services.osu_service import OsuService
from src.services.report_service import ReportService
from src.utils.database_manager import DatabaseConnectionPool
from src.utils.database_manager import DatabaseManager
from src.utils.document_store import StorageError
from src.utils.storage_worker import run_blocking
from src.utils.storage_worker import run_storage


async def test_failed_creation_does_not_exhaust_pool(tmp_path, monkeypatch):
    pool = DatabaseConnectionPool(str(tmp_path / "pool.db"), max_connections=1)
    factory = pool._create_connection

    def fail():
        raise StorageError("offline")

    monkeypatch.setattr(pool, "_create_connection", fail)
    for _ in range(3):
        with pytest.raises(StorageError, match="offline"):
            await pool.get_connection()
        assert pool._created_connections == 0
    monkeypatch.setattr(pool, "_create_connection", factory)
    conn = await asyncio.wait_for(pool.get_connection(), 1)
    await pool.return_connection(conn)
    pool.close()


async def test_pool_timeout_and_closed_connection_recovery(tmp_path):
    pool = DatabaseConnectionPool(str(tmp_path / "pool.db"), 1, acquire_timeout=0.03)
    conn = await pool.get_connection()
    with pytest.raises(StorageError, match="timed out"):
        await pool.get_connection()
    conn.close()
    await pool.return_connection(conn)
    replacement = await pool.get_connection()
    assert replacement is not conn
    assert replacement.execute("SELECT 1").fetchone()[0] == 1
    await pool.return_connection(replacement)
    pool.close()
    assert pool._created_connections == 0


async def test_rollback_failure_does_not_hide_original_error(tmp_path):
    manager = DatabaseManager(str(tmp_path / "pool.db"))
    with pytest.raises(ValueError, match="original"):
        async with manager.get_connection() as conn:
            conn.close()
            raise ValueError("original")
    assert manager.pool._created_connections == 0
    assert await manager.cache_set("recovered", 42)
    assert await manager.cache_get("recovered") == 42
    await manager.close()


async def test_slow_storage_and_cancellation_do_not_block_loop():
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def slow():
        started.set()
        assert release.wait(2)
        finished.set()

    task = asyncio.create_task(run_storage(slow))
    while not started.is_set():
        await asyncio.sleep(0)
    # This heartbeat must advance while the worker is still blocked.
    await asyncio.wait_for(asyncio.sleep(0.01), 0.2)
    task.cancel()
    task.cancel()  # Repeated cancellation must also preserve serialization.
    second = asyncio.create_task(run_storage(lambda: finished.is_set()))
    await asyncio.sleep(0.01)
    assert not second.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await second is True


async def test_cancelled_connection_creation_releases_capacity(tmp_path, monkeypatch):
    pool = DatabaseConnectionPool(str(tmp_path / "pool.db"), 1)
    factory = pool._create_connection
    started, release = threading.Event(), threading.Event()

    def slow_create():
        started.set()
        assert release.wait(2)
        return factory()

    monkeypatch.setattr(pool, "_create_connection", slow_create)
    task = asyncio.create_task(pool.get_connection())
    while not started.is_set():
        await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert pool._created_connections == 0
    monkeypatch.setattr(pool, "_create_connection", factory)
    conn = await pool.get_connection()
    await pool.return_connection(conn)
    pool.close()


@pytest.mark.parametrize("operation", ["bind", "unbind", "toggle"])
async def test_hoyolab_write_failure_preserves_cached_account(monkeypatch, operation):
    service = GenshinService()
    service._accounts = {"42": {"encrypted_cookie": "old", "auto_sign_in": True}}
    before = copy.deepcopy(service._accounts)
    monkeypatch.setattr(
        service, "_save_accounts", Mock(side_effect=StorageError("offline"))
    )
    with pytest.raises(StorageError):
        if operation == "bind":
            client = Mock(get_game_accounts=AsyncMock(return_value=[]))
            monkeypatch.setattr(
                "src.services.genshin_service.genshin.Client", Mock(return_value=client)
            )
            await service.bind_account(42, "new-cookie", "global")
        elif operation == "unbind":
            await run_storage(service.unbind_account, 42)
        else:
            await run_storage(service.toggle_auto_sign_in, 42, False)
    assert service._accounts == before


@pytest.mark.parametrize("operation", ["bind", "unbind"])
async def test_osu_write_failure_preserves_cached_link(monkeypatch, operation):
    service = OsuService()
    service.bind(42, "old")
    monkeypatch.setattr(
        service, "_save_links", Mock(side_effect=StorageError("offline"))
    )
    with pytest.raises(StorageError):
        (
            await run_storage(service.bind, 42, "new")
            if operation == "bind"
            else await run_storage(service.unbind, 42)
        )
    assert service.get_bound_username(42) == "old"


def member(guild, user_id, rank, ban=True, moderate=True):
    result = Mock(spec=discord.Member)
    result.id = user_id
    result.guild = guild
    result.top_role = rank
    result.guild_permissions = SimpleNamespace(
        ban_members=ban, moderate_members=moderate
    )
    result.ban = AsyncMock()
    result.timeout = AsyncMock()
    return result


@pytest.mark.parametrize(
    "reason", ["no_ban", "revoked", "equal_role", "owner_target", "bot_role", "self"]
)
async def test_report_ban_rejects_unauthorized_actor(reason):
    guild = SimpleNamespace(id=9, owner_id=99)
    actor = member(guild, 1, 5, ban=reason != "no_ban")
    refreshed = member(guild, 1, 5, ban=reason not in ("no_ban", "revoked"))
    target = member(
        guild,
        99 if reason == "owner_target" else 1 if reason == "self" else 2,
        5 if reason == "equal_role" else 3,
    )
    guild.me = member(guild, 10, 2 if reason == "bot_role" else 10)
    guild.fetch_member = AsyncMock(side_effect=[refreshed, target])
    success, error = await ReportService().execute_ban(target, actor, "reason")
    assert not success and error
    target.ban.assert_not_awaited()


async def test_report_ban_allows_owner_above_bot_target():
    guild = SimpleNamespace(id=9, owner_id=99)
    owner = member(guild, 99, 1)
    target = member(guild, 2, 3)
    guild.me = member(guild, 10, 10)
    guild.fetch_member = AsyncMock(side_effect=[owner, target])
    success, error = await ReportService().execute_ban(target, owner, "reason")
    assert success and not error
    target.ban.assert_awaited_once()


@pytest.mark.skipif(
    os.getenv("MYSQL_INTEGRATION_TEST") != "1",
    reason="Requires isolated MySQL test database",
)
async def test_live_mysql_recovers_closed_connection(monkeypatch, tmp_path):
    database = os.environ.get("MYSQL_TEST_DATABASE", "")
    assert database.endswith("_test")
    monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    pool = DatabaseConnectionPool(str(tmp_path / "unused.db"), 1)
    conn = await pool.get_connection()
    await run_blocking(conn.close)
    await pool.return_connection(conn)
    recovered = await pool.get_connection()
    assert recovered is not conn
    result = await run_blocking(recovered.execute, "SELECT 1 AS alive")
    assert result.fetchone()["alive"] == 1
    await pool.return_connection(recovered)
    pool.close()


async def test_concurrent_osu_bindings_preserve_every_user():
    from src.utils.document_store import read_document

    service = OsuService()
    await asyncio.gather(
        *(
            run_blocking(service.bind, user_id, f"player-{user_id}")
            for user_id in range(12)
        )
    )
    saved = read_document("data/storage/osu_links.json")
    assert saved == {str(user_id): f"player-{user_id}" for user_id in range(12)}


async def test_report_ban_button_requires_ban_permission():
    from src.cogs.core.report import ReportActionView

    guild = SimpleNamespace(id=9, owner_id=99)
    actor = member(guild, 1, 5, ban=False, moderate=True)
    target = member(guild, 2, 3)
    event = SimpleNamespace(
        guild=guild,
        guild_id=9,
        user=actor,
        response=SimpleNamespace(send_message=AsyncMock(), send_modal=AsyncMock()),
    )
    view = ReportActionView(target, Mock())
    await view.ban_button.callback(event)
    event.response.send_message.assert_awaited_once()
    event.response.send_modal.assert_not_awaited()


async def test_settings_acknowledges_before_storage():
    from src.cogs.features.age_guard import AgeGuard

    event = SimpleNamespace(
        guild=Mock(),
        guild_id=9,
        user=Mock(spec=discord.Member),
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    def save(*args):
        event.response.defer.assert_awaited_once()
        assert threading.current_thread() is not threading.main_thread()

    cog = AgeGuard.__new__(AgeGuard)
    cog.service = Mock(set_adult_role=Mock(side_effect=save))
    await AgeGuard.set_adult_role.callback(
        cog, event, SimpleNamespace(id=4, mention="role")
    )
    event.followup.send.assert_awaited_once()
    event.response.send_message.assert_not_awaited()


async def test_message_listener_storage_runs_outside_loop():
    from src.cogs.core.message_logger import MessageLogger

    event = SimpleNamespace(
        author=SimpleNamespace(id=1, bot=False),
        guild=SimpleNamespace(id=9),
        id=7,
        content="hello",
        channel=SimpleNamespace(id=8),
        attachments=[],
    )
    started, release = threading.Event(), threading.Event()

    def save(*args):
        started.set()
        assert release.wait(2)

    cog = MessageLogger.__new__(MessageLogger)
    cog.service = Mock(
        get_record=Mock(return_value=None), add_record=Mock(side_effect=save)
    )
    task = asyncio.create_task(cog.on_message(event))
    while not started.is_set():
        await asyncio.sleep(0)
    await asyncio.wait_for(asyncio.sleep(0.01), 0.2)
    release.set()
    await task
    cog.service.add_record.assert_called_once()


async def test_blacklist_lookup_deadline_does_not_wait_for_slow_storage(monkeypatch):
    from src.utils.blacklist_manager import BlacklistManager

    manager = BlacklistManager()
    started, release = threading.Event(), threading.Event()

    def slow_lookup(user_id):
        started.set()
        assert release.wait(2)
        return None

    monkeypatch.setattr(manager, "local_check", slow_lookup)
    monkeypatch.setattr(manager, "api_check", AsyncMock(return_value=None))
    task = asyncio.create_task(asyncio.wait_for(manager.check(42), timeout=0.05))
    try:
        while not started.is_set():
            await asyncio.sleep(0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=0.3)
        assert not release.is_set()
    finally:
        release.set()
        # Drain the retained worker before the event loop is torn down.
        await run_storage(lambda: None)
