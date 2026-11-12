"""Browse and edit the bot's stored documents, with Chinese names for every field.

The browser reads documents the way the bot does (``read_document``), so it
sees MySQL in MySQL mode and the JSON files in JSON mode. Writing is careful:

* only while the bot is stopped, because its services cache documents and
  would overwrite an edit made underneath them;
* only if the document has not changed since it was opened;
* only after a copy of the current version is saved under
  ``data/backups/data-browser``;
* never for fields that hold credentials, which are shown masked.
"""

import copy
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from rich import box
from rich.console import Group
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.control_panel import labels
from src.control_panel import render
from src.control_panel import theme
from src.control_panel.state import BotStatus
from src.utils.document_store import canonical
from src.utils.document_store import connect_mysql
from src.utils.document_store import read_document
from src.utils.document_store import using_mysql
from src.utils.document_store import write_document

BACKUP_FOLDER = "data/backups/data-browser"
# Under data/: tool caches, generated art and backups, not the bot's records.
SKIPPED_FOLDERS = frozenset({"ai", "art", "cache", "worker-packages", "backups"})
SKIPPED_PREFIXES = (".", "models_cache", "auth", "policy")
MAX_TEXT = 80
TIME_KEY = re.compile(r"(_at|_time|time|until|born|start)$")


class Conflict(Exception):
    """The document changed after it was opened; nothing was written."""


class ReadOnly(Exception):
    """Writing is not allowed right now; the message says why."""


@dataclass(frozen=True)
class DocInfo:
    path: str  # relative to the project, as the bot names it
    label: str
    size: int
    folder: bool = False  # the companion files, gathered into one entry


@dataclass(frozen=True)
class Row:
    key: Any  # the dict key, the list index or the document path
    label: str
    english: str
    kind: str  # "doc", "folder", "dict", "list", "value" or "secret"
    text: str
    editable: bool


def read_only_reason(status: BotStatus) -> Optional[str]:
    """Why edits are refused for this bot status, or None when they are allowed."""
    if status.state == "running":
        return "機器人執行中，只能瀏覽。要修改請先停止機器人，否則會被它的快取蓋回去。"
    if status.state != "stopped":
        return "機器人狀態不明，先只能瀏覽。確認機器人已停止後再修改。"
    return None


# ── values ────────────────────────────────────────────────────────


def _clock(value: float) -> str:
    seconds = value / 1000 if value > 1e12 else value
    try:
        return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def _size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def describe(key: Any, value: Any) -> str:
    """How a stored value reads on screen."""
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "（空）"
    if isinstance(value, (int, float)):
        text = f"{value}"
        if isinstance(key, str) and TIME_KEY.search(key) and value > 1e9:
            when = _clock(float(value))
            if when:
                text += f"（{when}）"
        return text
    if isinstance(value, dict):
        return f"{len(value)} 個欄位"
    if isinstance(value, list):
        return f"{len(value)} 項"
    text = str(value).replace("\r", "").replace("\n", " ⏎ ")
    if text == "":
        return "（空字串）"
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "是／否"
    if isinstance(value, int):
        return "整數"
    if isinstance(value, float):
        return "數字"
    if value is None:
        return "空值"
    return "文字"


_TRUE = {"是", "true", "yes", "y", "1", "on", "開", "啟用"}
_FALSE = {"否", "false", "no", "n", "0", "off", "關", "停用"}


def parse_value(text: str, original: Any) -> Any:
    """Read what was typed as the same kind of value the field already holds."""
    raw = text.strip()
    if isinstance(original, bool):
        if raw.lower() in _TRUE:
            return True
        if raw.lower() in _FALSE:
            return False
        raise ValueError("請輸入「是」或「否」")
    if isinstance(original, int):
        try:
            return int(raw.replace(",", ""))
        except ValueError:
            raise ValueError("請輸入整數") from None
    if isinstance(original, float):
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            raise ValueError("請輸入數字") from None
    if original is None:
        if raw in ("空", "null", "None"):
            return None
        if raw in ("是", "否"):
            return raw == "是"
        try:
            value = json.loads(raw)
        except ValueError:
            return text
        return value if isinstance(value, (bool, int, float, str)) else text
    if raw == '""':
        return ""
    return text


