# Discord 訊息編輯刪除日誌機器人 - Copilot 指南

## 項目概述

這是一個 Python Discord bot，用於監控和記錄伺服器成員的訊息編輯和刪除操作，並包含防炸群功能。

## 核心功能模塊

### 1. 配置管理 (utils/config_manager.py)
- 管理伺服器日誌頻道設置
- 保存和加載訊息記錄
- JSON 持久化存儲

### 2. 日誌生成 (utils/logger.py)
- 生成編輯訊息的 Embed
- 生成刪除訊息的 Embed
- 使用 UTC+8 時區

### 3. 防炸群管理 (utils/anti_spam.py)
- 管理防炸群設置 (啟用/禁用、時間視窗、訊息限制、動作)
- 追蹤用戶訊息發送頻率
- 生成防炸群日誌 Embed
- 支持禁言或刪除訊息的響應

### 4. 事件監聽 (main.py)
- `on_message`: 監聽和檢查垃圾訊息
- `on_message_edit`: 監聽訊息編輯
- `on_message_delete`: 監聽訊息刪除

### 5. 管理命令 (main.py)
- `/編刪紀錄設定`: 設置日誌頻道
- `/anti_spam_set`: 設置防炸群功能
- `/anti_spam_status`: 查看防炸群狀態
- `/clear`: 清除訊息
- `/kick`: 踢出成員
- `/ban`: 封禁成員
- `/mute`: 禁言成員
- `/warn`: 警告成員
- `/help`: 幫助信息

## 編碼規範

- 使用繁體中文註解和變數名
- 所有 Embed 必須包含完整的信息：用戶ID、伺服器名稱、頻道ID、訊息ID、時間
- 時區統一使用 UTC+8
- JSON 文件使用 `ensure_ascii=False` 以支持繁體中文
- 不使用表情符號，改用 [文本] 格式

## 數據結構

### config.json
```json
{
  "guilds": {
    "伺服器ID": {
      "log_channel": 頻道ID
    }
  }
}
```

### guild_*_messages.json
```json
{
  "訊息ID": {
    "message_id": 訊息ID,
    "author_id": 作者ID,
    "channel_id": 頻道ID,
    "original_content": "原始內容",
    "edit_history": [],
    "deleted": false
  }
}
```

## 防炸群工作原理

1. **訊息監控**: `on_message` 事件在每條訊息發送時檢查
2. **頻率計算**: 使用時間視窗追蹤用戶訊息數量
3. **閾值檢查**: 如果超過 `messages_per_window` 且在 `window_seconds` 內，觸發防炸群
4. **執行動作**: 根據 `action` 設置禁言或刪除訊息
5. **記錄日誌**: 發送防炸群事件到日誌頻道

## 關鍵實現細節

- Embed 長度限制：標題和字段值最多 1024 字符
- 多次編輯時更新同一個 Embed (計數編輯次數)
- 刪除時直接顯示刪除前的訊息內容
- 防炸群使用時間戳追蹤訊息，定期清理過期記錄
- 權限檢查使用 `guild_permissions` 屬性
- Slash Commands 使用 discord.app_commands

## 依賴

- discord.py 2.3.2
- python-dotenv 1.0.0

## 環境設置

需要以下環境變數：
- `DISCORD_TOKEN`: Discord bot token
