"""BOT. installer: download the project from GitHub and set up a developer machine.

One job only: download the project. In a terminal it shows a black-and-white
screen laid out like the bot's control panel (boxes, a text box for the install
folder, a progress panel, the logo); anywhere else, or with ``--plain``, it
prints plain lines. Only the Python standard library is used, so it runs before
anything is installed. No colour, no Nova.

    python install.py                     # opens the screen
    python install.py --dir bot --test    # install into ./bot, then run the tests
    python install.py --plain --yes       # no screen, no questions

It checks the machine, gets the code (git, or a ZIP from GitHub when git is
missing), creates a virtual environment, installs the dependencies, writes a
starter ``.env`` (never overwritten) and checks that the packages import.
Secrets are never asked for or written; ``.env`` is left for you to fill in.
"""

from __future__ import annotations

import argparse
import collections
import os
import platform
import re
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.request
import zipfile

REPO = "keeiv/bot"
REPO_URL = "https://github.com/%s.git" % REPO
ZIP_URL = "https://codeload.github.com/%s/zip/refs/heads/%%s" % REPO
DEFAULT_DIR = "bot"
MIN_PYTHON = (3, 10)
TESTED_PYTHON = (3, 13)  # the newest version CI runs
STEPS = (
    "檢查環境",
    "取得程式碼",
    "建立虛擬環境",
    "安裝依賴套件",
    "建立設定檔 .env",
    "檢查安裝結果",
)
TOTAL_STEPS = len(STEPS)
IMPORTS = (
    "discord",
    "aiohttp",
    "pymysql",
    "PIL",
    "cryptography",
    "genshin",
    "ossapi",
    "psutil",
    "dotenv",
    "deep_translator",
    "rich",
)

ENV_TEMPLATE = """# BOT. local settings. This file is not tracked by Git; never share it.
DISCORD_TOKEN=
OSU_CLIENT_ID=
OSU_CLIENT_SECRET=
GITHUB_TOKEN=
BLACKLIST_API_KEY=
# Start in JSON mode. MySQL mode needs a finished migration (see README).
STORAGE_BACKEND=json
BOT_API_ENABLED=false
BOT_API_HOST=127.0.0.1
BOT_API_PORT=8080
BOT_API_SECRET=
"""

# The BOT. logo in one grey: the bars and the swoosh solid, the round centre shaded.
LOGO = (
    "███████████ ████",
    "██████████▀ ████",
    "██▄▄        ████",
    "████        ████",
    "████  ▄▓▓▄  ████",
    "████ ▓▓▓▓▓▓  ▀▀█",
    "████▄ ▀▓▓▀  ██▄ ",
    "▀████▓  ▄▄▄████▀",
    "  ▀▀ ▄▓██████▀  ",
    "     ▀▓███▀     ",
)


class Failure(Exception):
    """A step could not be completed; the message says what to do."""


# ── plain output ──────────────────────────────────────────────────
class Screen:
    """Plain lines, for pipes, logs and ``--plain``."""

    def __init__(self, out=None):
        self.out = out or sys.stdout
        try:  # a Windows console may default to a legacy code page
            self.out.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    def say(self, text=""):
        self.out.write(text + "\n")
        self.out.flush()

    def header(self):
        self.say("=" * 52)
        self.say("  BOT. 安裝程式")
        self.say("  從 GitHub 下載專案並配置開發環境")
        self.say("=" * 52)
        self.say()

    def step(self, number, title):
        self.say("[%d/%d] %s" % (number, TOTAL_STEPS, title))

    def ok(self, text):
        self.say("      [ OK ] " + text)

    def skip(self, text):
        self.say("      [ -- ] " + text)

    def warn(self, text):
        self.say("      [WARN] " + text)

    def fail(self, text):
        self.say("      [FAIL] " + text)

    def note(self, text):
        self.say("             " + text)

    def log(self, line):
        """Live output of a running command; the plain screen shows only results."""

    def done(self, seconds, lines):
        self.say()
        self.say("-" * 52)
        self.say("完成，用時 %d 秒。接下來：" % seconds)
        self.say()
        for line in lines:
            self.say(line)
        self.say("-" * 52)


