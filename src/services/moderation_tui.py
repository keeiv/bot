"""The review worker's terminal screen: start-up checklist, then two review slots.

State changes come from the review engine and the server (any thread); the
screen only reads them, so drawing never touches the network or a model.
"""

from collections import deque
from datetime import datetime
import threading
import time

from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if __package__:
    from . import moderation_protocol as protocol
    from ..control_panel import nova
    from ..control_panel import theme
else:
    import moderation_protocol as protocol
    import nova
    import theme

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
WIDTH = 92
PENDING, RUNNING, OK, WARN, FAIL = "pending", "running", "ok", "warn", "fail"
VERDICT_TEXT = {
    protocol.SAFE: ("✓ 安全", theme.OK),
    protocol.UNSAFE: ("✗ 不安全", theme.ERR),
    protocol.UNCERTAIN: ("? 無法確定", theme.WARN),
    protocol.ERROR: ("! 失敗", theme.ERR),
}
RESULT_TEXT = {
    protocol.APPROVED: ("通過", theme.OK),
    protocol.REJECTED: ("拒絕", theme.ERR),
    protocol.UNAVAILABLE: ("改人工", theme.WARN),
}
CATEGORY_TEXT = {"sexual": "色情", "violence": "暴力", "tos": "違反 Discord 規範"}


def _size(count):
    return (
        f"{count / 1024:.0f} KB"
        if count < 1024 * 1024
        else f"{count / 1024 / 1024:.1f} MB"
    )


