#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
機器人管理面板

keeiv 瀨戶凱伊
"""

from datetime import datetime
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading
import time

try:
    from rich import box
    from rich.console import Console
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("請先安裝 rich 套件: pip install rich")
    sys.exit(1)

# ─── 設定 ────────────────────────────────────────────────────────────────────

VERSION = "v1.0.0"
AUTHOR = "keeiv 瀨戶凱伊"

BOTS: list[dict] = [
    {
        "id": "BOT",
        "label": "START-BOT",
        "path": Path(r"C:\Users\Finn0\OneDrive\文件\new_bot"),
        "module": "src.main",  # 用 python -m 啟動
        "entries": [],
        "process": None,
        "start_at": None,
        "pid": None,
        "status": "初始化中",
        "last_err": "",
        "_lock": threading.Lock(),
    },
    {
        "id": "黑塔",
        "label": "START-黑塔",
        "path": Path(r"C:\Users\Finn0\OneDrive\文件\discord-bot"),
        "module": None,
        "entries": ["main.py", "src/main.py", "bot.py"],
        "process": None,
        "start_at": None,
        "pid": None,
        "status": "初始化中",
        "last_err": "",
        "_lock": threading.Lock(),
    },
]

# ─── 日誌緩衝 ────────────────────────────────────────────────────────────────

_logs: list[tuple[str, str, str]] = []
_log_lock = threading.Lock()
_resume_event_cache: dict[str, float] = {}
_resume_cache_lock = threading.Lock()

_BRACKET_LEVEL_RE = re.compile(
    r"\[\d{4}-\d{2}-\d{2} .*?\] \[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\]"
)
_PLAIN_LEVEL_RE = re.compile(r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL):")


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    with _log_lock:
        _logs.append((ts, level, msg))
        if len(_logs) > 200:
            _logs.pop(0)


def _collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def _extract_level(line: str) -> str | None:
    bracket_match = _BRACKET_LEVEL_RE.search(line)
    if bracket_match:
        return bracket_match.group(1)

    plain_match = _PLAIN_LEVEL_RE.match(line)
    if plain_match:
        return plain_match.group(1)

    return None


def _is_new_log_record(line: str) -> bool:
    if _extract_level(line):
        return True

    starters = (
        "Traceback (most recent call last):",
        "Exception in",
        "Unhandled exception",
    )
    return line.startswith(starters)


def _event_level(line: str) -> str:
    level = _extract_level(line)
    if level in {"DEBUG", "INFO", "WARNING"}:
        return "INFO"
    if level in {"ERROR", "CRITICAL"}:
        return "ERR"
    # 無等級前綴時保守視為錯誤，避免真正錯誤被吞掉
    return "ERR"


def _should_suppress_resume(bot_id: str, level: str, msg: str) -> bool:
    if level != "INFO":
        return False

    normalized = _collapse_spaces(msg)
    if "has successfully RESUMED session" not in normalized:
        return False

    key = f"{bot_id}:{normalized}"
    now = time.time()
    with _resume_cache_lock:
        last = _resume_event_cache.get(key)
        _resume_event_cache[key] = now

    # 30 秒內相同 RESUMED 視為重複訊息，避免洗版
    return last is not None and (now - last) < 30


def _emit_stderr_log(bot: dict, level: str, line: str) -> None:
    normalized = _collapse_spaces(line)
    if not normalized:
        return

    if _should_suppress_resume(bot["id"], level, normalized):
        return

    short = normalized[:160]
    log(level, f"[{bot['id']}] {short}")
    if level in {"ERR", "ERROR"}:
        with bot["_lock"]:
            bot["last_err"] = short


# ─── 工具函式 ────────────────────────────────────────────────────────────────


def _find_python(base: Path) -> str:
    """找到 bot 虛擬環境的 Python 執行檔"""
    for venv in (".venv", "venv", "env"):
        for scripts in ("Scripts", "bin"):
            for exe in ("python.exe", "python"):
                p = base / venv / scripts / exe
                if p.exists():
                    return str(p)
    return sys.executable


def _find_entry(base: Path, candidates: list[str]) -> Path | None:
    for c in candidates:
        p = base / c
        if p.exists():
            return p
    return None


def _uptime(start: datetime | None) -> str:
    if start is None:
        return "-"
    s = int((datetime.now() - start).total_seconds())
    if s < 60:
        return f"{s}s"
    elif s < 3600:
        return f"{s // 60}m{s % 60}s"
    return f"{s // 3600}h{(s % 3600) // 60}m"


# ─── Bot 管理 ────────────────────────────────────────────────────────────────


def _read_stderr(bot: dict, proc) -> None:
    """讀取 bot stderr 並寫入日誌"""
    _noise = ("[notice]", "To update, run:", "--upgrade pip")
    pending_line = ""
    pending_level = "INFO"

    def flush_pending() -> None:
        nonlocal pending_line, pending_level
        if pending_line:
            _emit_stderr_log(bot, pending_level, pending_line)
        pending_line = ""
        pending_level = "INFO"

    try:
        for raw in proc.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            # 過濾 pip 版本提示雜訊
            if any(n in line for n in _noise):
                continue

            if _is_new_log_record(line):
                flush_pending()
                pending_line = line.strip()
                pending_level = _event_level(line)
            else:
                continuation = line.strip()
                # 補上換行被拆斷的訊息，避免同一事件被判成兩條
                if pending_line:
                    pending_line = f"{pending_line} {continuation}"
                else:
                    pending_line = continuation
                    pending_level = _event_level(continuation)

        flush_pending()
    except Exception:
        pass


def _read_stdout(proc) -> None:
    """讀取並丟棄 stdout，避免管道阻塞"""
    try:
        for _ in proc.stdout:
            pass
    except Exception:
        pass


def _install_requirements(bot: dict, python: str) -> bool:
    """安裝 bot 依賴套件，成功回傳 True"""
    req = bot["path"] / "requirements.txt"
    if not req.exists():
        return True
    log("SYS", f"[{bot['id']}]  安裝依賴套件...")
    with bot["_lock"]:
        bot["status"] = "安裝依賴"
    try:
        subprocess.run(
            [
                python,
                "-m",
                "pip",
                "install",
                "-r",
                str(req),
                "-q",
                "--disable-pip-version-check",
            ],
            cwd=str(bot["path"]),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=True,
        )
        log("SYS", f"[{bot['id']}]  依賴套件已就緒")
        return True
    except subprocess.CalledProcessError as e:
        log("ERROR", f"[{bot['id']}]  套件安裝失敗 (exit {e.returncode})")
        return False
    except subprocess.TimeoutExpired:
        log("ERROR", f"[{bot['id']}]  套件安裝逾時")
        return False
    except Exception as exc:
        log("ERROR", f"[{bot['id']}]  套件安裝異常: {exc}")
        return False


def _launch(bot: dict) -> None:
    python = _find_python(bot["path"])
    entry = _find_entry(bot["path"], bot["entries"])

    # 判斷啟動方式：模組模式 (-m) 或檔案模式
    module = bot.get("module")
    if module:
        cmd_args = [python, "-m", module]
    else:
        entry = _find_entry(bot["path"], bot["entries"])
        if entry is None:
            log(
                "ERROR",
                f"[{bot['id']}]  找不到入口點 (嘗試: {', '.join(bot['entries'])})",
            )
            with bot["_lock"]:
                bot["status"] = "錯誤"
            return
        cmd_args = [python, str(entry)]

    # 安裝依賴（若找不到自己的 venv 則用共用 Python）
    if not _install_requirements(bot, python):
        with bot["_lock"]:
            bot["status"] = "錯誤"
        return

    log("START", f"[{bot['id']}]  啟動 {bot['id']}")

    try:
        flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        )
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            cmd_args,
            cwd=str(bot["path"]),
            stdout=subprocess.PIPE,  # PIPE 避免 Windows 編碼崩潰
            stderr=subprocess.PIPE,
            creationflags=flags,
            env=env,
        )
        with bot["_lock"]:
            bot["process"] = proc
            bot["pid"] = proc.pid
            bot["start_at"] = datetime.now()
            bot["status"] = "運行中"
            bot["last_err"] = ""
        # 非同步讀取 stderr（顯示錯誤）
        threading.Thread(target=_read_stderr, args=(bot, proc), daemon=True).start()
        # 非同步丟棄 stdout（防止管道阻塞）
        threading.Thread(target=_read_stdout, args=(proc,), daemon=True).start()
        log("START", f"[{bot['id']}]  啟動 {bot['id']}  PID {proc.pid}")
    except Exception as exc:
        log("ERROR", f"[{bot['id']}]  啟動失敗: {exc}")
        with bot["_lock"]:
            bot["status"] = "錯誤"


def _monitor() -> None:
    while True:
        for bot in BOTS:
            with bot["_lock"]:
                proc = bot["process"]
                if proc and proc.poll() is not None:
                    code = proc.poll()
                    bot["status"] = f"已停止({code})"
                    bot["pid"] = None
        time.sleep(2)


# ─── 渲染 ────────────────────────────────────────────────────────────────────


def _render():
    # 1. 標題欄
    title_text = Text.assemble(
        ("  機器人管理面板  ", "bold cyan"),
        (" | ", "dim white"),
        (f"{VERSION}", "bold yellow"),
        ("  ·  Made by ", "dim white"),
        (AUTHOR, "bold white"),
    )
    header = Panel(title_text, box=box.DOUBLE_EDGE, border_style="cyan", padding=(0, 1))

    # 2. 初始化提示
    init_line = Text("▶初始化 Bot\n", style="bold green")

    # 3. 日誌區
    log_text = Text()
    with _log_lock:
        recent = list(_logs[-18:])
    for ts, level, msg in recent:
        log_text.append(f"[{ts}] ", style="dim white")
        if level == "SYS":
            log_text.append("▶ SYS   ", style="bold green")
        elif level == "START":
            log_text.append("▶ START ", style="bold cyan")
        elif level == "INFO":
            log_text.append("▶ INFO  ", style="bold blue")
        elif level == "ERR":
            log_text.append("▶ ERR   ", style="bold red")
        elif level == "ERROR":
            log_text.append("▶ ERROR ", style="bold red")
        else:
            log_text.append(f"▶ {level:<7}", style="bold yellow")
        log_text.append(f" {msg}\n", style="white")

    # 4. 狀態表格
    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        min_width=55,
        padding=(0, 2),
    )
    table.add_column("名稱", style="white", min_width=10)
    table.add_column("狀態", min_width=14)
    table.add_column("PID", style="yellow", min_width=8)
    table.add_column("運行時間", style="cyan", min_width=10)
    table.add_column("最後錯誤", style="dim red", min_width=30)

    for bot in BOTS:
        with bot["_lock"]:
            status = bot["status"]
            pid = str(bot["pid"]) if bot["pid"] else "-"
            start_at = bot["start_at"]
            last_err = bot.get("last_err", "")
        uptime = _uptime(start_at)

        if "運行中" in status:
            st = Text("● 運行中", style="bold green")
        elif "錯誤" in status or "失敗" in status:
            st = Text("● 錯誤", style="bold red")
        elif "停止" in status:
            st = Text("● " + status, style="bold red")
        else:
            st = Text("○ " + status, style="dim yellow")

        table.add_row(bot["id"], st, pid, uptime, last_err[:40] if last_err else "")

    status_panel = Panel(
        table,
        title="[bold cyan]Bot 運行狀態[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
    )

    return Group(header, init_line, log_text, status_panel)


# ─── 主程式 ──────────────────────────────────────────────────────────────────


def main() -> None:
    console = Console()

    log("SYS", f"管理面板啟動  Python {platform.python_version()}")
    log("SYS", f"Log 目錄：{(Path(__file__).parent / 'data' / 'logs').resolve()}")

    # 啟動各 bot
    for bot in BOTS:
        t = threading.Thread(target=_launch, args=(bot,), daemon=True)
        t.start()
        time.sleep(0.4)

    # 監控執行緒
    threading.Thread(target=_monitor, daemon=True).start()

    try:
        with Live(
            _render(),
            console=console,
            refresh_per_second=2,
            screen=True,
        ) as live:
            while True:
                live.update(_render())
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n[yellow]正在關閉所有 Bot...[/yellow]")
        for bot in BOTS:
            with bot["_lock"]:
                proc = bot["process"]
                pid = bot["pid"]
            if proc and proc.poll() is None:
                proc.terminate()
                console.print(f"  [red]已終止 {bot['label']}  PID {pid}[/red]")
        console.print("[green][完成] 所有 Bot 已關閉[/green]")


if __name__ == "__main__":
    main()
