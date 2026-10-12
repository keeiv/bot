"""The terminal control panel: status reading, actions, menu, drawing, key loop.

Nothing here starts or stops a real bot: processes are faked, and the panel
only ever reads the temporary directory the test runs in.
"""

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
import io
import os
from pathlib import Path
import time
from types import SimpleNamespace

import psutil
import pytest
from rich.console import Console

from src.control_panel import actions
from src.control_panel import menu
from src.control_panel import render
from src.control_panel import state
from src.control_panel.app import ControlPanel
from src.control_panel.app import Keyboard
from src.control_panel.state import BotStatus
from src.control_panel.state import Paths
from src.control_panel.state import StatusReader


@pytest.fixture
def paths(tmp_path):
    (tmp_path / "data" / "logs").mkdir(parents=True)
    return Paths(
        root=tmp_path,
        lock=tmp_path / "bot.lock",
        logs=tmp_path / "data" / "logs",
        python="python",
    )


def _log(paths, *lines):
    paths.runtime_log.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── state: log ────────────────────────────────────────────────────
def test_log_records_group_tracebacks_with_their_record():
    records = state.parse_records(
        [
            "2026-10-11 18:13:37,494 INFO src.bot: ready",
            "2026-10-11 18:13:38,000 ERROR src.utils.runtime: failed",
            "Traceback (most recent call last):",
            '  File "x.py", line 1, in f',
            "ValueError: boom",
            "2026-10-11 18:13:39,000 WARNING discord.gateway: slow",
        ]
    )
    assert [r.level for r in records] == ["INFO", "ERROR", "WARNING"]
    assert records[1].extra_lines == 3 and records[1].message == "failed"
    assert records[0].time == "18:13:37"


def test_tail_filters_by_level_and_returns_the_last_records(paths):
    _log(
        paths,
        *(f"2026-10-11 10:00:{i:02d},000 INFO src.x: line {i}" for i in range(30)),
        "2026-10-11 10:01:00,000 ERROR src.x: broken",
    )
    last = state.tail_records(paths.runtime_log, 5)
    assert [r.message for r in last][-1] == "broken" and len(last) == 5
    only_errors = state.tail_records(paths.runtime_log, 5, min_level="WARNING")
    assert [r.message for r in only_errors] == ["broken"]
    assert state.tail_records(paths.runtime_log, 0) == []
    assert state.tail_records(paths.logs / "missing.log", 5) == []


def test_tail_reads_only_the_end_of_a_big_log_and_drops_the_cut_line(paths):
    lines = [
        f"2026-10-11 10:00:00,000 INFO src.x: message number {i}" for i in range(500)
    ]
    _log(paths, *lines)
    records = state.tail_records(paths.runtime_log, 1000, max_bytes=2_000)
    assert 0 < len(records) < 500
    assert records[-1].message == "message number 499"
    # No half line was parsed into a bogus first record.
    assert all(r.message.startswith("message number") for r in records)


def test_names_and_durations():
    assert state.short_logger("src.utils.lang_context") == "lang_context"
    assert state.short_logger("discord.gateway") == "discord.gateway"
    assert state.format_duration(5) == "5s"
    assert state.format_duration(125) == "2m 5s"
    assert state.format_duration(3 * 3600 + 120) == "3h 2m"
    assert state.format_duration(2 * 86_400 + 3600) == "2d 1h"
    assert state.format_duration(-4) == "0s"


# ── state: bot process ────────────────────────────────────────────
def test_lock_file_parsing(paths):
    assert state.read_lock_pid(paths.lock) is None
    paths.lock.write_text("not a pid", encoding="utf-8")
    assert state.read_lock_pid(paths.lock) is None
    paths.lock.write_text(" 4242\n", encoding="utf-8")
    assert state.read_lock_pid(paths.lock) == 4242


def test_only_this_projects_bot_is_recognised(paths):
    root = str(paths.root)
    py = r"C:\x\.venv\Scripts\python.exe"
    classify = state.classify_process

    # The real thing, as the launcher and the scheduled task start it.
    assert classify([py, "-X", "utf8", "-m", "src.main"], root, paths.root) == "bot"
    assert classify(["python", "-m", "src.main"], root, paths.root) == "bot"
    script = str(paths.root / "src" / "main.py")
    assert classify([py, script], r"C:\elsewhere", paths.root) == "bot"
    assert classify(["python", r"src\main.py"], root, paths.root) == "bot"

    # Not the bot.
    assert classify(["notepad.exe", "notes.txt"], root, paths.root) == "other"
    assert classify(["python", "-m", "pytest"], root, paths.root) == "other"
    assert classify(["python", "-c", "import src.main"], root, paths.root) == "other"
    assert classify(["python"], root, paths.root) == "other"


