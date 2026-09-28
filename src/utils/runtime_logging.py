"""Keep diagnostic I/O off the Discord event loop and heartbeat thread."""

from contextlib import contextmanager
import logging
from logging.handlers import QueueHandler
from logging.handlers import QueueListener
from logging.handlers import RotatingFileHandler
from pathlib import Path
import queue


class GatewayTracebackFilter(logging.Filter):
    """Treat gateway stack source lines as data, not %-format placeholders."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "discord.gateway" and isinstance(record.msg, str):
            header, separator, stack = record.msg.partition("\nLoop thread traceback")
            if (
                separator
                and "heartbeat blocked for more than" in header
                and record.args
            ):
                record.msg = (header % record.args) + separator + stack
                record.args = ()
        return True


class NonBlockingQueueHandler(QueueHandler):
    """Drop overflow rather than block or write errors to a stalled console."""

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass


@contextmanager
def runtime_logging(directory: str = "data/logs"):
    """Write bounded, rotating logs on a background worker."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    sink = RotatingFileHandler(
        Path(directory) / "runtime.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    sink.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    pending = queue.Queue(maxsize=4096)
    handler = NonBlockingQueueHandler(pending)
    handler.addFilter(GatewayTracebackFilter())
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    listener = QueueListener(pending, sink)
    listener.start()
    try:
        yield
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)
        # Make room for QueueListener's non-blocking shutdown sentinel.
        if pending.full():
            try:
                pending.get_nowait()
            except queue.Empty:
                pass
        listener.stop()
        handler.close()
        sink.close()
