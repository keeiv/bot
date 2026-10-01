# 全域黑名單功能使用指南

本文中的 `.json` 路徑是業務資料的邏輯鍵。正式 MySQL 模式存入 `documents`，不更新保留的 JSON；JSON 相容模式才讀寫檔案。修改資料應使用指令或公開儲存介面，不能編輯遷移前的 JSON 來更新正式 MySQL。

## 來源與查詢順序

| 來源 | 資料位置 | 管理方式 |
|------|----------|----------|
| 本地黑名單 | `data/storage/blacklist.json` 文件鍵 | `/blacklist add`、`remove` |
| CatHome API | `api.cathome.shop/v1/blacklist` | 外部服務管理 |

一般攔截先查本地黑名單，命中即返回；本地未命中時才查 CatHome API。本地「local」指機器人管理的資料來源，正式部署同樣保存於 MySQL。`/blacklist info` 則分別查詢並顯示兩個來源。

未設定 `BLACKLIST_API_KEY` 時僅使用本地黑名單。外部 API 查詢失敗或回傳非成功狀態時，無法確認外部封鎖；一般 Slash 指令還設有短查詢時限，逾時可能放行，因此不保證每次都能攔截外部黑名單。

## 開發者管理指令

僅限 `src/config/constants.py` 的 `DEVELOPER_IDS` 帳號，目前包含 `241619561760292866`、`964849855396741130`。

- `/blacklist add <user> <reason> [mode]`：新增或更新本地封鎖；原因必填，模式預設 `block`，可選 `global_ban`。
- `/blacklist remove <user>`：移除本地封鎖；不修改 CatHome API。
- `/blacklist list`：列出本地用戶 ID、原因與模式，附總筆數；過長的清單會截斷。
- `/blacklist info <user>`：顯示本地及外部來源的狀態、原因、模式，以及已有的申訴狀態；本地項目另顯示新增時間。

新增及移除指令回覆操作者，不會立即私訊目標用戶。用戶之後觸發攔截時才收到封鎖提示及申訴按鈕。

## 使用者申訴

`/申訴` 或封鎖提示中的「提交申訴」按鈕會直接提交目前封鎖來源及原封鎖原因，沒有供用戶填寫新原因的 Modal。每位用戶只能有一筆「待處理」申訴。

`/申訴狀態` 顯示「待處理」、「已接受」或「已駁回」，以及來源、提交時間與已保存的審核資訊。

1. 提交成功後，機器人嘗試私訊各開發者，附封鎖資訊及接受／駁回按鈕。私訊權限可能影響通知送達。
2. 開發者接受時開啟 Modal，可留空或填寫最多 1000 字的審核備註；這是審核表單。
3. 接受 `local` 來源申訴會移除本地封鎖；若 CatHome API 仍封鎖該用戶，之後仍可能被攔截。
4. 接受 `api` 來源申訴只更新本機申訴狀態，不會向 CatHome API 送出解封請求。外部封鎖仍須由該服務管理者處理。
5. 駁回不移除封鎖。審核完成後會嘗試私訊用戶；用戶也可使用 `/申訴狀態` 查詢。

## 攔截範圍與模式

一般 Slash、`!` 前綴指令，以及 `>>>ticket`、`envc*` 專用前綴均檢查黑名單；申訴指令保留可用，開發者專用黑名單管理另檢查開發者身分。查詢失敗或逾時的例外見前述說明。

- `block`：拒絕一般指令，不因加入伺服器而踢出成員。
- `global_ban`：在觸發檢查的伺服器嘗試封禁成員；需要機器人具有封禁權限。沒有權限或 Discord 操作失敗時，不能保證封禁成功。

封鎖提示的申訴按鈕會註冊持久化 View，重啟後仍可處理提交。這不代表所有舊審核訊息的按鈕都會在重啟後重新註冊。

## 資料結構

以下是示意資料；ID 與時間均為範例值，`mode` 可為 `block` 或 `global_ban`。

本地黑名單文件鍵：`data/storage/blacklist.json`。

```json
{
  "users": {
    "111111111111111111": {
      "user_id": 111111111111111111,
      "reason": "封鎖原因",
      "mode": "block",
      "added_by": 222222222222222222,
      "added_at": "2026-10-01T12:00:00+08:00",
      "expires_at": null,
      "note": null
    }
  }
}
```

申訴文件鍵：`data/storage/appeals.json`。`reason` 是提交時的封鎖原因；`source` 為 `local` 或 `api`，`status` 使用上述中文狀態。

```json
{
  "111111111111111111": {
    "user_id": 111111111111111111,
    "reason": "封鎖原因",
    "source": "local",
    "status": "待處理",
    "created_at": "2026-10-01T12:05:00+08:00",
    "reviewed_at": null,
    "reviewed_by": null,
    "review_reason": null
  }
}
```

這些本機建立的時間欄位使用 UTC+8；CatHome API 的原始欄位由外部服務定義。申訴記錄不會自動刪除，正式 MySQL 資料應透過公開介面管理；保留的 JSON 只供備份與核對，不應手動修改來更動現行資料。

## 環境設定

```env
BLACKLIST_API_KEY=
```

金鑰只放在 Git 忽略的 `.env`。儲存與開發規範見 [開發指南](docs/DEVELOPMENT.md)，部署及故障排查見 [文件導覽](docs/Home.md)。
