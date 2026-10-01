<img width="1384" height="1040" alt="圖片" src="https://github.com/user-attachments/assets/39815446-fc60-4a4a-9c13-df71df9be1c0" />

# Discord Bot

一個功能完整的 Discord 機器人，包含訊息管理、伺服器安全、遊戲、成就、osu! 整合、HoYoLAB/米游社 整合、GitHub 監控與暫時語音頻道。

## 技術棧與運行架構

| 技術 | 實際用途 |
|------|----------|
| Python 3.13 | 目前部署的執行環境；專案最低要求為 Python 3.10 |
| discord.py 2.7 | Discord Gateway、指令、事件與互動元件 |
| aiohttp 3.14 | 非同步 HTTP 客戶端與儀表板 API 伺服器 |
| Oracle MySQL 8.4 + PyMySQL | 正式環境業務資料、快取、指標與運作歷史儲存 |
| ossapi | osu! API v2 玩家資料查詢 |
| genshin + cryptography | HoYoLAB／米游社整合與帳號 Cookie 加密 |
| psutil | 系統資源監控 |
| GitHub Actions | Python 3.10–3.13 自動測試、格式與品質檢查 |

機器人與 MySQL 在 Windows 本機運行。網站使用 Next.js、React 與 Tailwind CSS，部署於 Vercel；網站伺服器透過 Cloudflare Tunnel 存取本機 aiohttp API。網站不直接連線 MySQL，API 密鑰保存在伺服器環境變數。

## 主要功能

### 訊息管理
- 記錄訊息編輯與刪除內容，自動發送到指定日誌頻道
- 審計日誌：成員加入/離開、語音頻道異動、角色變更、暱稱變更、頻道建立/刪除/修改

### 管理指令
- `/clear` 清除訊息、`/kick` 踢出、`/ban` 封禁、`/mute` 禁言、`/warn` 警告
- `/bl_add|bl_remove|bl_list|bl_info` 雙軌黑名單管理 (機器人資料庫 + CatHome API) + 申訴系統
- `/申訴` / `/申訴狀態` 申訴黑名單（Modal 表單 + 開發者審核）
- `/settings` 伺服器設定儀表板 (日誌/舉報頻道、防刷屏、歡迎訊息一站式管理)
- `/role assign` / `/role remove` 身份組管理
- `/emoji get` / `/emoji upload` 表情符號管理
- `/welcome setup` / `/welcome disable` 歡迎訊息與自動角色

### 防刷屏系統
- 7 層偵測引擎：洪水/重複/提及/連結/表情/換行/突襲
- 6 種處理動作：警告/刪除/禁言/踢出/封禁/封鎖頻道
- 自動升級懲罰 + 白名單管理
- `/anti_spam` 群組指令完整設定介面 (10 個子指令)

### 舉報系統
- 右鍵訊息 > 應用程式 > `舉報訊息` — 舉報可疑訊息到設定頻道
- 管理員可透過按鈕直接禁言/封禁/警告，每個動作附帶表單
- `/report_channel set` 設定舉報頻道

### 機器人外觀
- `/bot_appearance name` 更改伺服器暱稱
- `/bot_appearance avatar` / `banner` 更改頭像/橫幅 (需開發者審核)

### 抽獎系統
- `/giveaway start` 建立抽獎 (支援 `1d12h30m` 時長格式)
- `/giveaway end` 提前結束、`/giveaway reroll` 重新抽取
- 按鈕式參與，自動到期結算

### 工單系統
- `>>>ticket setup #頻道 @身份組` 設定工單系統
- 點擊「開啟工單」按鈕自動建立私人討論串，@通知指定身份組
- 支援關閉工單 / 有原因關閉工單，使用討論串鎖定保留紀錄

### 遊戲
- `/deep_sea_oxygen` 深海氧氣瓶：2 人合作回合制，共享氧氣 + 道具系統
- `/russian_roulette` 俄羅斯輪盤：2 人對抗，籌碼 + 道具系統

### 成就系統
- 聊天互動、遊戲、社交等多種成就類型
- `/achievement` 查看個人成就進度與解鎖狀態

### osu! 整合
- `/user_info_osu` 查詢玩家資料
- `/osu_bind` 綁定帳號、`/osu_unbind` 解除綁定
- `/osu_best` 查詢 Best Performance、`/osu_recent` 最近遊玩記錄

