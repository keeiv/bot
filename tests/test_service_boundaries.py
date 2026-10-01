"""Public service contracts under JSON and isolated MySQL storage."""

import asyncio
import copy
import importlib
import os
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pymysql
import pytest

from src.services.age_guard_service import AgeGuardService
from src.services.audit_log_service import AuditLogService
from src.services.github_watch_service import GithubWatchService
from src.services.management_service import ManagementService
from src.services.message_log_service import MessageLogService
from src.services.temp_voice_service import TempVoiceService
from src.services.ticket_service import TicketService
from src.utils.anti_spam import AntiSpamManager
from src.utils.document_store import read_document
from src.utils.document_store import StorageError
from src.utils.document_store import write_document
from src.utils.storage_worker import run_blocking


@pytest.fixture(params=["json", "mysql"])
def backend(request, monkeypatch, tmp_path):
    if request.param == "mysql":
        if os.getenv("MYSQL_INTEGRATION_TEST") != "1":
            pytest.skip("Requires isolated MySQL database")
        database = os.environ.get("MYSQL_TEST_DATABASE", "")
        assert database.endswith("_test"), "Never use production data"
        monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setenv("STORAGE_BACKEND", request.param)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    # Unique document keys isolate each case, including across MySQL fixtures.
    prefix = tmp_path.name
    for name in ("management", "github_watch", "age_guard", "ticket", "temp_voice"):
        module = importlib.import_module(f"src.services.{name}_service")
        monkeypatch.setattr(module, "_DATA_FILE", f"data/storage/{prefix}-{name}.json")
    for name in ("audit_log", "message_log"):
        module = importlib.import_module(f"src.services.{name}_service")
        monkeypatch.setattr(
            module, "_CHANNELS_FILE", f"data/storage/{prefix}-channels.json"
        )
    monkeypatch.setattr(
        AntiSpamManager, "SETTINGS_FILE", f"data/storage/{prefix}-antispam.json"
    )
    return request.param


def fail_commit(monkeypatch, backend):
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


@pytest.mark.parametrize(
    "operation",
    [
        "add_repo",
        "remove_repo",
        "set_welcome",
        "clear_welcome",
        "add_role",
        "remove_role",
        "guild_update",
    ],
)
def test_management_failed_commit_preserves_memory_and_storage(
    backend, monkeypatch, operation
):
    service = ManagementService()
    service.update_guild_config(
        "9",
        {
            "welcome": {"message": "old"},
            "auto_roles": [{"role_id": 4}],
            "unknown": {"future": True},
        },
    )
    service.add_tracked_repo("9", "owner", "repo", 8)
    before = service.get_all_configs()
    path = importlib.import_module("src.services.management_service")._DATA_FILE
    fail_commit(monkeypatch, backend)
    operations = {
        "add_repo": lambda: service.add_tracked_repo("10", "new", "repo", 1),
        "remove_repo": lambda: service.remove_tracked_repo("9", "owner/repo"),
        "set_welcome": lambda: service.set_welcome_config("9", {"message": "new"}),
        "clear_welcome": lambda: service.clear_welcome_config("9"),
        "add_role": lambda: service.add_auto_role("9", {"role_id": 5}),
        "remove_role": lambda: service.remove_auto_role("9", 1),
        "guild_update": lambda: service.update_guild_config("9", {"unknown": {}}),
    }
    with pytest.raises((OSError, StorageError)):
        operations[operation]()
    assert service.get_all_configs() == before
    assert read_document(path) == before


