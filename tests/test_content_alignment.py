"""Regression checks for documented logging, access and persistence behavior."""

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime
from datetime import timedelta
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pytest

from src.cogs.core.blacklist import AppealAcceptModal
from src.cogs.core.message_logger import MessageLogger
from src.cogs.features.temp_voice import TempVoice
from src.cogs.features.ticket import Ticket
from src.services import message_log_store
from src.services.blacklist_service import BlacklistService
from src.services.message_log_service import MessageLogService
from src.utils.document_store import initialize_schema
from src.utils.document_store import read_document
from src.utils.document_store import StorageError
from src.utils.document_store import write_document
from src.utils.message_cache import MessageCache
from src.utils.mysql_compat import MySQLConnection
from src.utils.time_utils import TZ_OFFSET


@pytest.fixture(params=["json", "mysql"])
def log_service(request, monkeypatch, tmp_path):
    if request.param == "mysql":
        if os.getenv("MYSQL_INTEGRATION_TEST") != "1":
            pytest.skip("Requires isolated MySQL database")
        database = os.environ.get("MYSQL_TEST_DATABASE", "")
        assert database.endswith("_test"), "Never use production data"
        monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setenv("STORAGE_BACKEND", request.param)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    message_log_store.forget_ready()
    if request.param == "mysql":
        initialize_schema()
        with MySQLConnection() as db:
            for sql in message_log_store.mysql_schema():
                db.execute(sql)
            for table in ("message_edits", "message_log", "message_log_meta"):
                db.execute(f"DELETE FROM {table}")
            # Earlier runs may have left an old-format log behind to be imported.
            db.execute(
                "DELETE FROM documents WHERE path=?", (message_log_store.LEGACY_FILE,)
            )
    service = MessageLogService()
    service.message_cache = MessageCache()
    yield service, request.param
    message_log_store.forget_ready()


def seed_log(service):
    service.add_record(9, 7, "A", 42, 8)
    return service.get_record(9, 7)


class FailingCommit:
    """A connection whose commit fails, as a full disk or a dropped server would."""

    def __init__(self, inner):
        self.inner = inner

    def execute(self, *args):
        return self.inner.execute(*args)

    def commit(self):
        raise StorageError("test commit failure")

    def rollback(self):
        self.inner.rollback()

    def close(self):
        self.inner.close()


@pytest.mark.parametrize("operation", ["add", "edit", "delete", "cleanup"])
def test_log_failed_commit_changes_neither_cache_nor_storage(
    log_service, monkeypatch, operation
):
    service, _ = log_service
    seed_log(service)
    service.set_log_channel_id(9, 50)
    old = (datetime.now(TZ_OFFSET) - timedelta(days=60)).isoformat()
    with service.store.transaction(write=True) as db:
        db.execute("UPDATE message_log SET created_at=?", (old,))
    service.message_cache.clear_all()
    baseline = service.get_record(9, 7)
    real = service.store._connect
    monkeypatch.setattr(service.store, "_connect", lambda: FailingCommit(real()))
    operations = {
        "add": lambda: service.add_record(10, 8, "new", 43, 8),
        "edit": lambda: service.record_edit(9, 7, "B"),
        "delete": lambda: service.mark_deleted(9, 7),
        "cleanup": service.cleanup_old_logs,
    }
    with pytest.raises(StorageError):
        operations[operation]()
    assert service.get_record(9, 7) == baseline
    monkeypatch.setattr(service.store, "_connect", real)
    service.message_cache.clear_all()
    assert service.get_record(9, 7) == baseline
    assert service.get_record(10, 8) is None


def test_log_records_handed_out_are_copies(log_service):
    service, _ = log_service
    seed_log(service)
    service.get_record(9, 7)["edit_history"].append("outside")
    assert service.get_record(9, 7)["edit_history"] == []
    updates = {"edit_history": ["B"]}
    service.message_cache.update(9, 7, updates)
    updates["edit_history"].append("outside")
    assert service.message_cache.get(9, 7)["edit_history"] == ["B"]