def test_a_reused_pid_that_merely_mentions_src_main_is_not_the_bot(paths):
    # Regression: a substring match took notepad opening C:\notes\src\main.py
    # for the bot, and the panel would have ended it.
    root = str(paths.root)
    classify = state.classify_process
    assert (
        classify([r"C:\Windows\notepad.exe", r"C:\notes\src\main.py"], root, paths.root)
        == "other"
    )
    assert classify(["code.exe", "src.main"], root, paths.root) == "other"
    assert classify(["python.exe.bak", "-m", "src.main"], root, paths.root) == "other"
    # Python, but running some other script that is named like the bot's.
    assert classify(["python", r"C:\notes\src\main.py"], root, paths.root) == "other"


def test_another_projects_bot_is_not_this_bot(paths):
    """This machine has other projects with their own src/main.py."""
    other = r"C:\Users\someone\discord-bot"
    classify = state.classify_process
    assert classify(["python", "-m", "src.main"], other, paths.root) == "other"
    assert classify(["python", r"src\main.py"], other, paths.root) == "other"
    assert classify([other + r"\src\main.py"], other, paths.root) == "other"


def test_unreadable_processes_are_unknown_never_guessed(paths):
    classify = state.classify_process
    assert classify([], str(paths.root), paths.root) == "unknown"
    # The module / relative script depend on the working directory.
    assert classify(["python", "-m", "src.main"], None, paths.root) == "unknown"
    assert classify(["python", r"src\main.py"], None, paths.root) == "unknown"
    # An absolute script path does not.
    script = str(paths.root / "src" / "main.py")
    assert classify(["python", script], None, paths.root) == "bot"


def test_status_stopped_stale_and_running(paths, monkeypatch):
    reader = StatusReader(paths)
    assert reader.read().state == "stopped"

    # A PID that does not exist (or was reused) is a stale lock, not a bot.
    paths.lock.write_text("999999999", encoding="utf-8")
    assert reader.read().state == "stale"
    paths.lock.write_text(str(os.getpid()), encoding="utf-8")
    assert reader.read().state == "stale"  # this is pytest, not src.main

    monkeypatch.setattr(state, "classify_process", lambda *a: state.BOT)
    running = StatusReader(paths).read()
    assert running.state == "running" and running.pid == os.getpid()
    assert running.verified
    assert running.rss_mb and running.threads and running.started_at


class DeniedProcess:
    """A live process Windows will not describe (e.g. an elevated bot)."""

    pid = 4242

    def is_running(self):
        return True

    def _denied(self, *args):
        raise psutil.AccessDenied(self.pid)

    status = cmdline = cwd = create_time = memory_info = _denied
    num_threads = cpu_percent = _denied

    def oneshot(self):
        from contextlib import nullcontext

        return nullcontext()


def test_access_denied_is_alive_not_stale(paths, monkeypatch):
    # Regression: AccessDenied was read as a dead process, so the panel deleted
    # the lock of a live (elevated) bot and started a second copy.
    paths.lock.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(state.psutil, "Process", lambda pid: DeniedProcess())
    status = StatusReader(paths).read()
    assert status.state == "running" and not status.verified and status.pid == 4242

    # Starting must refuse and must leave the lock alone.
    launched = []
    outcome = actions.start_bot(
        paths, StatusReader(paths), popen=lambda *a, **k: launched.append(a)
    )
    assert not outcome.ok and "權限不足" in outcome.message
    assert not launched and paths.lock.exists()

    # Stopping must refuse to end something it cannot identify.
    monkeypatch.setattr(actions, "_kill_tree", lambda *_: pytest.fail("killed"))
    stopped = actions.stop_bot(paths, status)
    assert not stopped.ok and "無法確認" in stopped.message
    assert paths.lock.exists()


def test_restart_does_not_start_a_second_bot_beside_an_unverified_one(
    paths, monkeypatch
):
    paths.lock.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(state.psutil, "Process", lambda pid: DeniedProcess())
    launched = []
    outcome = actions.restart_bot(
        paths,
        StatusReader(paths),
        start=lambda p, r: launched.append(1) or actions.Outcome(True, "started"),
        sleep=lambda _: None,
    )
    assert not outcome.ok and not launched