class Dashboard:
    """Thread-safe state plus ``__rich__`` drawing."""

    def __init__(self, stages, address=""):
        self.stages = stages
        self.address = address
        self.lock = threading.RLock()
        self.steps = []  # start-up: {"label", "state", "detail", "fraction"}
        self.ready = False
        self.ollama = None  # None while unknown, then True / False
        self.models = {}  # stage number -> downloaded
        self.slots = [None] * protocol.MAX_IMAGES
        self.history = deque(maxlen=7)
        self.counts = {
            protocol.APPROVED: 0,
            protocol.REJECTED: 0,
            protocol.UNAVAILABLE: 0,
        }
        self.started = time.monotonic()
        self.live = None
        self.plain = False  # no terminal: print one line per event instead

    # ── state, written from anywhere ──────────────────────────────
    def step(self, label, state=RUNNING, detail="", fraction=None):
        """Create or update a start-up step by its label."""
        with self.lock:
            if self.plain and (state != RUNNING or fraction is None):
                print(f"[{state}] {label} {detail}", flush=True)
            for entry in self.steps:
                if entry["label"] == label:
                    entry.update(state=state, detail=detail, fraction=fraction)
                    return
            self.steps.append(
                {"label": label, "state": state, "detail": detail, "fraction": fraction}
            )

    def set_ready(self, ready=True):
        with self.lock:
            self.ready = ready

    def emit(self, kind, **details):
        """Progress from the engine and the server: ``begin``, ``stage``, ``end``."""
        with self.lock:
            slot = details.get("slot")
            if kind == "begin":
                self.slots[slot] = {
                    "name": details["name"],
                    "bytes": details["bytes"],
                    "began": time.monotonic(),
                    "stages": {},
                    "result": None,
                }
            elif kind == "stage" and self.slots[slot] is not None:
                info = self.slots[slot]["stages"].setdefault(
                    details["stage"], {"state": PENDING, "began": 0.0, "seconds": 0.0}
                )
                if details["state"] == RUNNING:
                    info.update(state=RUNNING, began=time.monotonic())
                else:
                    info.update(
                        state=details["state"], seconds=time.monotonic() - info["began"]
                    )
            elif kind == "end" and self.slots[slot] is not None:
                result = details["result"]
                self.slots[slot]["result"] = result
                self.slots[slot]["ended"] = time.monotonic()
                self.counts[result["verdict"]] += 1
                self.history.appendleft(
                    (
                        datetime.now().strftime("%H:%M:%S"),
                        self.slots[slot]["name"],
                        result,
                    )
                )
                if self.plain:
                    print(
                        f"[review] {result['verdict']} stage={result['stage']}",
                        flush=True,
                    )

    # ── drawing ───────────────────────────────────────────────────
    def __rich__(self):
        with self.lock:
            busy = any(s is not None and s["result"] is None for s in self.slots)
            parts = [self._header(busy)]
            if not self.ready:
                parts.append(self._boot())
            else:
                parts += [self._slot(i) for i in range(len(self.slots))]
                parts.append(self._history())
            parts.append(
                Text(self._footer(), style=theme.DIM, no_wrap=True, overflow="ellipsis")
            )
            return Group(*parts)

    def _header(self, busy):
        title = Text()
        title.append("✻  ", style=f"bold {theme.ACCENT}")
        title.append_text(theme.gradient("B O T ."))
        title.append("   圖片審核工作站", style=f"bold {theme.TEXT}")
        facts = Text(no_wrap=True, overflow="ellipsis")
        if self.ollama is None:
            facts.append("◌ Ollama 檢查中", style=theme.DIM)
        elif self.ollama:
            facts.append("● Ollama 運作中", style=f"bold {theme.OK}")
        else:
            facts.append("✗ Ollama 沒有回應", style=f"bold {theme.ERR}")
        ready = sum(1 for ok in self.models.values() if ok)
        facts.append(
            f"   模型 {ready}/{len(self.stages)}",
            style=theme.TEXT if ready == len(self.stages) else theme.WARN,
        )
        if self.address:
            facts.append(f"   {self.address}", style=theme.DIM)
        flow = Text(no_wrap=True, overflow="ellipsis")
        flow.append("三階段：", style=theme.DIM)
        for stage in self.stages:
            flow.append(stage["label"], style=theme.MUTED)
            if stage is not self.stages[-1]:
                flow.append(" → ", style=theme.DIM)
        flow.append("   全數安全才通過", style=theme.DIM)
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_column(width=nova.WIDTH, no_wrap=True)
        grid.add_row(
            Group(title, theme.brand_bar(40), facts, flow),
            nova.sprite("awake" if busy else "resting"),
        )
        return Panel(
            grid,
            box=box.ROUNDED,
            border_style=theme.ACCENT,
            padding=(0, 2),
            width=WIDTH,
        )

    def _boot(self):
        table = Table.grid(padding=(0, 2))
        table.add_column(width=1)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True, overflow="ellipsis")
        frame = SPINNER[int(time.monotonic() * 10) % len(SPINNER)]
        marks = {
            PENDING: ("○", theme.DIM),
            OK: ("✓", theme.OK),
            WARN: ("!", theme.WARN),
            FAIL: ("✗", theme.ERR),
        }
        for entry in self.steps:
            if entry["state"] == RUNNING:
                mark = Text(frame, style=f"bold {theme.ACCENT}")
            else:
                symbol, colour = marks[entry["state"]]
                mark = Text(symbol, style=f"bold {colour}")
            detail = Text(entry["detail"], style=theme.MUTED)
            if entry["fraction"] is not None:
                bar = Text()
                filled = round(min(max(entry["fraction"], 0.0), 1.0) * 24)
                for i in range(24):
                    bar.append(
                        "━",
                        style=(
                            theme.gradient_colour(i / 23)
                            if i < filled
                            else theme.BORDER
                        ),
                    )
                bar.append(f" {entry['fraction']:.0%}  ", style=theme.TEXT)
                bar.append_text(detail)
                detail = bar
            table.add_row(mark, Text(entry["label"], style=theme.TEXT), detail)
        if not self.steps:
            table.add_row("", Text("正在準備…", style=theme.DIM), "")
        return Panel(
            table,
            title=Text(" 準備中 ", style=f"bold {theme.TEXT}"),
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(1, 2),
            width=WIDTH,
        )

    def _slot(self, index):
        slot = self.slots[index]
        title = Text(f" 審核槽 {index + 1} ", style=f"bold {theme.TEXT}")
        if slot is None:
            return Panel(
                Text("閒置，等待機器人送來圖片", style=theme.DIM),
                title=title,
                title_align="left",
                box=box.ROUNDED,
                border_style=theme.BORDER,
                padding=(0, 2),
                width=WIDTH,
            )
        now = time.monotonic()
        result = slot["result"]
        head = Text(no_wrap=True, overflow="ellipsis")
        head.append(slot["name"], style=f"bold {theme.TEXT}")
        head.append(f"  {_size(slot['bytes'])}", style=theme.DIM)
        elapsed = (slot.get("ended", now)) - slot["began"]
        head.append(f"   用時 {elapsed:.0f} 秒", style=theme.DIM)
        lines = [head]
        frame = SPINNER[int(now * 10) % len(SPINNER)]
        for stage in self.stages:
            number = stage["stage"]
            info = slot["stages"].get(number)
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{'①②③'[number - 1]} {stage['label']}  ", style=theme.MUTED)
            row.append(f"{stage['model']:<24}", style=theme.DIM)
            if info is None:
                row.append("○ 等待" if result is None else "– 未進行", style=theme.DIM)
            elif info["state"] == RUNNING:
                row.append(
                    f"{frame} {'思考中' if stage['think'] else '判讀中'} {now - info['began']:.0f} 秒",
                    style=f"bold {theme.ACCENT}",
                )
            else:
                text, colour = VERDICT_TEXT.get(info["state"], ("?", theme.DIM))
                row.append(text, style=f"bold {colour}")
                row.append(f"  {info['seconds']:.1f} 秒", style=theme.DIM)
            lines.append(row)
        border = theme.ACCENT
        if result is not None:
            text, border = RESULT_TEXT[result["verdict"]]
            final = Text()
            final.append(f"結果：{text}", style=f"bold {border}")
            if result["categories"]:
                final.append(
                    "  " + "、".join(CATEGORY_TEXT[c] for c in result["categories"]),
                    style=theme.MUTED,
                )
            lines.append(final)
        return Panel(
            Group(*lines),
            title=title,
            title_align="left",
            box=box.ROUNDED,
            border_style=border,
            padding=(0, 2),
            width=WIDTH,
        )

    def _history(self):
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True, overflow="ellipsis")
        for clock, name, result in self.history:
            text, colour = RESULT_TEXT[result["verdict"]]
            where = f"第 {result['stage']} 階段" if result["stage"] else "—"
            categories = "、".join(CATEGORY_TEXT[c] for c in result["categories"])
            table.add_row(
                Text(clock, style=theme.DIM),
                Text(text, style=f"bold {colour}"),
                Text(where, style=theme.MUTED),
                Text(f"{name}  {categories}".strip(), style=theme.MUTED),
            )
        if not self.history:
            table.add_row(Text("還沒有審核紀錄", style=theme.DIM), "", "", "")
        counts = self.counts
        title = Text(
            f" 紀錄 · 通過 {counts[protocol.APPROVED]} · 拒絕 {counts[protocol.REJECTED]} · 改人工 {counts[protocol.UNAVAILABLE]} ",
            style=f"bold {theme.TEXT}",
        )
        return Panel(
            table,
            title=title,
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(0, 2),
            width=WIDTH,
        )

    def _footer(self):
        up = int(time.monotonic() - self.started)
        hours, rest = divmod(up, 3600)
        return f" 同時審核 {protocol.MAX_IMAGES} 張   Ctrl+C 結束   已執行 {hours}:{rest // 60:02d}:{rest % 60:02d}"

    # ── running it ────────────────────────────────────────────────
    def __enter__(self):
        self.live = Live(
            self, screen=True, auto_refresh=True, refresh_per_second=8, transient=True
        )
        self.live.__enter__()
        return self

    def __exit__(self, *exc):
        if self.live is not None:
            self.live.__exit__(*exc)
        return False
