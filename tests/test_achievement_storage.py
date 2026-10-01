"""Achievement progress remains intact across storage and concurrency failures."""

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import time
from unittest.mock import Mock

import pymysql
import pytest

from src.services import achievement_service
from src.services.achievement_service import ACHIEVEMENTS
from src.services.achievement_service import AchievementService
from src.utils.document_store import connect_mysql
from src.utils.document_store import document_key
from src.utils.document_store import read_document
from src.utils.document_store import StorageError
from src.utils.document_store import write_document


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
    monkeypatch.setattr(
        achievement_service,
        "_DATA_FILE",
        f"data/storage/{tmp_path.name}-achievements.json",
    )
    return request.param


@pytest.fixture
def initial():
    return {
        "1461349028263497969": {
            "987654321987654321": {
                "unlocked": ["first_edit", "legacy_achievement"],
                "unlocked_at_first_edit": "2026-09-01T12:00:00+08:00",
                "edit_count": 42,
                "future": {"labels": ["舊資料", "🎵"]},
            },
            "other-guild": {"unlocked": ["first_delete"], "unknown": [1]},
        },
        "other-user": {"other-guild": {"unlocked": [], "keep": True}},
    }


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


def test_public_queries_return_detached_progress_and_definitions(backend, initial):
    write_document(achievement_service._DATA_FILE, initial)
    service = AchievementService()
    unlocked = service.get_user_achievements(1461349028263497969, 987654321987654321)
    unlocked.append("outside")
    assert (
        service.get_user_achievements(1461349028263497969, 987654321987654321)
        == initial["1461349028263497969"]["987654321987654321"]["unlocked"]
    )
    combined = service.get_user_achievements(1461349028263497969)
    combined.clear()
    assert set(service.get_user_achievements(1461349028263497969)) == {
        "first_edit",
        "first_delete",
        "legacy_achievement",
    }
    info = service.get_achievement_info("first_edit")
    info["name"] = "outside"
    assert service.get_achievement_info("first_edit") == ACHIEVEMENTS["first_edit"]
    assert service.get_achievement_info("unknown") is None
    progress = service.get_progress(1461349028263497969, 987654321987654321)
    assert progress == {
        "unlocked": 2,
        "total": len(ACHIEVEMENTS),
        "percentage": round(2 / len(ACHIEVEMENTS) * 100, 1),
    }
    progress["unlocked"] = 0
    assert (
        service.get_progress(1461349028263497969, 987654321987654321)["unlocked"] == 2
    )
    assert read_document(achievement_service._DATA_FILE) == initial


def test_unlock_preserves_ids_timestamps_other_users_and_metadata(backend, initial):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    service = AchievementService()
    assert service.unlock(1461349028263497969, 987654321987654321, "first_delete")
    saved = read_document(path)
    guild = saved["1461349028263497969"]["987654321987654321"]
    timestamp = guild.pop("unlocked_at_first_delete")
    assert datetime.fromisoformat(timestamp).utcoffset().total_seconds() == 8 * 3600
    expected = copy.deepcopy(initial)
    expected["1461349028263497969"]["987654321987654321"]["unlocked"].append(
        "first_delete"
    )
    assert saved == expected
    assert (
        AchievementService().get_user_achievements(
            1461349028263497969, 987654321987654321
        )
        == guild["unlocked"]
    )


def test_duplicate_and_unknown_unlock_do_not_write(backend, monkeypatch):
    service = AchievementService()
    assert service.unlock(1, 9, "first_edit")
    before = read_document(achievement_service._DATA_FILE)
    writer = Mock(wraps=achievement_service.write_document)
    monkeypatch.setattr(achievement_service, "write_document", writer)
    assert not service.unlock(1, 9, "first_edit")
    assert not service.unlock(1, 9, "unknown")
    writer.assert_not_called()
    assert read_document(achievement_service._DATA_FILE) == before


def test_failed_unlock_preserves_cache_and_persisted_progress(
    backend, monkeypatch, initial
):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    service = AchievementService()
    before = service.get_user_achievements(1461349028263497969, 987654321987654321)
    fail_commit(monkeypatch, backend)
    with pytest.raises((OSError, StorageError)):
        service.unlock(1461349028263497969, 987654321987654321, "first_delete")
    assert (
        service.get_user_achievements(1461349028263497969, 987654321987654321) == before
    )
    assert read_document(path) == initial


