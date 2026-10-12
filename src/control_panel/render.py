"""Pure drawing code: state in, rich renderables out. No input, no I/O."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import platform
from typing import Optional

from rich import box
from rich.align import Align
from rich.cells import cell_len
from rich.console import Group
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.control_panel import launch
from src.control_panel import logo
from src.control_panel import menu
from src.control_panel import nova
from src.control_panel import theme
from src.control_panel.ai_usage import AiUsage
from src.control_panel.ai_usage import NO_USAGE
from src.control_panel.database import DbStatus
from src.control_panel.host import HostInfo
from src.control_panel.state import BotStatus
from src.control_panel.state import format_duration
from src.control_panel.state import LogRecord
from src.control_panel.state import Paths
from src.control_panel.state import short_logger

MAX_WIDTH = 120
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SELECTED_BG = "#2b2421"
TIP = "控制台關閉後，在獨立視窗執行的機器人仍會繼續運作"

NOTICE_STYLES = {
    "ok": theme.OK,
    "warn": theme.WARN,
    "err": theme.ERR,
    "info": theme.INFO,
}
NOTICE_MARKS = {"ok": "✓", "warn": "!", "err": "✗", "info": "i"}


@dataclass(frozen=True)
class Notice:
    kind: str  # "ok", "warn", "err" or "info"
    text: str


@dataclass(frozen=True)
class ViewState:
    paths: Paths
    status: BotStatus
    records: Sequence[LogRecord]
    selected: int
    now: datetime
    width: int
    height: int
    notice: Optional[Notice] = None
    busy: Optional[str] = None
    spinner: int = 0
    confirm: Optional[str] = None
    host: Optional[HostInfo] = None
    database: Optional[DbStatus] = None
    db_enabled: bool = False
    memory_percent: Optional[float] = None
    warnings: int = 0
    errors: int = 0
    ai: AiUsage = NO_USAGE


def _width(width: int) -> int:
    return max(min(width, MAX_WIDTH), 40)


# ── header ────────────────────────────────────────────────────────
LOGO_SIZE = 12  # columns; half as many rows
LOGO_MIN_WIDTH = 72
NOVA_TEXT_WIDTH = 10  # "無本地模型", the longest line
NOVA_SPRITE_MIN_WIDTH = 100  # narrower, Nova's column keeps only its text


def _title_line() -> Text:
    title = Text("✻  ", style=f"bold {theme.ACCENT}")
    title.append_text(theme.gradient("B O T ."))
    title.append("   機器人控制台", style=f"bold {theme.TEXT}")
    return title


def _fact(label: str, value: str, style: str = theme.MUTED) -> Text:
    line = Text(no_wrap=True, overflow="ellipsis")
    # Pad by display width so Chinese labels of different length line up.
    line.append(label + " " * (6 - cell_len(label)) + "  ", style=theme.DIM)
    line.append(value, style=style)
    return line


def host_lines(host: Optional[HostInfo]) -> list[Text]:
    """Three lines: machine, system and memory; processor; graphics."""
    if host is None:
        return [_fact("主機", "正在讀取硬體資訊…", theme.DIM), Text(""), Text("")]
    shape = f" · {host.cores} 核心 {host.threads} 執行緒" if host.cores else ""
    graphics = " ／ ".join(host.gpus) if host.gpus else "未偵測到顯示卡"
    # Memory sits on the short first line: a second graphics card's long name
    # is what gets cut when Nova takes the right of the header, not the memory.
    memory = f" · {host.memory_gb:.0f} GB 記憶體" if host.memory_gb else ""
    return [
        _fact("主機", f"{host.model_line} · {host.os_name}{memory}"),
        _fact("處理器", f"{host.cpu or '—'}{shape}"),
        _fact("顯示卡", graphics),
    ]


def usage_bar(usage: AiUsage, width: int = NOVA_TEXT_WIDTH) -> Text:
    """The AI allowance; grey from end to end while nothing can be measured."""
    bar = Text(no_wrap=True)
    fraction = usage.fraction if usage.connected else None
    filled = 0 if fraction is None else round(fraction * width)
    for index in range(width):
        if index < filled:
            bar.append("━", style=theme.gradient_colour(index / max(width - 1, 1)))
        else:
            bar.append("━", style=theme.BORDER)
    return bar


def nova_lines(usage: AiUsage) -> list[Text]:
    """Six lines beside Nova: its name, then what AI is in use and how much."""

    def line(value: str, style: str) -> Text:
        return Text(value, style=style, no_wrap=True, overflow="ellipsis")

    name = Text(no_wrap=True)
    name.append("諾瓦", style=f"bold {theme.TEXT}")
    name.append(" Nova", style=theme.DIM)
    if not usage.connected:
        state = line("休息中", theme.DIM)
    elif usage.fraction is not None:
        state = line(f"已用 {usage.fraction:.0%}", theme.MUTED)
    else:
        state = line("未計量", theme.DIM)
    return [
        name,
        line("AI 用量", theme.DIM),
        line(usage.model or "無模型", theme.TEXT if usage.model else theme.MUTED),
        line(
            usage.local_model or "無本地模型",
            theme.TEXT if usage.local_model else theme.MUTED,
        ),
        usage_bar(usage),
        state,
    ]


def nova_block(usage: AiUsage, *, with_sprite: bool) -> RenderableType:
    """Nova and the AI usage; the sprite rests until a model is connected."""
    text = Group(*nova_lines(usage))
    if not with_sprite:
        return text
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=nova.WIDTH, no_wrap=True)
    grid.add_column(width=NOVA_TEXT_WIDTH, no_wrap=True)
    grid.add_row(nova.sprite("awake" if usage.connected else "resting"), text)
    return grid


def header(
    paths: Paths,
    width: int,
    host: Optional[HostInfo] = None,
    *,
    detailed: bool = False,
    ai: AiUsage = NO_USAGE,
) -> Panel:
    """The top box. ``detailed`` adds the logo, the hardware and Nova."""
    width = _width(width)
    if not detailed:
        body: RenderableType = Group(
            _title_line(),
            theme.brand_bar(min(width - 8, 44)),
            Text(str(paths.root), style=theme.MUTED, no_wrap=True, overflow="ellipsis"),
            Text(
                f"Python {platform.python_version()} · {platform.system()} "
                f"{platform.release()}",
                style=theme.DIM,
            ),
        )
    else:
        lines = Group(
            _title_line(),
            theme.brand_bar(min(width - LOGO_SIZE - 12, 44)),
            Text(str(paths.root), style=theme.DIM, no_wrap=True, overflow="ellipsis"),
            *host_lines(host),
        )
        if width >= LOGO_MIN_WIDTH:
            sprite = width >= NOVA_SPRITE_MIN_WIDTH
            nova_width = NOVA_TEXT_WIDTH + (nova.WIDTH + 1 if sprite else 0)
            grid = Table.grid(padding=(0, 2), expand=True)
            grid.add_column(width=LOGO_SIZE, no_wrap=True)
            grid.add_column(no_wrap=True, overflow="ellipsis", ratio=1)
            grid.add_column(width=nova_width, no_wrap=True)
            grid.add_row(
                logo.logo_text(LOGO_SIZE), lines, nova_block(ai, with_sprite=sprite)
            )
            body = grid
        else:
            body = lines
    return Panel(
        body,
        box=box.ROUNDED,
        border_style=theme.ACCENT,
        padding=(0, 2),
        width=width,
    )


# ── status card ───────────────────────────────────────────────────
def _status_line(status: BotStatus, now: datetime) -> Text:
    line = Text()
    if status.state == "running":
        line.append("● 運行中", style=f"bold {theme.OK}")
        parts = [("PID", str(status.pid))]
        if status.started_at:
            seconds = (now - status.started_at).total_seconds()
            parts.append(("已運行", format_duration(seconds)))
        if status.cpu_percent is not None:
            parts.append(("CPU", f"{status.cpu_percent:.0f}%"))
        if status.rss_mb is not None:
            parts.append(("記憶體", f"{status.rss_mb:.0f} MB"))
        if status.threads is not None:
            parts.append(("執行緒", str(status.threads)))
        for label, value in parts:
            line.append(f"   {label} ", style=theme.DIM)
            line.append(value, style=theme.TEXT)
        if not status.verified:
            line.append("   無法確認（權限不足）", style=theme.WARN)
    elif status.state == "stale":
        line.append("◌ 狀態不明", style=f"bold {theme.WARN}")
        line.append(
            f"   鎖定檔指向的 PID {status.pid} 已不是機器人（可直接啟動，會自動清除）",
            style=theme.MUTED,
        )
    else:
        line.append("○ 已停止", style=f"bold {theme.MUTED}")
        line.append("   機器人目前沒有在執行", style=theme.DIM)
    return line


def _message_line(state: ViewState) -> Text:
    line = Text(no_wrap=True, overflow="ellipsis")
    if state.confirm:
        line.append("? ", style=f"bold {theme.WARN}")
        line.append(state.confirm, style=f"bold {theme.TEXT}")
        line.append("   Y 確定 · 其他鍵取消", style=theme.MUTED)
    elif state.busy:
        frame = SPINNER[state.spinner % len(SPINNER)]
        line.append(f"{frame} ", style=f"bold {theme.ACCENT}")
        line.append(state.busy, style=theme.TEXT)
    elif state.notice:
        colour = NOTICE_STYLES[state.notice.kind]
        line.append(f"{NOTICE_MARKS[state.notice.kind]} ", style=f"bold {colour}")
        line.append(state.notice.text, style=colour)
    else:
        line.append(TIP, style=theme.DIM)
    return line


def _health_line(state: ViewState) -> Text:
    """Database, memory and recent trouble: what the process line cannot tell."""
    line = Text(no_wrap=True, overflow="ellipsis")
    status = state.database
    if not state.db_enabled:
        line.append("○ 資料庫 JSON 模式", style=theme.DIM)
    elif status is None:
        line.append("◌ 資料庫 檢查中…", style=theme.DIM)
    elif status.state == "ready":
        line.append("● 資料庫 連線正常", style=f"bold {theme.OK}")
    elif status.state == "down":
        line.append("✗ 資料庫 沒有執行", style=f"bold {theme.ERR}")
        line.append("  按 M 啟動", style=theme.MUTED)
    else:
        line.append("! 資料庫 無法登入", style=f"bold {theme.WARN}")
        line.append(f"  {status.detail}", style=theme.MUTED)
    if state.memory_percent is not None:
        high = state.memory_percent >= launch.MEMORY_WARN_PERCENT
        line.append("   記憶體 ", style=theme.DIM)
        line.append(
            f"{state.memory_percent:.0f}%",
            style=f"bold {theme.ERR}" if high else theme.TEXT,
        )
    line.append("   近 5 分鐘 ", style=theme.DIM)
    if state.errors:
        line.append(f"{state.errors} 個錯誤", style=f"bold {theme.ERR}")
        line.append(" · ", style=theme.DIM)
    if state.warnings:
        line.append(f"{state.warnings} 個警告", style=f"bold {theme.WARN}")
    elif not state.errors:
        line.append("沒有警告", style=theme.DIM)
    return line


def status_card(state: ViewState) -> Panel:
    colour = {"running": theme.OK, "stale": theme.WARN}.get(
        state.status.state, theme.BORDER
    )
    return Panel(
        Group(
            _status_line(state.status, state.now),
            _health_line(state),
            _message_line(state),
        ),
        box=box.ROUNDED,
        border_style=colour,
        padding=(0, 2),
        width=_width(state.width),
    )


# ── menu ──────────────────────────────────────────────────────────
def _menu_cell(
    column: menu.MenuColumn, selected: menu.MenuItem, cell_width: int, height: int
) -> Text:
    cell = Text(no_wrap=True, overflow="crop")
    cell.append(f"  {column.title}\n", style=f"bold {column.colour}")
    for item in column.items:
        chosen = item is selected
        pointer = "❯ " if chosen else "  "
        row = Text(no_wrap=True)
        row.append(pointer, style=f"bold {column.colour}")
        row.append(f"{item.key.upper()}", style=f"bold {column.colour}")
        row.append("  ")
        row.append(
            item.label,
            style=f"bold {theme.TEXT}" if chosen else theme.MUTED,
        )
        padding = max(cell_width - cell_len(row.plain), 0)
        row.append(" " * padding)
        if chosen:
            row.stylize(f"on {SELECTED_BG}")
        cell.append_text(row)
        cell.append("\n")
    for _ in range(height - len(column.items)):
        cell.append("\n")
    return cell


def menu_block(selected: menu.MenuItem, width: int) -> Group:
    width = _width(width)
    height = max(len(column.items) for column in menu.COLUMNS)
    if width >= 96:
        gap = 3
        cell_width = (width - gap * (len(menu.COLUMNS) - 1) - 2) // len(menu.COLUMNS)
        grid = Table.grid(padding=(0, gap), expand=False)
        for _ in menu.COLUMNS:
            grid.add_column(width=cell_width, no_wrap=True)
        grid.add_row(
            *(
                _menu_cell(column, selected, cell_width, height)
                for column in menu.COLUMNS
            )
        )
        body: RenderableType = grid
    else:
        body = Group(
            *(_menu_cell(column, selected, width - 2, 0) for column in menu.COLUMNS)
        )
    hint = Text(no_wrap=True, overflow="ellipsis")
    hint.append("  ❯ ", style=f"bold {menu.column_of(selected).colour}")
    hint.append(selected.hint, style=theme.MUTED)
    return Group(body, hint)


# ── logs ──────────────────────────────────────────────────────────
def log_line(record: LogRecord) -> Text:
    line = Text(no_wrap=True, overflow="ellipsis")
    line.append(f"{record.time}  ", style=theme.DIM)
    line.append(
        f"{theme.LEVEL_TAGS.get(record.level, record.level):<5}  ",
        style=theme.LEVEL_STYLES.get(record.level, theme.MUTED),
    )
    line.append(f"{short_logger(record.logger)}  ", style=theme.ROSE)
    if record.count > 1:
        line.append(f"×{record.count}  ", style=f"bold {theme.ACCENT}")
    line.append(
        record.message,
        style=theme.TEXT if record.level in ("ERROR", "CRITICAL") else theme.MUTED,
    )
    if record.extra_lines:
        line.append(f"  (+{record.extra_lines} 行)", style=theme.DIM)
    return line


def logs_panel(
    records: Sequence[LogRecord], rows: int, width: int, title: str = "日誌"
) -> Panel:
    rows = max(rows, 1)
    lines = [log_line(record) for record in records[-rows:]]
    if not lines:
        lines = [Text("還沒有日誌", style=theme.DIM)]
    lines += [Text("")] * (rows - len(lines))
    return Panel(
        Group(*lines),
        title=Text(f" {title} ", style=f"bold {theme.TEXT}"),
        title_align="left",
        box=box.ROUNDED,
        border_style=theme.BORDER,
        padding=(0, 1),
        width=_width(width),
    )


# ── footer ────────────────────────────────────────────────────────
def footer(now: datetime, hint: str, width: int) -> Table:
    grid = Table.grid(expand=False)
    width = _width(width)
    clock = now.strftime("%H:%M:%S")
    grid.add_column(width=width - len(clock) - 2, no_wrap=True, overflow="ellipsis")
    grid.add_column(justify="right", width=len(clock) + 2)
    grid.add_row(
        Text(f" {hint}", style=theme.DIM),
        Text(clock, style=theme.DIM),
    )
    return grid


DASHBOARD_HINT = "↑↓ 選擇   Enter 執行   或直接按選項前的字母／數字   Q 離開"


def dashboard(state: ViewState) -> Group:
    selected = menu.ITEMS[state.selected]
    wide = _width(state.width) >= 96
    tallest = max(len(c.items) for c in menu.COLUMNS)
    menu_rows = tallest + 2 if wide else sum(len(c.items) + 1 for c in menu.COLUMNS) + 1
    # header (6 + 2), status card (3 + 2), menu, blank line, footer, log border
    fixed = 8 + 5 + menu_rows + 1 + 1 + 2
    log_rows = state.height - fixed - 1
    parts: list[RenderableType] = [
        header(state.paths, state.width, state.host, detailed=True, ai=state.ai),
        status_card(state),
        menu_block(selected, state.width),
    ]
    # On a short terminal the log goes first; the footer's key hints stay.
    if log_rows >= 3:
        parts += [
            Text(""),
            logs_panel(state.records, log_rows, state.width, "日誌 · runtime.log"),
        ]
    parts.append(footer(state.now, DASHBOARD_HINT, state.width))
    return Group(*parts)


# ── other pages ───────────────────────────────────────────────────
def page_title(title: str, width: int) -> Text:
    line = Text()
    line.append("✻  ", style=f"bold {theme.ACCENT}")
    line.append(title, style=f"bold {theme.TEXT}")
    return line


def status_detail(status: BotStatus, paths: Paths, now: datetime, width: int) -> Group:
    table = Table.grid(padding=(0, 3))
    table.add_column(style=theme.DIM, no_wrap=True)
    table.add_column(style=theme.TEXT, overflow="fold")
    names = {
        "running": ("運行中", theme.OK),
        "stale": ("狀態不明（鎖定檔過期）", theme.WARN),
        "stopped": ("已停止", theme.MUTED),
    }
    label, colour = names[status.state]
    table.add_row("狀態", Text(label, style=f"bold {colour}"))
    table.add_row("PID", str(status.pid) if status.pid else "—")
    if status.started_at:
        table.add_row("啟動時間", status.started_at.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row(
            "已運行", format_duration((now - status.started_at).total_seconds())
        )
    if status.cpu_percent is not None:
        table.add_row("CPU", f"{status.cpu_percent:.1f}%")
    if status.rss_mb is not None:
        table.add_row("記憶體", f"{status.rss_mb:.0f} MB")
    if status.threads is not None:
        table.add_row("執行緒", str(status.threads))
    if status.cmdline:
        table.add_row("指令列", status.cmdline)
    table.add_row("Python", paths.python)
    table.add_row("鎖定檔", str(paths.lock))
    table.add_row("日誌", str(paths.runtime_log))
    return Group(
        header(paths, width),
        Panel(
            table,
            title=Text(" 詳細狀態 ", style=f"bold {theme.TEXT}"),
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.OK if status.state == "running" else theme.BORDER,
            padding=(1, 2),
            width=_width(width),
        ),
        footer(now, "任意鍵返回", width),
    )


def guide_page(paths: Paths, now: datetime, width: int) -> Group:
    table = Table.grid(padding=(0, 3))
    table.add_column(style=f"bold {theme.ACCENT}", no_wrap=True)
    table.add_column(style=theme.TEXT)
    for command, text in menu.GUIDE_LINES:
        table.add_row(command, text)
    note = Text(
        "開發者指令在 Discord 裡執行，只有列在 src/config/constants.py 的 "
        "DEVELOPER_IDS 的帳號能使用。\n想在本機檢查 Cog，可用選單的 9。",
        style=theme.MUTED,
    )
    return Group(
        header(paths, width),
        Panel(
            Group(table, Text(""), note),
            title=Text(" 開發者指令 ", style=f"bold {theme.TEXT}"),
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(1, 2),
            width=_width(width),
        ),
        footer(now, "任意鍵返回", width),
    )


def log_page(
    records: Sequence[LogRecord],
    only_warnings: bool,
    paths: Paths,
    now: datetime,
    width: int,
    height: int,
) -> Group:
    rows = max(height - 5, 3)
    mode = "警告以上" if only_warnings else "全部"
    return Group(
        page_title(f"即時日誌 · {mode}", width),
        logs_panel(records, rows, width, str(paths.runtime_log)),
        footer(now, "W 切換只看警告以上   O 開啟日誌資料夾   Q 返回", width),
    )


def choice_page(
    title: str,
    choices: Sequence[menu.Choice],
    selected: int,
    paths: Paths,
    now: datetime,
    width: int,
) -> Group:
    body = Text()
    for index, choice in enumerate(choices):
        chosen = index == selected
        body.append("❯ " if chosen else "  ", style=f"bold {theme.ACCENT}")
        body.append(choice.key.upper(), style=f"bold {theme.ACCENT}")
        body.append("  ")
        body.append(choice.label, style=f"bold {theme.TEXT}" if chosen else theme.MUTED)
        body.append("\n")
    return Group(
        header(paths, width),
        Panel(
            body,
            title=Text(f" {title} ", style=f"bold {theme.TEXT}"),
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(1, 2),
            width=_width(width),
        ),
        footer(now, "↑↓ 選擇   Enter 執行   Q 返回", width),
    )


def command_banner(title: str, argv: Sequence[str], width: int) -> Group:
    shown = " ".join(argv)
    return Group(
        Text(""),
        Text.assemble(("✻  ", f"bold {theme.ACCENT}"), (title, f"bold {theme.TEXT}")),
        Text(f"   $ {shown}", style=theme.DIM, no_wrap=True, overflow="ellipsis"),
        theme.brand_bar(_width(width) - 2),
        Text(""),
    )


def command_result(code: int, seconds: float) -> Text:
    line = Text()
    if code == 0:
        line.append("\n✓ 完成", style=f"bold {theme.OK}")
    else:
        line.append(f"\n✗ 失敗（結束碼 {code}）", style=f"bold {theme.ERR}")
    line.append(f"   用時 {format_duration(seconds)}", style=theme.DIM)
    return line


# ── launch screen ─────────────────────────────────────────────────
STEP_MARKS = {
    launch.PENDING: ("○", theme.DIM),
    launch.OK: ("✓", theme.OK),
    launch.WARN: ("!", theme.WARN),
    launch.FAIL: ("✗", theme.ERR),
    launch.SKIP: ("–", theme.DIM),
}
LOGO_ROW_SECONDS = 0.07  # the logo is drawn in from the top, one row at a time


def _progress_bar(fraction: float, width: int = 40) -> Text:
    bar = Text(no_wrap=True)
    filled = round(min(max(fraction, 0.0), 1.0) * width)
    for index in range(width):
        if index < filled:
            bar.append("━", style=theme.gradient_colour(index / max(width - 1, 1)))
        else:
            bar.append("─", style=theme.BORDER)
    return bar


def _step_table(steps: Sequence[launch.Step], spinner: int) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(width=1)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True, overflow="ellipsis")
    for step in steps:
        if step.state == launch.RUNNING:
            mark = Text(SPINNER[spinner % len(SPINNER)], style=f"bold {theme.ACCENT}")
            label_style = f"bold {theme.TEXT}"
            detail_style = theme.MUTED
        else:
            symbol, colour = STEP_MARKS[step.state]
            mark = Text(symbol, style=f"bold {colour}")
            label_style = theme.TEXT if step.state != launch.PENDING else theme.DIM
            detail_style = {
                launch.WARN: theme.WARN,
                launch.FAIL: theme.ERR,
            }.get(step.state, theme.DIM)
        table.add_row(
            mark,
            Text(f"{step.label:<6}", style=label_style),
            Text(step.detail, style=detail_style),
        )
    return table


def launch_screen(
    title: str,
    steps: Sequence[launch.Step],
    outcome: Optional[tuple[bool, str]],
    *,
    progress: float,
    elapsed: float,
    spinner: int,
    width: int,
    height: int,
) -> RenderableType:
    """The animated start-up screen: logo, a progress sweep, and the checklist."""
    width = min(_width(width), 96)
    # What is left for the logo once the text and the frame have their rows.
    spare = height - (len(steps) + 9)
    logo_rows = max(min(spare, 12), 0)
    parts: list[RenderableType] = []
    if logo_rows >= 4:
        shown = int(elapsed / LOGO_ROW_SECONDS) + 1
        parts += [
            Align.center(logo.logo_text(logo_rows * 2, visible_rows=shown)),
            Text(""),
        ]
    heading = Text(justify="center")
    heading.append_text(theme.gradient("B O T ."))
    heading.append(f"   {title}", style=f"bold {theme.TEXT}")
    parts += [
        Align.center(heading),
        Align.center(_progress_bar(progress)),
        Text(""),
        Align.center(_step_table(steps, spinner)),
        Text(""),
    ]
    border = theme.ACCENT
    if outcome is not None:
        ok, message = outcome
        states = {step.state for step in steps}
        border = theme.OK if ok and launch.WARN not in states else theme.WARN
        if not ok:
            border = theme.ERR
        closing = Text(justify="center")
        closing.append(
            "✓ " if ok else "✗ ", style=f"bold {theme.OK if ok else theme.ERR}"
        )
        closing.append(message, style=theme.OK if ok else theme.ERR)
        closing.append("   按任意鍵繼續", style=theme.DIM)
        parts.append(Align.center(closing))
    else:
        parts.append(Text(""))
    return Align.center(
        Panel(
            Group(*parts),
            box=box.ROUNDED,
            border_style=border,
            padding=(0, 3),
            width=width,
        ),
        vertical="middle",
        height=max(height - 1, 10),
    )


def host_page(
    host: Optional[HostInfo],
    paths: Paths,
    now: datetime,
    width: int,
    *,
    memory_percent: Optional[float] = None,
) -> Group:
    table = Table.grid(padding=(0, 3))
    table.add_column(style=theme.DIM, no_wrap=True)
    table.add_column(style=theme.TEXT, overflow="fold")
    if host is None:
        table.add_row("狀態", "正在讀取硬體資訊…")
    else:
        table.add_row("主機型號", host.model_line)
        if host.board and host.board != host.machine:
            table.add_row("主機板", host.board)
        table.add_row("處理器", host.cpu or "—")
        if host.cores:
            table.add_row("核心／執行緒", f"{host.cores} 核心 · {host.threads} 執行緒")
        table.add_row("顯示卡", "\n".join(host.gpus) if host.gpus else "未偵測到")
        memory = f"{host.memory_gb:.1f} GB"
        if memory_percent is not None:
            memory += f"（已使用 {memory_percent:.0f}%）"
        table.add_row("記憶體", memory)
        table.add_row("作業系統", host.os_name)
    table.add_row("Python", f"{platform.python_version()} · {paths.python}")
    return Group(
        header(paths, width),
        Panel(
            table,
            title=Text(" 主機資訊 ", style=f"bold {theme.TEXT}"),
            title_align="left",
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(1, 2),
            width=_width(width),
        ),
        footer(now, "任意鍵返回", width),
    )
