"""A desktop shortcut that opens the panel in its own window, or brings it back.

``python -m src.control_panel.shortcut install`` writes ``BOT. 控制台.lnk`` on
the desktop with the BOT. icon. The shortcut runs ``pythonw`` (no console of
its own) with ``open``: if a panel window is already there it is brought to
the front, otherwise a new Windows Terminal window is opened for it (a classic
console window when Windows Terminal is missing). Pin the shortcut to the
taskbar by right-clicking it; Windows does not let programs pin themselves.

A panel that is an inactive tab inside another terminal window cannot be found
by its title, so a click then opens a second panel window. Two panels only
read the same files, so this is harmless.
"""

from collections.abc import Callable
from collections.abc import Sequence
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

from src.control_panel.state import project_paths

SHORTCUT_NAME = "BOT. 控制台.lnk"
WINDOW_TITLES = ("BOT. 機器人控制台", "BOT. Control Panel")  # panel, launcher
# Windows Terminal and the classic console. Other windows (a browser tab named
# "BOT. Control Panel", say) must never be picked.
TERMINAL_CLASSES = ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass")
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

Window = tuple[int, str, str]  # handle, title, class name


# ── finding and focusing the window ───────────────────────────────
def list_windows() -> list[Window]:
    """Every visible top-level window."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[Window] = []

    def visit(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        found.append((int(hwnd), title.value, name.value))
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(callback(visit), 0)
    return found


def find_panel(windows: Sequence[Window]) -> Optional[int]:
    """The handle of a terminal window showing the panel, if there is one."""
    for hwnd, title, class_name in windows:
        if class_name in TERMINAL_CLASSES and any(t in title for t in WINDOW_TITLES):
            return hwnd
    return None


def focus(hwnd: int) -> bool:
    """Restore and raise ``hwnd``; if Windows refuses, flash it on the taskbar."""
    import ctypes

    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    if user32.SetForegroundWindow(hwnd):
        return True
    user32.FlashWindow(hwnd, True)
    return False


# ── opening a new window ──────────────────────────────────────────
def launch_command(root: Path, terminal: Optional[str]) -> list[str]:
    """How to open ``run_bot.bat`` in a window of its own."""
    script = str(root / "run_bot.bat")
    if terminal:
        return [
            terminal,
            "-w",
            "new",
            "--title",
            WINDOW_TITLES[0],
            "-d",
            str(root),
            "cmd",
            "/c",
            script,
        ]
    return ["cmd", "/c", script]


def open_panel(
    root: Optional[Path] = None,
    *,
    windows: Callable[[], Sequence[Window]] = list_windows,
    raise_window: Callable[[int], bool] = focus,
    spawn: Callable[..., object] = subprocess.Popen,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> str:
    """Bring the panel to the front, or open it. Returns what was done."""
    root = root or project_paths().root
    hwnd = find_panel(windows())
    if hwnd is not None:
        raise_window(hwnd)
        return "focused"
    terminal = which("wt")
    flags = 0 if terminal else getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    spawn(launch_command(root, terminal), cwd=str(root), creationflags=flags)
    return "opened"


# ── installing the shortcut ───────────────────────────────────────
def write_icon(root: Path) -> Path:
    """``bot-panel.ico`` next to the logo, made from the logo."""
    from PIL import Image

    assets = root / "src" / "control_panel" / "assets"
    icon = assets / "bot-panel.ico"
    image = Image.open(assets / "bot-logo.png").convert("RGBA")
    side = max(image.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    # Pillow only writes sizes up to the source's, and large taskbars want 256.
    largest = max(ICON_SIZES)[0]
    if side < largest:
        square = square.resize((largest, largest), Image.Resampling.LANCZOS)
    square.save(icon, sizes=ICON_SIZES)
    return icon


def desktop() -> Path:
    """The desktop folder, wherever Windows (or OneDrive) has put it."""
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
            "[Environment]::GetFolderPath('Desktop')",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return Path(result.stdout.strip())


# The shortcut is written through IShellLinkW, the Unicode interface. The usual
# WScript.Shell object converts paths to the system's ANSI code page, so on an
# English-locale Windows a folder named 文件 becomes "??" and saving fails.
# Every value comes in through the environment, so no path is ever spliced
# into the script and nothing needs escaping.
_SHORTCUT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[ComImport, Guid("000214F9-0000-0000-C000-000000000046"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IShellLinkW {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder f, int cch, IntPtr fd, int flags);
    void GetIDList(out IntPtr ppidl);
    void SetIDList(IntPtr pidl);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string s);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string s);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string s);
    void GetHotkey(out short key);
    void SetHotkey(short key);
    void GetShowCmd(out int cmd);
    void SetShowCmd(int cmd);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch, out int index);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string s, int index);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string s, int reserved);
    void Resolve(IntPtr hwnd, int flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string s);
}

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class CShellLink {}

public static class BotShortcut {
    public static void Save(string link, string target, string args, string dir, string icon, string note) {
        IShellLinkW s = (IShellLinkW)new CShellLink();
        s.SetPath(target);
        s.SetArguments(args);
        s.SetWorkingDirectory(dir);
        s.SetIconLocation(icon, 0);
        s.SetDescription(note);
        ((IPersistFile)s).Save(link, true);
    }
}
'@
[BotShortcut]::Save($env:BOT_LNK, $env:BOT_TARGET, $env:BOT_ARGS, $env:BOT_ROOT, $env:BOT_ICON, $env:BOT_NOTE)
"""


def install(
    root: Optional[Path] = None,
    *,
    folder: Optional[Path] = None,
    run: Callable[..., object] = subprocess.run,
) -> Path:
    """Write the icon and the desktop shortcut; returns the shortcut's path."""
    root = root or project_paths().root
    folder = folder or desktop()
    icon = write_icon(root)
    target = root / ".venv" / "Scripts" / "pythonw.exe"
    if not target.exists():
        found = shutil.which("pythonw")
        if not found:
            raise FileNotFoundError("找不到 pythonw.exe，請先建立 .venv")
        target = Path(found)
    link = folder / SHORTCUT_NAME
    env = {
        **os.environ,
        "BOT_LNK": str(link),
        "BOT_TARGET": str(target),
        "BOT_ARGS": "-X utf8 -m src.control_panel.shortcut open",
        "BOT_ROOT": str(root),
        "BOT_ICON": str(icon),
        "BOT_NOTE": "BOT. 機器人控制台",
    }
    run(
        ["powershell", "-NoProfile", "-Command", _SHORTCUT_SCRIPT],
        env=env,
        check=True,
    )
    return link


def main(argv: Sequence[str]) -> int:
    command = argv[0] if argv else "open"
    if command == "install":
        link = install()
        print(f"已建立捷徑：{link}")
        print("右鍵捷徑 →「釘選到工作列」，之後點一下就能開啟或切回控制台。")
        return 0
    if command == "open":
        open_panel()
        return 0
    print("用法：python -m src.control_panel.shortcut [install|open]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