def test_unverified_status_is_shown_on_the_card(paths):
    unverified = BotStatus("running", 4242, verified=False)
    plain, _ = _capture(render.dashboard(_view(paths, status=unverified)))
    assert "無法確認（權限不足）" in plain
    verified = BotStatus("running", 4242)
    plain, _ = _capture(render.dashboard(_view(paths, status=verified)))
    assert "無法確認" not in plain


# ── actions ───────────────────────────────────────────────────────
def test_every_command_the_old_menu_had_exists(paths):
    for name in (
        "install",
        "tests",
        "format",
        "cogs",
        "tools",
        "worker_check",
        "worker_enable",
        "worker_disable",
    ):
        command = actions.build_command(paths, name)
        assert command.title and command.argv[0] == "python"
    tools = actions.build_command(paths, "tools")
    assert tools.argv[1:] == ("-X", "utf8", "-m", "src.tool_console")
    assert tools.interactive
    assert actions.build_command(paths, "tests").env == {"PYTHONPATH": "."}
    assert actions.build_command(paths, "worker_enable").argv[-3:] == (
        "-m",
        "src.tool_worker_setup",
        "enable",
    )


class FakeReader:
    def __init__(self, *statuses):
        self.statuses = list(statuses)

    def read(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]


class FakeProcess:
    def __init__(self, pid=4321, exits=None):
        self.pid = pid
        self.exits = exits

    def poll(self):
        return self.exits


def test_start_refuses_a_second_copy(paths):
    launched = []
    outcome = actions.start_bot(
        paths,
        FakeReader(BotStatus("running", 77)),
        popen=lambda *a, **k: launched.append(a),
    )
    assert not outcome.ok and "77" in outcome.message and not launched


def test_start_clears_a_stale_lock_and_launches_src_main(paths):
    paths.lock.write_text("123", encoding="utf-8")
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return FakeProcess(4321)

    reader = FakeReader(BotStatus("stale", 123), BotStatus("running", 4321))
    outcome = actions.start_bot(paths, reader, popen=popen, sleep=lambda _: None)
    assert outcome.ok and "4321" in outcome.message
    assert not paths.lock.exists()
    argv, kwargs = calls[0]
    assert argv == ["python", "-X", "utf8", "-m", "src.main"]
    assert kwargs["cwd"] == paths.root


def test_start_reports_a_bot_that_dies_immediately(paths):
    outcome = actions.start_bot(
        paths,
        FakeReader(BotStatus("stopped")),
        popen=lambda *a, **k: FakeProcess(exits=1),
        sleep=lambda _: None,
    )
    assert not outcome.ok and "1" in outcome.message


def test_start_that_is_still_initialising_is_not_an_error(paths):
    outcome = actions.start_bot(
        paths,
        FakeReader(BotStatus("stopped")),
        popen=lambda *a, **k: FakeProcess(),
        wait=0.05,
        sleep=lambda _: time.sleep(0.01),
    )
    assert outcome.ok and "尚未完成" in outcome.message


def test_stop_never_touches_a_stopped_or_stale_bot(paths, monkeypatch):
    monkeypatch.setattr(actions, "_kill_tree", lambda *_: pytest.fail("killed"))
    assert not actions.stop_bot(paths, BotStatus("stopped")).ok
    paths.lock.write_text("123", encoding="utf-8")
    assert actions.stop_bot(paths, BotStatus("stale", 123)).ok
    assert not paths.lock.exists()


def test_stop_does_not_kill_an_unrelated_program_behind_a_reused_pid(
    paths, monkeypatch
):
    paths.lock.write_text("500", encoding="utf-8")
    fake = SimpleNamespace(cmdline=lambda: ["notepad.exe"], cwd=lambda: "C:\\")
    monkeypatch.setattr(actions.psutil, "Process", lambda pid: fake)
    monkeypatch.setattr(actions, "_kill_tree", lambda *_: pytest.fail("killed"))
    outcome = actions.stop_bot(paths, BotStatus("running", 500))
    assert outcome.ok and "不是機器人" in outcome.message
    assert not paths.lock.exists()


