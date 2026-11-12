"""Background loops survive a bad round.

discord.ext.tasks stops a loop for good once its body raises. In October 2026
the daily check-in loop died three times on a MySQL blip and stayed dead until
the next restart, so these loops must swallow and log a failed round.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.cogs.core import system_maintenance
from src.cogs.core.system_maintenance import SystemMaintenance
from src.cogs.features import genshin_cog
from src.cogs.features import giveaway
from src.cogs.features.genshin_cog import GenshinCog
from src.cogs.features.giveaway import Giveaway
from src.services.giveaway_service import ANNOUNCE_TRIES
from src.utils.document_store import StorageError


class SigninService:
    def __init__(self, *, last="", fail_read=False, fail_run=False):
        self.last = last
        self.fail_read = fail_read
        self.fail_run = fail_run
        self.saved = []
        self.runs = 0

    def get_last_signin_date(self):
        if self.fail_read:
            raise StorageError("MySQL connection failed; JSON fallback is disabled")
        return self.last

    def save_last_signin_date(self, day):
        self.saved.append(day)
        self.last = day

    async def run_global_auto_sign_in(self):
        self.runs += 1
        if self.fail_run:
            raise RuntimeError("interrupted")
        return {7: [{"game": "genshin"}]}


def signin_cog(service, monkeypatch, hour=9):
    cog = object.__new__(GenshinCog)
    cog.bot = SimpleNamespace()
    cog.service = service
    cog._send_signin_report = AsyncMock()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 11, hour, 0, tzinfo=tz)

    monkeypatch.setattr(genshin_cog, "datetime", Clock)
    return cog


async def signin_round(cog):
    await GenshinCog._auto_signin_loop.coro(cog)


async def test_signin_round_survives_a_storage_failure(monkeypatch):
    service = SigninService(fail_read=True)
    cog = signin_cog(service, monkeypatch)

    await signin_round(cog)  # must not raise: a raise ends the loop for good

    service.fail_read = False
    await signin_round(cog)
    assert service.runs == 1
    assert service.saved == ["2026-11-11"]
    cog._send_signin_report.assert_awaited_once()


async def test_signin_day_is_marked_only_after_the_run_finishes(monkeypatch):
    service = SigninService(fail_run=True)
    cog = signin_cog(service, monkeypatch)

    await signin_round(cog)
    assert service.saved == []  # an interrupted run is not "done for today"

    service.fail_run = False
    await signin_round(cog)
    assert service.saved == ["2026-11-11"]


async def test_signin_runs_once_a_day_even_if_the_date_cannot_be_saved(monkeypatch):
    service = SigninService()

    def broken_save(day):
        raise StorageError("MySQL commit failed")

    service.save_last_signin_date = broken_save
    cog = signin_cog(service, monkeypatch)

    await signin_round(cog)
    await signin_round(cog)

    assert service.runs == 1  # no second round of DMs half an hour later
    cog._send_signin_report.assert_awaited_once()


async def test_signin_waits_for_eight(monkeypatch):
    service = SigninService()
    cog = signin_cog(service, monkeypatch, hour=7)
    await signin_round(cog)
    assert service.runs == 0


class GiveawayService:
    def __init__(self, expired, fail=False):
        self.expired = expired
        self.fail = fail
        self.reopened = []

    def check_expired(self):
        if self.fail:
            raise StorageError("MySQL connection failed; JSON fallback is disabled")
        return self.expired

    def reopen(self, giveaway_id):
        self.reopened.append(giveaway_id)

    def pending_announcements(self):
        return []


def giveaway_cog(service):
    cog = object.__new__(Giveaway)
    cog.bot = SimpleNamespace(wait_until_ready=AsyncMock())
    cog.service = service
    return cog


async def test_giveaway_round_survives_a_storage_failure():
    cog = giveaway_cog(GiveawayService([], fail=True))
    await Giveaway.check_giveaways.coro(cog)


async def test_one_failed_giveaway_does_not_block_the_rest():
    service = GiveawayService([("a", {"prize": "A"}), ("b", {"prize": "B"})])
    cog = giveaway_cog(service)
    ended = []

    async def end(giveaway_id, ga):
        if giveaway_id == "a":
            raise StorageError("MySQL commit failed")
        ended.append(giveaway_id)

    cog._end_giveaway = end
    await Giveaway.check_giveaways.coro(cog)

    assert ended == ["b"]
    # The draw that could not be stored is tried again next round.
    assert service.reopened == ["a"]


async def test_a_broken_record_is_not_retried_forever():
    service = GiveawayService([("a", {})])
    cog = giveaway_cog(service)
    cog._end_giveaway = AsyncMock(side_effect=KeyError("guild_id"))
    await Giveaway.check_giveaways.coro(cog)
    assert service.reopened == []


def test_reopen_puts_an_unsettled_giveaway_back(monkeypatch):
    service = object.__new__(giveaway.GiveawayService)
    data = {
        "a": {"ended": True, "winner_ids": []},
        "b": {"ended": True, "winner_ids": ["1"]},
        "c": {"ended": True, "winner_ids": [], "settled": True},
    }
    monkeypatch.setattr(service, "_load", lambda: data, raising=False)
    saved = []
    monkeypatch.setattr(service, "_save", saved.append, raising=False)

    service.reopen("a")
    service.reopen("b")  # already drawn: stays ended
    service.reopen("c")  # settled with nobody in it: stays ended
    service.reopen("missing")

    assert data["a"]["ended"] is False
    assert data["b"]["ended"] is True
    assert data["c"]["ended"] is True
    assert len(saved) == 1


def maintenance(monkeypatch, *, host, own):
    cog = object.__new__(SystemMaintenance)
    cog.memory_threshold = 80.0
    cog.process_memory_threshold = 25.0
    cog.cpu_threshold = 80.0
    cog._memory_pressure = False
    cog.perform_emergency_cleanup = AsyncMock()
    monkeypatch.setattr(
        system_maintenance.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(percent=host),
    )
    monkeypatch.setattr(system_maintenance.psutil, "cpu_percent", lambda _: 5.0)
    monkeypatch.setattr(
        system_maintenance.psutil,
        "Process",
        lambda: SimpleNamespace(
            memory_percent=lambda: own,
            memory_info=lambda: SimpleNamespace(rss=111 * 1024 * 1024),
        ),
    )
    return cog


async def test_a_full_host_does_not_empty_the_bots_caches(monkeypatch, caplog):
    """The host sat above 80% for weeks while the bot used 111 MB of 15 GB."""
    cog = maintenance(monkeypatch, host=98.2, own=0.7)
    with caplog.at_level("WARNING"):
        await cog.check_system_health()
        await cog.check_system_health()

    cog.perform_emergency_cleanup.assert_not_awaited()
    # Said once when it starts, not every half hour.
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 1


async def test_the_bots_own_memory_still_triggers_a_cleanup(monkeypatch):
    cog = maintenance(monkeypatch, host=98.2, own=31.0)
    await cog.check_system_health()
    cog.perform_emergency_cleanup.assert_awaited_once()


@pytest.mark.parametrize("host", [50.0])
async def test_memory_warning_returns_after_recovery(monkeypatch, caplog, host):
    cog = maintenance(monkeypatch, host=98.2, own=0.7)
    with caplog.at_level("WARNING"):
        await cog.check_system_health()
        monkeypatch.setattr(
            system_maintenance.psutil,
            "virtual_memory",
            lambda: SimpleNamespace(percent=host),
        )
        await cog.check_system_health()
        monkeypatch.setattr(
            system_maintenance.psutil,
            "virtual_memory",
            lambda: SimpleNamespace(percent=98.2),
        )
        await cog.check_system_health()
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 2


def test_nobody_joins_or_leaves_after_the_deadline(monkeypatch):
    """A reopened draw is past its end time and must keep the list it had."""
    service = object.__new__(giveaway.GiveawayService)
    data = {
        "late": {"ended": False, "end_time": 1.0, "participants": ["1"]},
        "open": {"ended": False, "end_time": 4102444800.0, "participants": []},
    }
    monkeypatch.setattr(service, "_load", lambda: data, raising=False)
    monkeypatch.setattr(service, "_save", lambda _: None, raising=False)

    assert service.toggle_participant("late", "2") == (None, 0)
    assert service.toggle_participant("late", "1") == (None, 0)
    assert data["late"]["participants"] == ["1"]
    assert service.toggle_participant("open", "2") == ("joined", 1)


def stored_giveaways(monkeypatch, data):
    service = object.__new__(giveaway.GiveawayService)
    monkeypatch.setattr(service, "_load", lambda: data, raising=False)
    monkeypatch.setattr(service, "_save", lambda _: None, raising=False)
    return service


def test_a_draw_cut_short_is_picked_up_on_the_next_check(monkeypatch):
    """Closed by one check, then the bot stopped before the winners were stored."""
    data = {
        "due": {"ended": False, "end_time": 1.0, "participants": ["1"]},
        "old": {"ended": True, "winner_ids": []},  # ended before drawing was tracked
    }
    service = stored_giveaways(monkeypatch, data)
    assert [gid for gid, _ in service.check_expired()] == ["due"]
    assert data["due"]["drawing"] is True
    # The restart: nothing settled it, so the next check returns it again.
    assert [gid for gid, _ in service.check_expired()] == ["due"]
    service.mark_ended("due", ["1"])
    assert "drawing" not in data["due"]
    assert service.check_expired() == []


def test_an_unposted_result_is_retried_a_few_times_then_left(monkeypatch):
    data = {"a": {"ended": False, "end_time": 1.0, "participants": ["1"]}}
    service = stored_giveaways(monkeypatch, data)
    service.mark_ended("a", ["1"])
    assert [gid for gid, _ in service.pending_announcements()] == ["a"]
    for _ in range(ANNOUNCE_TRIES):
        service.mark_announced("a", False)
    assert service.pending_announcements() == []
    data["a"]["announce_tries"] = 0
    service.mark_announced("a", True)
    assert service.pending_announcements() == []


async def test_a_failed_post_is_counted_instead_of_swallowed(monkeypatch):
    data = {
        "a": {
            "ended": False,
            "end_time": 1.0,
            "participants": ["1"],
            "winners": 1,
            "guild_id": 5,
            "channel_id": 6,
            "message_id": 7,
            "prize": "P",
            "host_id": 8,
        }
    }
    service = stored_giveaways(monkeypatch, data)
    monkeypatch.setattr(service, "get", lambda gid: data.get(gid), raising=False)

    async def english(_):
        return "en"

    monkeypatch.setattr("src.cogs.features.giveaway.guild_language", english)
    cog = object.__new__(Giveaway)
    cog.service = service
    cog.bot = SimpleNamespace(
        wait_until_ready=AsyncMock(),
        get_channel=lambda _: None,
        fetch_channel=AsyncMock(side_effect=RuntimeError("channel gone")),
    )
    await Giveaway.check_giveaways.coro(cog)
    assert data["a"]["winner_ids"] == ["1"]
    assert data["a"]["announced"] is False
    # One try in the drawing round, one more from the retry pass of the same round.
    assert data["a"]["announce_tries"] == 2
