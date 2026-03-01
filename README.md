<img width="1384" height="1040" alt="圖片" src="https://github.com/user-attachments/assets/39815446-fc60-4a4a-9c13-df71df9be1c0" />

# Discord Bot

一個功能完整的 Discord 機器人，包含訊息管理、伺服器安全、遊戲、osu! 整合與 GitHub 監控。

## 主要功能

### 訊息管理
- 記錄訊息編輯與刪除內容，自動發送到指定日誌頻道
- 審計日誌：成員加入/離開、語音頻道異動、角色變更、暱稱變更、頻道建立/刪除/修改

### 管理指令
- `/clear` 清除訊息、`/kick` 踢出、`/ban` 封禁、`/mute` 禁言、`/warn` 警告
- `/黑名單` 黑名單管理 (新增/移除/列表) + 申訴系統
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
- `/osu bind` 綁定帳號、`/osu best` 查詢 BP、`/osu recent` 最近遊玩、`/osu score` 特定譜面

### GitHub 監控
- `/repo_watch set` 設定通用倉庫監控、`/repo_watch status` / `disable`
- `/repo_track add` 專門追蹤 keeiv/bot 倉庫更新 (commits + PRs)

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
```

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
| 身份組管理 | 管理角色 |
| 表情符號上傳 | 管理表情符號 |
| 歡迎訊息設定 | 管理伺服器 |
| GitHub 監控設定 | 管理伺服器 |
| 黑名單管理 | 開發者限定 |
| 其他查詢指令 | 無特殊限制 |

## 資料存放

- `data/config/bot.json`：伺服器設定 (日誌頻道、舉報頻道)
- `data/storage/`：成就、黑名單、申訴、GitHub 監控、osu! 綁定、抽獎、工單等
- `data/logs/messages/`：訊息編輯/刪除日誌

## 時區

所有時間使用 UTC+8。

## 開發

- `src/`：核心原始碼，包含機器人主要的 Cogs 模組與邏輯
- `src/cogs/core/`：核心管理 (admin、audit_log、blacklist、bot_appearance、report 等)
- `src/cogs/features/`：功能模組 (anti_spam、giveaway、achievements、osu_info 等)
- `src/cogs/games/`：遊戲模組
- `src/utils/`：工具函式庫
- `services/`：外部服務整合
- `tests/`：自動化測試
- `scripts/`：開發維護腳本
- `docs/`：說明文件

## 依賴

- discord.py 2.3.2
- python-dotenv 1.0.0
- ossapi (osu! API)
- psutil (系統監控)
- aiohttp (非同步 HTTP)
- deep-translator (免費多引擎翻譯)

## 授權

MIT License
