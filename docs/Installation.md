# 安裝與啟動

專案最低要求 Python 3.10，目前部署使用 Python 3.13。從專案根目錄執行命令，避免相對資料路徑指向其他位置。

```bash
git clone https://github.com/keeiv/bot.git
cd bot
python --version
python -m venv .venv
```

Windows PowerShell 啟用虛擬環境：

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux／macOS：

```bash
source .venv/bin/activate
```

安裝執行依賴；開發與測試另外安裝 `requirements-dev.txt`：

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

在根目錄建立 `.env`，至少設定 `DISCORD_TOKEN`。完整範例與 MySQL 連線欄位見 [README](../README.md#安裝)，支援設定見 [Configuration.md](Configuration.md)。Discord 應用程式必須啟用程式需要的 Message Content 與 Server Members intents。

## 儲存初始化

開發可使用 `STORAGE_BACKEND=json`，僅搭配測試資料。正式 MySQL 需先建立獨立資料庫及帳號；本機部署使用 `127.0.0.1:3307`。

搬移前停止所有寫入程序，保留 JSON／SQLite 與原 `GENSHIN_ENCRYPTION_KEY`。目前命令列遷移工具使用 Windows 的 `LOCALAPPDATA` 備份位置；從根目錄執行：

```bash
python -m src.migrate_storage
```

核對成功後設定 `STORAGE_BACKEND=mysql`；工具不會自動切換後端。原始 JSON／SQLite 與備份不可刪除。跨平台程式呼叫可使用 `migrate(root, backup)`，其中備份目錄必須明確指定。

## 啟動與測試

```bash
python -m src.main
python -m pytest -q
```

不要使用 `python src/main.py`，入口使用套件相對匯入。Cog 由 `Bot.load_cogs()` 自動載入，不需要逐一登記。一般測試使用臨時資料，不需要正式帳號；MySQL 整合測試見 [CONTRIBUTING.md](../CONTRIBUTING.md)。
