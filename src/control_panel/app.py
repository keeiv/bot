"""The interactive loop: keys in, screens out."""

import atexit
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
import sys
import threading
import time
from typing import Optional

import psutil  # type: ignore[import-untyped]  # no typing metadata
from rich.console import Console
from rich.console import RenderableType
from rich.live import Live

from src.control_panel import actions
from src.control_panel import ai_usage
from src.control_panel import database
from src.control_panel import launch
from src.control_panel import menu
from src.control_panel import render
from src.control_panel import theme
from src.control_panel.host import HostInfo
from src.control_panel.host import HostReader
from src.control_panel.state import Paths
from src.control_panel.state import project_paths
from src.control_panel.state import recent_events
from src.control_panel.state import StatusReader
from src.control_panel.state import summarise_log

TICK = 1.0  # how often status and log are re-read
HOLD_OK_SECONDS = 1.5  # how long a clean start-up screen stays before closing
HOLD_WARN_SECONDS = 3.5  # the same when opening the panel and a check only warned
NOTICE_SECONDS = 8.0


# ── keyboard ──────────────────────────────────────────────────────
class Keyboard:
    """Source of normalised keys: ``up`` ``down`` ``enter`` ``esc`` or one char."""

    def poll(self, timeout: float) -> Optional[str]:
        raise NotImplementedError

    @contextmanager
    def cooked(self) -> Iterator[None]:
        """Normal console input (Ctrl+C interrupts) while a child program runs."""
        yield

    def close(self) -> None:
        """Give the console back exactly as it was found."""


_ENABLE_PROCESSED_INPUT = 0x0001


class WindowsKeyboard(Keyboard):
    """Reads keys with ``msvcrt``.

    Ctrl+C normally reaches every program on the console as a signal; cmd then
    asks "Terminate batch job (Y/N)?" while the launcher is still running. The
    panel switches that signal off so Ctrl+C arrives as an ordinary key, and
    switches it back on for child programs and when it exits.
    """

    def __init__(self) -> None:
        import ctypes
        import msvcrt

        self._msvcrt = msvcrt
        self._kernel = ctypes.windll.kernel32
        self._handle = self._kernel.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        self._usable = bool(
            self._kernel.GetConsoleMode(self._handle, ctypes.byref(mode))
        )
        self._original = mode.value
        self._closed = False
        self._set(self._original & ~_ENABLE_PROCESSED_INPUT)
        atexit.register(self.close)

    def _set(self, mode: int) -> None:
        if self._usable:
            self._kernel.SetConsoleMode(self._handle, mode)

    @contextmanager
    def cooked(self) -> Iterator[None]:
        self._set(self._original)
        try:
            yield
        finally:
            if not self._closed:
                self._set(self._original & ~_ENABLE_PROCESSED_INPUT)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._set(self._original)

    def poll(self, timeout: float) -> Optional[str]:
        deadline = time.monotonic() + timeout
        while True:
            if self._msvcrt.kbhit():
                return self._read()
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)

    def _read(self) -> Optional[str]:
        char = self._msvcrt.getwch()
        if char in ("\x00", "\xe0"):  # arrow and function keys come in two parts
            code = self._msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(code)
        if char == "\x03":
            return "ctrl-c"
        if char == "\r":
            return "enter"
        if char == "\x1b":
            return "esc"
        return char.lower()