### HoYoLAB/米游社 整合
- `/mhy bind` 安全綁定 HoYoLAB/米游社 Cookie（支援國際服/國服）
- `/mhy tutorial` 獲取 Cookie 獲取教學指引
- `/mhy status` 查看帳號綁定狀態
- `/mhy toggle_autosignin` 開啟/關閉每日自動簽到
- `/mhy notes` 查詢遊戲便箋（樹脂/體力等）
- `/mhy redeem` 兌換遊戲禮包碼
- `/mhy stats` 查詢遊戲統計數據
- `/mhy abyss` 查詢深境螺旋/虛構敘述數據
- 支援原神、崩壞：星穹鐵道、絕區零等多款遊戲

### GitHub 監控
- `/repo_watch set` 設定通用倉庫監控、`/repo_watch status` / `disable`
- `/repo_track add` 專門追蹤 keeiv/bot 倉庫更新 (commits + PRs)
- 倉庫追蹤使用 `GITHUB_TOKEN` 認證、共用查詢快取與 ETag；受到限流時依重試時間暫停輪詢

### 錯誤集中處理
- 全域攔截 Slash / Prefix 指令錯誤，回覆友善中文提示
- 未預期錯誤自動記錄到指定頻道 + 終端輸出
- 處理類型：權限不足、冷卻中、參數錯誤、CheckFailure 等

### 伺服器設定儀表板
- `/settings` 開啟互動式設定面板 (需管理員)
- 支援設定：日誌頻道、舉報頻道、防刷屏開關、歡迎訊息總覽
- Select Menu + Button 即時修改，無需記指令

### 網站儀表板

- Discord 登入、伺服器選擇與管理權限檢查
- 管理歡迎訊息、防刷屏、年齡守門員、暫時語音頻道、工單、GitHub 監控與審計日誌設定
- 設定檢查、面板部署，以及機器人即時狀態與 24 小時／7 天歷史資料
- 本機 API 預設使用 `127.0.0.1:8080`，以共享密鑰驗證請求

### 翻譯系統
- 右鍵訊息 > 應用程式 > `翻譯訊息` — 將任意訊息翻譯為指定語言
- 支援 14 種語言：英文、中文、日文、韓文、法文、德文、西班牙文、義大利文、葡萄牙文、俄文、泰文、越南文、印尼文、菲律賓文

### 年齡守門員
- `/age_guard set_adult_role` 設定 18+ 身份組、`/age_guard set_punishment_role` 設定懲罰身份組
- `/age_guard toggle` 啟用/禁用、`/age_guard status` 查看狀態
- 從訊息中的「數字 + 歲」偵測未成年年齡宣告，依設定移除成人身份組並加入懲罰身份組

### 暫時語音頻道
- `/temp_voice setup` 設定觸發頻道、類別與名稱範本（`{username}` 佔位符，預設：`{username}的家`）
- `/temp_voice status` 查看系統狀態、`/temp_voice disable` 停用系統
- 加入觸發頻道後自動建立個人語音頻道，成員離開後自動刪除
- 使用者可透過 `envc*` 前綴指令自行管理頻道：
  - 基礎設定：`envc*name`、`envc*limit`、`envc*bitrate`
  - 隱私設定：`envc*hide`/`unhide`、`envc*lock`/`unlock`
  - 成員管理：`envc*kick`、`envc*ban`/`unban`
  - 所有權管理：`envc*transfer`、`envc*claim`

### 其他
- `/user_info` 查看用戶資訊 (含 osu! 綁定與成就進度)
- `/server_info` 查看伺服器資訊
- `/help` 多頁幫助資訊

## 安裝

1. 安裝依賴
```bash
pip install -r requirements.txt
```

2. 設定環境變數
在專案根目錄建立 `.env`，設定 Discord、外部服務與儲存連線資訊：
```env
DISCORD_TOKEN=
OSU_CLIENT_ID=
OSU_CLIENT_SECRET=
GITHUB_TOKEN=
BLACKLIST_API_KEY=
GENSHIN_ENCRYPTION_KEY=
STORAGE_BACKEND=mysql
STORAGE_ROOT=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
BOT_API_ENABLED=false
BOT_API_HOST=127.0.0.1
BOT_API_PORT=8080
BOT_API_SECRET=
```

`STORAGE_ROOT` 可設定為專案絕對路徑；未設定時以啟動目錄為準，應從專案根目錄執行。MySQL 資料庫與專用帳號需預先建立，帳號須具備建表及資料讀寫權限。未設定 `STORAGE_BACKEND` 時程式使用 JSON 相容模式；目前正式環境明確設定為 `mysql`。

全新帳號儲存會產生並保存 `GENSHIN_ENCRYPTION_KEY`；已有加密帳號時必須沿用原金鑰，缺失時服務會中止初始化。啟用儀表板 API 時，設定 `BOT_API_ENABLED=true` 與至少 32 字元的 `BOT_API_SECRET`。

