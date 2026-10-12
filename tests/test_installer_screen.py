"""The installer's terminal screen: black and white, laid out like the control panel."""

import importlib.util
from pathlib import Path
import re
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "install.py"
spec = importlib.util.spec_from_file_location("bot_install_screen", SCRIPT)
install = importlib.util.module_from_spec(spec)
sys.modules["bot_install_screen"] = install
spec.loader.exec_module(install)

SIZES = [(56, 22), (80, 24), (92, 32), (120, 40), (200, 60)]
MODES = ["welcome", "working", "failed", "done"]
FACTS = ("Python 3.13.7 · git 2.45", "Windows 11")


def frame(mode, model=None, text="C:/x/bot", status="new", size=(92, 32)):
    model = model or install.TuiScreen()
    if mode == "done" and model.finished is None:
        model.finished = (12, ["  1. 編輯設定檔", "       C:/x/bot/.env"])
    if mode == "failed" and model.error is None:
        model.error = ["pip 安裝失敗", "ERROR: boom"]
    return install.compose(
        mode,
        size[0],
        size[1],
        install.TextBox(text),
        model,
        install.parse(["--dir", "bot"]),
        FACTS,
        status,
        1_700_000_000.0,
    )


# ── drawing ───────────────────────────────────────────────────────
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("size", SIZES)
def test_every_screen_fits_the_terminal_exactly(mode, size):
    lines = frame(mode, size=size)
    width = max(min(size[0], install.MAX_WIDTH), install.MIN_WIDTH)
    assert len(lines) == size[1] - 1  # never scrolls the terminal
    for line in lines:
        assert install.cells(line) in (0, width), (mode, size, line)


@pytest.mark.parametrize("mode", MODES)
def test_the_screen_is_black_and_white_only(mode):
    codes = set()
    for line in frame(mode):
        codes |= set(re.findall(r"\x1b\[([0-9;?]*)[A-Za-z]", line))
    assert codes <= {"0", "1", "2", "7"}, codes  # reset, bold, dim, reverse: no colours
    text = "\n".join(frame(mode))
    assert "Nova" not in text and "諾瓦" not in text


def test_the_logo_is_one_shape_in_one_grey():
    assert len({len(row) for row in install.LOGO}) == 1
    assert set("".join(install.LOGO)) <= set("█▀▄▓ ")
    assert "█" in "\n".join(frame("welcome", size=(92, 32)))  # room: the logo is drawn
    assert "█" not in "\n".join(frame("welcome", size=(80, 24)))  # short: it is dropped


def test_the_welcome_screen_has_one_function_and_a_text_box():
    text = "\n".join(frame("welcome"))
    assert "下載專案" in text and "安裝位置" in text and "C:/x/bot" in text
    assert text.count("❯") == 1  # one menu entry


def test_the_welcome_screen_says_what_the_folder_will_get():
    assert "會建立" in "\n".join(frame("welcome", status="new"))
    assert "更新" in "\n".join(frame("welcome", status="update"))
    assert "請換一個" in "\n".join(frame("welcome", status="blocked"))


def test_the_result_screens_show_the_reason_or_the_next_steps():
    assert "ERROR: boom" in "\n".join(frame("failed"))
    done = "\n".join(frame("done", size=(80, 30)))
    assert "完成，用時 12 秒" in done and "C:/x/bot/.env" in done


def test_fit_counts_double_width_text_and_keeps_styles():
    assert install.cells("安裝") == 4 and install.cells(install.bold("abc")) == 3
    assert install.cells(install.fit("安裝程式", 10)) == 10
    cut = install.fit("安裝程式很長很長很長", 9)
    assert install.cells(cut) == 9 and "…" in cut
    styled = install.fit(install.bold("x" * 30), 10)
    assert install.cells(styled) == 10 and install.RESET in styled


# ── the text box ──────────────────────────────────────────────────
def test_text_box_editing():
    box = install.TextBox("hello")
    box.key("home")
    box.key("x")
    assert (box.text, box.pos) == ("xhello", 1)
    box.key("end")
    box.key("backspace")
    assert box.text == "xhell"
    box.key("left")
    box.key("delete")
    assert box.text == "xhel"
    box.key("ctrl-u")
    assert box.text == "" and box.pos == 0
    assert box.key("esc") is False and box.key("enter") is False  # not editing keys


def test_text_box_render_is_exact_width_around_the_cursor():
    box = install.TextBox("C:/very/long/path/" * 6)
    for width in (10, 30, 60):
        shown = box.render(width)
        assert install.cells(shown) == width
        assert install.REVERSE in shown  # the cursor
    assert install.cells(install.TextBox("資料夾" * 20).render(25)) == 25
    assert install.cells(install.TextBox("").render(12)) == 12


# ── driving the screen with a fake terminal and keyboard ──────────
class FakeTerminal:
    def __init__(self, size=(92, 32)):
        self.frames = []
        self._size = size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def size(self):
        return self._size

    def draw(self, lines):
        self.frames.append("\n".join(lines))


class FakeKeys:
    """Plays ``script``; ``None`` is an idle tick. Out of keys: Esc."""

    def __init__(self, script):
        self.script = list(script)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def poll(self, timeout):
        time.sleep(0.01)
        return self.script.pop(0) if self.script else "esc"


def fake_installer(behaviours, created):
    """Each created installer takes the next behaviour: ok, fail or wait."""

    class Job:
        def __init__(self, options, screen):
            self.options, self.screen = options, screen
            self.cancel = install.threading.Event()
            self.behaviour = behaviours.pop(0)
            created.append(options.dir)

        def install(self):
            self.screen.step(1, install.STEPS[0])
            self.screen.ok("fine")
            if self.behaviour == "wait":
                self.cancel.wait(5)
                raise install.Failure("已中止")
            if self.behaviour == "fail":
                self.screen.step(2, install.STEPS[1])
                self.screen.fail("nope")
                raise install.Failure("取得程式碼失敗\n網路不通")
            self.screen.done(3, ["  next"])

    return Job