def test_stop_ends_the_bot_and_removes_the_lock(paths, monkeypatch):
    paths.lock.write_text("500", encoding="utf-8")
    fake = SimpleNamespace(
        cmdline=lambda: ["python", "-m", "src.main"], cwd=lambda: str(paths.root)
    )
    killed = []
    monkeypatch.setattr(actions.psutil, "Process", lambda pid: fake)
    monkeypatch.setattr(actions, "_kill_tree", killed.append)
    outcome = actions.stop_bot(paths, BotStatus("running", 500))
    assert outcome.ok and killed == [fake] and not paths.lock.exists()


def test_stop_reports_missing_permission(paths, monkeypatch):
    def denied(pid):
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(actions.psutil, "Process", denied)
    outcome = actions.stop_bot(paths, BotStatus("running", 500))
    assert not outcome.ok


def test_restart_stops_then_starts(paths):
    stopped = []
    reader = FakeReader(BotStatus("stopped"))
    outcome = actions.restart_bot(
        paths,
        reader,
        start=lambda p, r: stopped.append("start") or actions.Outcome(True, "ok"),
        sleep=lambda _: None,
    )
    assert outcome.ok and stopped == ["start"]


# ── menu ──────────────────────────────────────────────────────────
def test_menu_keeps_every_key_of_the_old_launcher():
    assert set(menu.BY_KEY) == set("123456789twdslqmh")
    assert len(menu.ITEMS) == len(menu.BY_KEY)  # no duplicate hotkeys
    assert menu.BY_KEY["t"].label == "檔案工具終端"


def test_every_menu_item_has_something_to_run(paths):
    handled = {"start", "stop", "restart", "status", "logs", "guide", "worker"}
    handled |= {"database", "host"}
    handled |= {"project", "data", "quit"}
    for item in menu.ITEMS:
        if item.action in handled:
            continue
        assert item.kind == "cmd"
        actions.build_command(paths, item.action)
    for item in menu.ITEMS:
        if item.action in ("stop", "restart"):
            assert item.confirm  # these ask first
    for choice in menu.WORKER_CHOICES:
        if choice.action not in ("back", "worker_packages"):
            actions.build_command(paths, choice.action)


# ── drawing ───────────────────────────────────────────────────────
def _capture(renderable, width=100, height=34):
    console = Console(
        file=io.StringIO(),
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=width,
        height=height,
    )
    console.print(renderable)
    plain = console.export_text(styles=False, clear=False)
    return plain, console.export_text(styles=True)


def _view(paths, **overrides):
    values = {
        "paths": paths,
        "status": BotStatus("stopped"),
        "records": [],
        "selected": 0,
        "now": datetime(2026, 10, 11, 12, 0, 0),
        "width": 100,
        "height": 34,
    }
    values.update(overrides)
    return render.ViewState(**values)


@pytest.mark.parametrize("width", [48, 60, 80, 100, 130])
def test_dashboard_draws_at_every_width(paths, width):
    plain, styled = _capture(render.dashboard(_view(paths, width=width)), width=width)
    for text in ("機器人控制台", "已停止", "啟動機器人", "離開", "日誌"):
        assert text in plain
    assert "\x1b[38;2;" in styled  # true colour is really emitted
    assert max(len(line) for line in plain.splitlines()) <= width * 2  # CJK is wide


def test_dashboard_shows_the_running_bot_and_its_log(paths):
    records = state.parse_records(
        [
            "2026-10-11 18:13:37,494 INFO src.bot: ready",
            "2026-10-11 18:13:38,000 ERROR src.utils.runtime: failed",
            "Traceback (most recent call last):",
        ]
    )
    running = BotStatus(
        "running",
        4321,
        datetime(2026, 10, 11, 9, 0, 0),
        2.0,
        312.0,
        41,
        "python -m src.main",
    )
    plain, _ = _capture(render.dashboard(_view(paths, status=running, records=records)))
    for text in (
        "運行中",
        "PID 4321",
        "已運行 3h 0m",
        "312 MB",
        "41",
        "runtime",
        "(+1 行)",
    ):
        assert text in plain


def test_dashboard_shows_busy_notice_and_confirmation_in_turn(paths):
    shown = lambda **kw: _capture(render.dashboard(_view(paths, **kw)))[0]  # noqa: E731
    assert "正在啟動機器人" in shown(busy="正在啟動機器人…")
    assert "機器人已啟動" in shown(notice=render.Notice("ok", "機器人已啟動"))
    confirm = shown(confirm="確定要停止機器人嗎？")
    assert "確定要停止機器人嗎？" in confirm and "Y 確定" in confirm
    assert "仍會繼續運作" in shown()


