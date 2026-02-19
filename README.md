# Discord 訊息編輯刪除日誌機器人

Discord bot，用於記錄伺服器成員的訊息編輯與刪除操作，並提供防刷屏、遊戲、成就與 osu 查詢等附加功能。

## 功能特性

### 核心功能
- **訊息編輯監控**: 記錄訊息編輯前後的內容，支援多次編輯歷史
- **訊息刪除監控**: 記錄被刪除訊息的內容
- **JSON 持久化**: 記錄與設定保存於本機檔案
- **即時通知**: 編輯與刪除事件即時發送到指定日誌頻道
- **反刷屏**: 自動檢測與處理垃圾訊息/刷屏行為

### 擴充功能
- **用戶/伺服器資訊**: `/user_info`、`/server_info`
- **成就系統**: `/achievements`、`/achievement_codex`
- **osu 查詢與綁定**: `/user_info_osu`、`/osu bind`、`/osu best`、`/osu recent`
- **GitHub 更新通知**: `/repo_watch set/status/disable`
- **遊戲**: 俄羅斯輪盤、深海氧氣瓶

### 管理功能
- `/編刪紀錄設定` - 設置日誌頻道
- `/anti_spam_set` - 設置防炸群功能
- `/anti_spam_status` - 查看防炸群狀態
- `/clear` - 清除訊息
- `/kick` - 踢出成員
- `/ban` - 封禁成員
- `/mute` - 禁言成員
- `/warn` - 警告成員
- `/help` - 顯示幫助信息

## 嵌入信息(Embed)包含信息

每条日誌都包含以下信息：
- [用戶] **用戶ID和名稱**
- [伺服器] **伺服器名稱和ID**
- [頻道] **原始頻道ID**
- [ID] **訊息ID**
- [時間] **時間** (月/日 時:分 UTC+8)
- [內容] **編輯前後的訊息內容** (編輯情況) 或 **删除前的訊息** (刪除情況)
- [統計] **編輯次數** (編輯情況)

## 安裝步驟

### 1. 克隆或下載項目
```bash
cd new_bot
```

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 配置環境變數

複製 `.env.example` 到 `.env`：
```bash
cp .env.example .env
```

編輯 `.env` 文件，添加必要環境變數：
```
DISCORD_TOKEN=your_bot_token_here
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret
GITHUB_TOKEN=your_github_token_optional
```

### 4. 運行bot

```bash
python main.py
```

## 配置

### config.json 結構

配置文件存儲所有伺服器的日誌頻道設置：

```json
{
  "guilds": {
    "伺服器ID": {
      "log_channel": 頻道ID
    }
  }
}
```

### 訊息記錄 (data/guild_*_messages.json)

每個伺服器的訊息記錄結構：

```json
{
  "訊息ID": {
    "message_id": 訊息ID,
    "author_id": 作者ID,
    "channel_id": 頻道ID,
    "original_content": "原始訊息內容",
    "edit_history": ["編輯版本1", "編輯版本2"],
    "deleted": false
  }
}
```

## 使用示例

### 設置日誌頻道

```
/編刪紀錄設定 #日誌
```

這將設置 #日誌 頻道為訊息編輯和刪除的日誌頻道。

### 設置防炸群功能

```
/anti_spam_set true 10 10 mute
```

- 啟用防炸群 (true)
- 時間視窗: 10秒
- 訊息限制: 最多10條訊息
- 觸發動作: 禁言 (mute) 或刪除 (delete)

### 查看防炸群狀態

```
/anti_spam_status
```

顯示當前伺服器的防炸群設置。

### 清除訊息

```
/clear 10
```

清除最後10條訊息。

### 踢出成員

```
/kick @用戶 違反規則
```

### 禁言成員

```
/mute @用戶 30 騷擾其他成員
```

禁言30分鐘。

## 防炸群功能說明

### 工作原理

防炸群功能會監控所有訊息，並記錄每個用戶在時間視窗內發送的訊息數量。如果超過設置的限制，會自動執行配置的動作：

- **禁言 (mute)**: 禁言用戶 1 小時
- **刪除 (delete)**: 刪除該用戶近期發送的訊息

### 自定義設置

可以通過 `/anti_spam_set` 命令自定義防炸群功能的參數：

| 參數 | 說明 | 預設值 | 建議值 |
|------|------|--------|-------|
| enabled | 是否啟用防炸群 | true | true |
| messages_per_window | 時間視窗內的訊息限制 | 10 | 5-15 |
| window_seconds | 時間視窗大小 | 10 | 5-30秒 |
| action | 觸發時的動作 | mute | mute或delete |

## 權限要求

| 命令 | 所需權限 |
|------|--------|
| `/編刪紀錄設定` | 管理員 |
| `/anti_spam_set` | 管理員 |
| `/anti_spam_status` | 管理員 |
| `/clear` | 管理訊息 |
| `/kick` | 踢出成員 |
| `/ban` | 封禁成員 |
| `/mute` | 管理成員 |
| `/warn` | 管理成員 |

## 數據存儲

- **config.json**: 伺服器配置 (日誌頻道設置)
- **data/guild_{伺服器ID}_messages.json**: 每個伺服器的訊息記錄

## 時區

所有時間戳使用 **UTC+8** 時區。

## 故障排除

### Bot 不回應命令

1. 確保 bot 有以下權限：
   - 發送訊息
   - 發送嵌入信息
   - 查看頻道

2. 確保 bot 的角色在頻道的權限之上

3. 檢查 `.env` 文件中的 token 是否正確

### 日誌沒有出現

1. 使用 `/編刪紀錄設定` 命令設置日誌頻道
2. 確保 bot 有在該頻道發送訊息的權限
3. 檢查 `config.json` 是否正確保存了日誌頻道ID

### 訊息記錄缺失

訊息記錄只在 bot 運行時記錄。如果 bot 離線時訊息被編輯或刪除，記錄將不會被保存。

## 開發信息

### 項目結構

```
new_bot/
├── main.py              # 主程序 (包含所有指令和事件監聽)
├── requirements.txt     # 依賴列表
├── config.json          # 配置文件
├── .env                 # 環境變數 (本地)
├── .env.example         # 環境變數示例
├── README.md            # 本說明文檔
├── utils/
│   ├── config_manager.py    # 配置管理
│   ├── logger.py            # 日誌嵌入生成
│   └── anti_spam.py         # 防炸群管理
└── data/                # 訊息記錄目錄
    └── guild_*.json     # 伺服器訊息記錄
```

## 許可證

MIT License

## 支持

如有問題或建議，請聯繫開發者或提交 issue。