def set_at(data: Any, trail: list[Any], value: Any) -> Any:
    """A copy of ``data`` with the value at ``trail`` replaced."""
    result = copy.deepcopy(data)
    node = result
    for key in trail[:-1]:
        node = node[key]
    node[trail[-1]] = value
    return result


# ── storage ───────────────────────────────────────────────────────


def _write_pretty(target: Path, data: Any) -> None:
    """Keep a hand-readable JSON file hand-readable; replaced in one step."""
    fd, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=target.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(data, ensure_ascii=False, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    """The bot's documents, read and written through the bot's own storage code."""

    def __init__(self, root: Path) -> None:
        self.root = root
        # The panel runs as its own process: give it the settings the bot uses.
        load_dotenv(root / ".env", override=False)
        os.environ.setdefault("STORAGE_ROOT", str(root))

    @property
    def mysql(self) -> bool:
        return using_mysql()

    def _sizes(self, prefix: str = "") -> list[tuple[str, int]]:
        if self.mysql:
            with connect_mysql() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT path, CHAR_LENGTH(payload) FROM documents "
                        "WHERE path LIKE %s ORDER BY path",
                        (prefix + "%",),
                    )
                    return [(str(path), int(size)) for path, size in cursor.fetchall()]
        rows = []
        for file in sorted((self.root / "data").rglob("*.json")):
            parts = file.relative_to(self.root).parts
            if SKIPPED_FOLDERS & set(parts) or file.name.startswith(SKIPPED_PREFIXES):
                continue
            path = "/".join(parts)
            if path.startswith(prefix):
                rows.append((path, file.stat().st_size))
        return rows

    def documents(self) -> list[DocInfo]:
        """Every document; the companions' files gathered into one entry at the end."""
        rows = self._sizes()
        pets = [row for row in rows if row[0].startswith(labels.PET_FOLDER)]
        docs = [
            DocInfo(path, labels.document_label(path), size)
            for path, size in rows
            if not path.startswith(labels.PET_FOLDER)
        ]
        # The bot's own documents first, then unknown ones, then leftovers.
        docs.sort(
            key=lambda doc: (
                labels.is_unused(doc.path),
                not labels.is_named_document(doc.path),
                doc.label,
            )
        )
        if pets:
            docs.append(
                DocInfo(
                    labels.PET_FOLDER,
                    f"夥伴（{len(pets)} 份）",
                    sum(size for _, size in pets),
                    folder=True,
                )
            )
        return docs

    def pets(self) -> list[DocInfo]:
        return [
            DocInfo(path, labels.document_label(path), size)
            for path, size in self._sizes(labels.PET_FOLDER)
        ]

    def read(self, path: str) -> Any:
        return read_document(self.root / path)

    def write(self, path: str, data: Any, expected: Any) -> Path:
        """Write ``data`` if the stored document still equals ``expected``.

        Returns where the previous version was saved.
        """
        current = self.read(path)
        if canonical(current) != canonical(expected):
            raise Conflict(path)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.root / BACKUP_FOLDER / stamp / path
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        target = self.root / path
        if not self.mysql and "\n" in target.read_text(encoding="utf-8-sig"):
            _write_pretty(target, data)
        else:
            write_document(target, data)
        return backup


# ── browsing ──────────────────────────────────────────────────────