# ── panel ─────────────────────────────────────────────────────────
class ControlPanel:
    def __init__(
        self,
        console: Console,
        keyboard: Keyboard,
        paths: Optional[Paths] = None,
        *,
        clock: Callable[[], datetime] = datetime.now,
        host: Optional[HostReader] = None,
        settings: Optional[database.DbSettings] = None,
        monitor: Optional[database.DatabaseMonitor] = None,
        boot: bool = False,
        pause: float = 0.15,
        ai_source: Optional[ai_usage.UsageSource] = None,
    ) -> None:
        self.console = console
        self.keyboard = keyboard
        self.paths = paths or project_paths()
        self.reader = StatusReader(self.paths)
        self.clock = clock
        self.host_reader = host or HostReader(HostInfo)
        self.settings = settings or database.load_settings(self.paths.root)
        if monitor is None and self.settings.enabled:
            monitor = database.DatabaseMonitor(self.settings)
        self.monitor = monitor
        self.boot = boot  # check the host and the database when first opened
        self.pause = pause
        self.selected = 0
        self.status = self.reader.read()
        self.summary = summarise_log(self.paths.runtime_log, self.clock())
        self.memory_percent: Optional[float] = None
        # Where Nova's AI usage comes from. Nothing is connected yet.
        self.ai_source: ai_usage.UsageSource = ai_source or ai_usage.NoUsageSource()
        self.ai = self.ai_source.read()
        self.notice: Optional[render.Notice] = None
        self.notice_until = 0.0
        self.busy: Optional[str] = None
        self.confirm_item: Optional[menu.MenuItem] = None
        self._spinner = 0
        self._last_tick = 0.0

    # data
    def refresh(self, *, force: bool = False) -> bool:
        """Re-read status and log at most once per tick; True if anything changed."""
        now = time.monotonic()
        changed = False
        if self.notice and now >= self.notice_until:
            self.notice = None
            changed = True
        if self.busy:
            self._spinner += 1
            changed = True
        if force or now - self._last_tick >= TICK:
            self._last_tick = now
            self.status = self.reader.read()
            self.summary = summarise_log(self.paths.runtime_log, self.clock())
            self.memory_percent = psutil.virtual_memory().percent
            try:
                self.ai = self.ai_source.read()
            except Exception:  # a broken source must not take the panel down
                self.ai = ai_usage.NO_USAGE
            changed = True
        return changed

    def say(self, kind: str, text: str) -> None:
        self.notice = render.Notice(kind, text)
        self.notice_until = time.monotonic() + NOTICE_SECONDS

    def view_state(self) -> render.ViewState:
        size = self.console.size
        return render.ViewState(
            self.paths,
            self.status,
            self.summary.events,
            self.selected,
            self.clock(),
            size.width,
            size.height,
            self.notice,
            self.busy,
            self._spinner,
            self.confirm_item.confirm if self.confirm_item else None,
            self.host_reader.info,
            self.monitor.status if self.monitor else None,
            self.settings.enabled,
            self.memory_percent,
            self.summary.warnings,
            self.summary.errors,
            ai=self.ai,
        )

    # main loop
    def run(self) -> int:
        self._set_title("BOT. 機器人控制台")
        try:
            if self.boot:
                self._show_run(launch.open_run(), launch.run_open, hold_warnings=True)
            while True:
                item = self._dashboard()
                if item is None or item.kind == "quit":
                    break
                self._execute(item)
        except KeyboardInterrupt:
            # Windows delivers Ctrl+C as a signal, not as a key press.
            pass
        self.console.print(f"[{theme.DIM}]再見。機器人不會因為關閉控制台而停止。[/]")
        return 0

    def _dashboard(self) -> Optional[menu.MenuItem]:
        """Show the dashboard until an item needs the whole terminal."""
        with Live(
            console=self.console, screen=True, auto_refresh=False, transient=True
        ) as live:
            self.refresh(force=True)
            dirty = True
            while True:
                if self.refresh():
                    dirty = True
                if dirty:
                    live.update(render.dashboard(self.view_state()), refresh=True)
                    dirty = False
                key = self.keyboard.poll(0.05)
                if key is None:
                    continue
                dirty = True
                outcome = self._on_key(key)
                if outcome is not None:
                    return outcome

    def _on_key(self, key: str) -> Optional[menu.MenuItem]:
        if key == "ctrl-c":
            return menu.BY_KEY["q"]
        if self.busy:
            return None  # a start or stop is in progress
        if self.confirm_item is not None:
            item = self.confirm_item
            self.confirm_item = None
            if key == "y":
                return self._begin(item)
            self.say("info", "已取消")
            return None
        if key in ("up", "down"):
            step = -1 if key == "up" else 1
            self.selected = (self.selected + step) % len(menu.ITEMS)
            return None
        if key == "enter":
            return self._choose(menu.ITEMS[self.selected])
        hotkey_item = menu.BY_KEY.get(key)
        if hotkey_item is not None:
            self.selected = menu.ITEMS.index(hotkey_item)
            return self._choose(hotkey_item)
        return None

    def _choose(self, item: menu.MenuItem) -> Optional[menu.MenuItem]:
        if item.confirm and self.status.state != "stopped":
            self.confirm_item = item
            return None
        return self._begin(item)

    def _begin(self, item: menu.MenuItem) -> Optional[menu.MenuItem]:
        """Stop runs in the background; everything else takes the screen."""
        if item.kind == "bg":
            self._run_background(item)
            return None
        return item

    # background actions (start, stop, restart)
    def _run_background(self, item: menu.MenuItem) -> None:
        self.busy = "正在停止機器人…"
        self.notice = None

        def work() -> None:
            try:
                outcome = self._do(item.action)
            except Exception as exc:  # shown to the user, never fatal
                outcome = actions.Outcome(False, f"發生錯誤：{exc}")
            self.busy = None
            self.say("ok" if outcome.ok else "err", outcome.message)
            self._last_tick = 0.0  # re-read the status right away

        threading.Thread(target=work, daemon=True).start()

    def _do(self, action: str) -> actions.Outcome:
        return actions.stop_bot(self.paths, self.reader.read())

    # start-up sequences: the animated launch screen
    def _context(self) -> launch.Context:
        return launch.Context(
            self.paths,
            self.reader,
            self.host_reader,
            self.settings,
            self.monitor,
            pause=self.pause,
        )

    def _run_launch(self, item: menu.MenuItem) -> None:
        if item.action == "start":
            outcome = self._show_run(launch.start_run(), launch.run_start)
        elif item.action == "restart":
            outcome = self._show_run(
                launch.start_run(restart=True),
                lambda run, ctx: launch.run_start(run, ctx, restart=True),
            )
        else:
            outcome = self._show_run(launch.database_run(), launch.run_database)
        if outcome.message:
            self.say("ok" if outcome.ok else "err", outcome.message)

    def _show_run(
        self,
        run: launch.Run,
        work: Callable[[launch.Run, launch.Context], None],
        *,
        hold_warnings: bool = False,
    ) -> actions.Outcome:
        """Draw ``run`` while it works; a clean run closes itself, a bad one waits.

        A run that only warned waits for a key, except with ``hold_warnings``
        (opening the panel): there the warning is shown for a few seconds and
        the panel opens, since the same facts stay on the dashboard.
        """
        launch.spawn(run, self._context(), work)
        with Live(
            console=self.console, screen=True, auto_refresh=False, transient=True
        ) as live:
            frame = 0
            while True:
                outcome = run.outcome
                steps = run.snapshot()
                size = self.console.size
                live.update(
                    render.launch_screen(
                        run.title,
                        steps,
                        (outcome.ok, outcome.message) if outcome else None,
                        progress=run.progress,
                        elapsed=time.monotonic() - run.started_at,
                        spinner=frame,
                        width=size.width,
                        height=size.height,
                    ),
                    refresh=True,
                )
                frame += 1
                key = self.keyboard.poll(0.06)
                if outcome is None or run.finished_at is None:
                    continue  # keys mean nothing until the run is over
                failed = any(s.state == launch.FAIL for s in steps)
                warned = any(s.state == launch.WARN for s in steps)
                waited = time.monotonic() - run.finished_at
                if not outcome.ok or failed:
                    closes_itself = False
                elif warned:
                    closes_itself = hold_warnings and waited >= HOLD_WARN_SECONDS
                else:
                    closes_itself = waited >= HOLD_OK_SECONDS
                if key is not None or closes_itself:
                    self._last_tick = 0.0  # re-read everything on return
                    return outcome

    # items that take over the terminal
    def _execute(self, item: menu.MenuItem) -> None:
        if item.kind == "launch":
            self._run_launch(item)
        elif item.action == "host":
            self._page(self._host_page, None)
        elif item.action == "status":
            self._page(self._status_page, None)
        elif item.action == "guide":
            self._page(self._guide_page, None)
        elif item.action == "logs":
            self._log_viewer()
        elif item.action == "worker":
            self._worker_menu("區網檔案工作站", menu.WORKER_CHOICES)
        elif item.action == "review":
            self._worker_menu("圖片審核工作站", menu.REVIEW_CHOICES)
        elif item.action in ("project", "data"):
            self._open_folders(item.action)
        else:
            self._run_in_terminal(item.action)

    def _open_folders(self, action: str) -> None:
        if action == "project":
            outcome = actions.open_folder(self.paths.root)
        else:
            actions.open_folder(self.paths.root / "data")
            outcome = actions.open_folder(self.paths.logs)
        self.say("ok" if outcome.ok else "err", outcome.message)

    def _run_in_terminal(self, name: str) -> None:
        command = actions.build_command(self.paths, name)
        width = self.console.size.width
        self.console.clear()
        self.console.print(render.command_banner(command.title, command.argv, width))
        started = time.monotonic()
        try:
            with self.keyboard.cooked():
                code = actions.run_command(self.paths, command)
        except KeyboardInterrupt:
            code = 130
        except OSError as exc:
            self.console.print(f"[{theme.ERR}]無法執行：{exc}[/]")
            code = 1
        if command.interactive and code == 0:
            return
        self.console.print(render.command_result(code, time.monotonic() - started))
        self.console.print(f"[{theme.DIM}]按任意鍵返回…[/]")
        self._wait_for_key()

    def _wait_for_key(self) -> None:
        while self.keyboard.poll(0.2) is None:
            pass

    # generic full-screen page
    def _page(
        self,
        build: Callable[[], RenderableType],
        on_key: Optional[Callable[[str], bool]],
        *,
        interval: float = 0.5,
    ) -> None:
        """Draw ``build()`` until a key is pressed (``on_key`` returns True to stay)."""
        with Live(
            console=self.console, screen=True, auto_refresh=False, transient=True
        ) as live:
            last = 0.0
            while True:
                now = time.monotonic()
                if now - last >= interval:
                    last = now
                    live.update(build(), refresh=True)
                key = self.keyboard.poll(0.05)
                if key is None:
                    continue
                if on_key is not None and on_key(key):
                    last = 0.0  # redraw at once
                    continue
                return

    def _status_page(self) -> RenderableType:
        size = self.console.size
        return render.status_detail(
            self.reader.read(), self.paths, self.clock(), size.width
        )

    def _host_page(self) -> RenderableType:
        return render.host_page(
            self.host_reader.info,
            self.paths,
            self.clock(),
            self.console.size.width,
            memory_percent=psutil.virtual_memory().percent,
        )

    def _guide_page(self) -> RenderableType:
        return render.guide_page(self.paths, self.clock(), self.console.size.width)

    def _log_viewer(self) -> None:
        state = {"warnings": False}

        def build() -> RenderableType:
            size = self.console.size
            records = recent_events(
                self.paths.runtime_log,
                max(size.height - 5, 3),
                min_level="WARNING" if state["warnings"] else "DEBUG",
            )
            return render.log_page(
                records,
                state["warnings"],
                self.paths,
                self.clock(),
                size.width,
                size.height,
            )

        def on_key(key: str) -> bool:
            if key == "w":
                state["warnings"] = not state["warnings"]
                return True
            if key == "o":
                outcome = actions.open_folder(self.paths.logs)
                if not outcome.ok:
                    self.say("err", outcome.message)
                return True
            return key not in ("q", "esc", "ctrl-c")

        self._page(build, on_key)

    def _worker_menu(self, title: str, choices: tuple[menu.Choice, ...]) -> None:
        position = [0]
        chosen: list[Optional[menu.Choice]] = [None]

        def build() -> RenderableType:
            return render.choice_page(
                title,
                choices,
                position[0],
                self.paths,
                self.clock(),
                self.console.size.width,
            )

        def on_key(key: str) -> bool:
            if key in ("up", "down"):
                step = -1 if key == "up" else 1
                position[0] = (position[0] + step) % len(choices)
                return True
            if key == "enter":
                chosen[0] = choices[position[0]]
                return False
            if key in ("esc", "ctrl-c"):
                chosen[0] = choices[-1]
                return False
            for number, choice in enumerate(choices):
                if key == choice.key:
                    position[0] = number
                    chosen[0] = choice
                    return False
            return True

        while True:
            chosen[0] = None
            self._page(build, on_key)
            choice = chosen[0]
            if choice is None or choice.action == "back":
                return
            if choice.action == "worker_packages":
                folder = self.paths.root / "data" / "worker-packages"
                outcome = actions.open_folder(folder)
                self.say("ok" if outcome.ok else "err", outcome.message)
                return
            self._run_in_terminal(choice.action)

    @staticmethod
    def _set_title(title: str) -> None:
        if sys.stdout.isatty():
            sys.stdout.write(f"\x1b]0;{title}\x07")
            sys.stdout.flush()


def main() -> int:
    console = Console(highlight=False)
    if not console.is_terminal:
        status = StatusReader(project_paths()).read()
        console.print(f"機器人狀態：{status.state}")
        console.print("控制台需要在互動式終端機中執行。")
        return 2
    try:
        keyboard = WindowsKeyboard()
    except ImportError:
        console.print("這個控制台目前只支援 Windows 終端機。")
        return 2
    try:
        return ControlPanel(console, keyboard, host=HostReader(), boot=True).run()
    finally:
        keyboard.close()
