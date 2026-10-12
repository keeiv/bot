"""The panel's menu: every action of the old ``run_bot.bat`` menu, same keys."""

from dataclasses import dataclass
from typing import Optional

from src.control_panel import theme


@dataclass(frozen=True)
class MenuItem:
    key: str  # lower-case hotkey
    label: str
    hint: str
    action: str
    kind: str  # "bg", "launch", "page", "cmd", "folder", "submenu" or "quit"
    confirm: Optional[str] = None


@dataclass(frozen=True)
class MenuColumn:
    title: str
    colour: str
    items: tuple[MenuItem, ...]


COLUMNS: tuple[MenuColumn, ...] = (
    MenuColumn(
        "機器人",
        theme.ACCENT,
        (
            MenuItem(
                "1",
                "啟動機器人",
                "檢查主機、環境與資料庫，再在新視窗啟動 BOT.",
                "start",
                "launch",
            ),
            MenuItem(
                "2",
                "停止機器人",
                "結束機器人與它的子程序",
                "stop",
                "bg",
                "確定要停止機器人嗎？",
            ),
            MenuItem(
                "3",
                "重新啟動",
                "先停止，再走一次完整的啟動檢查",
                "restart",
                "launch",
                "確定要重新啟動機器人嗎？",
            ),
            MenuItem(
                "4",
                "詳細狀態",
                "PID、運行時間、CPU、記憶體與指令列",
                "status",
                "page",
            ),
            MenuItem(
                "5",
                "即時日誌",
                "在這裡查看 runtime.log，可只看警告以上",
                "logs",
                "page",
            ),
            MenuItem(
                "m",
                "啟動資料庫",
                "檢查 MySQL；沒有在執行就用專案的腳本啟動它",
                "database",
                "launch",
            ),
        ),
    ),
    MenuColumn(
        "系統",
        theme.INFO,
        (
            MenuItem(
                "6",
                "安裝／更新依賴",
                "pip install -r requirements.txt",
                "install",
                "cmd",
            ),
            MenuItem("7", "執行測試", "pytest", "tests", "cmd"),
            MenuItem("8", "檢查程式碼格式", "black --check src tests", "format", "cmd"),
            MenuItem(
                "9",
                "檢查 Cog 匯入",
                "逐一匯入所有 Cog 模組，找出語法或匯入錯誤",
                "cogs",
                "cmd",
            ),
            MenuItem(
                "h",
                "主機資訊",
                "這台電腦的型號、處理器、顯示卡與記憶體",
                "host",
                "page",
            ),
        ),
    ),
    MenuColumn(
        "工具",
        theme.ROSE,
        (
            MenuItem(
                "t",
                "檔案工具終端",
                "開發者專用：切換測試等級、授予或撤銷 Nova",
                "tools",
                "cmd",
            ),
            MenuItem(
                "w",
                "區網檔案工作站",
                "檢查配對、啟用或恢復遠端處理",
                "worker",
                "submenu",
            ),
            MenuItem(
                "d",
                "開發者指令說明",
                "在 Discord 裡使用的開發者指令",
                "guide",
                "page",
            ),
            MenuItem("s", "專案資料夾", "用檔案總管開啟", "project", "folder"),
            MenuItem("l", "資料與日誌資料夾", "data 與 data\\logs", "data", "folder"),
            MenuItem(
                "q", "離開", "只關閉控制台，不會停止執行中的機器人", "quit", "quit"
            ),
        ),
    ),
)

ITEMS: tuple[MenuItem, ...] = tuple(item for column in COLUMNS for item in column.items)
BY_KEY: dict[str, MenuItem] = {item.key: item for item in ITEMS}


def column_of(item: MenuItem) -> MenuColumn:
    for column in COLUMNS:
        if item in column.items:
            return column
    raise KeyError(item.key)


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    action: str


WORKER_CHOICES: tuple[Choice, ...] = (
    Choice("1", "檢查配對與圖片轉換", "worker_check"),
    Choice("2", "驗證後啟用遠端處理", "worker_enable"),
    Choice("3", "恢復本機處理", "worker_disable"),
    Choice("4", "開啟可攜式工作站套件資料夾", "worker_packages"),
    Choice("q", "返回", "back"),
)

GUIDE_LINES: tuple[tuple[str, str], ...] = (
    ("/dev-status", "檢視機器人開發者狀態"),
    ("!dev-status", "檢視機器人開發者狀態（前綴指令）"),
    (">>>info", "開啟互動式開發者面板"),
)
