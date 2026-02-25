<img width="1384" height="1040" alt="圖片" src="https://github.com/user-attachments/assets/39815446-fc60-4a4a-9c13-df71df9be1c0" />

# Discord Bot

一個功能完整的 Discord 機器人，包含訊息管理、遊戲、osu 整合與 GitHub 監控。

## 主要功能

### 訊息管理
- 記錄訊息編輯與刪除內容
- 自動發送到指定日誌頻道
- 防刷屏保護，可設定時間視窗與處理方式

### 管理
- 清除訊息、踢出、封禁、禁言、警告
- 黑名單管理
- 反刷群設定與狀態查詢

### 遊戲
- 深海氧氣瓶：多人回合制遊戲，道具與策略
- 俄羅斯輪盤：運氣遊戲

### 成就系統
- 多種成就類型，包含稀有與開發者限定
- 查看個人成就進度與解鎖狀態

### osu 整合
- `/user_info_osu <username>` 查詢玩家資料
- `/osu bind <username>` 綁定 Discord 與 osu 帳號
- `/osu best` 查詢 BP（支援綁定帳號免填）
- `/osu recent` 查詢最近遊玩
- `/user_info` 會顯示已綁定的 osu 資訊

### GitHub 監控
- `/repo_watch set owner:<owner> repo:<repo> channel:<channel>` 設定通用倉庫監控
- `/repo_track add` 專門追蹤 keeiv/bot 倉庫更新 (包含 commits 和 PRs)
- `/repo_watch status` 查看通用監控狀態
- `/repo_track status` 查看 keeiv/bot 追蹤狀態
- `/repo_watch disable` 停用通用監控
- `/repo_track remove` 移除 keeiv/bot 追蹤

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
python src/main.py
```

## 權限說明

| 指令 | 所需權限 |
|------|----------|
| 訊息管理相關 | 管理員 |
| 反刷群設定 | 管理員 |
| 清除/踢出/封禁/禁言/警告 | 對應管理權限 |
| GitHub 監控設定 | 管理伺服器 |
| Repository 追蹤設定 | 管理頻道 |
| 其他查詢指令 | 無特殊限制 |

## 資料存放

- `data/storage/management.json`：管理功能配置 (包含 repo_track)
- `data/storage/github_watch.json`：通用 GitHub 監控設定
- `data/`：訊息記錄、成就、osu 綁定資料

## 時區

所有時間使用 UTC+8。

## 開發

• `src/`：核心原始碼，包含機器人主要的 Cogs 模組與邏輯。
• `services/`：核心服務層，處理背景運算與外部整合邏輯。
• `tests/`：自動化測試腳本，確保程式碼品質與 CI 檢查通過。
• `scripts/`開發與維護用的輔助腳本。
• `docs/`：存放專案相關的說明文件與指南。
• `.github/`：GitHub Actions 的 CI/CD 工作流配置檔案

## 授權

MIT License
