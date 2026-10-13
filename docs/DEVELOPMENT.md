# 開發指南

給第一次接手這個專案的人：怎麼跑起來、程式放在哪、新功能要遵守哪些規則，以及提交前要檢查什麼。

| 項目 | 內容 |
| --- | --- |
| Python | 最低 3.10，目前部署使用 3.13；CI 在 Linux 測 3.10–3.13 |
| 依賴 | 以 `pyproject.toml` 為準；`requirements.txt`、`requirements-dev.txt` 只是安裝入口 |
| 儲存 | 正式環境 Oracle MySQL 8.4，另有 JSON 相容模式 |
| 安裝與啟動 | 一行指令的快速安裝：`python install.py`（見 [README](../README.md#快速開始)）；手動步驟見 [安裝指南](Installation.md) |
| 提交規則 | [貢獻指南](../CONTRIBUTING.md) |

## 目錄

- [專案結構](#專案結構)
- [啟動與載入](#啟動與載入)
- [Cog 與 Service](#cog-與-service)
- [英文與中文介面](#英文與中文介面)
- [儲存](#儲存)
- [區網節點](#區網節點)
- [終端機控制台](#終端機控制台)
- [測試與檢查](#測試與檢查)
- [提交與推送](#提交與推送)

## 專案結構

```text
install.py               安裝程式：從 GitHub 下載專案並配置開發環境（只用標準函式庫）
src/
  main.py               啟動入口：Token、重複程序與儲存就緒檢查
  bot.py                Bot、全域黑名單檢查、Cog 自動載入、指令翻譯器
  migrate_storage.py    JSON／SQLite 搬移到 MySQL 並核對內容
  tool_worker_setup.py  NovaGrid 區網處理節點：建立套件、驗證、啟用
  moderation_worker_setup.py  AI 圖片審核節點：建立套件、驗證、啟用
  cogs/core/            錯誤處理、設定、日誌、黑名單、外觀、語言、儀表板 API
  cogs/features/        功能指令、互動元件與事件監聽
  cogs/games/           小遊戲
  services/             業務規則、設定修改、保存與公開查詢介面；
                        也包含 NovaGrid 與兩種節點的程式
  locales/              英文與中文訊息目錄、指令說明翻譯、說明頁內容
  utils/                儲存、背景工作、翻譯、語言判斷與共用工具
  control_panel/        Windows 終端機控制台、Nova、桌面捷徑
services/               獨立外部整合（GitHub、osu! API），不是 Cog 的 Service
tests/                  自動化測試
docs/                   說明文件
```

## 啟動與載入

從專案根目錄執行 `python -m src.main`。入口檢查 Token、重複程序與儲存狀態後建立 Bot；`setup_hook()` 初始化共用工具與黑名單 HTTP Session，載入 Cog 並同步應用指令。

`Bot.load_cogs()` 用 `pkgutil.walk_packages()` 掃描 `src/cogs`，逐一 `load_extension()`，不需要維護載入清單。**任何一個模組載入失敗都會中止啟動**，不會以不完整的狀態上線。所以 `src/cogs` 下的每個非套件 Python 模組都要有 `async def setup(bot)`（套件本身會被略過）；純工具放 `src/utils`，業務邏輯放 `src/services`。

```python
import discord
from discord import app_commands
from discord.ext import commands

from src.utils.i18n import text as tx
from src.utils.lang_context import localized


class Example(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="example", description="Say hello")
    @localized("interaction")
    async def example(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(tx("example.hello"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Example(bot))
```

這個範例要能通過測試，還需要在訊息目錄加入 `example.hello`、在指令說明翻譯加入 `"Say hello"`，見 [英文與中文介面](#英文與中文介面)。

背景任務在 `cog_unload()` 取消；需要 Discord 已就緒的任務用 `before_loop` 等待 `wait_until_ready()`。避免重複註冊持久化元件或重複啟動同一個背景工作。

### 指令可以在哪裡使用

`bot.py` 預設所有應用指令只能在伺服器內使用。要開放給個人應用程式（私訊、未加入機器人的伺服器），在指令上明確加：

```python
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
```

在私訊或個人應用程式中，`interaction.guild` 可能是 `None`，也不能假設機器人在該伺服器裡。實際能否以個人應用程式安裝，還要在 Discord Developer Portal 開啟 User Install。

## Cog 與 Service

| 層 | 負責 |
| --- | --- |
| Cog | 指令參數、Discord 權限、互動確認（`defer`）、Embed 與訊息 |
| Service | 資料的新增、修改、刪除、保存與快取 |

- 公開查詢回傳獨立副本，修改查詢結果不會影響 Service；不要直接改 `.config`、快取或呼叫 `_load()`／`_save()`。
- 修改設定時，保留同一伺服器的其他功能、其他伺服器的資料，以及計數器與未知欄位。
- 保存失敗時要拋出錯誤，不能更新記憶體、不能回報成功，也不能用空資料覆蓋原設定；保存成功後才發布新的狀態。

同步的資料庫操作用 `run_storage()`，並把讀取、修改、保存放在同一個工作裡。它限制排隊數量、依序執行，取消時也會等正在跑的工作清理完。不要把讀、改、寫拆成多個工作，也不要在等待外部 API 之後用舊副本覆寫新設定。

```python
from src.utils.storage_worker import run_storage

# 在已完成參數與權限檢查的互動指令內：
await interaction.response.defer(thinking=True, ephemeral=True)
await run_storage(service.add_tracked_repo, str(interaction.guild_id), owner, repo, channel.id)
await interaction.followup.send(tx("management.saved"), ephemeral=True)
```

（`management.saved` 只是示意的鍵名，實際使用前要在訊息目錄加入。）

## 英文與中文介面

機器人自己說的每一句話都有英文與中文兩版。規則：

| 要翻譯的東西 | 放在哪裡 | 怎麼用 |
| --- | --- | --- |
| 回覆、Embed、按鈕、表單文字 | `src/locales/<模組>_messages.py` 的 `MESSAGES` | `tx("key", v0=...)`（`src.utils.i18n.text`） |
| 指令說明、參數說明、選項名稱 | `src/locales/commands.py` 的 `TEXT`（英文 → 中文） | 程式裡寫英文原文，由 `CommandTranslator` 翻成中文 |
| 右鍵選單名稱 | `src/locales/commands.py` 的 `CONTEXT_MENU_NAMES` | 程式裡寫英文名稱 |
| View 上的按鈕文字 | 繼承 `LocalizedView`，在 `i18n` 對應鍵名 | 建立 View 時自動套用當下語言 |

- **語言從哪裡來**：入口函式加上 `@localized("interaction")`（或 `"ctx"`、`"message"`、`"guild"`），裡面的 `tx()` 就會用對的語言：在機器人所在的伺服器依伺服器語言；在私訊，或在機器人沒有加入的伺服器以個人應用程式使用時，依個人設定；沒有設定時依 Discord 用戶端語言（判斷在 `src/utils/lang_context.py`）。需要明確指定語言時用 `t(lang, "key")`。
- **新增訊息模組**：在 `src/locales/__init__.py` 的匯入與註冊清單加入它。鍵名重複會在載入時直接報錯。
- **指令名稱**：斜線指令名稱一律英文，不翻譯。
- **儲存的值不翻譯**：遊戲道具、申訴狀態這類存進資料庫的識別字維持原值，只在顯示時翻譯。
- **目前不翻譯**：網站儀表板 API 的回應（網站依賴中文內容）、本機命令列工具與日誌。

`tests/test_i18n.py` 會檢查：每個訊息都有兩種語言且佔位符相同、每個指令說明都是英文且有中文翻譯、翻譯長度符合 Discord 限制、右鍵選單都有中文名稱。

## 儲存

正式部署使用 Oracle MySQL 8.4。`document_store` 在 MySQL 模式把 `data/storage/management.json` 這類路徑當作 `documents.path` 的識別鍵，內容是完整 JSON 並附校驗值。路徑帶 `.json` 不代表會寫回檔案；`open_document()` 是相容舊程式的介面，新程式可用 `read_document()`／`write_document()`。

- JSON 相容模式才讀寫本機檔案；資料庫失敗時**不會**退回搬移前的 JSON。
- 運作歷史、快取、指標與審計資料另外使用資料表。
- 搬移、原始檔保留與金鑰規則見 [README](../README.md#快速開始)，MySQL 細節見 [設定與儲存](Configuration.md)。

## 區網節點

兩種節點都是「另一台電腦上的可攜式套件」，彼此獨立：

| 節點 | 做什麼 | 程式 | 說明 |
| --- | --- | --- | --- |
| NovaGrid 處理節點 | 圖片壓縮、轉換 | `src/services/` 的 `novagrid.py`、`tool_worker.py`、`tool_remote.py`、`tool_protocol.py` | [tool-worker.md](tool-worker.md) |
| AI 圖片審核節點 | 三階段本地模型審核 | `src/services/moderation_*.py` | [image-review.md](image-review.md) |

修改這些檔案時要注意：

- **套件裡沒有 `src/`**：檔案會被平放複製進套件，用內附的 Python 執行。所以這些模組用 `if __package__:` 同時支援 `from .x import` 與平放時的 `import x`，也不能匯入 `src.` 底下其他模組（控制台的 `theme.py`、`nova.py` 是例外，會一起複製）。
- **引擎識別碼**：主機與節點會比對原始碼雜湊（`engine_digest()`），不一致就拒用。改了引擎或審核規則，就要重建套件並更新節點。
- **安全**：連線用固定 SHA-256 憑證指紋與 256 位元金鑰；套件與配對設定含金鑰，放在 Git 忽略的 `data/` 與 `.file-tools-worker.json`、`.image-review-worker.json`，不能提交。
- **失敗時的行為**：審核節點任何一步失敗都回報「無法判定」，機器人改走人工審核，模型的猜測永遠不會被當成通過。

## 終端機控制台

`src/control_panel/` 是 Windows 專用的終端機介面（`python -X utf8 -m src.control_panel`）。本機的 `run_bot.bat` 只是啟動它的捷徑，不在版本控制內。

**功能**

- 啟動、停止與重新啟動機器人，顯示狀態（PID、運行時間、CPU、記憶體）、這台電腦的硬體、資料庫連線與日誌；重複的日誌訊息會合併成一行（例如 `×282`）。
- 執行依賴安裝、測試、格式檢查，以及兩種區網節點（NovaGrid、AI 圖片審核）的設定。
- 開啟和啟動機器人時會逐步檢查環境、資料庫與鎖定檔；資料庫沒有在執行就自動啟動，`M` 可單獨檢查或啟動資料庫。資料庫只處理本機 3307 埠的 `NewBotMySQL` 實例：先找 `%LOCALAPPDATA%\NewBotMySQL`，找不到再找各應用程式套件資料夾裡的同名實例；啟動前會確認同一個實例沒有其他 `mysqld` 在執行。
- `python -m src.control_panel.shortcut install` 在桌面建立捷徑；已經開著就切回那個視窗，沒開才開新的。控制台若是另一個終端機視窗裡未選取的分頁，捷徑找不到它，會再開一個新視窗；兩個控制台只讀取同樣的檔案，不會互相影響。
- 操作：↑↓ 選擇、Enter 執行，或直接按選項前的字母／數字；`Q` 離開控制台，不會停止在獨立視窗執行的機器人。

**修改時要注意**

- `render.py` 只把狀態畫成畫面，沒有輸入輸出，方便測試；鍵盤與迴圈在 `app.py`。
- 它處理的是 **Windows 的路徑與程序**（機器人與 `mysqld` 的命令列、MySQL 設定檔）。比對路徑一律用 Windows 規則（`ntpath`、`PureWindowsPath`），不要用 `os.path`，否則在 Linux 的 CI 上行為會不同。另外，Python 3.13 起 `ntpath.isabs()` 不再把「只以一個斜線或反斜線開頭」的路徑（例如 `\Windows`）當成絕對路徑，UNC 路徑則仍是絕對路徑；控制台用 `state._is_absolute()` 自行判斷。
- 只能在 Windows 執行的部分（`msvcrt`、`ctypes.windll`、PowerShell）要能注入或替換，讓測試不必真的呼叫它們。

## 測試與檢查

新增功能或修改保存邏輯時，至少驗證：正常流程、保存失敗、副本隔離、既有欄位保留；需要外部查詢的，也測等待期間設定被改的情況。一律使用臨時資料，不要用正式 Token、Cookie 或使用者資料；測試環境會限制對外連線。

提交前執行與 CI 相同的檢查：

```bash
python -m pytest -q
python -m flake8 src services tests
python -m black --check src services tests
python -m isort --check-only src services tests
python -m bandit -r src services -ll
```

CI 在 Ubuntu 上用 Python 3.10–3.13 執行，另外啟動 MySQL 8.4 跑整合測試。本機是 Windows 時要特別留意兩件事：

- 新語法不能超過 Python 3.10。
- Windows 專用的程式在 Linux 上也要能通過測試。

MySQL 整合測試的本機設定見 [貢獻指南](../CONTRIBUTING.md#資料遷移與測試隔離)。

## 提交與推送

提交訊息沿用專案格式：第一行是 `類型: 中文主旨`，類型用 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`；需要說明時空一行，用中文寫做了什麼、為什麼。

```text
feat: 新增 AI 圖片審核節點

機器人頭像與橫幅變更先送到區網審核節點，由三個本地視覺模型依序判斷……
```

不能提交的東西：

- `.env`
- `data/`（含節點套件與執行資料）
- 節點的配對設定與金鑰（`.file-tools-worker.json`、`.image-review-worker.json`、`worker.json`、`worker-key.pem`）
- 本機啟動腳本 `run_bot*.bat`
- 桌面捷徑產生的 `bot-panel.ico`

以上都已列在 `.gitignore`。提交前用 `git status` 確認，有疑慮就先掃一次差異裡有沒有 Token 或金鑰。