class Browser:
    """Where the user is: the document list, the companions' folder, or inside one."""

    def __init__(self, store: Store, read_only: Callable[[], Optional[str]]) -> None:
        self.store = store
        self.read_only = read_only
        self.docs: list[DocInfo] = []
        self.folder: Optional[DocInfo] = None
        self.folder_docs: list[DocInfo] = []
        self.doc: Optional[DocInfo] = None
        self.data: Any = None
        self.trail: list[Any] = []
        self.selected = 0
        self.offset = 0
        self.notice: Optional[tuple[str, str]] = None
        self._positions: list[int] = []

    def load(self) -> None:
        self.docs = self.store.documents()

    @property
    def in_document(self) -> bool:
        return self.doc is not None

    def node(self) -> Any:
        node = self.data
        for key in self.trail:
            node = node[key]
        return node

    def _secret_here(self) -> bool:
        return any(
            isinstance(key, str) and labels.is_sensitive(key) for key in self.trail
        )

    def _parent_name(self) -> Optional[str]:
        return next((k for k in reversed(self.trail) if isinstance(k, str)), None)

    def breadcrumb(self) -> list[str]:
        crumbs = ["資料庫"]
        if self.folder is not None:
            crumbs.append(self.folder.label)
        if self.doc is not None:
            crumbs.append(self.doc.label)
            parent: Optional[str] = None
            for key in self.trail:
                if isinstance(key, int):
                    crumbs.append(f"第 {key + 1} 項")
                else:
                    crumbs.append(labels.field_label(key, parent, self.doc.path))
                    parent = key
        return crumbs

    def rows(self) -> list[Row]:
        if self.doc is None:
            docs = self.folder_docs if self.folder is not None else self.docs
            return [
                Row(
                    doc.path,
                    doc.label,
                    _size(doc.size),  # the right-hand column
                    "folder" if doc.folder else "doc",
                    doc.path,
                    False,
                )
                for doc in docs
            ]
        node = self.node()
        hidden = self._secret_here()
        parent = self._parent_name()
        if isinstance(node, dict):
            items = list(node.items())
        elif isinstance(node, list):
            items = list(enumerate(node))
        else:
            items = []
        rows = []
        for key, value in items:
            if isinstance(key, int):
                label, english = f"第 {key + 1} 項", ""
            else:
                label = labels.field_label(key, parent, self.doc.path)
                english = key
            if isinstance(value, dict):
                kind = "dict"
            elif isinstance(value, list):
                kind = "list"
            elif hidden or (isinstance(key, str) and labels.is_sensitive(key)):
                kind = "secret"
            else:
                kind = "value"
            text = "•••（已隱藏）" if kind == "secret" else describe(key, value)
            rows.append(Row(key, label, english, kind, text, kind == "value"))
        return rows

    def move(self, step: int) -> None:
        count = len(self.rows())
        if count:
            self.selected = (self.selected + step) % count

    def enter(self) -> None:
        rows = self.rows()
        if not rows:
            return
        row = rows[self.selected]
        if row.kind == "folder":
            folder = next(doc for doc in self.docs if doc.path == row.key)
            self.folder_docs = self.store.pets()
            self.folder = folder
            self._descend()
        elif row.kind == "doc":
            listed = self.folder_docs if self.folder is not None else self.docs
            doc = next(doc for doc in listed if doc.path == row.key)
            self.data = self.store.read(doc.path)
            self.doc = doc
            self.trail = []
            self._descend()
        elif row.kind in ("dict", "list"):
            self.trail.append(row.key)
            self._descend()
        elif row.kind == "secret":
            self.notice = ("info", "這個欄位存放憑證，不顯示也不能在這裡修改")
        else:
            self.notice = ("info", "這是單一的值，按 E 修改")

    def back(self) -> bool:
        """Go up one level; False when already at the top."""
        if self.doc is not None and self.trail:
            self.trail.pop()
        elif self.doc is not None:
            self.doc = None
            self.data = None
        elif self.folder is not None:
            self.folder = None
            self.folder_docs = []
        else:
            return False
        self.selected = self._positions.pop() if self._positions else 0
        self.offset = 0
        return True

    def _descend(self) -> None:
        self._positions.append(self.selected)
        self.selected = 0
        self.offset = 0

    def reload(self) -> None:
        if self.doc is not None:
            self.data = self.store.read(self.doc.path)
            # The shape may have changed: keep only the part of the trail that exists.
            node, kept = self.data, []
            for key in self.trail:
                try:
                    node = node[key]
                except (KeyError, IndexError, TypeError):
                    break
                kept.append(key)
            dropped = len(self.trail) - len(kept)
            if dropped:
                del self._positions[-dropped:]
            self.trail = kept
        elif self.folder is not None:
            self.folder_docs = self.store.pets()
        else:
            self.load()
        self.selected = min(self.selected, max(len(self.rows()) - 1, 0))

    def edit_target(self) -> Optional[Row]:
        rows = self.rows()
        if not self.in_document or not rows:
            return None
        row = rows[self.selected]
        return row if row.editable else None

    def apply(self, row: Row, value: Any) -> str:
        """Write one changed value; returns where the old version was saved."""
        if self.doc is None:
            raise ReadOnly("沒有開啟中的文件")
        reason = self.read_only()
        if reason:
            raise ReadOnly(reason)
        updated = set_at(self.data, [*self.trail, row.key], value)
        backup = self.store.write(self.doc.path, updated, self.data)
        self.data = updated
        return backup.relative_to(self.store.root).as_posix()

    def on_key(self, key: str) -> bool:
        """Handle a browsing key; False means leave the browser."""
        self.notice = None
        if key in ("up", "down"):
            self.move(-1 if key == "up" else 1)
        elif key in ("enter", "right"):
            self.enter()
        elif key in ("esc", "left", "\x08"):
            return self.back()
        elif key == "r":
            self.reload()
            self.notice = ("ok", "已重新讀取")
        return True


