# Discord Bot - Copilot 指南

## 專案概述與依賴

Python Discord 機器人，提供訊息與審計日誌、伺服器管理、防刷屏、工單、暫時語音、遊戲、成就、osu!、HoYoLAB／米游社與 GitHub 監控。

專案最低要求 Python 3.10，目前本機部署使用 Python 3.13；CI 測試 3.10–3.13。依賴以 `pyproject.toml` 為準，目前包含 `discord.py>=2.7.1,<3`、`python-dotenv>=1.2.3,<2`、aiohttp、PyMySQL、genshin、cryptography、ossapi、psutil 與 deep-translator。正式儲存使用 Oracle MySQL 8.4。

## 目錄與載入

```text
src/
  main.py              套件入口、儲存就緒檢查與程序清理
  bot.py               黑名單檢查、Discord Bot 與 Cog 自動載入
  migrate_storage.py   JSON／SQLite 搬移及內容核對
  cogs/core/           管理、日誌、設定、儀表板 API 與背景維護
  cogs/features/       防刷屏、工單、暫時語音、帳號整合等功能
  cogs/games/          深海氧氣瓶、俄羅斯輪盤
  services/            業務規則、資料修改、保存、公開查詢及外部整合
  utils/               document_store、storage_worker、API 與共用工具
  config/constants.py  共用常數及開發者身分
services/              獨立外部整合；與 src/services 分開
tests/                 隔離測試
```

從根目錄執行 `python -m src.main`。Cog 使用 `pkgutil.walk_packages` 自動掃描非套件模組，需有 `async def setup(bot)`，不維護手動列表。純工具放在 `src/utils` 或 `src/services`。

## 修改與儲存規範

- Cog 負責 Discord 參數、權限、確認及呈現；資料修改透過公開 Service 方法，不直接修改 Service 字典或私有快取。
- 查詢應回傳獨立副本；保存成功後才發布快取，失敗應拋錯，保留原資料與未知欄位。
- 同步讀取、修改、保存作為完整操作交給 `run_storage()`；外部網路操作需有逾時，互動在耗時工作前 defer。
- 業務資料使用 `read_document()`／`write_document()`；既有 `open_document()` 是相容介面。MySQL 模式中的 `.json` 路徑是 `documents.path` 邏輯鍵，不能直接讀寫遷移前 JSON。
- MySQL 故障不得回退舊快照；不得刪除原 JSON／SQLite、備份或既有加密金鑰。
- 運作歷史、快取、指標與審計事件使用 `samples`、`cache_entries`、`metrics`、`audit_logs` 資料表。
- 文件及介面採繁體中文，識別字使用清楚的英文。日誌描述事件、狀態與原因。
- 主要 Discord 顯示時間使用 UTC+8；外部資料、診斷及內部時間也有 UTC、Unix 時間戳與單調時鐘，依欄位處理。
- Slash 指令使用 `discord.app_commands`。區分 Discord 的預設指令權限與執行時權限檢查，不把前者當作後者。

## 功能與資料位置

下列路徑表示業務文件鍵；JSON 相容模式才使用同名實體檔案。

| 文件鍵 | 內容 |
|--------|------|
| `data/config/bot.json` | 一般日誌／舉報頻道 |
| `data/storage/log_channels.json` | 訊息與審計日誌共用頻道設定 |
| `data/storage/blacklist.json`、`data/storage/appeals.json` | 本地封鎖及申訴 |
| `data/storage/management.json` | 固定倉庫追蹤、歡迎訊息、自動角色 |
| `data/storage/github_watch.json` | 通用 GitHub 提交監控 |
| `data/storage/anti_spam_settings.json` | 防刷屏及白名單 |
| `data/storage/achievements.json` | 成就 |
| `data/storage/osu_links.json`、`data/storage/genshin_accounts.json` | 綁定及加密帳號 |
| `data/storage/giveaways.json`、`data/storage/tickets.json`、`data/storage/temp_voice.json` | 抽獎、工單、暫時語音 |
| `data/logs/messages/message_log.json` | 訊息日誌記錄 |

- 防刷屏有 7 類偵測，`/anti_spam` 群組有 11 個子指令，包含 `mute_duration`。
- 翻譯提供 14 個選項：繁體中文、簡體中文、英文、日文、韓文、法文、德文、西班牙文、俄文、葡萄牙文、泰文、越南文、印尼文、阿拉伯文。
- 黑名單一般查詢本地優先，再查 CatHome API；申訴提交使用原封鎖原因。接受外部來源申訴不等於向外部服務解封。
- 訊息日誌處理 Discord 快取內非機器人成員的編輯及單筆刪除；沒有 raw／bulk 事件補全。
- GitHub 通用監控追蹤提交；固定 `keeiv/bot` 追蹤另查最新開啟 PR，不追蹤 PR 合併。
- 開發者身分以 `src/config/constants.py` 的 `DEVELOPER_IDS` 為準。

## 設定、測試與安全資料

設定見 [Configuration.md](../docs/Configuration.md) 與 [README](../README.md#安裝)，流程見 [DEVELOPMENT.md](../docs/DEVELOPMENT.md) 與 [CONTRIBUTING.md](../CONTRIBUTING.md)。

`DISCORD_TOKEN` 必填；外部服務憑證、MySQL 連線、原 `GENSHIN_ENCRYPTION_KEY` 與選用的儀表板密鑰依功能配置。不得提交真實 `.env`、Token、Cookie、使用者資料或備份。

一般測試使用臨時資料，不啟動正式 Bot。MySQL 整合測試使用獨立帳號與 `_test` 資料庫；詳細隔離及品質命令見貢獻指南。`docs/audits` 是歷史報告，不能當作現行設定。
