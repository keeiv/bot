# 訊息編輯／刪除日誌

## 監聽範圍

Cog 記錄伺服器中非機器人成員的訊息，並處理 Discord 訊息快取內的編輯與單筆刪除事件，向設定的日誌頻道發送 Embed。

- 編輯：涵蓋文字或附件變更，顯示事件發生前後的文字並記錄編輯次數；符合圖片條件的編輯後附件可作為 Embed 預覽。
- 刪除：顯示刪除前的文字，符合圖片條件的附件可作為 Embed 預覽，並將已有記錄標記為已刪除。
- 不處理私訊或機器人訊息，也沒有 raw／bulk 事件補全；快取外的編輯與刪除、批次刪除不在此監聽範圍內。保存在資料庫中的記錄不會讓 Discord 自動派發快取外事件。

## 設定

使用 `/編刪紀錄設定 <channel>` 指定日誌頻道，需要執行者具有管理員權限。Bot 在日誌頻道須能查看、發送訊息及嵌入連結。

Discord 應用程式需啟用 Message Content intent；程式也使用伺服器訊息 intents。沒有文字內容權限時，不能期待完整文字日誌。

每個日誌 Embed 包含作者 ID、原始頻道 ID、伺服器名稱及 ID、訊息 ID、事件時間；主要格式化時間使用 UTC+8。

## 資料保存

- 訊息記錄鍵：`data/logs/messages/message_log.json`。
- 頻道設定鍵：`data/storage/log_channels.json`，與審計日誌共用。
- `/settings` 的一般日誌頻道另使用 `data/config/bot.json`，不能混為同一設定。
- 正式 MySQL 模式保存於 `documents`，上述路徑是邏輯鍵；不更新保留的 JSON。JSON 相容模式才讀寫檔案。
- 定期清理按訊息記錄的 `created_at` 保留 30 天，每 24 小時檢查一次。

示意記錄如下；ID 與時間為範例值。`original_content` 保留最初內容，`edit_history` 保存之後的文字內容；日誌畫面使用當次 Discord 事件的內容。`last_edited_at` 和 `deleted_at` 分別在編輯、刪除時加入。

```json
{
  "987654321_123456789": {
    "message_id": 123456789,
    "guild_id": 987654321,
    "channel_id": 555555555,
    "author_id": 111111111,
    "original_content": "最初訊息內容",
    "edit_history": ["第一次編輯後的內容"],
    "deleted": false,
    "attachments": [],
    "created_at": "2026-10-01T10:30:00+08:00",
    "last_edited_at": "2026-10-01T10:35:00+08:00"
  }
}
```

## 排查

1. 指令無法使用：核對執行者管理員權限及所在伺服器。
2. 沒有日誌：核對 `/編刪紀錄設定` 的頻道、Bot 發送與嵌入權限、intents，以及事件是否屬於上述監聽範圍。
3. 保存錯誤：MySQL 模式核對資料庫程序、連線、帳號權限及錯誤日誌；JSON 模式核對磁碟空間與目錄寫入權限。不得編輯遷移前 JSON 或回退舊快照來修復 MySQL 問題。

設定與資料應透過指令或公開 Service 方法管理。開發與部署說明見 [文件導覽](docs/Home.md)。
