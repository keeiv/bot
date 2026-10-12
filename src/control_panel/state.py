"""What the panel shows: the bot process and the tail of its log.

Everything here only reads. Nothing starts, stops or imports the bot.
"""

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
import ntpath
import os
from pathlib import Path
import re
import sys
import threading
from typing import Optional, TypeVar

import psutil  # type: ignore[import-untyped]  # no typing metadata

T = TypeVar("T")

RECENT_WINDOW = timedelta(minutes=5)

LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

_RECORD = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?:,\d+)? "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) (?P<logger>[^:\s]+): "
    r"(?P<message>.*)$"
)


@dataclass(frozen=True)
class Paths:
    root: Path
    lock: Path
    logs: Path
    python: str

    @property
    def runtime_log(self) -> Path:
        return self.logs / "runtime.log"


def find_python(root: Path) -> str:
    """The project's virtualenv Python, or the one running the panel."""
    for venv in (".venv", "venv"):
        candidate = root / venv / "Scripts" / "python.exe"
        if candidate.is_file():
            return str(candidate)
        candidate = root / venv / "bin" / "python"
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def project_paths(root: Optional[Path] = None) -> Paths:
    root = root or Path(__file__).resolve().parents[2]
    return Paths(
        root=root,
        lock=root / "bot.lock",
        logs=root / "data" / "logs",
        python=find_python(root),
    )


# ── bot process ───────────────────────────────────────────────────
def read_lock_pid(lock: Path) -> Optional[int]:
    try:
        text = lock.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


BOT = "bot"  # this project's bot, verified
OTHER = "other"  # some other program (a reused PID, another project's bot)
UNKNOWN = "unknown"  # cannot be told (access denied)

_PYTHON_EXE = re.compile(r"^(pythonw?(\d+(\.\d+)*)?|pyw?)(\.exe)?$", re.IGNORECASE)


def _same_path(first: str, second: str) -> bool:
    # These are Windows processes' paths: compare them the way Windows does
    # (either slash, any case), whichever system runs this code.
    def normal(path: str) -> str:
        return ntpath.normcase(ntpath.normpath(path))

    return normal(first) == normal(second)


def _is_absolute(path: str) -> bool:
    """A drive or a leading slash names a fixed place, not one under the cwd.

    ``ntpath.isabs`` stopped counting a path without a drive as absolute in
    Python 3.13, so the rule is spelled out here.
    """
    return ntpath.splitdrive(path)[1].startswith(("/", "\\"))


def classify_process(cmdline: Sequence[str], cwd: Optional[str], root: Path) -> str:
    """Is this process *this project's* bot?

    The bot runs as ``python -m src.main`` from the project folder (or
    ``python <project>/src/main.py``). A leftover lock file can name a PID that
    Windows later gave to another program, and this machine also runs other
    projects with their own ``src/main.py``. So the executable must be Python,
    the module or script must be exactly ``src.main`` / ``src/main.py``, and it
    must belong to ``root``. When that cannot be established because the
    command line or working directory is unreadable, the answer is UNKNOWN,
    never a guess.
    """
    args = list(cmdline)
    if not args:
        return UNKNOWN
    if not _PYTHON_EXE.match(os.path.basename(args[0].replace("\\", "/"))):
        return OTHER
    module = script = None
    index = 1
    while index < len(args):
        arg = args[index]
        if arg in ("-X", "-W"):
            index += 2
        elif arg == "-m":
            module = args[index + 1] if index + 1 < len(args) else ""
            break
        elif arg == "-c":
            return OTHER
        elif arg.startswith("-"):
            index += 1
        else:
            script = arg
            break
    if module is not None:
        if module != "src.main":
            return OTHER
        if cwd is None:
            return UNKNOWN
        return BOT if _same_path(cwd, str(root)) else OTHER
    if script is None:
        return OTHER
    absolute = _is_absolute(script)
    if not absolute and cwd is None:
        return UNKNOWN
    full = script if absolute else ntpath.join(cwd or "", script)
    return BOT if _same_path(full, str(root / "src" / "main.py")) else OTHER


@dataclass(frozen=True)
class BotStatus:
    state: str  # "running", "stopped" or "stale"
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    cpu_percent: Optional[float] = None
    rss_mb: Optional[float] = None
    threads: Optional[int] = None
    cmdline: str = ""
    # False when the PID is alive but could not be confirmed to be the bot
    # (for example the bot runs elevated and the panel does not).
    verified: bool = True


def _read(function: Callable[[], T]) -> Optional[T]:
    """A process detail, or None when Windows refuses to share it."""
    try:
        return function()
    except psutil.AccessDenied:
        return None


