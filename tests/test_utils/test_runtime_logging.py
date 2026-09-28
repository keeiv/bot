import logging
from logging.handlers import QueueListener
import queue
import threading

from src.utils.runtime_logging import GatewayTracebackFilter
from src.utils.runtime_logging import NonBlockingQueueHandler
from src.utils.runtime_logging import runtime_logging


def test_gateway_stack_percent_is_literal():
    stack = (
        '\nLoop thread traceback (most recent call last):\nprint(f"{memory}% %s %(x)s")'
    )
    record = logging.LogRecord(
        "discord.gateway",
        logging.WARNING,
        "",
        0,
        "Shard ID %s heartbeat blocked for more than %s seconds." + stack,
        (None, 10),
        None,
    )
    GatewayTracebackFilter().filter(record)
    assert (
        record.getMessage()
        == "Shard ID None heartbeat blocked for more than 10 seconds." + stack
    )


def test_slow_sink_does_not_block_producer():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class SlowSink(logging.Handler):
        def emit(self, record):
            entered.set()
            release.wait(5)

    pending = queue.Queue(maxsize=1)
    handler = NonBlockingQueueHandler(pending)
    listener = QueueListener(pending, SlowSink())
    record = logging.makeLogRecord({"msg": "test"})
    listener.start()
    try:
        handler.handle(record)
        assert entered.wait(1)

        def produce():
            for _ in range(100):
                handler.handle(record)
            finished.set()

        worker = threading.Thread(target=produce, daemon=True)
        worker.start()
        assert finished.wait(1)
    finally:
        pending.get(timeout=2)
        release.set()
        listener.stop()


def test_runtime_file_and_handler_restoration(tmp_path):
    root = logging.getLogger()
    original = root.handlers[:]
    with runtime_logging(str(tmp_path)):
        logging.getLogger("discord.gateway").warning(
            'Shard ID %s heartbeat blocked for more than %s seconds.\nLoop thread traceback:\nprint("80%%")',
            None,
            10,
        )
    assert root.handlers == original
    assert 'print("80%%")' in (tmp_path / "runtime.log").read_text(encoding="utf-8")