# ── screen ────────────────────────────────────────────────────────

_NOTICE_STYLES = {
    "ok": theme.OK,
    "err": theme.ERR,
    "warn": theme.WARN,
    "info": theme.INFO,
}
_NUMBER = re.compile(r"-?\d[\d.]*(（.*）)?")


def _value_text(row: Row) -> Text:
    if row.kind == "doc" and labels.is_unused(row.key):
        return Text.assemble(("未使用  ", theme.WARN), (row.text, theme.DIM))
    if row.kind in ("doc", "folder", "secret"):
        return Text(row.text, style=theme.DIM)
    if row.kind in ("dict", "list"):
        return Text(f"▸ {row.text}", style=theme.ACCENT)
    if row.text in ("是", "否"):
        colour = theme.OK if row.text == "是" else theme.ERR
        return Text(row.text, style=f"bold {colour}")
    if row.text in ("（空）", "（空字串）"):
        return Text(row.text, style=theme.DIM)
    if _NUMBER.fullmatch(row.text):
        return Text(row.text, style=theme.INFO)
    return Text(row.text, style=theme.TEXT)


def _status_line(browser: Browser) -> Text:
    line = Text()
    reason = browser.read_only()
    if reason:
        line.append("唯讀  ", style=f"bold {theme.WARN}")
        line.append(reason, style=theme.WARN)
    else:
        line.append("可修改  ", style=f"bold {theme.OK}")
        line.append(f"每次儲存前，舊版本會先備份到 {BACKUP_FOLDER}", style=theme.MUTED)
    if browser.notice:
        kind, message = browser.notice
        line.append("\n")
        line.append(message, style=_NOTICE_STYLES.get(kind, theme.TEXT))
    return line