def test_log_an_edit_is_a_row_not_a_rewrite(log_service):
    service, _ = log_service
    seed_log(service)
    service.add_record(9, 8, "other message", 42, 8)
    service.record_edit(9, 7, "B")
    service.record_edit(9, 7, "C")
    with service.store.transaction() as db:
        edits = db.execute(
            "SELECT seq, content FROM message_edits WHERE guild_id=? AND message_id=? ORDER BY seq",
            (9, 7),
        ).fetchall()
    assert [tuple(row) for row in edits] == [(1, "B"), (2, "C")]
    assert service.get_record(9, 8)["edit_history"] == []
    assert service.record_edit(9, 999, "nothing to edit") is False


def test_log_concurrent_instances_preserve_each_edit(log_service):
    service, _ = log_service
    seed_log(service)
    other = MessageLogService()
    other.message_cache = MessageCache()
    with ThreadPoolExecutor(max_workers=4) as workers:
        futures = [
            workers.submit((service if i % 2 else other).record_edit, 9, 7, str(i))
            for i in range(12)
        ]
        assert all(future.result() for future in futures)
    service.message_cache.clear_all()
    record = service.get_record(9, 7)
    assert sorted(record["edit_history"], key=int) == [str(i) for i in range(12)]
    assert record["original_content"] == "A"


def test_log_cleanup_evicts_old_records_and_their_edits(log_service):
    service, _ = log_service
    service.set_log_channel_id(9, 50)
    seed_log(service)
    service.record_edit(9, 7, "B")
    service.add_record(9, 8, "fresh", 42, 8)
    old = (datetime.now(TZ_OFFSET) - timedelta(days=60)).isoformat()
    with service.store.transaction(write=True) as db:
        db.execute("UPDATE message_log SET created_at=? WHERE message_id=7", (old,))
    assert service.cleanup_old_logs() == 1
    assert service.get_record(9, 7) is None
    assert service.get_record(9, 8)["original_content"] == "fresh"
    with service.store.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM message_edits").fetchone()[0] == 0


def test_log_repeated_delivery_does_not_reset_history(log_service):
    service, _ = log_service
    seed_log(service)
    service.record_edit(9, 7, "B")
    before = service.get_record(9, 7)
    service.add_record(9, 7, "overwritten", 43, 10)
    service.message_cache.clear_all()
    assert service.get_record(9, 7) == before


def test_log_legacy_json_is_imported_once_and_left_alone(log_service):
    service, _ = log_service
    legacy = {
        "9_7": {
            "message_id": 7,
            "guild_id": 9,
            "channel_id": 8,
            "author_id": 42,
            "original_content": "old",
            "edit_history": ["older edit"],
            "deleted": True,
            "deleted_at": "2026-11-01T00:00:00+08:00",
            "attachments": ["https://cdn.example/a.png"],
            "created_at": "2026-11-01T00:00:00+08:00",
            "future": {"labels": ["preserved"]},
        },
        "broken": "not a record",
    }
    write_document(message_log_store.LEGACY_FILE, legacy)
    message_log_store.forget_ready()
    fresh = MessageLogService()
    fresh.message_cache = MessageCache()
    record = fresh.get_record(9, 7)
    assert record["original_content"] == "old"
    assert record["edit_history"] == ["older edit"]
    assert record["deleted"] is True
    assert record["future"] == {"labels": ["preserved"]}
    assert read_document(message_log_store.LEGACY_FILE) == legacy
    # A later change to the old file is not imported again.
    legacy["9_7"]["original_content"] = "changed"
    write_document(message_log_store.LEGACY_FILE, legacy)
    message_log_store.forget_ready()
    again = MessageLogService()
    again.message_cache = MessageCache()
    assert again.get_record(9, 7)["original_content"] == "old"


def message(content, attachments=()):
    return SimpleNamespace(
        author=SimpleNamespace(id=42, bot=False),
        guild=SimpleNamespace(id=9, name="test guild"),
        id=7,
        content=content,
        channel=SimpleNamespace(id=8),
        attachments=[SimpleNamespace(url=url) for url in attachments],
    )


