"""Nova, the AI usage placeholder and the desktop shortcut of the control panel."""

from datetime import datetime
import io
from pathlib import Path
import subprocess

import pytest
from rich.console import Console

from src.control_panel import ai_usage
from src.control_panel import nova
from src.control_panel import render
from src.control_panel import shortcut
from src.control_panel import theme
from src.control_panel.state import BotStatus
from src.control_panel.state import project_paths


def _capture(renderable, width=120):
    console = Console(
        file=io.StringIO(), width=width, force_terminal=True, color_system="truecolor"
    )
    with console.capture() as capture:
        console.print(renderable)
    styled = capture.get()
    plain = Console(file=io.StringIO(), width=width)
    with plain.capture() as plain_capture:
        plain.print(renderable)
    return plain_capture.get(), styled


def _view(width=120, ai=ai_usage.NO_USAGE):
    return render.ViewState(
        project_paths(),
        BotStatus("stopped"),
        [],
        0,
        datetime(2026, 10, 11, 21, 0),
        width,
        34,
        ai=ai,
    )


# ── Nova ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("frame", list(nova.FRAMES))
def test_every_frame_is_a_full_rectangle_of_known_colours(frame):
    pixels = nova.FRAMES[frame]
    assert len(pixels) == nova.ROWS * 2
    assert {len(row) for row in pixels} == {nova.WIDTH}
    assert set("".join(pixels)) <= set(nova.PALETTE) | {"."}


def test_nova_is_built_from_the_logo_colours():
    used = {nova.PALETTE[c] for c in "".join(nova.AWAKE) if c != "."}
    assert set(theme.BRAND) <= used  # all seven logo colours are in the sprite


def test_resting_nova_has_an_unlit_star_and_closed_eyes():
    awake, resting = "".join(nova.AWAKE), "".join(nova.RESTING)
    assert "Y" in awake and "Y" not in resting  # the star goes out
    assert "W" in awake and "W" not in resting  # no eye highlights: eyes closed


def test_sprite_is_drawn_with_half_blocks_in_true_colour():
    text = nova.sprite("awake")
    lines = text.plain.split("\n")
    assert len(lines) == nova.ROWS
    assert all(len(line) == nova.WIDTH for line in lines)
    _, styled = _capture(text, width=40)
    assert "\x1b[38;2;" in styled


# ── AI usage ──────────────────────────────────────────────────────
def test_the_panel_has_no_ai_source_yet():
    usage = ai_usage.NoUsageSource().read()
    assert not usage.connected
    assert usage.fraction is None


def test_dashboard_shows_no_model_no_local_model_and_a_grey_bar():
    plain, _ = _capture(render.dashboard(_view()))
    for text in ("諾瓦", "AI 用量", "無模型", "無本地模型", "休息中"):
        assert text in plain
    bar = render.usage_bar(ai_usage.NO_USAGE)
    assert bar.plain == "━" * render.NOVA_TEXT_WIDTH
    assert {str(span.style) for span in bar.spans} == {theme.BORDER}


def test_a_future_source_fills_the_bar_and_wakes_nova():
    usage = ai_usage.AiUsage(model="some-model", used=25, limit=100, unit="tokens")
    assert usage.fraction == 0.25
    bar = render.usage_bar(usage)
    coloured = [s for s in bar.spans if str(s.style) != theme.BORDER]
    assert sum(s.end - s.start for s in coloured) == round(
        0.25 * render.NOVA_TEXT_WIDTH
    )
    plain, _ = _capture(render.dashboard(_view(ai=usage)))
    assert "some-model" in plain and "已用 25%" in plain
    assert "無模型" not in plain


def test_a_model_without_a_limit_is_not_given_a_made_up_fraction():
    usage = ai_usage.AiUsage(local_model="local", used=10, limit=None)
    assert usage.fraction is None
    plain, _ = _capture(render.dashboard(_view(ai=usage)))
    assert "未計量" in plain


