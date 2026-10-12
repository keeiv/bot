"""The machine the bot runs on: model, processor, graphics card, memory.

Read once, in the background, with a single PowerShell query. Serial numbers
and other identifiers are never read.
"""

from dataclasses import dataclass
from dataclasses import field
import json
import platform
import subprocess
import sys
import threading
from typing import Callable, Optional

import psutil  # type: ignore[import-untyped]  # no typing metadata

_QUERY = (
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
    "$ErrorActionPreference='SilentlyContinue';"
    "$cs=Get-CimInstance Win32_ComputerSystem;"
    "$bb=Get-CimInstance Win32_BaseBoard;"
    "$cpu=Get-CimInstance Win32_Processor|Select-Object -First 1;"
    "$gpu=@(Get-CimInstance Win32_VideoController|ForEach-Object{$_.Name});"
    "$os=Get-CimInstance Win32_OperatingSystem;"
    "[pscustomobject]@{maker=$cs.Manufacturer;model=$cs.Model;"
    "board_maker=$bb.Manufacturer;board=$bb.Product;"
    "cpu=$cpu.Name;gpu=$gpu;os=$os.Caption;build=$os.BuildNumber}"
    "|ConvertTo-Json -Compress"
)

# What OEM firmware puts in these fields on machines that were built from parts.
_PLACEHOLDERS = (
    "system manufacturer",
    "system product name",
    "to be filled by o.e.m.",
    "default string",
    "not applicable",
    "unknown",
    "o.e.m.",
)


@dataclass(frozen=True)
class HostInfo:
    machine: str = ""  # "ASUS ROG Zephyrus G14"
    board: str = ""  # motherboard, for machines without a real model name
    cpu: str = ""
    gpus: tuple[str, ...] = field(default_factory=tuple)
    os_name: str = ""
    cores: int = 0
    threads: int = 0
    memory_gb: float = 0.0

    @property
    def model_line(self) -> str:
        return self.machine or self.board or platform.node() or "—"


def _clean(value: object) -> str:
    text = " ".join(str(value or "").split())
    return "" if text.lower() in _PLACEHOLDERS else text


def _join(maker: str, name: str) -> str:
    """``maker name`` without repeating the maker (``ASUS ASUS PRIME`` -> ``ASUS PRIME``)."""
    if not name:
        return maker
    if maker and not name.lower().startswith(maker.lower().split()[0]):
        return f"{maker} {name}"
    return name


def parse_host(raw: str, *, cores: int, threads: int, memory_bytes: int) -> HostInfo:
    """Build a :class:`HostInfo` from the PowerShell JSON (may be empty or bad)."""
    try:
        data = json.loads(raw.lstrip("\ufeff")) if raw.strip() else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    gpus = data.get("gpu") or []
    if isinstance(gpus, str):
        gpus = [gpus]
    cleaned_gpus = tuple(dict.fromkeys(_clean(g) for g in gpus if _clean(g)))
    maker, model = _clean(data.get("maker")), _clean(data.get("model"))
    board = _join(_clean(data.get("board_maker")), _clean(data.get("board")))
    os_name = _clean(data.get("os")).replace("Microsoft ", "")
    return HostInfo(
        machine=_join(maker, model) if model else "",
        board=board,
        cpu=_clean(data.get("cpu")) or _clean(platform.processor()),
        gpus=cleaned_gpus,
        os_name=os_name or f"{platform.system()} {platform.release()}",
        cores=cores,
        threads=threads,
        memory_gb=memory_bytes / (1024**3),
    )


def read_host(
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> HostInfo:
    """Ask Windows for the hardware description. Never raises."""
    raw = ""
    if sys.platform == "win32":
        try:
            done = run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _QUERY],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            raw = done.stdout or ""
        except (OSError, subprocess.SubprocessError):
            raw = ""
    return parse_host(
        raw,
        cores=psutil.cpu_count(logical=False) or 0,
        threads=psutil.cpu_count(logical=True) or 0,
        memory_bytes=psutil.virtual_memory().total,
    )


class HostReader:
    """Reads the host in a background thread so the panel opens at once."""

    def __init__(self, read: Callable[[], HostInfo] = read_host) -> None:
        self._read = read
        self._info: Optional[HostInfo] = None
        self._done = threading.Event()
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            self._info = self._read()
        except Exception:  # hardware info is decoration; never break the panel
            self._info = HostInfo()
        finally:
            self._done.set()

    @property
    def info(self) -> Optional[HostInfo]:
        """The host, or None while it is still being read."""
        return self._info

    def wait(self, timeout: float) -> Optional[HostInfo]:
        self._done.wait(timeout)
        return self._info
