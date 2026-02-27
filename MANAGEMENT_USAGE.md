# Management Cog 使用指南

## Repository Tracking
追蹤 GitHub 倉庫更新，包含 commits 和 pull requests。

### 指令:
- `/repo_track add channel:<channel>` - 追蹤 keeiv/bot 倉庫更新
- `/repo_track remove` - 移除追蹤
- `/repo_track status` - 顯示追蹤狀態

### 範例:
```
/repo_track add channel:#更新通知
```

## Role Management
身份組管理指令。

### 指令:
- `/role assign <user> <role>` - 為用戶分配身份組
- `/role remove <user> <role>` - 從用戶移除身份組

### 權限:
- 需要「管理角色」權限
- 無法操作高於自己最高角色的身份組

## Emoji Management
表情符號管理指令。

### 指令:
- `/emoji get <emoji>` - 獲取表情符號大圖
- `/emoji upload <name> <image>` - 上傳表情符號到伺服器

### 權限:
- 上傳需要「管理表情符號」權限
- Bot 需要「管理表情符號」權限

## Welcome Messages
設定新成員歡迎訊息，支援自動角色分配。

### 指令:
- `/welcome setup <channel> [message] [embed_title] [embed_color] [auto_role] [send_dm]` - 設定歡迎訊息
- `/welcome disable` - 停用歡迎訊息
- `/welcome preview` - 預覽歡迎訊息
- `/welcome templates` - 查看預設歡迎訊息模板

### 訊息模板變數:
- `{user}` - 用戶 mention
- `{server}` - 伺服器名稱
- `{count}` - 成員數量
- `{created_at}` - 伺服器建立日期

### 可選參數:
- `embed_title` - 嵌入訊息標題
- `embed_color` - 嵌入訊息顏色 (hex 格式，如 `#FF5733`)
- `auto_role` - 新成員自動分配的角色
- `send_dm` - 是否同時發送私訊

### 範例:
```
/welcome setup channel:#歡迎 message:"歡迎 {user} 加入 {server}！你是第 {count} 位成員！" auto_role:@新成員
```

## 所需 Bot 權限
- Manage Channels
- Manage Roles
- Manage Emojis
- Send Messages
- Embed Links
- Read Message History

## 資料儲存
所有設定儲存於 `data/storage/management.json`

## 備註
- 倉庫追蹤每 5 分鐘檢查一次更新
- 所有指令需要對應的 Discord 權限
- 訊息中不使用表情符號