def test_selected_item_is_marked_and_explained(paths):
    plain, _ = _capture(render.dashboard(_view(paths, selected=1)))
    assert "❯ 2  停止機器人" in plain
    assert menu.ITEMS[1].hint in plain
    assert "❯ 1  啟動機器人" not in plain


def test_other_pages_draw(paths):
    now = datetime(2026, 10, 11, 12, 0, 0)
    running = BotStatus(
        "running", 9, now - timedelta(hours=1), 1.0, 10.0, 3, "python -m src.main"
    )
    assert "詳細狀態" in _capture(render.status_detail(running, paths, now, 100))[0]
    assert "/dev-status" in _capture(render.guide_page(paths, now, 100))[0]
    assert (
        "區網檔案工作站"
        in _capture(
            render.choice_page(
                "區網檔案工作站", menu.WORKER_CHOICES, 0, paths, now, 100
            )
        )[0]
    )
    assert "警告以上" in _capture(render.log_page([], True, paths, now, 100, 30))[0]
    banner = _capture(
        render.command_banner("執行測試", ["python", "-m", "pytest"], 100)
    )
    assert "python -m pytest" in banner[0]
    assert "完成" in _capture(render.command_result(0, 3.0))[0]
    assert "結束碼 2" in _capture(render.command_result(2, 3.0))[0]


# ── key loop ──────────────────────────────────────────────────────
class ScriptedKeys(Keyboard):
    def __init__(self, *keys):
        self.keys = list(keys)

    def poll(self, timeout):
        assert self.keys, "the panel asked for more keys than the test gave"
        return self.keys.pop(0)


def _panel(paths, *keys):
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=34)
    return ControlPanel(console, ScriptedKeys(*keys), paths)


def _wait_idle(panel, timeout=3.0):
    deadline = time.monotonic() + timeout
    while panel.busy and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not panel.busy


def test_arrows_wrap_and_hotkeys_select(paths):
    panel = _panel(paths)
    assert panel._on_key("up") is None and panel.selected == len(menu.ITEMS) - 1
    assert panel._on_key("down") is None and panel.selected == 0
    item = panel._on_key("7")
    assert item is menu.BY_KEY["7"] and panel.selected == menu.ITEMS.index(item)
    assert panel._on_key("x") is None
    assert panel._on_key("ctrl-c") is menu.BY_KEY["q"]


def test_quit_leaves_the_bot_running(paths):
    assert _panel(paths, "q").run() == 0


class InterruptingKeys(Keyboard):
    def poll(self, timeout):
        raise KeyboardInterrupt


def test_ctrl_c_quits_cleanly_instead_of_a_traceback(paths):
    # Windows delivers Ctrl+C as a signal, so it surfaces as KeyboardInterrupt.
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=34)
    assert ControlPanel(console, InterruptingKeys(), paths).run() == 0


def test_a_command_runs_in_the_terminal_then_waits_for_a_key(paths, monkeypatch):
    ran = []
    monkeypatch.setattr(actions, "run_command", lambda p, c: ran.append(c.title) or 0)
    panel = _panel(paths, "7", "x", "q")  # run tests, any key, quit
    assert panel.run() == 0
    assert ran == ["執行測試"]


def test_interactive_tool_terminal_returns_without_a_pause(paths, monkeypatch):
    ran = []
    monkeypatch.setattr(actions, "run_command", lambda p, c: ran.append(c.title) or 0)
    assert _panel(paths, "t", "q").run() == 0  # no extra key needed
    assert ran == ["檔案工具終端"]


def test_failed_command_is_reported_not_raised(paths, monkeypatch):
    def broken(p, c):
        raise OSError("no such file")

    monkeypatch.setattr(actions, "run_command", broken)
    assert _panel(paths, "8", "x", "q").run() == 0


def test_pages_close_on_any_key(paths):
    assert _panel(paths, "4", "x", "d", "x", "q").run() == 0


def test_log_viewer_toggles_the_filter_and_quits(paths):
    _log(paths, "2026-10-11 10:00:00,000 ERROR src.x: broken")
    assert _panel(paths, "5", "w", "w", "q", "q").run() == 0


