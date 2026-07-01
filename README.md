<img width="1384" height="1040" alt="圖片" src="https://github.com/user-attachments/assets/39815446-fc60-4a4a-9c13-df71df9be1c0" />

# Discord Bot

一個功能完整的 Discord 機器人，包含訊息管理、伺服器安全、遊戲、成就、osu! 整合、HoYoLAB/米游社 整合、GitHub 監控與暫時語音頻道。

## 主要功能

### 訊息管理
- 記錄訊息編輯與刪除內容，自動發送到指定日誌頻道
- 審計日誌：成員加入/離開、語音頻道異動、角色變更、暱稱變更、頻道建立/刪除/修改

### 管理指令
- `/clear` 清除訊息、`/kick` 踢出、`/ban` 封禁、`/mute` 禁言、`/warn` 警告
- `/bl_add|bl_remove|bl_list|bl_info` 雙軌黑名單管理 (本地 JSON + CatHome API) + 申訴系統
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

### 錯誤集中處理
- 全域攔截 Slash / Prefix 指令錯誤，回覆友善中文提示
- 未預期錯誤自動記錄到指定頻道 + 終端輸出
- 處理類型：權限不足、冷卻中、參數錯誤、CheckFailure 等

### 伺服器設定儀表板
- `/settings` 開啟互動式設定面板 (需管理員)
- 支援設定：日誌頻道、舉報頻道、防刷屏開關、歡迎訊息總覽
- Select Menu + Button 即時修改，無需記指令

### 翻譯系統
- 右鍵訊息 > 應用程式 > `翻譯訊息` — 將任意訊息翻譯為指定語言
- 支援 14 種語言：英文、中文、日文、韓文、法文、德文、西班牙文、義大利文、葡萄牙文、俄文、泰文、越南文、印尼文、菲律賓文

### 年齡守門員
- `/age_guard set_adult_role` 設定 18+ 身份組、`/age_guard set_punishment_role` 設定懲罰身份組
- `/age_guard toggle` 啟用/禁用、`/age_guard status` 查看狀態
- 自動監測成人內容並對未驗證成員施加懲罰

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
複製 `.env.example` 為 `.env`，填入你的金鑰：
```env
DISCORD_TOKEN=
OSU_CLIENT_ID=
OSU_CLIENT_SECRET=
GITHUB_TOKEN=
BLACKLIST_API_KEY=
GENSHIN_ENCRYPTION_KEY=
```

**注意**：`GENSHIN_ENCRYPTION_KEY` 會在首次運行時自動生成，無需手動設置。

3. 執行
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

- `data/config/bot.json`：伺服器設定 (日誌頻道、舉報頻道)
- `data/storage/`：成就、黑名單、申訴、GitHub 監控、osu! 綁定、HoYoLAB/米游社 帳號、抽獎、工單、暫時語音頻道、年齡守門員、防刷屏設定等
- `data/logs/messages/`：訊息編輯/刪除日誌

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

- discord.py 2.6+
- python-dotenv 1.0.0
- ossapi (osu! API)
- genshin (HoYoLAB/米游社 API)
- cryptography (加密)
- psutil (系統監控)
- aiohttp (非同步 HTTP)
- deep-translator (免費多引擎翻譯)

## 授權

MIT License