def test_management_snapshots_inputs_and_other_fields_are_preserved(backend):
    service = ManagementService()
    initial = {"unknown": {"future": [1]}, "auto_roles": [{"role_id": 1}]}
    service.update_guild_config("9", initial)
    initial["unknown"]["future"].append(2)
    service.update_guild_config("other", {"keep": True})
    service.set_welcome_config("9", {"message": "old", "embed_title": "keep"})
    service.update_welcome_config("9", {"message": "new"})
    service.add_tracked_repo("9", "owner", "repo", 8)
    snapshot = service.config
    snapshot["9"]["unknown"]["future"].append(3)
    snapshot = service.get_welcome_config("9")
    snapshot["message"] = "outside"
    service.add_auto_role("9", {"role_id": 2})
    assert service.remove_auto_role("9", 0) is None
    assert service.remove_auto_role("9", -1) is None
    assert service.remove_auto_role("9", 99) is None
    assert service.remove_auto_role("9", 1) == {"role_id": 1}
    assert service.get_welcome_config("9") == {"message": "new", "embed_title": "keep"}
    assert service.get_auto_roles("9") == [{"role_id": 2}]
    reloaded = ManagementService()
    assert reloaded.get_all_configs() == service.get_all_configs()
    assert reloaded.get_guild_config("9")["unknown"] == {"future": [1]}
    assert reloaded.get_guild_config("other") == {"keep": True}


async def test_concurrent_management_updates_keep_every_guild(backend):
    service = ManagementService()
    await asyncio.gather(
        *(run_blocking(service.add_auto_role, str(i), {"role_id": i}) for i in range(8))
    )
    assert ManagementService().get_all_configs() == {
        str(i): {"auto_roles": [{"role_id": i}]} for i in range(8)
    }


async def test_repository_removed_during_fetch_is_not_restored(backend):
    service = ManagementService()
    service.add_tracked_repo("9", "owner", "repo", 8)
    expected = service.get_tracked_repos("9")["owner/repo"]

    async def fetch(url):
        service.remove_tracked_repo("9", "owner/repo")
        if url.endswith("/pulls"):
            return []
        return [
            {
                "sha": "new",
                "html_url": "https://example.test",
                "commit": {
                    "message": "new",
                    "committer": {"date": "2026-10-01T00:00:00+00:00"},
                    "author": {"name": "author"},
                },
            }
        ]

    service._fetch_github_list = AsyncMock(side_effect=fetch)
    assert await service.check_repo_updates("9", "owner/repo", expected) == []
    assert service.get_tracked_repos("9") == {}


def test_github_polling_rejects_changed_subscription_and_preserves_other_fields(
    backend,
):
    service = GithubWatchService()
    service.update_config(
        9,
        {
            "owner": "owner",
            "repo": "repo",
            "enabled": True,
            "channel_id": 8,
            "unknown": [1],
        },
    )
    snapshot = service.get_config(9)
    assert service.record_commit(9, snapshot, "abc")
    service.update_config(9, {"owner": "new"})
    assert not service.record_commit(9, snapshot, "stale")
    assert service.get_config(9)["last_sha"] is None
    assert service.get_config(9)["unknown"] == [1]
    snapshot = service.get_all_configs()
    snapshot["9"]["unknown"].append(2)
    assert service.get_config(9)["unknown"] == [1]


@pytest.mark.parametrize(
    "kind",
    [
        "github",
        "ageguard",
        "tempvoice",
        "ticket",
        "antispam",
        "audit",
        "message_channels",
    ],
)
def test_setting_services_preserve_state_after_failed_commit(
    backend, monkeypatch, kind
):
    if kind == "github":
        service = GithubWatchService()
        updater, reader = service.update_config, service.get_config
    elif kind == "ageguard":
        service = AgeGuardService()
        updater, reader = service.update_config, service.get_config
    elif kind in ("tempvoice", "ticket"):
        service = TempVoiceService() if kind == "tempvoice" else TicketService()
        updater, reader = service.update_guild_config, service.get_guild_config
    elif kind == "antispam":
        service = AntiSpamManager()
        updater, reader = service.update_settings, service.get_settings
    elif kind == "audit":
        service = AuditLogService()
        updater, reader = service.set_channel_id, service.get_channel_id
    else:
        service = MessageLogService()
        updater, reader = service.set_log_channel_id, service.get_log_channel_id

    def update(value):
        updater(
            9, value if kind in ("audit", "message_channels") else {"enabled": value}
        )

    def snapshot():
        return reader(9)

    update(1 if kind in ("audit", "message_channels") else True)
    before = copy.deepcopy(snapshot())
    fail_commit(monkeypatch, backend)
    with pytest.raises((OSError, StorageError)):
        update(2 if kind in ("audit", "message_channels") else False)
    assert snapshot() == before