# ── running things ────────────────────────────────────────────────
def run(args, cwd=None, env=None, on_line=None, cancel=None):
    """Run a command; return ``(exit code, last lines of its output)``.

    Output lines go to ``on_line`` as they appear. ``cancel`` (an Event) stops it.
    """
    try:
        process = subprocess.Popen(  # nosec B603
            args,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return 127, str(error)
    lines = collections.deque(maxlen=12)

    def read():
        for raw in process.stdout:
            line = raw.rstrip()
            if line.strip():
                lines.append(line)
                if on_line:
                    on_line(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    cancelled = False
    while process.poll() is None:
        if cancel is not None and cancel.is_set():
            process.terminate()
            cancelled = True
            break
        time.sleep(0.05)
    process.wait()
    reader.join(2)
    return (130 if cancelled else process.returncode), "\n".join(lines)


def download(url, destination):
    """Fetch ``url`` (HTTPS only) into ``destination``."""
    if not url.startswith("https://"):
        raise Failure("只允許以 HTTPS 下載：" + url)
    with urllib.request.urlopen(url, timeout=60) as response:  # nosec B310
        with open(destination, "wb") as stream:
            shutil.copyfileobj(response, stream, 1024 * 1024)


def venv_python(root):
    if os.name == "nt":
        return os.path.join(root, ".venv", "Scripts", "python.exe")
    return os.path.join(root, ".venv", "bin", "python")


def same_repo(url, wanted=REPO_URL):
    """Is ``url`` the GitHub repository (https or ssh spelling, any case)?"""

    def normal(text):
        text = text.strip().lower().rstrip("/")
        if text.endswith(".git"):
            text = text[:-4]
        for prefix in (
            "git@github.com:",
            "https://github.com/",
            "ssh://git@github.com/",
        ):
            if text.startswith(prefix):
                return text[len(prefix) :]
        return text

    return normal(url) == normal(wanted)


def unzip_here(archive, destination):
    """Extract a GitHub ZIP (one top folder) into ``destination``'s root."""
    os.makedirs(destination, exist_ok=True)
    base = os.path.realpath(destination)
    with zipfile.ZipFile(archive) as bundle:
        names = [n for n in bundle.namelist() if n and not n.startswith("/")]
        tops = {n.split("/")[0] for n in names}
        if len(tops) != 1:
            raise Failure("下載的壓縮檔結構不是預期的格式")
        prefix = tops.pop() + "/"
        for member in bundle.infolist():
            if not member.filename.startswith(prefix) or member.filename == prefix:
                continue
            relative = member.filename[len(prefix) :]
            target = os.path.realpath(os.path.join(base, relative))
            if target != base and not target.startswith(base + os.sep):
                raise Failure("壓縮檔含有不安全的路徑，已中止")
            if member.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with bundle.open(member) as source, open(target, "wb") as stream:
                shutil.copyfileobj(source, stream)


def inspect_target(path):
    """What an install into ``path`` would do: ``new``, ``update`` or ``blocked``."""
    root = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(root):
        return "new"
    if not os.path.isdir(root):
        return "blocked"
    if not os.listdir(root):
        return "new"
    return "update" if os.path.isdir(os.path.join(root, ".git")) else "blocked"


# ── the installer ─────────────────────────────────────────────────
class Installer:
    def __init__(
        self, options, screen=None, runner=None, fetch=download, which=shutil.which
    ):
        self.options = options
        self.screen = screen or Screen()
        self.cancel = threading.Event()
        self.run = runner or self.stream
        self.fetch = fetch
        self.which = which
        self.root = os.path.abspath(os.path.expanduser(options.dir))
        self.git = None
        self.started = time.time()

    def stream(self, args, cwd=None, env=None):
        """The default runner: live output goes to the screen, and it can be cancelled."""
        return run(args, cwd, env, on_line=self.screen.log, cancel=self.cancel)

    def check_cancelled(self):
        if self.cancel.is_set():
            raise Failure("已中止")

    # 1. the machine
    def check_machine(self):
        screen = self.screen
        screen.step(1, STEPS[0])
        version = sys.version_info
        text = "Python %d.%d.%d" % version[:3]
        if version < MIN_PYTHON:
            raise Failure("需要 Python %d.%d 以上，目前是 %s" % (MIN_PYTHON + (text,)))
        if version[:2] > TESTED_PYTHON:
            screen.warn(
                "%s 比 CI 測試過的 %d.%d 新，部分套件可能還沒支援"
                % ((text,) + TESTED_PYTHON)
            )
        else:
            screen.ok(text)
        self.git = None if self.options.zip else self.which("git")
        if self.git:
            code, output = self.run([self.git, "--version"])
            screen.ok(output.splitlines()[0] if code == 0 and output else "git")
        elif self.options.zip:
            screen.skip("依指定改用 ZIP 下載，不使用 git")
        else:
            screen.warn("找不到 git，改用 ZIP 下載（之後無法用 git 更新）")

    # 2. the code
    def get_code(self):
        screen = self.screen
        screen.step(2, STEPS[1])
        root = self.root
        exists = os.path.isdir(root) and os.listdir(root)
        if exists and os.path.isdir(os.path.join(root, ".git")):
            return self.update(root)
        if exists:
            raise Failure(
                "資料夾已存在而且不是 BOT. 的 git 倉庫："
                + root
                + "\n換一個資料夾，或先清空它"
            )
        if self.git:
            return self.clone(root)
        return self.from_zip(root)

    def update(self, root):
        code, remote = self.run(
            [self.git or "git", "-C", root, "remote", "get-url", "origin"]
        )
        if code != 0 or not same_repo(remote.strip(), self.options.repo):
            raise Failure(
                "這個資料夾的 git 來源不是 " + self.options.repo + "，不會更動它"
            )
        code, output = self.run([self.git, "-C", root, "pull", "--ff-only"])
        if code != 0:
            raise Failure("git pull 失敗（有未提交的修改或分支已分歧？）\n" + output)
        self.screen.ok("已更新現有的倉庫：" + root)
        self.screen.note(output.splitlines()[-1] if output else "")

    def clone(self, root):
        command = [self.git, "clone", "--progress"]
        if self.options.branch:
            command += ["--branch", self.options.branch]
        code, output = self.run(command + [self.options.repo, root])
        if code != 0:
            raise Failure("git clone 失敗\n" + output)
        self.screen.ok("已複製 %s 到 %s" % (self.options.repo, root))

    def from_zip(self, root):
        branch = self.options.branch or "main"
        with tempfile.TemporaryDirectory(prefix="bot-install-") as scratch:
            archive = os.path.join(scratch, "bot.zip")
            try:
                self.screen.log("下載 " + ZIP_URL % branch)
                self.fetch(ZIP_URL % branch, archive)
                self.screen.log("解壓縮")
                unzip_here(archive, root)
            except (OSError, zipfile.BadZipFile) as error:
                raise Failure("下載或解壓縮失敗：%s" % error)
        self.screen.ok("已下載 %s 分支到 %s" % (branch, root))

    # 3. the virtual environment
    def make_venv(self):
        screen = self.screen
        screen.step(3, STEPS[2])
        python = venv_python(self.root)
        if os.path.exists(python):
            screen.skip(".venv 已存在，沿用")
            return
        code, output = self.run(
            [sys.executable, "-m", "venv", os.path.join(self.root, ".venv")]
        )
        if code != 0 or not os.path.exists(python):
            raise Failure("建立虛擬環境失敗\n" + output)
        screen.ok(".venv")

    # 4. the dependencies
    def install_packages(self):
        screen = self.screen
        screen.step(4, STEPS[3])
        python = venv_python(self.root)
        files = ["requirements.txt"]
        if not self.options.no_dev:
            files.append("requirements-dev.txt")
        command = [
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--progress-bar",
            "off",
        ]
        for name in files:
            if not os.path.exists(os.path.join(self.root, name)):
                raise Failure("找不到 " + name + "，程式碼可能沒有完整取得")
            command += ["-r", name]
        before = time.time()
        code, output = self.run(command, cwd=self.root)
        if code != 0:
            raise Failure("pip 安裝失敗\n" + output)
        screen.ok("%s（%d 秒）" % (" + ".join(files), time.time() - before))

    # 5. .env
    def write_env(self):
        screen = self.screen
        screen.step(5, STEPS[4])
        path = os.path.join(self.root, ".env")
        if os.path.exists(path):
            screen.skip(".env 已存在，不會更動")
            return
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(ENV_TEMPLATE)
        screen.ok(".env（空白範本，請自行填入 DISCORD_TOKEN）")

    # 6. check
    def verify(self):
        screen = self.screen
        screen.step(6, STEPS[5])
        python = venv_python(self.root)
        script = (
            "import importlib\n"
            "missing = []\n"
            "for name in %r:\n"
            "    try:\n"
            "        importlib.import_module(name)\n"
            "    except Exception:\n"
            "        missing.append(name)\n"
            "print('missing=' + ','.join(missing))\n" % (IMPORTS,)
        )
        code, output = self.run([python, "-c", script], cwd=self.root)
        marker = [line for line in output.splitlines() if line.startswith("missing=")]
        if code != 0 or not marker:
            raise Failure("無法執行虛擬環境的 Python\n" + output)
        missing = [name for name in marker[-1][len("missing=") :].split(",") if name]
        if missing:
            raise Failure("這些套件無法匯入：" + ", ".join(missing))
        screen.ok("%d 個主要套件都能匯入" % len(IMPORTS))
        if self.options.test:
            screen.note("執行測試…")
            before = time.time()
            code, output = self.run(
                [python, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=self.root
            )
            summary = output.splitlines()[-1] if output else ""
            if code != 0:
                raise Failure("測試沒有全部通過\n" + output)
            screen.ok("測試通過（%d 秒）：%s" % (time.time() - before, summary))

    # all of it
    def install(self):
        self.screen.header()
        self.check_machine()
        if self.options.check:
            self.screen.say()
            self.screen.say("只檢查環境，沒有安裝任何東西。")
            return 0
        for step in (
            self.get_code,
            self.make_venv,
            self.install_packages,
            self.write_env,
            self.verify,
        ):
            self.check_cancelled()
            step()
        self.finish()
        return 0

    def next_steps(self):
        python = venv_python(self.root)
        run_python = os.path.relpath(python, self.root)
        return [
            "  1. 編輯設定檔，填入 DISCORD_TOKEN",
            "       " + os.path.join(self.root, ".env"),
            "  2. 啟動機器人",
            "       cd " + self.root,
            "       " + run_python + " -m src.main",
            "  3. 執行測試",
            "       " + run_python + " -m pytest -q",
            "",
            "說明文件：docs/DEVELOPMENT.md、CONTRIBUTING.md",
        ]

    def finish(self):
        self.screen.done(time.time() - self.started, self.next_steps())


# ── drawing text ──────────────────────────────────────────────────
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
BOLD, DIM, REVERSE, RESET = "\x1b[1m", "\x1b[2m", "\x1b[7m", "\x1b[0m"
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def bold(text):
    return BOLD + text + RESET


def dim(text):
    return DIM + text + RESET


def reverse(text):
    return REVERSE + text + RESET


def char_cells(char):
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def cells(text):
    """How many terminal columns ``text`` takes (CJK is double width, styles are free)."""
    return sum(char_cells(c) for c in _ANSI.sub("", text))


def fit(text, width):
    """``text`` padded or cut to exactly ``width`` columns; styles are kept."""
    if cells(text) <= width:
        return text + " " * (width - cells(text))
    out, used, index = [], 0, 0
    while index < len(text):
        match = _ANSI.match(text, index)
        if match:
            out.append(match.group())
            index = match.end()
            continue
        step = char_cells(text[index])
        if used + step > width - 1:
            break
        out.append(text[index])
        used += step
        index += 1
    return "".join(out) + "…" + RESET + " " * (width - used - 1)


def box(rows, width, title=""):
    """A rounded box ``width`` columns wide around ``rows`` (strings)."""
    inner = width - 2
    label = " %s " % title if title else ""
    top = "╭─" + bold(label) + "─" * (inner - 1 - cells(label)) + "╮"
    lines = [top]
    for row in rows:
        lines.append("│ " + fit(row, inner - 2) + " │")
    lines.append("╰" + "─" * inner + "╯")
    return lines


def side_by_side(left, right, gap=3):
    """Two blocks next to each other; ``left`` has a fixed width."""
    width = max((cells(line) for line in left), default=0)
    rows = max(len(left), len(right))
    out = []
    for index in range(rows):
        a = left[index] if index < len(left) else ""
        b = right[index] if index < len(right) else ""
        out.append(a + " " * (width - cells(a)) + " " * gap + b)
    return out


# ── the text box ──────────────────────────────────────────────────
class TextBox:
    """One line of editable text with a cursor."""

    def __init__(self, text=""):
        self.text = text
        self.pos = len(text)

    def key(self, key):
        """Apply one key; returns True when it was an editing key."""
        text, pos = self.text, self.pos
        if len(key) == 1 and key.isprintable():
            self.text, self.pos = text[:pos] + key + text[pos:], pos + 1
        elif key == "backspace" and pos:
            self.text, self.pos = text[: pos - 1] + text[pos:], pos - 1
        elif key == "delete":
            self.text = text[:pos] + text[pos + 1 :]
        elif key == "left":
            self.pos = max(pos - 1, 0)
        elif key == "right":
            self.pos = min(pos + 1, len(text))
        elif key == "home":
            self.pos = 0
        elif key == "end":
            self.pos = len(text)
        elif key == "ctrl-u":
            self.text, self.pos = text[pos:], 0
        else:
            return False
        return True

    def render(self, width):
        """The text, cut to ``width`` columns around the cursor, cursor in reverse video."""
        before, at, after = (
            self.text[: self.pos],
            self.text[self.pos : self.pos + 1] or " ",
            self.text[self.pos + 1 :],
        )
        while cells(before) + char_cells(at) > width - 1 and before:
            before = before[1:]
        room = width - cells(before) - char_cells(at)
        trimmed = ""
        for char in after:
            if cells(trimmed) + char_cells(char) > room:
                break
            trimmed += char
        used = cells(before) + char_cells(at) + cells(trimmed)
        return before + reverse(at) + trimmed + " " * (width - used)


# ── what the screen shows ─────────────────────────────────────────
class TuiScreen:
    """The installer's ``Screen`` for the terminal UI: it records, the view draws."""

    def __init__(self):
        self.lock = threading.RLock()
        self.state = ["pending"] * TOTAL_STEPS  # pending, running, ok, skip, warn, fail
        self.detail = [""] * TOTAL_STEPS
        self.current = -1
        self.log_lines = collections.deque(maxlen=200)
        self.finished = None  # (seconds, next-step lines) on success
        self.error = None  # lines of the reason on failure

    def say(self, text=""):
        pass

    def header(self):
        pass

    def step(self, number, title):
        with self.lock:
            if self.current >= 0 and self.state[self.current] == "running":
                self.state[self.current] = "ok"
            self.current = number - 1
            self.state[self.current] = "running"

    def _mark(self, state, text):
        with self.lock:
            if self.current >= 0:
                self.state[self.current] = state
                self.detail[self.current] = text

    def ok(self, text):
        self._mark("ok", text)

    def skip(self, text):
        self._mark("skip", text)

    def warn(self, text):
        self._mark("warn", text)

    def fail(self, text):
        self._mark("fail", text)

    def note(self, text):
        with self.lock:
            if self.current >= 0 and text.strip():
                self.detail[self.current] = text.strip()

    def log(self, line):
        with self.lock:
            self.log_lines.append(line.strip())

    def done(self, seconds, lines):
        with self.lock:
            self.finished = (seconds, list(lines))

    def completed(self):
        with self.lock:
            return sum(1 for s in self.state if s in ("ok", "skip", "warn"))


MIN_WIDTH, MAX_WIDTH = 56, 92
MARKS = {
    "pending": "○",
    "running": "",
    "ok": "✓",
    "skip": "–",
    "warn": "!",
    "fail": "✗",
}


def header_box(width, height, facts, logo=True):
    """The top box: the logo (when there is room) and what this machine has."""
    inner = width - 6
    text = [
        bold("✻  B O T .   安裝程式"),
        "▂" * min(inner - 20, 36),
        dim("從 GitHub 下載專案並配置開發環境"),
        "",
        dim(facts[0]),
        dim(facts[1]),
    ]
    if logo and height >= 28 and width >= 64:
        block = side_by_side(list(LOGO), [""] * 2 + text, gap=3)
        return box(block, width)
    return box(text, width)


def welcome_panel(width, textbox, options, status):
    notes = {
        "new": "會建立這個資料夾",
        "update": "資料夾已有 BOT. 倉庫，會改為更新（不動 .env 與 .venv）",
        "blocked": "這個資料夾已存在而且不是 BOT. 倉庫，請換一個位置",
    }
    rows = [
        "安裝位置",
        "╭" + "─" * (width - 10) + "╮",
        "│" + " " + textbox.render(width - 12) + " " + "│",
        "╰" + "─" * (width - 10) + "╯",
        dim(notes[status]),
        "",
        dim(
            "來源  %s%s"
            % (options.repo, "（分支 %s）" % options.branch if options.branch else "")
        ),
        dim("內容  程式碼 · 虛擬環境 · 依賴套件 · .env 範本"),
    ]
    return box(rows, width, "下載專案")


def progress_panel(width, model, now):
    rows = []
    frame = SPINNER[int(now * 10) % len(SPINNER)]
    with model.lock:
        for index, title in enumerate(STEPS):
            state = model.state[index]
            mark = frame if state == "running" else MARKS[state]
            line = "%s  %d  %s" % (mark, index + 1, title)
            if model.detail[index]:
                line = fit(line, 24) + dim(model.detail[index])
            rows.append(
                bold(line)
                if state == "running"
                else (dim(line) if state == "pending" else line)
            )
        done = model.completed()
    span = width - 12
    filled = round(span * done / TOTAL_STEPS)
    rows.append("")
    rows.append("━" * filled + "─" * (span - filled) + "  %d/%d" % (done, TOTAL_STEPS))
    return box(rows, width, "進度")


def bar_panel(width, model):
    span = width - 12
    done = model.completed()
    filled = round(span * done / TOTAL_STEPS)
    return box(
        ["━" * filled + "─" * (span - filled) + "  %d/%d" % (done, TOTAL_STEPS)],
        width,
        "進度",
    )


def log_panel(width, model, rows):
    with model.lock:
        shown = list(model.log_lines)[-rows:]
    lines = [dim(line) for line in shown] or [dim("等待輸出…")]
    lines += [""] * (rows - len(lines))
    return box(lines, width, "輸出")


def result_panel(width, model, failed):
    with model.lock:
        if failed:
            rows = [bold("✗  " + model.error[0])] + [
                "   " + line for line in model.error[1:]
            ]
            rows += ["", "排除問題後可以重試，已完成的步驟會被略過。"]
            return box(rows, width, "沒有完成")
        seconds, lines = model.finished
    return box([bold("✓  完成，用時 %d 秒" % seconds), ""] + lines, width, "完成")


def compose(mode, width, height, textbox, model, options, facts, status, now):
    """The whole screen as a list of lines (``height - 1`` of them)."""
    width = max(min(width, MAX_WIDTH), MIN_WIDTH)
    # The result needs the room the logo takes, so the logo only shows before it.
    lines = header_box(width, height, facts, logo=mode in ("welcome", "working"))
    if mode == "welcome":
        lines += welcome_panel(width, textbox, options, status)
        lines += [
            "",
            fit(
                " ❯ " + bold("1  下載專案") + dim("   取得程式碼、建立環境、安裝依賴"),
                width,
            ),
        ]
        hint = "輸入資料夾 · Enter 開始 · Esc 離開"
    elif mode == "working":
        lines += progress_panel(width, model, now)
        spare = height - 1 - len(lines) - 2 - 1
        if spare >= 3:
            lines += log_panel(width, model, spare - 2)
        hint = "Ctrl+C 中止"
    elif mode == "failed":
        lines += progress_panel(width, model, now)
        lines += result_panel(width, model, True)
        hint = "Enter 重試 · Esc 離開"
    else:
        lines += bar_panel(width, model)
        lines += result_panel(width, model, False)
        hint = "按任意鍵離開"
    clock = time.strftime("%H:%M:%S", time.localtime(now))
    while len(lines) < height - 2:
        lines.append("")
    footer = " " + hint
    lines = lines[: height - 2]
    lines.append(dim(fit(footer, width - len(clock)) + clock))
    return lines


# ── the terminal ──────────────────────────────────────────────────
class Terminal:
    """Alternate screen, hidden cursor, one frame at a time."""

    def __init__(self, out=None):
        self.out = out or sys.stdout

    def __enter__(self):
        if os.name == "nt":
            try:
                import ctypes

                kernel = ctypes.windll.kernel32
                handle = kernel.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel.SetConsoleMode(
                        handle, mode.value | 0x0004
                    )  # virtual terminal output
            except (ImportError, AttributeError, OSError):
                pass
        self.out.write("\x1b[?1049h\x1b[?25l")
        self.out.flush()
        return self

    def __exit__(self, *exc):
        self.out.write("\x1b[?25h\x1b[?1049l")
        self.out.flush()
        return False

    def size(self):
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def draw(self, lines):
        self.out.write(
            "\x1b[H"
            + "".join(line + "\x1b[K\r\n" for line in lines[:-1])
            + lines[-1]
            + "\x1b[K\x1b[J"
        )
        self.out.flush()


class WindowsKeys:
    def __init__(self):
        import msvcrt

        self.msvcrt = msvcrt

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def poll(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.msvcrt.kbhit():
                return self.read()
            time.sleep(0.01)
        return None

    def read(self):
        char = self.msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            return {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
                "G": "home",
                "O": "end",
                "S": "delete",
            }.get(self.msvcrt.getwch())
        return normal_key(char)


class PosixKeys:
    def __enter__(self):
        import termios
        import tty

        self.termios = termios
        self.fd = sys.stdin.fileno()
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.saved)
        return False

    def poll(self, timeout):
        import select

        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        char = os.read(self.fd, 1).decode("utf-8", "replace")
        if char != "\x1b":
            return normal_key(char)
        if not select.select([self.fd], [], [], 0.05)[0]:
            return "esc"
        rest = os.read(self.fd, 8).decode("utf-8", "replace")
        return {
            "[D": "left",
            "[C": "right",
            "[H": "home",
            "[F": "end",
            "[3~": "delete",
            "[1~": "home",
            "[4~": "end",
        }.get(rest)


def normal_key(char):
    if char in ("\r", "\n"):
        return "enter"
    if char in ("\x7f", "\x08"):
        return "backspace"
    if char == "\x1b":
        return "esc"
    if char == "\x03":
        return "ctrl-c"
    if char == "\x15":
        return "ctrl-u"
    return char


def make_keys():
    return WindowsKeys() if os.name == "nt" else PosixKeys()


def os_name(system=platform.system, release=platform.release, version=platform.version):
    """The system's name; Windows 11 still reports itself as release 10, so use the build."""
    name = system()
    if name == "Windows":
        build = version().split(".")[-1]
        if build.isdigit() and int(build) >= 22000:
            return "Windows 11"
    return "%s %s" % (name, release())


def machine_facts(which=shutil.which, runner=run):
    """Two short lines about this computer, for the header."""
    git = which("git")
    version = ""
    if git:
        code, output = runner([git, "--version"])
        if code == 0 and output:
            version = output.splitlines()[0].replace("git version ", "git ")
    python = "Python %d.%d.%d" % sys.version_info[:3]
    return (
        "%s · %s" % (python, version or "沒有 git（改用 ZIP 下載）"),
        os_name(),
    )


def run_tui(
    options,
    *,
    terminal=None,
    keys=None,
    installer=Installer,
    clock=time.time,
    facts=None,
):
    """The terminal UI. Returns the exit code (0 done, 1 failed, 130 stopped)."""
    terminal = terminal or Terminal()
    keys = keys or make_keys()
    facts = facts or machine_facts()
    model = TuiScreen()
    textbox = TextBox(os.path.abspath(os.path.expanduser(options.dir)))
    mode = "working" if options.yes else "welcome"
    job = worker = None
    code = 1

    def start():
        nonlocal job, worker, model, mode
        model = TuiScreen()
        options.dir = textbox.text.strip()
        job = installer(options, model)

        def work():
            try:
                job.install()
            except Failure as error:
                model.error = str(error).splitlines() or ["失敗"]
            except Exception as error:  # a crash is shown, never swallowed
                model.error = ["程式發生錯誤：%s" % error]

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        mode = "working"

    with terminal, keys:
        if mode == "working":
            start()
        while True:
            if mode == "working" and not worker.is_alive():
                if model.error:
                    mode = "failed"
                    code = 130 if job.cancel.is_set() else 1
                else:
                    mode, code = "done", 0
            width, height = terminal.size()
            status = (
                inspect_target(textbox.text.strip() or DEFAULT_DIR)
                if mode == "welcome"
                else "new"
            )
            terminal.draw(
                compose(
                    mode, width, height, textbox, model, options, facts, status, clock()
                )
            )
            try:
                key = keys.poll(0.1)
            except KeyboardInterrupt:
                key = "ctrl-c"
            if key is None:
                continue
            if mode == "welcome":
                if key in ("esc", "ctrl-c"):
                    return 130
                if key == "enter" and textbox.text.strip() and status != "blocked":
                    start()
                else:
                    textbox.key(key)
            elif mode == "working":
                if key == "ctrl-c":
                    job.cancel.set()
            elif mode == "failed":
                if key == "enter" and not job.cancel.is_set():
                    start()
                elif key in ("esc", "ctrl-c"):
                    return code
            else:
                return 0


# ── command line ──────────────────────────────────────────────────
def parse(argv):
    parser = argparse.ArgumentParser(
        description="BOT. 安裝程式：從 GitHub 下載專案並配置開發環境"
    )
    parser.add_argument("--dir", help="安裝到哪個資料夾（預設 ./%s）" % DEFAULT_DIR)
    parser.add_argument("--branch", help="分支或標籤（預設是倉庫的預設分支）")
    parser.add_argument(
        "--repo", default=REPO_URL, help="倉庫位址（預設 %s）" % REPO_URL
    )
    parser.add_argument("--zip", action="store_true", help="不用 git，改下載 ZIP")
    parser.add_argument("--no-dev", action="store_true", help="不安裝開發與測試工具")
    parser.add_argument("--test", action="store_true", help="裝好後執行全部測試")
    parser.add_argument("--check", action="store_true", help="只檢查環境，不安裝")
    parser.add_argument("--plain", action="store_true", help="不開啟畫面，只印純文字")
    parser.add_argument(
        "--yes", action="store_true", help="不詢問，全部用預設值（畫面會直接開始）"
    )
    options = parser.parse_args(argv)
    if options.zip and options.repo != REPO_URL:
        parser.error("--zip 只能下載官方倉庫")
    return options


def interactive():
    return bool(
        sys.stdin
        and sys.stdout
        and sys.stdin.isatty()
        and sys.stdout.isatty()
        and os.environ.get("TERM") != "dumb"
    )


def main(argv=None, *, ask=input, installer=Installer, tui=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    options = parse(sys.argv[1:] if argv is None else argv)
    use_tui = (
        not options.plain and not options.check and (tui is not None or interactive())
    )
    if not options.dir:
        options.dir = DEFAULT_DIR
        if not use_tui and not options.yes and not options.check and interactive():
            answer = ask("安裝到哪個資料夾？（Enter = ./%s）> " % DEFAULT_DIR).strip()
            options.dir = answer or DEFAULT_DIR
    if use_tui:
        code = (tui or run_tui)(options)
        if code == 130:
            print("已中止。")
        return code
    job = installer(options)
    try:
        return job.install()
    except Failure as error:
        job.screen.fail(str(error).splitlines()[0])
        for line in str(error).splitlines()[1:]:
            job.screen.note(line)
        job.screen.say()
        job.screen.say("安裝沒有完成。排除問題後可以再執行一次，已完成的步驟會被略過。")
        return 1
    except KeyboardInterrupt:
        job.screen.say()
        job.screen.say("已中止。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
