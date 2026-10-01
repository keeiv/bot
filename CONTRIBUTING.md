# 貢獻指南

本專案接受錯誤修復、功能、測試與文件更新。一般貢獻使用 Fork 與 Pull Request；維護者可依已確認的變更範圍直接提交至 `main`。

## 變更範圍

局部修正與文件更新可直接提交 PR。新增依賴、資料格式或資料表變更、跨模組架構調整，以及修改既有指令或權限的變更，應先以 Issue 說明目的、相容性與遷移方式，再進行實作。

## 開發環境

專案最低要求 Python 3.10，目前部署使用 Python 3.13；CI 在 Linux 測試 Python 3.10–3.13。依賴與工具版本以 `pyproject.toml` 為準。

```bash
python -m venv .venv
```

Windows PowerShell 啟用環境：

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux／macOS 啟用環境：

```bash
source .venv/bin/activate
```

安裝執行與開發依賴：

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

啟動機器人所需的 `.env` 設定與 MySQL 遷移流程見 [README](README.md)。一般測試不需要 Discord Token 或正式 MySQL，測試設定會使用臨時資料並限制外部網路連線。

## 程式碼與資料存取

- 函式、類別與變數使用清楚的英文命名；註解、文件字串與介面文字可使用繁體中文。
- 日誌描述事件、狀態與原因，避免針對特定操作人員撰寫提示。
- Cog 負責 Discord 參數、權限、確認及呈現；業務修改透過公開 Service 方法執行，不可直接修改 Service 的設定字典或私有快取。查詢結果為獨立副本。保存失敗應拋出錯誤，成功後才發布記憶體狀態。
- 新功能的載入與分層範例見 [開發指南](docs/DEVELOPMENT.md)。`src/cogs` 自動掃描非套件模組，純工具放入 `src/utils` 或 `src/services`，不維護手動載入清單。
- 業務文件資料使用 `src/utils/document_store.py`，不得在 MySQL 模式直接讀寫舊 JSON，或在資料庫故障時回退至遷移前快照。
- 資料庫與外部服務的同步呼叫不得長時間阻塞 Discord 事件迴圈；完整的同步資料讀取、修改及保存使用 `run_storage()`；外部網路操作使用非同步客戶端或適當的背景執行與逾時。
- 互動指令在耗時處理前應及時回應或 defer，並處理互動過期與 API 超時。
- 保留既有加密金鑰與 Cookie 密文；缺少原金鑰時不得產生替代金鑰覆蓋既有帳號。

## 資料遷移與測試隔離

正式儲存使用 Oracle MySQL 8.4 與 PyMySQL。業務文件以完整 JSON 結構存入 `documents`；運作歷史、快取、指標與審計資料使用獨立資料表。

涉及儲存的變更必須驗證舊資料相容性。遷移前停止所有來源寫入，備份原 JSON／SQLite 與加密金鑰，再核對來源雜湊、文件內容與資料表記錄。遷移失敗應回復交易，不得刪除原始檔案或備份。

一般測試：

```bash
python -m pytest -q
```

MySQL 整合測試在 CI 的獨立 MySQL 8.4 工作固定執行；本機執行時，須配置獨立的 MySQL 帳號與測試資料庫；資料庫名稱必須以 `_test` 結尾。以下範例使用預先建立的測試資料庫，連線資訊透過測試程序環境變數提供：

```powershell
$env:MYSQL_INTEGRATION_TEST = "1"
$env:MYSQL_TEST_DATABASE = "new_bot_test"
python -m pytest tests/test_mysql_storage.py tests/test_storage_reliability.py tests/test_service_boundaries.py -q
```

測試帳號不得具備正式資料庫權限，不得將整合測試指向正式資料庫。一般測試中跳過此測試屬預期行為。

## 格式與品質檢查

先排序匯入，再格式化：

```bash
python -m isort src services tests
python -m black src services tests
```

提交前執行與 CI 一致的檢查：

```bash
python -m pytest -v --cov=src --cov-report=xml
python -m flake8 src services tests
python -m black --check src services tests
python -m isort --check-only src services tests
python -m bandit -r src services -ll
```

新增測試應驗證可觀察行為、錯誤處理或資料完整性；避免測試正式服務或複製實作細節。單純文字更新可核對內容、連結及差異，不必重新啟動機器人。

## 提交與 Pull Request

提交訊息與 PR 標題使用 Conventional Commits 前綴，搭配簡潔的繁體中文描述：

- `feat:` 新功能，例如 `feat: 導入 MySQL 儲存與資料遷移`
- `fix:` 錯誤修復，例如 `fix: 修復資料庫未啟動時的機器人初始化`
- `docs:` 文件更新
- `style:` 格式調整
- `refactor:` 重構
- `test:` 測試更新

PR 說明應包含問題、變更後的行為與驗證結果。涉及資料遷移時補充備份、相容性與回復方式；有相關 Issue 時附上連結。機器人與網站使用不同倉庫，跨專案變更分別提交。

只提交與變更相關的檔案。`.env`、Token、密碼、加密金鑰、Cookie、使用者資料、資料庫檔案與本機備份不得提交；文件與範例只使用空值或示意值。

## 授權

目前版本使用 **AGPL-3.0-only**，作者為 **Keeiv**；完整條文見 [LICENSE](LICENSE)，著作權聲明見 [NOTICE](NOTICE)。新貢獻採用相同授權，並保留貢獻者與第三方元件的著作權聲明。

修改版本若提供網路互動服務，須在使用者可見處提供該運行版本完整對應原始碼的取得方式。原始碼應包含必要的建置與安裝資訊，不包含 Token、密碼、Cookie 或使用者資料。

已發布的 MIT 版本仍可依原條件使用；舊授權聲明保留於 [LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt)。