def logger_case():
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    cog = MessageLogger.__new__(MessageLogger)
    cog.bot = SimpleNamespace(get_channel=lambda _: channel, get_cog=lambda _: None)
    cog.service = MessageLogService()
    cog.service.message_cache = MessageCache()
    cog.service.set_log_channel_id(9, 50)
    return cog, channel


async def test_logger_reports_each_event_content_without_losing_original():
    cog, channel = logger_case()
    await cog.on_message(message("A"))
    await cog.on_message_edit(message("A"), message("B"))
    await cog.on_message_edit(message("B"), message("C"))
    edit = channel.send.call_args.kwargs["embed"]
    assert next(field.value for field in edit.fields if field.name == "編輯前") == (
        "```\nB\n```"
    )
    await cog.on_message_delete(message("C"))
    deleted = channel.send.call_args.kwargs["embed"]
    assert (
        next(field.value for field in deleted.fields if field.name == "刪除前的訊息")
        == "```\nC\n```"
    )
    record = cog.service.get_record(9, 7)
    assert record["original_content"] == "A"
    assert record["edit_history"] == ["B", "C"]
    assert record["deleted"] is True


async def test_logger_records_attachment_only_change_but_ignores_unchanged_event():
    cog, channel = logger_case()
    before = message("same", ["https://example.com/old.png"])
    after = message("same", ["https://example.com/new.png"])
    await cog.on_message(before)
    await cog.on_message_edit(before, after)
    assert channel.send.call_args.kwargs["embed"].image.url == after.attachments[0].url
    baseline = copy.deepcopy(cog.service.get_record(9, 7))
    await cog.on_message_edit(after, after)
    channel.send.assert_awaited_once()
    assert cog.service.get_record(9, 7) == baseline


@pytest.mark.parametrize("kind", ["ticket", "voice"])
@pytest.mark.parametrize("entry", [None, {"mode": "block"}, {"mode": "global_ban"}])
async def test_custom_prefix_commands_check_blacklist_before_action(kind, entry):
    manager = SimpleNamespace(check=AsyncMock(return_value=entry))
    bot = SimpleNamespace(blacklist_manager=manager)
    user = Mock(spec=discord.Member)
    user.id, user.bot = 42, False
    user.guild_permissions.administrator = True
    event = SimpleNamespace(
        locale=discord.Locale.taiwan_chinese,
        client=SimpleNamespace(get_guild=lambda _: object()),
        author=user,
        guild=Mock(),
        content=">>>ticket setup" if kind == "ticket" else "envc*name new",
        reply=AsyncMock(),
    )
    cog = (Ticket if kind == "ticket" else TempVoice).__new__(
        Ticket if kind == "ticket" else TempVoice
    )
    cog.bot = bot
    operation = AsyncMock()
    if kind == "ticket":
        cog._handle_setup = operation
    else:
        cog._cmd_name = operation
    await cog.on_message(event)
    manager.check.assert_awaited_once_with(42)
    if entry is None:
        operation.assert_awaited_once()
    else:
        operation.assert_not_awaited()


@pytest.mark.parametrize("source", ["local", "api"])
async def test_appeal_accept_notification_matches_actual_blacklist_source(source):
    manager = Mock()
    manager.get_appeal.return_value = {"source": source}
    target = SimpleNamespace(send=AsyncMock())
    bot = SimpleNamespace(
        blacklist_manager=manager, fetch_user=AsyncMock(return_value=target)
    )
    modal = AppealAcceptModal(42, SimpleNamespace(bot=bot))
    event = SimpleNamespace(
        locale=discord.Locale.taiwan_chinese,
        guild_id=None,
        client=SimpleNamespace(get_guild=lambda _: object()),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        user=SimpleNamespace(id=1),
        message=SimpleNamespace(embeds=[]),
    )
    await modal.on_submit(event)
    description = target.send.call_args.kwargs["embed"].description
    if source == "api":
        manager.local_remove.assert_not_called()
        assert "封鎖尚未解除" in description
    else:
        manager.local_remove.assert_called_once_with(42)
        assert "本地黑名單紀錄已移除" in description
    assert BlacklistService().build_notify_embed(False).description == (
        "您的申訴已被 **駁回**。"
    )
