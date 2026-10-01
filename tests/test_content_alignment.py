"""Regression checks for documented logging, access and persistence behavior."""

from concurrent.futures import ThreadPoolExecutor
import copy
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pymysql
import pytest

from src.cogs.core.blacklist import AppealAcceptModal
from src.cogs.core.message_logger import MessageLogger
from src.cogs.features.temp_voice import TempVoice
from src.cogs.features.ticket import Ticket
from src.services import message_log_service
from src.services.blacklist_service import BlacklistService
from src.services.message_log_service import MessageLogService
from src.utils.document_store import initialize_schema
from src.utils.document_store import read_document
from src.utils.document_store import StorageError
from src.utils.document_store import write_document
from src.utils.message_cache import MessageCache


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
    path = f"data/storage/{tmp_path.name}-messages.json"
    monkeypatch.setattr(message_log_service, "_LOG_FILE", path)
    if request.param == "mysql":
        initialize_schema()
    service = MessageLogService()
    service.message_cache = MessageCache()
    return service, path, request.param


def seed_log(service, path):
    service.add_record(9, 7, "A", 42, 8)
    data = read_document(path)
    data["9_7"]["future"] = {"labels": ["preserved"]}
    data["9_7"]["created_at"] = "2000-01-01T00:00:00+08:00"
    service.save_message_log(data)
    service.message_cache.set(9, 7, data["9_7"])
    return data


@pytest.mark.parametrize("operation", ["add", "edit", "delete", "cleanup"])
def test_log_failed_commit_preserves_both_caches_and_storage(
    log_service, monkeypatch, operation
):
    service, path, backend = log_service
    baseline = seed_log(service, path)
    cached = service.get_record(9, 7)
    if backend == "mysql":
        monkeypatch.setattr(
            pymysql.connections.Connection,
            "commit",
            Mock(side_effect=pymysql.OperationalError(2013, "test commit failure")),
        )
    else:
        monkeypatch.setattr(
            "src.utils.document_store.os.replace",
            Mock(side_effect=OSError("test disk failure")),
        )
    operations = {
        "add": lambda: service.add_record(10, 8, "new", 43, 8),
        "edit": lambda: service.record_edit(9, 7, "B"),
        "delete": lambda: service.mark_deleted(9, 7),
        "cleanup": service.cleanup_old_logs,
    }
    with pytest.raises((OSError, StorageError)):
        operations[operation]()
    assert service.load_message_log() == baseline
    assert service.get_record(9, 7) == cached
    assert read_document(path) == baseline


def test_log_snapshots_and_cache_updates_are_detached(log_service):
    service, path, _ = log_service
    baseline = seed_log(service, path)
    service.load_message_log()["9_7"]["future"]["labels"].append("outside")
    service.get_record(9, 7)["edit_history"].append("outside")
    baseline["9_7"]["future"]["labels"].clear()
    assert service.get_record(9, 7)["future"]["labels"] == ["preserved"]
    assert service.get_record(9, 7)["edit_history"] == []
    assert service.load_message_log() == read_document(path)
    updates = {"edit_history": ["B"]}
    service.message_cache.update(9, 7, updates)
    updates["edit_history"].append("outside")
    assert service.message_cache.get(9, 7)["edit_history"] == ["B"]


def test_log_invalid_read_does_not_replace_valid_cache(log_service):
    service, path, _ = log_service
    baseline = seed_log(service, path)
    write_document(path, [])
    with pytest.raises(TypeError, match="Message log must be an object"):
        service.record_edit(9, 7, "B")
    assert service.load_message_log() == baseline
    assert read_document(path) == []


def test_log_concurrent_instances_preserve_each_edit(log_service):
    service, path, _ = log_service
    seed_log(service, path)
    other = MessageLogService()
    other.message_cache = MessageCache()
    other.load_message_log()
    with ThreadPoolExecutor(max_workers=4) as workers:
        futures = [
            workers.submit((service if i % 2 else other).record_edit, 9, 7, str(i))
            for i in range(12)
        ]
        assert all(future.result() for future in futures)
    record = read_document(path)["9_7"]
    assert sorted(record["edit_history"], key=int) == [str(i) for i in range(12)]
    assert record["original_content"] == "A"
    assert record["future"] == {"labels": ["preserved"]}


def test_log_cleanup_evicts_removed_records(log_service):
    service, path, _ = log_service
    seed_log(service, path)
    assert service.cleanup_old_logs() == 1
    assert service.get_record(9, 7) is None
    assert read_document(path) == {}


def test_log_repeated_delivery_does_not_reset_history(log_service):
    service, path, _ = log_service
    seed_log(service, path)
    service.record_edit(9, 7, "B")
    before = read_document(path)
    service.add_record(9, 7, "overwritten", 43, 10)
    assert read_document(path) == before
    assert service.get_record(9, 7) == before["9_7"]


def test_log_public_save_refreshes_record_cache_across_instances(log_service):
    service, path, _ = log_service
    before = seed_log(service, path)
    other = MessageLogService()
    other.message_cache = service.message_cache
    other.load_message_log()
    updated = copy.deepcopy(before)
    updated["9_7"]["edit_history"].append("B")
    service.save_message_log(updated)
    assert other.get_record(9, 7)["edit_history"] == ["B"]


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