class StatusReader:
    """Reads the bot's status. Keeps the ``Process`` so CPU % has a baseline."""

    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self._process: Optional[psutil.Process] = None
        # The screen and a start-up sequence read the status from two threads.
        self._lock = threading.Lock()

    def read(self) -> BotStatus:
        with self._lock:
            return self._read_locked()

    def _read_locked(self) -> BotStatus:
        pid = read_lock_pid(self.paths.lock)
        if pid is None:
            return BotStatus("stopped")
        try:
            if self._process is None or self._process.pid != pid:
                self._process = psutil.Process(pid)
            process = self._process
            if not process.is_running():
                return BotStatus("stale", pid)
            if _read(process.status) == psutil.STATUS_ZOMBIE:
                return BotStatus("stale", pid)
            cmdline = _read(process.cmdline) or []
            verdict = classify_process(cmdline, _read(process.cwd), self.paths.root)
            if verdict == OTHER:
                return BotStatus("stale", pid)
            # BOT or UNKNOWN: the process is alive. An unreadable one must never
            # be called stale, or the panel would start a second bot beside it.
            with process.oneshot():
                created = _read(process.create_time)
                memory = _read(process.memory_info)
                return BotStatus(
                    "running",
                    pid,
                    datetime.fromtimestamp(created) if created else None,
                    _read(lambda: process.cpu_percent(None)),
                    memory.rss / (1024 * 1024) if memory else None,
                    _read(process.num_threads),
                    " ".join(cmdline),
                    verified=verdict == BOT,
                )
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            self._process = None
            return BotStatus("stale", pid)


# ── log tail ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class LogRecord:
    time: str
    level: str
    logger: str
    message: str
    extra_lines: int = 0  # traceback lines that followed this record
    count: int = 1  # how many identical records this one stands for
    when: Optional[datetime] = None


def parse_records(lines: Sequence[str]) -> list[LogRecord]:
    """Group raw lines into records; unmatched lines continue the previous one."""
    records: list[LogRecord] = []
    for line in lines:
        match = _RECORD.match(line)
        if match:
            try:
                when: Optional[datetime] = datetime.fromisoformat(
                    f"{match['date']} {match['time']}"
                )
            except ValueError:
                when = None
            records.append(
                LogRecord(
                    match["time"],
                    match["level"],
                    match["logger"],
                    match["message"],
                    when=when,
                )
            )
        elif records and line.strip():
            records[-1] = replace(records[-1], extra_lines=records[-1].extra_lines + 1)
    return records


def tail_records(
    path: Path,
    count: int,
    *,
    min_level: str = "DEBUG",
    max_bytes: int = 262_144,
) -> list[LogRecord]:
    """The last ``count`` records at or above ``min_level``."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(size - max_bytes, 0))
            raw = handle.read()
    except OSError:
        return []
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]  # the first line is probably cut in half
    threshold = LEVEL_ORDER.get(min_level, 0)
    records = [
        record
        for record in parse_records(lines)
        if LEVEL_ORDER.get(record.level, 0) >= threshold
    ]
    return records[-count:] if count > 0 else []


def collapse_records(records: Sequence[LogRecord]) -> list[LogRecord]:
    """Fold repeated records into one line with a count.

    Identical records (same level, logger and message) become a single entry at
    the position of the *latest* occurrence, so a warning that repeats every two
    seconds stays one line and the newer events below it remain visible.
    """
    merged: dict[tuple[str, str, str], LogRecord] = {}
    for record in records:
        key = (record.level, record.logger, record.message)
        earlier = merged.pop(key, None)
        if earlier is not None:
            record = replace(record, count=earlier.count + record.count)
        merged[key] = record
    return list(merged.values())


def recent_events(
    path: Path, count: int, *, min_level: str = "DEBUG", raw: int = 400
) -> list[LogRecord]:
    """The last ``count`` distinct events: repeats are folded into one line."""
    records = tail_records(path, raw, min_level=min_level)
    return collapse_records(records)[-count:] if count > 0 else []


def short_logger(name: str) -> str:
    """``src.utils.lang_context`` -> ``lang_context``; ``discord.gateway`` stays."""
    parts = name.split(".")
    if parts[0] == "src" and len(parts) > 1:
        return parts[-1]
    return name


def format_duration(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    days, rest = divmod(seconds, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@dataclass(frozen=True)
class LogSummary:
    """What the log says right now: distinct recent events and recent trouble."""

    events: list[LogRecord]
    warnings: int = 0  # warnings in the last few minutes (repeats counted)
    errors: int = 0


def summarise_log(
    path: Path,
    now: datetime,
    *,
    rows: int = 60,
    window: timedelta = RECENT_WINDOW,
    raw: int = 600,
) -> LogSummary:
    """Read the log once: folded events for display, plus recent warning counts."""
    records = tail_records(path, raw)
    since = now - window
    warnings = errors = 0
    for record in records:
        if record.when is None or record.when < since:
            continue
        if record.level == "WARNING":
            warnings += record.count
        elif record.level in ("ERROR", "CRITICAL"):
            errors += record.count
    return LogSummary(collapse_records(records)[-rows:], warnings, errors)