def test_failed_first_unlock_does_not_publish_or_create_progress(backend, monkeypatch):
    service = AchievementService()
    assert service.get_user_achievements(1, 9) == []
    fail_commit(monkeypatch, backend)
    with pytest.raises((OSError, StorageError)):
        service.unlock(1, 9, "first_edit")
    assert service.get_user_achievements(1, 9) == []
    with pytest.raises(FileNotFoundError):
        read_document(achievement_service._DATA_FILE)


@pytest.mark.parametrize(
    "failure",
    [
        OSError("test read failure"),
        StorageError("test database failure"),
        json.JSONDecodeError("test invalid document", "{", 1),
    ],
)
def test_read_failures_propagate_without_clearing_cache_or_rewriting_data(
    backend, monkeypatch, initial, failure
):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    service = AchievementService()
    service.get_user_achievements(1461349028263497969)
    before_cache = copy.deepcopy(service._cache)
    service._cache_time = 0
    monkeypatch.setattr(achievement_service, "read_document", Mock(side_effect=failure))
    with pytest.raises(type(failure)):
        service.get_user_achievements(1461349028263497969)
    with pytest.raises(type(failure)):
        service.unlock(1461349028263497969, 987654321987654321, "first_delete")
    assert service._cache == before_cache
    assert read_document(path) == initial


@pytest.mark.parametrize(
    "invalid",
    [
        [],
        {"1": []},
        {"1": {"9": []}},
        {"1": {"9": {"unlocked": {}}}},
        {"1": {"9": {"unlocked": [1]}}},
    ],
)
def test_invalid_records_never_replace_valid_cache_or_get_overwritten(
    backend, initial, invalid
):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    service = AchievementService()
    service.get_user_achievements(1461349028263497969)
    before_cache = copy.deepcopy(service._cache)
    write_document(path, invalid)
    service._cache_time = 0
    with pytest.raises(TypeError):
        service.get_user_achievements(1, 9)
    with pytest.raises(TypeError):
        service.unlock(1, 9, "first_edit")
    assert service._cache == before_cache
    assert read_document(path) == invalid


def test_corrupt_document_stays_intact_and_blocks_unlock(backend, initial):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    service = AchievementService()
    service.get_user_achievements(1461349028263497969)
    before_cache = copy.deepcopy(service._cache)
    if backend == "json":
        Path(path).write_text('{"interrupted":', encoding="utf-8")
        before = Path(path).read_bytes()
        failure = json.JSONDecodeError
    else:
        with connect_mysql() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE documents SET checksum=%s WHERE path=%s",
                    ("0" * 64, document_key(path)),
                )
                cursor.execute(
                    "SELECT payload, checksum FROM documents WHERE path=%s",
                    (document_key(path),),
                )
                before = cursor.fetchone()
            connection.commit()
        failure = StorageError
    service._cache_time = 0
    with pytest.raises(failure):
        service.get_user_achievements(1461349028263497969)
    with pytest.raises(failure):
        service.unlock(1461349028263497969, 987654321987654321, "first_delete")
    assert service._cache == before_cache
    if backend == "json":
        assert Path(path).read_bytes() == before
    else:
        with connect_mysql() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload, checksum FROM documents WHERE path=%s",
                    (document_key(path),),
                )
                assert cursor.fetchone() == before


def test_multiple_service_instances_keep_concurrent_unlocks(
    backend, monkeypatch, initial
):
    path = achievement_service._DATA_FILE
    write_document(path, initial)
    services = [AchievementService(), AchievementService()]
    for service in services:
        service.get_user_achievements(1, 9)
    writer = achievement_service.write_document

    def slow_write(path, data):
        time.sleep(0.002)
        writer(path, data)

    monkeypatch.setattr(achievement_service, "write_document", slow_write)
    ids = list(ACHIEVEMENTS)
    with ThreadPoolExecutor(max_workers=8) as workers:
        pending = [
            workers.submit(services[index % 2].unlock, 1, 9, achievement_id)
            for index, achievement_id in enumerate(ids)
        ]
        assert all(future.result() for future in pending)
    saved = read_document(path)
    assert set(saved.pop("1")["9"]["unlocked"]) == set(ids)
    assert saved == initial


def test_concurrent_duplicate_unlock_is_recorded_once(backend):
    services = [AchievementService(), AchievementService()]
    with ThreadPoolExecutor(max_workers=8) as workers:
        pending = [
            workers.submit(services[index % 2].unlock, 1, 9, "first_edit")
            for index in range(16)
        ]
        assert sum(future.result() for future in pending) == 1
    assert read_document(achievement_service._DATA_FILE)["1"]["9"]["unlocked"] == [
        "first_edit"
    ]
