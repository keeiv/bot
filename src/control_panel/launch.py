"""Step-by-step sequences: opening the panel, starting, restarting, the database.

A :class:`Run` is a list of steps worked through on a background thread while
the launch screen draws their progress. The same pieces serve every sequence,
so what the animation shows is exactly what is being checked or done.
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
import threading
import time
from typing import Optional

import psutil  # type: ignore[import-untyped]  # no typing metadata

from src.control_panel import actions
from src.control_panel import database
from src.control_panel.actions import Outcome
from src.control_panel.host import HostReader
from src.control_panel.state import Paths
from src.control_panel.state import StatusReader

PENDING, RUNNING, OK, WARN, FAIL, SKIP = (
    "pending",
    "running",
    "ok",
    "warn",
    "fail",
    "skip",
)
MEMORY_WARN_PERCENT = 90.0


@dataclass
class Step:
    key: str
    label: str
    state: str = PENDING
    detail: str = ""


class Run:
    """A sequence of steps and where it has got to. Safe to read while it runs."""

    def __init__(self, title: str, steps: list[Step]) -> None:
        self.title = title
        self._steps = steps
        self._lock = threading.Lock()
        self.outcome: Optional[Outcome] = None
        self.started_at = time.monotonic()
        self.finished_at: Optional[float] = None

    def begin(self, key: str, detail: str = "") -> None:
        self._set(key, RUNNING, detail)

    def finish(self, key: str, state: str, detail: str = "") -> None:
        self._set(key, state, detail)

    def note(self, key: str, detail: str) -> None:
        with self._lock:
            self._find(key).detail = detail

    def _set(self, key: str, state: str, detail: str) -> None:
        with self._lock:
            step = self._find(key)
            step.state = state
            if detail or state != RUNNING:
                step.detail = detail

    def _find(self, key: str) -> Step:
        for step in self._steps:
            if step.key == key:
                return step
        raise KeyError(key)

    def skip_rest(self, reason: str = "已略過") -> None:
        with self._lock:
            for step in self._steps:
                if step.state == PENDING:
                    step.state, step.detail = SKIP, reason

    def close(self, outcome: Outcome) -> None:
        with self._lock:
            self.outcome = outcome
            self.finished_at = time.monotonic()

    @property
    def finished(self) -> bool:
        return self.outcome is not None

    def snapshot(self) -> list[Step]:
        with self._lock:
            return [Step(s.key, s.label, s.state, s.detail) for s in self._steps]

    @property
    def progress(self) -> float:
        steps = self.snapshot()
        done = sum(1 for s in steps if s.state not in (PENDING, RUNNING))
        return done / len(steps) if steps else 1.0


@dataclass
class Context:
    paths: Paths
    reader: StatusReader
    host: HostReader
    settings: database.DbSettings
    monitor: Optional[database.DatabaseMonitor] = None
    pause: float = 0.15  # a beat between steps so the animation can be followed
    sleep: Callable[[float], None] = time.sleep
    stop: Callable[..., Outcome] = actions.stop_bot
    start: Callable[..., Outcome] = actions.start_bot
    ensure: Callable[..., database.EnsureResult] = database.ensure_database
    memory: Callable[[], tuple[float, float]] = field(
        default=lambda: (
            psutil.virtual_memory().total / 1024**3,
            psutil.virtual_memory().percent,
        )
    )


# ── building the lists ────────────────────────────────────────────
def _hardware() -> list[Step]:
    return [
        Step("host", "主機型號"),
        Step("cpu", "處理器"),
        Step("gpu", "顯示卡"),
        Step("memory", "記憶體"),
    ]


def open_run() -> Run:
    return Run("控制台啟動中", [*_hardware(), Step("db", "資料庫")])


def start_run(*, restart: bool = False) -> Run:
    steps = [Step("stop", "停止機器人")] if restart else []
    steps += [
        *_hardware(),
        Step("env", "環境設定"),
        Step("db", "資料庫"),
        Step("lock", "鎖定檔"),
        Step("launch", "啟動機器人"),
    ]
    return Run("正在重新啟動機器人" if restart else "正在啟動機器人", steps)


def database_run() -> Run:
    return Run("正在檢查資料庫", [Step("db", "資料庫")])


# ── the steps ─────────────────────────────────────────────────────
def _beat(ctx: Context) -> None:
    if ctx.pause:
        ctx.sleep(ctx.pause)


def _hardware_steps(run: Run, ctx: Context) -> None:
    run.begin("host")
    info = ctx.host.wait(6.0)
    if info is None:
        run.finish("host", WARN, "讀取逾時")
        for key in ("cpu", "gpu"):
            run.finish(key, SKIP, "")
    else:
        run.finish("host", OK, f"{info.model_line} · {info.os_name}")
        _beat(ctx)
        run.begin("cpu")
        _beat(ctx)
        shape = f" · {info.cores} 核心 {info.threads} 執行緒" if info.cores else ""
        run.finish("cpu", OK if info.cpu else SKIP, f"{info.cpu}{shape}" or "")
        _beat(ctx)
        run.begin("gpu")
        _beat(ctx)
        if info.gpus:
            run.finish("gpu", OK, " ／ ".join(info.gpus))
        else:
            run.finish("gpu", SKIP, "沒有偵測到")
    _beat(ctx)
    run.begin("memory")
    total, percent = ctx.memory()
    state = WARN if percent >= MEMORY_WARN_PERCENT else OK
    note = "，偏高" if state == WARN else ""
    run.finish("memory", state, f"{total:.0f} GB · 已使用 {percent:.0f}%{note}")
    _beat(ctx)


def _environment_step(run: Run, ctx: Context) -> bool:
    run.begin("env")
    env_file = (ctx.paths.root / ".env").is_file()
    if not database.has_discord_token(ctx.paths.root):
        where = "找不到 .env 檔" if not env_file else ".env 裡沒有 DISCORD_TOKEN"
        run.finish("env", FAIL, f"{where}，機器人無法登入 Discord")
        return False
    run.finish("env", OK, ".env 與 DISCORD_TOKEN 都在")
    _beat(ctx)
    return True


def _database_step(run: Run, ctx: Context, *, required: bool) -> bool:
    """Check the database and start it if it is not running. False = stop here."""
    run.begin("db", "檢查中…")
    result = ctx.ensure(
        ctx.settings,
        on_starting=lambda: run.note("db", "沒有回應，正在啟動資料庫…"),
    )
    status = result.status
    if ctx.monitor:
        ctx.monitor.update(status)
    if status.state == "disabled":
        run.finish("db", SKIP, status.detail)
        return True
    if status.state == "ready":
        suffix = "（剛剛自動啟動）" if result.started else ""
        run.finish("db", OK, f"{status.detail}{suffix}")
        _beat(ctx)
        return True
    reason = result.message or status.detail
    if status.state == "down":
        run.finish("db", FAIL if required else WARN, f"沒有執行：{reason}")
        return not required
    # The server answers but refuses the bot: say why, and let the bot decide.
    run.finish("db", WARN, f"伺服器有回應，但無法登入：{status.detail}")
    return True


def _lock_step(run: Run, ctx: Context) -> bool:
    run.begin("lock")
    status = ctx.reader.read()
    if status.state == "running":
        run.finish("lock", FAIL, f"機器人已在執行（PID {status.pid}）")
        return False
    if status.state == "stale":
        ctx.paths.lock.unlink(missing_ok=True)
        run.finish("lock", OK, "已清除過期的鎖定檔")
    else:
        run.finish("lock", OK, "沒有第二份機器人")
    _beat(ctx)
    return True


def _fail(run: Run, message: str) -> None:
    run.skip_rest()
    run.close(Outcome(False, message))


def _failed_detail(run: Run, key: str, fallback: str) -> str:
    for step in run.snapshot():
        if step.key == key and step.detail:
            return step.detail
    return fallback


def run_open(run: Run, ctx: Context) -> None:
    """First opening of the panel: read the hardware, bring the database up."""
    _hardware_steps(run, ctx)
    if not _database_step(run, ctx, required=False):
        run.close(Outcome(False, _failed_detail(run, "db", "資料庫沒有執行")))
        return
    run.close(Outcome(True, "準備完成"))


def run_start(run: Run, ctx: Context, *, restart: bool = False) -> None:
    if restart:
        run.begin("stop")
        status = ctx.reader.read()
        if status.state == "stopped":
            run.finish("stop", SKIP, "本來就沒有在執行")
        else:
            stopped = ctx.stop(ctx.paths, status)
            if not stopped.ok and ctx.reader.read().state == "running":
                run.finish("stop", FAIL, stopped.message)
                return _fail(run, stopped.message)
            run.finish("stop", OK, stopped.message)
            ctx.sleep(1.0 if ctx.pause else 0)
    _hardware_steps(run, ctx)
    if not _environment_step(run, ctx):
        return _fail(run, _failed_detail(run, "env", "環境設定不完整"))
    if not _database_step(run, ctx, required=True):
        return _fail(run, _failed_detail(run, "db", "資料庫沒有執行"))
    if not _lock_step(run, ctx):
        return _fail(run, _failed_detail(run, "lock", "機器人已在執行"))
    run.begin("launch", "在新視窗啟動，等待初始化…")
    outcome = ctx.start(ctx.paths, ctx.reader)
    run.finish("launch", OK if outcome.ok else FAIL, outcome.message)
    run.close(outcome)


def run_database(run: Run, ctx: Context) -> None:
    ok = _database_step(run, ctx, required=True)
    detail = _failed_detail(run, "db", "")
    state = [s for s in run.snapshot() if s.key == "db"][0].state
    run.close(Outcome(ok and state in (OK, SKIP), detail))


def execute(run: Run, ctx: Context, work: Callable[[Run, Context], None]) -> None:
    """Run ``work`` and make sure the run always ends, whatever happens inside."""
    try:
        work(run, ctx)
    except Exception as exc:  # shown on the launch screen, never fatal
        run.skip_rest()
        run.close(Outcome(False, f"發生錯誤：{type(exc).__name__}: {exc}"))
    if not run.finished:
        run.close(Outcome(True, ""))


def spawn(run: Run, ctx: Context, work: Callable[[Run, Context], None]) -> Run:
    threading.Thread(target=execute, args=(run, ctx, work), daemon=True).start()
    return run
