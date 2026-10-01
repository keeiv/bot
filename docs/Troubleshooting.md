# 故障排查

先從專案根目錄確認 `python --version` 至少為 3.10，並使用同一個虛擬環境安裝 `requirements.txt`。啟動命令是 `python -m src.main`，不可直接執行 `src/main.py`。

## 啟動失敗

- 缺少 `DISCORD_TOKEN`：檢查根目錄 `.env` 與執行目錄，不要把 Token 貼入日誌。
- MySQL 連線失敗：核對 `MYSQL_HOST`、`MYSQL_PORT`、資料庫程序與專用帳號權限。失敗時不會回退舊 JSON。
- 遷移未驗證：停止所有寫入，按 [README](../README.md#安裝) 進行備份、遷移與內容核對；不能自行偽造驗證標記。
- 缺少原加密金鑰：恢復原 `GENSHIN_ENCRYPTION_KEY`；新金鑰不能解密舊 Cookie。
- Cog 載入失敗：讀取第一個模組錯誤，檢查依賴與 `setup(bot)`。載入清單是自動掃描，不應手動加另一份列表。
- 重複程序：核對 `bot.lock` 的 PID，先關閉原實例；不要一邊寫正式資料一邊啟動第二個 Bot。

## 心跳或互動逾時

`heartbeat blocked` 表示 Discord 事件迴圈沒有及時處理心跳。新增同步儲存操作應使用 `run_storage()`，外部網路操作設定逾時；不要在事件處理中使用同步等待。檢查系統記憶體與其他長時間運算，不能只隱藏日誌。

`Unknown interaction` 可能是首次回覆超過 Discord 的互動時限。耗時處理前先 defer，之後使用 followup；不要重複首次回覆。

## 綁定存在但 osu! 查詢不可用

綁定資料與 API 初始化分開。檢查 `OSU_CLIENT_ID`／`OSU_CLIENT_SECRET` 及套件；不要刪除綁定資料來排查憑證問題。

## GitHub 限流

核對 `GITHUB_TOKEN` 是否已載入，並確認其他程序是否共用同一帳號額度。現有快取、ETag 與冷卻會減少重複請求；遵循回應中的限流等待時間，重啟程序會重置記憶體冷卻而不會增加額度。

## 儀表板 Unauthorized

API 要求伺服器端共享密鑰；瀏覽器直接開啟 API 根路徑時沒有密鑰。核對網站域名是否指向 Vercel、API 子網域是否指向本機 `127.0.0.1:8080`，以及網站伺服器的密鑰是否一致。

## 保存失敗

設定寫入失敗應顯示錯誤，原快取與已保存資料不應改變。恢復磁碟或資料庫後重新提交；不要把未確認的畫面狀態當成保存成功。修改此流程時執行 [貢獻指南](../CONTRIBUTING.md) 的一般與 MySQL 隔離測試。