3. 搬移既有資料

停止機器人後，在專案根目錄執行：

```bash
python -m src.migrate_storage
```

遷移程式備份並核對 JSON／SQLite 來源、每份文件與各資料表內容，通過後寫入驗證標記。原檔不刪除；目的資料有衝突時中止搬移。Windows 備份位於 `%LOCALAPPDATA%\NewBotMySQL\backups`。MySQL 模式啟動前會核對驗證標記。

4. 執行
```bash
python -m src.main
```

## 權限說明

| 指令 | 所需權限 |
|------|----------|
| 訊息日誌設定 | 管理員 |
| 防刷屏設定 | 管理員 |
| 清除/踢出/封禁/禁言/警告 | 對應管理權限 |
| 舉報頻道設定 | 管理伺服器 |
| 工單系統設定 | 管理員 |
| 翻譯系統 | 無特殊限制 |
| 年齡守門員設定 | 管理頻道 |
| 暫時語音頻道設定 | 管理頻道 |
| 身份組管理 | 管理角色 |
| 表情符號上傳 | 管理表情符號 |
| 歡迎訊息設定 | 管理伺服器 |
| GitHub 監控設定 | 管理伺服器 |
| HoYoLAB/米游社 綁定 | 無特殊限制 |
| 黑名單管理 | 開發者限定 |
| 設定儀表板 | 管理員 |
| 其他查詢指令 | 無特殊限制 |

## 資料存放

- `documents`：以原檔案相對路徑為主鍵，在 MySQL 中保存完整 JSON 結構與 SHA-256 校驗值，涵蓋設定、成就、黑名單、osu! 綁定、加密帳號及其他功能資料。
- `samples`、`cache_entries`、`metrics`、`audit_logs`：儲存運作歷史、快取、指標與審計資料。
- `migration_sources`、`migration_state`：儲存搬移來源副本與驗證完成標記。
- MySQL 模式不更新原 JSON／SQLite，資料庫連線失敗時不回退至舊檔。保留的原檔是遷移快照，後續新增資料以 MySQL 為準。
- `data/logs/runtime.log` 與啟動日誌仍使用檔案；日誌經背景佇列寫入，降低阻塞 Discord 心跳的風險。
- `.env` 保存連線資訊與加密金鑰，不納入 Git。

本機 Oracle MySQL 使用 `127.0.0.1:3307`，資料目錄位於 `%LOCALAPPDATA%\NewBotMySQL\data`。目前透過 Windows 使用者登入啟動；若 `start-mysql.ps1` 已配置，機器人啟動時也會啟動尚未運行的本機 3307 資料庫並等待就緒。此處理不適用於遠端資料庫。

## 時區

所有時間使用 UTC+8。

## 開發

- `src/`：核心原始碼，包含機器人主要的 Cogs 模組與邏輯
- `src/cogs/core/`：核心管理 (admin、audit_log、blacklist、bot_appearance、report、error_handler、settings 等)
- `src/cogs/features/`：功能模組 (anti_spam、giveaway、achievements、osu_info、genshin_cog、translate、age_guard、temp_voice 等)
- `src/cogs/games/`：遊戲模組
- `src/utils/`：工具函式庫
- `src/services/`：外部服務整合 (genshin_service、osu_service、github_watch 等)
- `tests/`：自動化測試
- `docs/`：說明文件

## 依賴

- Python 3.10+
- 依賴版本由 `pyproject.toml` 統一管理；使用 `requirements.txt` 安裝執行環境，使用 `requirements-dev.txt` 安裝開發工具。
- genshin (HoYoLAB/米游社 API)
- cryptography (加密)
- psutil (系統監控)
- aiohttp (非同步 HTTP)
- discord.py (Discord 框架)
- PyMySQL (MySQL 連線)
- ossapi (osu! API v2)
- deep-translator (免費多引擎翻譯)

## 授權

Copyright (c) 2026 Keeiv。

目前版本採用 **GNU Affero General Public License v3.0 only（AGPL-3.0-only）**，完整條文見 [LICENSE](LICENSE)，專案著作權聲明見 [NOTICE](NOTICE)。允許複製、修改、散布與商業使用；修改版本透過網路提供互動服務時，須向使用者提供免費取得該版本完整對應原始碼的方式。原始碼不包含部署密鑰或使用者資料。

本次授權變更不追溯取代已發布版本的 MIT 授權；舊聲明保留於 [LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt)。第三方元件保留各自的授權與著作權聲明。
