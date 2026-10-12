"""Things the panel can do: start and stop the bot, run project commands.

Nothing here prints. Each function returns an :class:`Outcome` the panel shows.
"""

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Optional

import psutil  # type: ignore[import-untyped]  # no typing metadata

from src.control_panel.state import BOT
from src.control_panel.state import BotStatus
from src.control_panel.state import classify_process
from src.control_panel.state import OTHER
from src.control_panel.state import Paths
from src.control_panel.state import StatusReader

_COG_CHECK = (
    "import importlib, pkgutil, src.cogs; "
    "modules = [i.name for i in pkgutil.walk_packages(src.cogs.__path__, "
    "'src.cogs.') if not i.ispkg]; "
    "[importlib.import_module(n) for n in modules]; "
    "print(f'[OK] Verified {len(modules)} Cog modules')"
)


@dataclass(frozen=True)
class Outcome:
    ok: bool
    message: str


@dataclass(frozen=True)
class Command:
    """A project command run in the panel's own terminal."""

    title: str
    argv: tuple[str, ...]
    env: Mapping[str, str]
    interactive: bool = False  # hands the keyboard to the program


def build_command(paths: Paths, name: str) -> Command:
    python = paths.python
    utf8 = (python, "-X", "utf8")
    commands: dict[str, Command] = {
        "install": Command(
            "安裝／更新依賴",
            (python, "-m", "pip", "install", "-r", "requirements.txt"),
            {},
        ),
        "tests": Command(
            "執行測試",
            (python, "-m", "pytest", "--color=yes"),
            {"PYTHONPATH": "."},
        ),
        "format": Command(
            "檢查程式碼格式",
            (python, "-m", "black", "--check", "--color", "src", "tests"),
            {},
        ),
        "cogs": Command("檢查 Cog 匯入", (python, "-c", _COG_CHECK), {}),
        "tools": Command(
            "檔案工具終端",
            (*utf8, "-m", "src.tool_console"),
            {},
            interactive=True,
        ),
        "worker_check": Command(
            "檢查配對與圖片轉換",
            (*utf8, "-m", "src.tool_worker_setup", "check"),
            {},
        ),
        "worker_enable": Command(
            "驗證後啟用遠端處理",
            (*utf8, "-m", "src.tool_worker_setup", "enable"),
            {},
        ),
        "worker_disable": Command(
            "恢復本機處理",
            (*utf8, "-m", "src.tool_worker_setup", "disable"),
            {},
        ),
    }
    return commands[name]


def run_command(paths: Paths, command: Command) -> int:
    """Run ``command`` attached to this terminal and return its exit code."""
    env = {**os.environ, **command.env}
    return subprocess.run(command.argv, cwd=paths.root, env=env).returncode


def open_folder(path: Path) -> Outcome:
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # Windows only
    except (OSError, AttributeError) as exc:
        return Outcome(False, f"無法開啟資料夾：{exc}")
    return Outcome(True, f"已開啟 {path}")


# ── start / stop ──────────────────────────────────────────────────
def start_bot(
    paths: Paths,
    reader: StatusReader,
    *,
    wait: float = 12.0,
    popen: Callable[..., Any] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    status = reader.read()
    if status.state == "running":
        note = "" if status.verified else "，權限不足無法確認"
        return Outcome(False, f"機器人已在執行中（PID {status.pid}{note}）")
    if status.state == "stale":
        # A dead or reused PID in the lock file would make the bot refuse to start.
        paths.lock.unlink(missing_ok=True)

    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    try:
        process = popen(
            [paths.python, "-X", "utf8", "-m", "src.main"],
            cwd=paths.root,
            creationflags=flags,
        )
    except OSError as exc:
        return Outcome(False, f"無法啟動機器人：{exc}")

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            return Outcome(
                False,
                f"機器人啟動後立刻結束（結束碼 {code}），請看日誌或新視窗的錯誤訊息",
            )
        current = reader.read()
        if current.state == "running" and current.pid == process.pid:
            return Outcome(True, f"機器人已啟動（PID {process.pid}）")
        sleep(0.25)
    return Outcome(True, f"機器人正在啟動（PID {process.pid}），尚未完成初始化")


def _kill_tree(process: psutil.Process, timeout: float = 5.0) -> None:
    family = [*process.children(recursive=True), process]
    for member in family:
        try:
            member.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(family, timeout=timeout)
    for member in alive:
        try:
            member.kill()
        except psutil.NoSuchProcess:
            pass


def stop_bot(paths: Paths, status: BotStatus) -> Outcome:
    if status.state == "stopped":
        return Outcome(False, "機器人目前沒有在執行")
    if status.state == "stale" or status.pid is None:
        paths.lock.unlink(missing_ok=True)
        return Outcome(True, "已清除過期的鎖定檔（機器人其實沒有在執行）")
    if not status.verified:
        return Outcome(
            False,
            f"無法確認 PID {status.pid} 是機器人（權限不足），為了安全沒有結束它。"
            "請以系統管理員身分重新開啟控制台，或到工作管理員手動結束",
        )
    try:
        process = psutil.Process(status.pid)
        # Check again right before killing: never end an unrelated program.
        try:
            cmdline = process.cmdline()
            cwd: Optional[str] = process.cwd()
        except psutil.AccessDenied:
            return Outcome(
                False,
                f"無法確認 PID {status.pid} 是機器人（權限不足），為了安全沒有結束它",
            )
        verdict = classify_process(cmdline, cwd, paths.root)
        if verdict == OTHER:
            paths.lock.unlink(missing_ok=True)
            return Outcome(True, "鎖定檔指向的不是機器人，已清除鎖定檔")
        if verdict != BOT:
            return Outcome(False, f"無法確認 PID {status.pid} 是機器人，沒有結束它")
        _kill_tree(process)
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return Outcome(False, f"沒有權限結束 PID {status.pid}，請用系統管理員身分執行")
    paths.lock.unlink(missing_ok=True)
    return Outcome(True, f"已停止機器人（PID {status.pid}）")


def restart_bot(
    paths: Paths,
    reader: StatusReader,
    *,
    start: Optional[Callable[..., Outcome]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    stopped = stop_bot(paths, reader.read())
    if not stopped.ok and reader.read().state == "running":
        return stopped
    sleep(1.5)
    return (start or start_bot)(paths, reader)