def test_worker_menu_runs_the_chosen_command_and_returns(paths, monkeypatch):
    ran = []
    monkeypatch.setattr(actions, "run_command", lambda p, c: ran.append(c.title) or 0)
    # open menu, press 2 (enable), any key after the result, Q back, Q quit
    assert _panel(paths, "w", "2", "x", "q", "q").run() == 0
    assert ran == ["驗證後啟用遠端處理"]


def test_stop_and_restart_ask_first_when_the_bot_is_running(paths, monkeypatch):
    stopped = []
    monkeypatch.setattr(
        actions,
        "stop_bot",
        lambda p, s: stopped.append(1) or actions.Outcome(True, "ok"),
    )
    panel = _panel(paths)
    panel.status = BotStatus("running", 5)
    assert panel._on_key("2") is None
    assert panel.confirm_item is menu.BY_KEY["2"] and not stopped
    assert panel._on_key("n") is None  # anything but Y cancels
    assert panel.confirm_item is None and not stopped
    assert panel.notice.text == "已取消"

    panel._on_key("2")
    panel._on_key("y")
    _wait_idle(panel)
    assert stopped == [1]
    assert panel.notice.kind == "ok"


def test_stop_without_a_running_bot_does_not_ask(paths, monkeypatch):
    monkeypatch.setattr(
        actions, "stop_bot", lambda p, s: actions.Outcome(False, "目前沒有在執行")
    )
    panel = _panel(paths)
    panel.status = BotStatus("stopped")
    panel._on_key("2")
    assert panel.confirm_item is None
    _wait_idle(panel)
    assert panel.notice.kind == "err"


def test_keys_are_ignored_while_a_stop_is_in_progress(paths, monkeypatch):
    release = []

    def slow_stop(p, status):
        while not release:
            time.sleep(0.01)
        return actions.Outcome(True, "stopped")

    monkeypatch.setattr(actions, "stop_bot", slow_stop)
    panel = _panel(paths)
    panel.status = BotStatus("running", 5)
    panel._on_key("2")
    panel._on_key("y")
    assert panel.busy
    assert panel._on_key("down") is None and panel.selected == 1
    assert panel._on_key("q") is None  # can't walk away from a half-done stop
    release.append(1)
    _wait_idle(panel)
    assert panel.notice.text == "stopped"


def test_a_crash_in_an_action_becomes_a_message(paths, monkeypatch):
    def explode(p, status):
        raise RuntimeError("boom")

    monkeypatch.setattr(actions, "stop_bot", explode)
    panel = _panel(paths)
    panel.status = BotStatus("running", 5)
    panel._on_key("2")
    panel._on_key("y")
    _wait_idle(panel)
    assert panel.notice.kind == "err" and "boom" in panel.notice.text


def test_notices_expire(paths, monkeypatch):
    panel = _panel(paths)
    panel.say("ok", "hello")
    assert panel.notice
    panel.notice_until = time.monotonic() - 1
    assert panel.refresh() is True and panel.notice is None


def test_panel_never_writes_into_the_project(paths):
    before = sorted(p.name for p in Path(paths.root).iterdir())
    _panel(paths, "4", "x", "q").run()
    assert sorted(p.name for p in Path(paths.root).iterdir()) == before


# ── launcher ──────────────────────────────────────────────────────
def test_launcher_starts_the_panel():
    launcher = Path(__file__).resolve().parents[1] / "run_bot.bat"
    if not launcher.is_file():
        pytest.skip("Local Windows launcher is not part of the source checkout")
    source = launcher.read_text(encoding="utf-8")
    assert "-X utf8 -m src.control_panel" in source
    assert b"\r\n" in launcher.read_bytes()  # cmd needs CRLF line endings


class CountingKeys(ScriptedKeys):
    def __init__(self, *keys):
        super().__init__(*keys)
        self.cooked_during = []

    @contextmanager
    def cooked(self):
        self.cooked_during.append("enter")
        try:
            yield
        finally:
            self.cooked_during.append("exit")


def test_child_programs_get_normal_console_input_back(paths, monkeypatch):
    # Ctrl+C must still interrupt pytest/pip, so the panel's own key mode is
    # switched off exactly while the child runs.
    seen = []
    keys = CountingKeys("7", "x", "q")
    monkeypatch.setattr(
        actions, "run_command", lambda p, c: seen.append(list(keys.cooked_during)) or 0
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=34)
    assert ControlPanel(console, keys, paths).run() == 0
    assert seen == [["enter"]]  # inside the child run
    assert keys.cooked_during == ["enter", "exit"]  # and restored afterwards