def test_a_broken_source_falls_back_to_nothing(tmp_path, monkeypatch):
    from src.control_panel import app

    class Broken:
        calls = 0

        def read(self):
            Broken.calls += 1
            if Broken.calls > 1:
                raise RuntimeError("source down")
            return ai_usage.AiUsage(model="m")

    panel = app.ControlPanel(
        Console(file=io.StringIO()),
        app.Keyboard(),
        ai_source=Broken(),
    )
    assert panel.ai.model == "m"
    panel.refresh(force=True)
    assert panel.ai == ai_usage.NO_USAGE


@pytest.mark.parametrize("width", [60, 80, 100, 130])
def test_nova_fits_every_width(width):
    plain, _ = _capture(render.dashboard(_view(width=width)), width=width)
    if width >= render.LOGO_MIN_WIDTH:
        assert "無本地模型" in plain
    if width >= render.NOVA_SPRITE_MIN_WIDTH:
        assert "▀" in plain.split("\n")[1][width // 2 :]  # the sprite on the right


# ── desktop shortcut ──────────────────────────────────────────────
WINDOWS = [
    (1, "BOT. Control Panel - Chrome", "Chrome_WidgetWin_1"),  # a browser tab
    (2, "PowerShell", "CASCADIA_HOSTING_WINDOW_CLASS"),
    (3, "BOT. 機器人控制台", "CASCADIA_HOSTING_WINDOW_CLASS"),
]


def test_only_a_terminal_window_showing_the_panel_is_found():
    assert shortcut.find_panel(WINDOWS) == 3
    assert shortcut.find_panel(WINDOWS[:2]) is None
    assert shortcut.find_panel([(4, "BOT. Control Panel", "ConsoleWindowClass")]) == 4


def test_open_raises_an_existing_panel_instead_of_opening_another(tmp_path):
    raised, spawned = [], []
    result = shortcut.open_panel(
        tmp_path,
        windows=lambda: WINDOWS,
        raise_window=raised.append,
        spawn=lambda *a, **k: spawned.append(a),
        which=lambda _: "wt.exe",
    )
    assert result == "focused" and raised == [3] and spawned == []


def test_open_starts_the_panel_in_a_new_terminal_window(tmp_path):
    spawned = []
    result = shortcut.open_panel(
        tmp_path,
        windows=lambda: WINDOWS[:2],
        raise_window=lambda _: True,
        spawn=lambda argv, **kw: spawned.append((argv, kw)),
        which=lambda _: "wt.exe",
    )
    argv, kw = spawned[0]
    assert result == "opened"
    assert argv[:3] == ["wt.exe", "-w", "new"]
    assert argv[-1] == str(tmp_path / "run_bot.bat")
    assert kw["cwd"] == str(tmp_path)


def test_without_windows_terminal_a_classic_console_is_used(tmp_path):
    spawned = []
    shortcut.open_panel(
        tmp_path,
        windows=lambda: [],
        raise_window=lambda _: True,
        spawn=lambda argv, **kw: spawned.append((argv, kw)),
        which=lambda _: None,
    )
    argv, kw = spawned[0]
    assert argv == ["cmd", "/c", str(tmp_path / "run_bot.bat")]
    assert kw["creationflags"] == getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def test_install_writes_the_icon_and_passes_paths_through_the_environment(tmp_path):
    root = tmp_path / "專案 有空格"
    assets = root / "src" / "control_panel" / "assets"
    assets.mkdir(parents=True)
    real = Path(shortcut.__file__).parent / "assets" / "bot-logo.png"
    (assets / "bot-logo.png").write_bytes(real.read_bytes())
    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    pythonw.parent.mkdir(parents=True)
    pythonw.write_bytes(b"")
    calls = []
    link = shortcut.install(
        root, folder=tmp_path, run=lambda argv, **kw: calls.append((argv, kw))
    )
    assert link == tmp_path / shortcut.SHORTCUT_NAME
    from PIL import Image

    with Image.open(assets / "bot-panel.ico") as icon:
        assert (16, 16) in icon.info["sizes"] and (256, 256) in icon.info["sizes"]
    argv, kw = calls[0]
    assert str(root) not in " ".join(argv)  # never spliced into the script
    env = kw["env"]
    assert env["BOT_LNK"] == str(link)
    assert env["BOT_TARGET"] == str(pythonw)
    assert env["BOT_ROOT"] == str(root)
    assert env["BOT_ARGS"].endswith("src.control_panel.shortcut open")
