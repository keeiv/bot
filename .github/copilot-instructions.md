# Discord Bot - Copilot 指南

## 項目概述

這是一個功能完整的 Python Discord bot，包含訊息管理、伺服器安全、遊戲、成就、osu! 整合與 GitHub 監控。

## 專案架構

```
src/
  bot.py              # Bot 主類別 (BlacklistCheckTree + 自動 Cog 載入)
  main.py             # 入口點
  cogs/
    core/             # 核心管理模組
      admin.py        # /clear, /kick, /ban, /mute, /warn, /help
      audit_log.py    # 成員/語音/角色/暱稱/頻道 事件自動記錄
      blacklist.py    # 黑名單管理 + 申訴系統 (Modal/View)
      bot_appearance.py  # 伺服器級頭像/橫幅設定 (開發者審核)
      report.py       # 右鍵選單舉報系統 + 禁言/封禁/警告 Modal
      message_logger.py  # 訊息編輯/刪除日誌
      developer.py    # 開發者專用指令
      performance_monitor.py  # 性能背景監控 (無指令)
      system_maintenance.py   # 系統背景維護 (無指令)
    features/         # 功能模組
      anti_spam.py    # 7層防刷屏系統 (10 個子指令)
      giveaway.py     # 抽獎系統 (按鈕參與, 自動結算)
      achievements.py # 成就系統
      management.py   # repo_track, role, emoji, welcome 管理
      osu_info.py     # osu! 整合 (bind/best/recent/score)
      translate.py    # 右鍵翻譯訊息 (deep-translator, 14 種語言)
      github_watch.py # GitHub 倉庫監控
      user_server_info.py  # 用戶/伺服器資訊查詢
    games/            # 遊戲模組
      deep_sea_oxygen.py   # 深海氧氣瓶 (2人合作)
      russian_roulette.py  # 俄羅斯輪盤 (2人對抗)
  utils/              # 工具函式
    config_manager.py    # 日誌頻道/舉報頻道設定 (data/config/bot.json)
    anti_spam.py         # 7層偵測引擎核心邏輯
    logger.py            # Embed 日誌生成
    blacklist_manager.py # 黑名單持久化
    message_cache.py     # 訊息快取
    config_optimizer.py  # 設定優化
    database_manager.py  # 資料庫管理
    api_optimizer.py     # API 快取優化
    network_optimizer.py # 網路優化
    github_manager.py    # GitHub API 管理
```

## 編碼規範

- 使用繁體中文 Docstring 和 Embed 標題/描述
- 變數名、函數名使用英文
- 所有 Embed 包含完整資訊：用戶ID、伺服器名稱、頻道、時間
- 時區統一使用 UTC+8
- JSON 文件使用 `ensure_ascii=False`
- 不使用表情符號，改用 `[文本]` 格式 (如 `[成功]`、`[失敗]`)
- Slash Commands 使用 `discord.app_commands`
- Embed 顏色使用 `discord.Color.from_rgb()`

## 數據結構

### data/config/bot.json
```json
{
  "guilds": {
    "伺服器ID": {
      "log_channel": 頻道ID,
      "report_channel": 頻道ID
    }
  }
}
```

### data/storage/ 目錄
- `achievements.json` - 成就數據
- `blacklist.json` - 黑名單
- `appeals.json` - 申訴記錄
- `github_watch.json` - GitHub 監控設定
- `osu_links.json` - osu! 綁定
- `management.json` - 倉庫追蹤/歡迎訊息設定
- `log_channels.json` - 日誌頻道 (審計日誌用)
- `giveaways.json` - 抽獎數據

## 關鍵實現細節

- Bot 使用 `BlacklistCheckTree` 自訂 CommandTree，全域攔截黑名單用戶
- Cog 透過 `pkgutil.walk_packages` 自動載入
- Embed 字段值上限 1024 字符，需截斷處理
- 權限檢查使用 `guild_permissions` 屬性
- 右鍵選單使用 `app_commands.ContextMenu`
- Modal 表單使用 `discord.ui.Modal` + `TextInput`
- 持久化按鈕使用 `discord.ui.View(timeout=None)`
- DEVELOPER_ID = 241619561760292866

## 依賴

- discord.py 2.3.2
- python-dotenv 1.0.0
- ossapi (osu! API)
- psutil (系統監控)
- aiohttp (非同步 HTTP)
- deep-translator (免費多引擎翻譯)

## 環境設置

需要以下環境變數：
- `DISCORD_TOKEN`: Discord bot token
- `OSU_CLIENT_ID` / `OSU_CLIENT_SECRET`: osu! API (選填)
- `GITHUB_TOKEN`: GitHub API (選填)

## 環境設置

需要以下環境變數：
- `DISCORD_TOKEN`: Discord bot token
