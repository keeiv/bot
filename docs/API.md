# API Documentation

## Bot API Endpoints

### osu! API Integration
需要設定 `OSU_CLIENT_ID` 和 `OSU_CLIENT_SECRET` 環境變數。

#### Commands
- `/user_info_osu <username>` - 查詢 osu! 用戶統計資料
- `/osu bind <username>` - 綁定 Discord 帳號到 osu! 帳號
- `/osu unbind` - 解除綁定
- `/osu best [username] [limit]` - 查詢最佳成績 (BP)
- `/osu recent [username]` - 查詢最近遊玩成績
- `/osu score <beatmap_id> [username]` - 查詢特定譜面成績

### GitHub Integration
需要設定 `GITHUB_TOKEN` 環境變數 (選填)。

#### 通用倉庫監控
- `/repo_watch set owner:<owner> repo:<repo> channel:<channel>` - 設定倉庫監控
- `/repo_watch status` - 查看監控狀態
- `/repo_watch disable` - 停用監控

#### keeiv/bot 專屬追蹤
- `/repo_track add channel:<channel>` - 追蹤 keeiv/bot 倉庫更新
- `/repo_track remove` - 移除追蹤
- `/repo_track status` - 查看追蹤狀態

#### GitHub 診斷
- `/github-diagnose` - 完整 API 連接診斷
- `/github-status` - 速率限制檢查

### Context Menu (右鍵選單)
- `舉報訊息` - 右鍵訊息 > 應用程式 > 舉報訊息

## Configuration Files

### Bot Configuration (`data/config/bot.json`)
```json
{
  "guilds": {
    "guild_id": {
      "log_channel": "channel_id",
      "report_channel": "channel_id"
    }
  }
}
```

### Storage Files (`data/storage/`)
- `achievements.json` - 成就數據
- `blacklist.json` - 黑名單
- `appeals.json` - 申訴記錄
- `github_watch.json` - GitHub 通用監控設定
- `giveaways.json` - 抽獎數據
- `log_channels.json` - 審計日誌頻道設定
- `management.json` - 倉庫追蹤/歡迎訊息設定
- `osu_links.json` - osu! 帳號綁定

### Message Logs (`data/logs/messages/`)
- `message_log.json` - 訊息編輯/刪除日誌
- General logs: `data/logs/messages/message_log.json`
