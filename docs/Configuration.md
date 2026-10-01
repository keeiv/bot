# 設定與儲存

程式從專案根目錄的 `.env` 載入環境變數。完整空值範例見 [README](../README.md#安裝)；此頁只列程式實際支援的主要欄位，不把尚未實作的設定當成可用功能。

| 欄位 | 用途與預設 |
| --- | --- |
| `DISCORD_TOKEN` | 必填；Discord 登入 |
| `STORAGE_BACKEND` | `json` 或 `mysql`；未設定預設 `json`，正式部署明確設為 `mysql` |
| `STORAGE_ROOT` | 文件路徑的根目錄；未設定以程序工作目錄為準 |
| `MYSQL_HOST`／`MYSQL_PORT` | 預設 `127.0.0.1`／`3307` |
| `MYSQL_USER`／`MYSQL_PASSWORD`／`MYSQL_DATABASE` | MySQL 模式的專用帳號及資料庫 |
| `GENSHIN_ENCRYPTION_KEY` | 帳號 Cookie 的原加密金鑰；已有密文時不可替換 |
| `OSU_CLIENT_ID`／`OSU_CLIENT_SECRET` | 啟用 osu! API；綁定資料與 API 是否可用是不同狀態 |
| `GITHUB_TOKEN` | 選用；GitHub 認證查詢 |
| `BLACKLIST_API_KEY` | 外部黑名單查詢 |
| `BOT_API_ENABLED` | 預設 `false`；設為 `true` 才啟動儀表板 API |
| `BOT_API_HOST`／`BOT_API_PORT` | 預設 `127.0.0.1`／`8080` |
| `BOT_API_SECRET` | 啟用 API 時至少 32 字元，與網站伺服器設定一致 |
| `BOT_REGION`／`BOT_VERSION` | 狀態頁的公開標籤 |

Bot 的一般文字指令前綴由 `src/bot.py` 設為 `!`，部分功能另有專用前綴。`COMMAND_PREFIX`、`DATABASE_PATH`、`BACKUP_INTERVAL` 並不是目前共用的環境設定介面。

## 業務設定

使用 Discord 指令或網站儀表板修改設定，兩者都透過 Service 保存。MySQL 模式不應編輯保留的 JSON 檔案來改設定。

| 邏輯文件鍵 | 內容 |
| --- | --- |
| `data/storage/management.json` | 倉庫追蹤、歡迎訊息、自動角色 |
| `data/storage/github_watch.json` | 通用 GitHub 監控與進度 |
| `data/storage/anti_spam_settings.json` | 防刷屏與白名單 |
| `data/storage/age_guard.json` | 年齡守門員 |
| `data/storage/tickets.json` | 工單設定、計數器與記錄 |
| `data/storage/temp_voice.json` | 暫時語音設定與頻道記錄 |
| `data/storage/log_channels.json` | 訊息及審計日誌共用頻道設定 |
| `data/storage/osu_links.json` | osu! 綁定 |
| `data/storage/genshin_accounts.json` | 加密帳號設定 |

這些路徑在 MySQL 模式是 `documents.path` 的鍵，資料保存於 MySQL；JSON 模式才使用實體文件。運作歷史、快取、指標與審計事件使用獨立資料表，見 [README](../README.md)。

## 儀表板連線

網站部署在 Vercel，網站伺服器透過 Tunnel 呼叫本機 API。公開網站域名指向網站前端，Tunnel 使用獨立 API 子網域。API 根路徑直接由瀏覽器開啟且未帶密鑰時回傳 Unauthorized 屬預期結果；不能以取消 API 驗證解決。

密碼、Token、Cookie、金鑰與使用者資料不得提交 Git。