def test_whitelist_snapshots_noop_and_failed_update(backend, monkeypatch):
    manager = AntiSpamManager()
    assert manager.update_whitelist(9, "add", 1, 2) == ["roles", "channels"]
    snapshot = manager.get_settings(9)
    snapshot["whitelisted_roles"].append(99)
    assert manager.get_settings(9)["whitelisted_roles"] == [1]
    assert manager.update_whitelist(9, "add", 1, 2) == []
    fail_commit(monkeypatch, backend)
    with pytest.raises((OSError, StorageError)):
        manager.update_whitelist(9, "remove", 1, 2)
    assert manager.get_settings(9)["whitelisted_roles"] == [1]
    assert manager.get_settings(9)["whitelisted_channels"] == [2]


def test_ticket_panel_and_settings_keep_counters_records_and_future_fields(backend):
    module = importlib.import_module("src.services.ticket_service")
    initial = {
        "guilds": {
            "9": {
                "channel_id": 8,
                "role_id": 4,
                "ticket_count": 12,
                "panel_message_id": 99,
                "unknown": [1],
            }
        },
        "tickets": {"7": {"state": "keep"}},
        "extra": True,
    }
    write_document(module._DATA_FILE, initial)
    service = TicketService()
    snapshot = service.get_guild_config(9)
    snapshot["unknown"].append(2)
    service.update_guild_config(9, {"enabled": True})
    expected = service.get_guild_config(9)
    service.increment_ticket_count(9)
    service.set_panel_message(9, 100, expected)
    saved = read_document(module._DATA_FILE)
    assert saved["tickets"] == initial["tickets"] and saved["extra"] is True
    assert saved["guilds"]["9"]["ticket_count"] == 13
    assert saved["guilds"]["9"]["unknown"] == [1]
    assert saved["guilds"]["9"]["panel_message_id"] == 100
    service.update_guild_config(9, {"channel_id": 20})
    with pytest.raises(ValueError, match="已變更"):
        service.set_panel_message(9, 200, expected)
    assert service.get_guild_config(9)["panel_message_id"] == 100


@pytest.mark.parametrize(
    "kind",
    [
        "management",
        "github_watch",
        "age_guard",
        "temp_voice",
        "ticket",
        "audit_log",
        "message_log",
        "antispam",
    ],
)
def test_invalid_document_shape_is_not_replaced_with_empty_settings(backend, kind):
    classes = {
        "management": ManagementService,
        "github_watch": GithubWatchService,
        "age_guard": AgeGuardService,
        "temp_voice": TempVoiceService,
        "ticket": TicketService,
        "audit_log": AuditLogService,
        "message_log": MessageLogService,
        "antispam": AntiSpamManager,
    }
    if kind == "antispam":
        path = AntiSpamManager.SETTINGS_FILE
    else:
        module = importlib.import_module(f"src.services.{kind}_service")
        path = (
            module._CHANNELS_FILE
            if kind in ("audit_log", "message_log")
            else module._DATA_FILE
        )
    write_document(path, ["invalid-object-shape"])
    with pytest.raises(TypeError):
        service = classes[kind]()
        if kind == "age_guard":
            service.update_config(9, {"enabled": True})
        elif kind in ("temp_voice", "ticket"):
            service.update_guild_config(9, {"enabled": True})
        elif kind == "audit_log":
            service.set_channel_id(9, 1)
        elif kind == "message_log":
            service.set_log_channel_id(9, 1)
    assert read_document(path) == ["invalid-object-shape"]


def test_cogs_use_public_services_instead_of_storage_or_private_state():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    violations = []
    for path in (root / "src/cogs").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name) and function.id in {
                "open_document",
                "write_document",
                "read_document",
            }:
                violations.append(f"{path.name}:{node.lineno} direct storage")
            if isinstance(function, ast.Attribute) and function.attr.startswith("_"):
                receiver = ast.unparse(function.value)
                if receiver.endswith((".service", ".manager")):
                    violations.append(
                        f"{path.name}:{node.lineno} private service method"
                    )
    assert not violations, "\n".join(violations)