def drive(tmp_path, script, behaviours, *extra):
    created, terminal = [], FakeTerminal()
    options = install.parse(["--dir", str(tmp_path / "bot"), *extra])
    code = install.run_tui(
        options,
        terminal=terminal,
        keys=FakeKeys(script),
        installer=fake_installer(list(behaviours), created),
        facts=FACTS,
    )
    return code, created, terminal.frames


def test_escape_on_the_first_screen_leaves_without_installing(tmp_path):
    code, created, frames = drive(tmp_path, ["esc"], [])
    assert code == 130 and created == []
    assert "下載專案" in frames[0]


def test_enter_downloads_and_any_key_closes_the_result(tmp_path):
    code, created, frames = drive(tmp_path, ["enter", None, None, None, "x"], ["ok"])
    assert code == 0 and created == [str(tmp_path / "bot")]
    assert "完成，用時" in frames[-1] and "next" in frames[-1]


def test_the_folder_can_be_typed_into_the_text_box(tmp_path):
    target = str(tmp_path / "elsewhere")
    typed = ["ctrl-u", *target, "enter", None, None, None, "x"]
    code, created, _ = drive(tmp_path, typed, ["ok"])
    assert code == 0 and created == [target]


def test_a_failure_is_shown_and_enter_tries_again(tmp_path):
    keys = ["enter", None, None, None, "enter", None, None, None, "x"]
    code, created, frames = drive(tmp_path, keys, ["fail", "ok"])
    assert len(created) == 2  # the retry started a second installer
    assert any("取得程式碼失敗" in f and "網路不通" in f for f in frames)
    assert code == 0


def test_a_failure_followed_by_escape_exits_with_failure(tmp_path):
    code, created, frames = drive(
        tmp_path, ["enter", None, None, None, "esc"], ["fail"]
    )
    assert code == 1 and len(created) == 1
    assert "沒有完成" in frames[-1]


def test_ctrl_c_while_working_stops_the_install_and_cannot_be_retried(tmp_path):
    keys = ["enter", None, "ctrl-c", None, None, None, "enter", "esc"]
    code, created, _ = drive(tmp_path, keys, ["wait"])
    assert code == 130 and len(created) == 1  # Enter after a stop does not restart


def test_a_folder_that_is_not_the_repository_cannot_be_started(tmp_path):
    folder = tmp_path / "bot"
    folder.mkdir()
    (folder / "mine.txt").write_text("keep", encoding="utf-8")
    code, created, frames = drive(tmp_path, ["enter", "enter", "esc"], [])
    assert created == [] and code == 130
    assert "請換一個" in frames[-1]


def test_yes_starts_at_once_without_the_first_screen(tmp_path):
    code, created, frames = drive(tmp_path, [None, None, None, "x"], ["ok"], "--yes")
    assert created == [str(tmp_path / "bot")] and code == 0
    assert "輸入資料夾" not in frames[0]


def test_inspect_target(tmp_path):
    assert install.inspect_target(str(tmp_path / "none")) == "new"
    (tmp_path / "empty").mkdir()
    assert install.inspect_target(str(tmp_path / "empty")) == "new"
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    assert install.inspect_target(str(tmp_path / "repo")) == "update"
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "f.txt").write_text("x", encoding="utf-8")
    assert install.inspect_target(str(tmp_path / "other")) == "blocked"
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    assert install.inspect_target(str(tmp_path / "file.txt")) == "blocked"


# ── which screen is used ──────────────────────────────────────────
def test_the_terminal_screen_is_used_unless_plain_or_check(tmp_path, monkeypatch):
    seen = []

    class PlainJob:
        def __init__(self, options):
            pass

        def install(self):
            seen.append("plain")
            return 0

    def fake_tui(options):
        seen.append("tui")
        return 0

    base = ["--dir", str(tmp_path / "bot")]
    install.main(base, tui=fake_tui, installer=PlainJob)
    install.main(base + ["--plain"], tui=fake_tui, installer=PlainJob)
    install.main(base + ["--check"], tui=fake_tui, installer=PlainJob)
    assert seen == ["tui", "plain", "plain"]
    monkeypatch.setattr(install, "interactive", lambda: False)
    install.main(base, installer=PlainJob)  # a pipe or a log: plain lines
    assert seen[-1] == "plain"


# ── running commands ──────────────────────────────────────────────
def test_run_streams_lines_and_returns_the_tail():
    lines = []
    code, tail = install.run(
        [sys.executable, "-c", "print('one'); print('two')"], on_line=lines.append
    )
    assert code == 0 and lines == ["one", "two"] and tail.splitlines() == ["one", "two"]


def test_run_can_be_cancelled():
    cancel = install.threading.Event()
    started = time.time()
    install.threading.Timer(0.3, cancel.set).start()
    code, _ = install.run(
        [sys.executable, "-c", "import time; time.sleep(30)"], cancel=cancel
    )
    assert code == 130 and time.time() - started < 10


def test_a_command_that_does_not_exist_is_a_failure_not_a_crash():
    code, message = install.run(["definitely-not-a-program-xyz"])
    assert code == 127 and message


def test_windows_11_is_named_by_its_build_number():
    def name(release, version):
        return install.os_name(lambda: "Windows", lambda: release, lambda: version)

    assert name("10", "10.0.26200") == "Windows 11"
    assert name("10", "10.0.19045") == "Windows 10"
    assert (
        install.os_name(lambda: "Linux", lambda: "6.1", lambda: "#1 SMP") == "Linux 6.1"
    )
