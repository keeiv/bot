"""English and Traditional Chinese copy for github_watch."""

MESSAGES: dict[str, dict[str, str]] = {
    "github_watch.repository_update": {"en": "Repository update", "zh": "檔案庫更新"},
    "github_watch.repository_notifications_enabled_repository_channel_interval": {
        "en": "Repository notifications enabled\nRepository: {v0}/{v1}\nChannel: {v2}\nInterval: {v3} minutes",
        "zh": "已啟用 repo 通知\nRepo: {v0}/{v1}\nChannel: {v2}\nInterval: {v3} 分鐘",
    },
    "github_watch.enabled_repository_channel_id_interval_minutes": {
        "en": "Enabled\nRepository: {v0}/{v1}\nChannel ID: {v2}\nInterval: {v3} minutes\nLast SHA: {v4}",
        "zh": "已啟用\nRepo: {v0}/{v1}\nChannel ID: {v2}\nInterval: {v3} 分鐘\nLast SHA: {v4}",
    },
    "github_watch.repository_notifications_disabled": {
        "en": "Repository notifications disabled",
        "zh": "已停用 repo 通知",
    },
    "github_watch.github_api_returned_no_data": {
        "en": "GitHub API returned no data",
        "zh": "GitHub API 回傳空資料",
    },
    "github_watch.github_api_failed": {
        "en": "GitHub API failed: {v0}",
        "zh": "GitHub API 失敗: {v0}",
    },
    "github_watch.info": {"en": "Info", "zh": "資訊"},
    "github_watch.repository_notifications_are_not_enabled_for": {
        "en": "Repository notifications are not enabled for this server",
        "zh": "此伺服器尚未啟用 repo 通知",
    },
}
