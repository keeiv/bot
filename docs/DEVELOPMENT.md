# 開發指南

## 從哪裡開始

專案要求 Python 3.10 以上，目前本機部署使用 Python 3.13。依賴定義見 `pyproject.toml`；安裝與啟動見 [安裝指南](Installation.md)，提交與品質檢查見 [貢獻指南](../CONTRIBUTING.md)。

```text
src/
  main.py                 啟動入口、儲存就緒檢查與程序清理
  bot.py                  Bot、全域黑名單檢查與 Cog 自動載入
  migrate_storage.py      JSON／SQLite 遷移與內容核對
  cogs/core/              錯誤處理、設定、日誌、儀表板 API 等
  cogs/features/          功能指令、互動元件與事件監聽
  cogs/games/             遊戲
  services/               業務規則、設定修改、保存與公開查詢介面
  utils/                  共用儲存、背景工作、快取與外部 API 工具
services/                 獨立的外部整合；不是 Cog 的業務 Service 目錄
tests/                    隔離測試
```

## 啟動與載入流程

從專案根目錄執行 `python -m src.main`。入口檢查 Token、重複程序與儲存狀態，再建立 Bot。`setup_hook()` 初始化共用工具、黑名單 HTTP Session，載入 Cog 並同步應用指令。

`Bot.load_cogs()` 使用 `pkgutil.walk_packages()` 掃描 `src/cogs`，逐一呼叫 `load_extension()`；不需要在 `bot.py` 維護手動載入清單。任一模組載入失敗會中止啟動，不能忽略錯誤後當作完整服務上線。

新增 Cog 放在 `src/cogs` 下，提供 `async def setup(bot)`。此目錄內的每個非套件 Python 模組都會被嘗試載入；純工具與 Service 放在 `src/utils` 或 `src/services`，避免缺少 `setup()`。

```python
from discord.ext import commands


class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def example(self, ctx):
        await ctx.send("Hello")


async def setup(bot):
    await bot.add_cog(Example(bot))
```

背景任務應在 `cog_unload()` 取消；需要 Discord 已就緒的任務使用 `before_loop` 等待 `wait_until_ready()`。避免重複註冊持久化元件或啟動同一背景工作。

## Cog 與 Service 的界線

- Cog 負責指令參數、Discord 權限、互動確認、Embed 與訊息發送。
- Service 負責業務資料的新增、修改、刪除、保存與快取發布。
- 公開查詢回傳獨立副本。修改查詢結果不會改動 Service；不得直接改 `.config`、快取或呼叫 `_load()`／`_save()`。
- 設定修改應保留同一伺服器的其他功能、其他伺服器資料，以及現有計數器與未知欄位。
- 保存失敗必須拋出錯誤；保存成功後才更新記憶體，不能回報成功或用空資料覆蓋原設定。

```python
from src.utils.storage_worker import run_storage

# 在已完成參數與權限檢查的互動指令內：
await interaction.response.defer(thinking=True, ephemeral=True)
await run_storage(service.add_tracked_repo, str(interaction.guild_id), owner, repo, channel.id)
await interaction.followup.send("設定已保存", ephemeral=True)
```

同步資料庫操作使用 `run_storage()`，將完整的讀取、修改、保存操作放在同一個工作內。它限制排隊數量、序列化工作並在取消時等待正在執行的工作清理完成。不要把讀、改、寫拆成多個工作，或在等待外部 API 後以舊副本覆寫新設定。

## 儲存模式

正式部署使用 Oracle MySQL 8.4。`document_store` 在 MySQL 模式將 `data/storage/management.json` 這類路徑作為 `documents.path` 的邏輯識別鍵，內容仍是完整 JSON 結構，並附校驗值。名稱帶 `.json` 不代表 MySQL 模式會寫回該檔案；`open_document()` 是現有相容介面。

新儲存程式可使用 `read_document()`／`write_document()`；JSON 相容模式才讀寫本機檔案。資料庫失敗不得回退到遷移前 JSON。運作歷史、快取、指標與審計資料另外使用資料表。遷移、原始檔保留與金鑰要求見 [README](../README.md#安裝)。

## 測試

新增功能或修改保存邏輯時，驗證正常流程、保存失敗、副本隔離與既有欄位保留；需要外部查詢時也測試等待期間設定變更。使用臨時資料，禁止正式 Token、Cookie 與使用者資料。

```bash
python -m pytest -q
python -m flake8 src services tests
python -m black --check src services tests
python -m isort --check-only src services tests
python -m bandit -r src services -ll
```

CI 在 Python 3.10–3.13 執行一般測試，另啟動 MySQL 8.4 執行整合測試。設定方式見 [貢獻指南](../CONTRIBUTING.md#資料遷移與測試隔離)。
