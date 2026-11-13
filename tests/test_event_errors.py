"""Storage outages inside event listeners are logged briefly, not as tracebacks."""

import logging

from src.bot import Bot
from src.utils.document_store import StorageError
from src.utils.event_errors import StorageOutageLog


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_other_errors_are_not_handled() -> None:
    log = StorageOutageLog(clock=Clock())
    assert log.report("on_message", ValueError("boom")) is False
    assert log.report("on_message", None) is False


def test_first_outage_warns_once_without_traceback(caplog) -> None:
    log = StorageOutageLog(clock=Clock())
    with caplog.at_level(logging.WARNING, logger="src.utils.event_errors"):
        assert log.report("on_message", StorageError("MySQL connection failed"))
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert "on_message" in record.getMessage()
    assert "MySQL connection failed" in record.getMessage()


def test_repeats_inside_the_window_are_counted_not_logged(caplog) -> None:
    clock = Clock()
    log = StorageOutageLog(clock=clock, window=60.0)
    with caplog.at_level(logging.WARNING, logger="src.utils.event_errors"):
        log.report("on_message", StorageError("down"))
        for _ in range(4):
            clock.now += 5
            assert log.report("on_member_join", StorageError("down"))
        assert len(caplog.records) == 1

        clock.now += 60
        assert log.report("on_message", StorageError("down"))
    assert len(caplog.records) == 2
    assert "4" in caplog.records[1].getMessage()


async def test_bot_on_error_swallows_storage_outage(caplog) -> None:
    async with Bot() as bot:
        with caplog.at_level(logging.WARNING):
            try:
                raise StorageError("MySQL connection failed")
            except StorageError:
                await bot.on_error("on_message", object())
    assert not any(r.exc_info for r in caplog.records)
    assert any("on_message" in r.getMessage() for r in caplog.records)


async def test_bot_on_error_still_logs_other_errors(caplog) -> None:
    async with Bot() as bot:
        with caplog.at_level(logging.ERROR, logger="discord.client"):
            try:
                raise ValueError("real bug")
            except ValueError:
                await bot.on_error("on_message", object())
    assert any(r.exc_info for r in caplog.records)
