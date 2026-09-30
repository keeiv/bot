"""Check startup recovery without touching the installed database."""

from unittest.mock import Mock

import pytest

from src.utils import mysql_runtime
from src.utils.document_store import StorageError


def test_json_does_not_start_mysql(monkeypatch):
    start = Mock()
    monkeypatch.setattr(mysql_runtime.subprocess, "run", start)
    mysql_runtime.prepare_storage()
    start.assert_not_called()


def test_local_mysql_waits_before_migration(tmp_path, monkeypatch):
    launcher = tmp_path / "NewBotMySQL/start-mysql.ps1"
    launcher.parent.mkdir()
    launcher.touch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setattr(mysql_runtime.sys, "platform", "win32")
    monkeypatch.setattr(
        mysql_runtime.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False
    )
    monkeypatch.setattr(
        mysql_runtime, "_listening", Mock(side_effect=[False, False, True])
    )
    monkeypatch.setattr(mysql_runtime.time, "sleep", Mock())
    start = Mock()
    verify = Mock()
    monkeypatch.setattr(mysql_runtime.subprocess, "run", start)
    monkeypatch.setattr(mysql_runtime, "require_migration", verify)
    mysql_runtime.prepare_storage()
    start.assert_called_once()
    assert start.call_args.args[0][-1] == str(launcher)
    verify.assert_called_once()


def test_remote_mysql_never_starts_local_server(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    monkeypatch.setenv("MYSQL_HOST", "db.example.invalid")
    start = Mock()
    verify = Mock(side_effect=StorageError("unavailable"))
    monkeypatch.setattr(mysql_runtime.subprocess, "run", start)
    monkeypatch.setattr(mysql_runtime, "require_migration", verify)
    with pytest.raises(StorageError):
        mysql_runtime.prepare_storage()
    start.assert_not_called()


def test_failed_preflight_cleans_lock(monkeypatch):
    from src import main

    monkeypatch.setattr(main, "TOKEN", "test-only")
    monkeypatch.setattr(main.signal, "signal", Mock())
    monkeypatch.setattr(main, "ensure_data_dir", Mock())
    monkeypatch.setattr(
        main, "prepare_storage", Mock(side_effect=StorageError("unavailable"))
    )
    with pytest.raises(StorageError):
        main.main()
    assert not main.os.path.exists("bot.lock")
