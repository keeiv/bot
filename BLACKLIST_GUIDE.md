# 全域黑名單功能使用指南

## 功能概述

雙軌全域黑名單系統，同時支援本地 JSON 黑名單與 CatHome API 黑名單，包含完整的申訴機制和自動通知。

## 雙軌架構

| 來源 | 儲存 | 管理方式 | 申訴支援 |
|------|------|----------|----------|
| 本地黑名單 | `data/storage/blacklist.json` | `/blacklist add/remove` | 是 |
| CatHome API | `api.cathome.shop/v1/blacklist` | 外部 API 管理 | 是 |

Bot 啟動後會同時檢查兩個來源，任一命中即觸發攔截。

## 開發者指令

### 黑名單管理指令

```
/blacklist add <用戶> [原因]
- 將用戶添加到本地黑名單
- 用戶收到 Embed 通知 + 申訴按鈕
- 範例: /blacklist add @使用者 擾亂秩序

/blacklist remove <用戶>
- 從本地黑名單移除用戶
- 用戶收到移除通知

/blacklist list
- 查看所有本地黑名單用戶
- 顯示用戶 ID、原因、新增時間

/blacklist info <用戶>
- 查詢用戶的黑名單狀態 (本地 + API 雙軌)
- 顯示來源、原因、時間
```

## 使用者指令

### 申訴指令

```
/申訴
- 提交黑名單申訴
- 打開 Modal 表單，填寫申訴原因 (最多 1000 字)
- 申訴內容發送到開發者審核

/申訴狀態
- 查看自己的申訴狀態
- 顯示待處理 / 已接受 / 已拒絕
```

### 申訴流程

1. **黑名單用戶被攔截**
   - 使用任何指令時自動顯示 Embed 通知
   - 通知中包含「提交申訴」按鈕

2. **提交申訴**
   - 點擊按鈕或使用 `/申訴` 指令
   - 填寫 Modal 申訴表單
   - 申訴提交後通知開發者審核

3. **開發者審核**
   - 開發者在私訊中收到申訴 Embed
   - 包含「接受」和「拒絕」按鈕
   - 接受時需填寫理由 (Modal)

4. **申訴結果**
   - **接受**：用戶從黑名單移除，可重新使用指令
   - **拒絕**：用戶仍在黑名單中，收到通知

## 黑名單用戶限制

被黑名單的用戶：
- 無法使用任何 Slash Command（除申訴外）
- 無法使用前綴指令
- 可以使用 `/申訴` 提交申訴
- 可以使用 `/申訴狀態` 查看申訴狀態
- 可以點擊攔截訊息中的申訴按鈕

## 數據存儲

- **本地黑名單**: `data/storage/blacklist.json`
  ```json
  {
    "users": {
      "用戶ID": {
        "reason": "原因",
        "added_by": 操作者ID,
        "added_at": "ISO時間戳"
      }
    }
  }
  ```

- **申訴記錄**: `data/storage/appeals.json`
  ```json
  {
    "用戶ID": {
      "user_id": 用戶ID,
      "reason": "申訴原因",
      "source": "local|api",
      "status": "pending|accepted|rejected",
      "created_at": "ISO時間戳",
      "reviewed_at": "ISO時間戳或null",
      "reviewed_by": 審核者ID或null,
      "review_reason": "審核理由或null"
    }
  }
  ```

## 環境變數

```env
BLACKLIST_API_KEY=your_cathome_api_key  # CatHome 黑名單 API 金鑰 (選填)
```

若未設定 `BLACKLIST_API_KEY`，僅使用本地黑名單。

## 特點

- **雙軌檢查**：本地 JSON + CatHome API 同時查詢
- **來源標記**：申訴記錄標記來源 (local/api)
- **持久化按鈕**：重啟後申訴按鈕仍可使用 (`timeout=None`)
- **防重複申訴**：同一用戶只能有一份待處理申訴
- **自動通知**：黑名單變動和申訴結果自動通知用戶
- **時區配置**：所有時間戳使用 UTC+8

## 注意事項

1. 開發者 ID 設定為 `241619561760292866`，修改請編輯對應常數
2. CatHome API 檢查為非同步，網路異常時自動降級為僅本地檢查
3. 申訴記錄不會自動刪除，可在 `data/storage/appeals.json` 手動管理