def page(browser: Browser, now: datetime, width: int, height: int) -> Group:
    """The browser screen: where you are, the rows, and the keys."""
    width = render._width(width)
    rows = browser.rows()
    visible = max(height - 11, 3)
    if browser.selected < browser.offset:
        browser.offset = browser.selected
    elif browser.selected >= browser.offset + visible:
        browser.offset = browser.selected - visible + 1

    title = render.page_title("資料庫管理", width)
    title.append(
        "   MySQL" if browser.store.mysql else "   JSON 相容模式", style=theme.DIM
    )

    crumbs = Text(no_wrap=True, overflow="ellipsis")
    trail = browser.breadcrumb()
    for index, crumb in enumerate(trail):
        if index:
            crumbs.append("  ›  ", style=theme.DIM)
        last = index == len(trail) - 1
        crumbs.append(crumb, style=f"bold {theme.TEXT}" if last else theme.MUTED)

    table = Table.grid(padding=(0, 2), expand=True)
    table.add_column(width=1, no_wrap=True)
    table.add_column(ratio=3, no_wrap=True, overflow="ellipsis")
    table.add_column(ratio=5, no_wrap=True, overflow="ellipsis")
    table.add_column(ratio=2, no_wrap=True, overflow="ellipsis", justify="right")
    for index in range(browser.offset, min(len(rows), browser.offset + visible)):
        row = rows[index]
        chosen = index == browser.selected
        marker = Text("❯", style=f"bold {theme.ACCENT}") if chosen else Text(" ")
        if chosen:
            label_style = f"bold {theme.TEXT}"
        elif row.kind == "secret" or (row.kind == "doc" and labels.is_unused(row.key)):
            label_style = theme.DIM
        elif row.editable:
            label_style = theme.MUTED
        else:
            label_style = theme.ACCENT
        english = row.english if row.english != row.label else ""
        table.add_row(
            marker,
            Text(f"[{row.label}]", style=label_style),
            _value_text(row),
            Text(english, style=theme.DIM),
        )
    if not rows:
        table.add_row("", Text("（這裡是空的）", style=theme.DIM), "", "")

    body: list[RenderableType] = [table]
    if len(rows) > visible:
        end = min(len(rows), browser.offset + visible)
        body.append(
            Text(
                f"{browser.offset + 1}–{end} / {len(rows)}",
                style=theme.DIM,
                justify="right",
            )
        )

    if browser.in_document:
        hint = "↑↓ 選擇   Enter 展開   E 修改   ← / Esc 上一層   R 重新讀取   Q 離開"
    else:
        hint = "↑↓ 選擇   Enter 開啟   ← / Esc 上一層   R 重新整理   Q 離開"
    return Group(
        title,
        Text(""),
        crumbs,
        Panel(
            Group(*body),
            box=box.ROUNDED,
            border_style=theme.BORDER,
            padding=(0, 1),
            width=width,
        ),
        _status_line(browser),
        render.footer(now, hint, width),
    )


_INPUT_HINTS = {
    "是／否": "輸入「是」或「否」",
    "整數": "輸入整數，例如 30",
    "數字": "輸入數字，例如 1.5",
    "空值": "輸入數字、是／否或文字；輸入「空」保持空值",
    "文字": '直接輸入文字；輸入 "" 代表空字串',
}


def edit_card(browser: Browser, row: Row, current: Any, width: int) -> Panel:
    """What is about to change, shown above the input prompt."""
    facts = Table.grid(padding=(0, 3))
    facts.add_column(style=theme.DIM, no_wrap=True)
    facts.add_column(style=theme.TEXT, overflow="fold")
    facts.add_row("位置", "  ›  ".join(browser.breadcrumb()))
    facts.add_row(
        "欄位",
        Text.assemble(
            (f"[{row.label}]", f"bold {theme.ACCENT}"), "  ", (row.english, theme.DIM)
        ),
    )
    facts.add_row("目前的值", Text(describe(row.key, current), style=theme.INFO))
    facts.add_row("輸入方式", Text(_INPUT_HINTS[type_name(current)], style=theme.MUTED))
    facts.add_row("取消", Text("什麼都不輸入，直接按 Enter", style=theme.MUTED))
    return Panel(
        facts,
        title=Text(" 修改欄位 ", style=f"bold {theme.TEXT}"),
        title_align="left",
        box=box.ROUNDED,
        border_style=theme.ACCENT,
        padding=(1, 2),
        width=render._width(width),
    )


def change_line(row: Row, before: Any, after: Any) -> Text:
    """The old value and the new one, shown before the final yes or no."""
    line = Text()
    line.append(f"[{row.label}]  ", style=f"bold {theme.TEXT}")
    line.append(describe(row.key, before), style=theme.MUTED)
    line.append("  →  ", style=theme.DIM)
    line.append(describe(row.key, after), style=f"bold {theme.ACCENT}")
    return line
