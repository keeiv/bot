"""English and Traditional Chinese copy for report."""

MESSAGES: dict[str, dict[str, str]] = {
    "report.mute_member": {"en": "Mute member", "zh": "禁言處理"},
    "report.ban_member": {"en": "Ban member", "zh": "封禁處理"},
    "report.warn_member": {"en": "Warn member", "zh": "警告處理"},
    "report.days": {"en": "Days", "zh": "天數"},
    "report.hours": {"en": "Hours", "zh": "小時"},
    "report.minutes": {"en": "Minutes", "zh": "分鐘"},
    "report.enter_a_reason_for_the_mute": {
        "en": "Enter a reason for the mute…",
        "zh": "請輸入禁言原因...",
    },
    "report.temporary_ban_enter_yes_leave_blank": {
        "en": "Temporary ban? Enter yes; leave blank for permanent",
        "zh": "是否暫時封禁 (輸入 '是' 或留空為永久)",
    },
    "report.blank_permanent_ban": {
        "en": "Blank = permanent ban",
        "zh": "留空 = 永久封禁",
    },
    "report.temporary_ban_duration_in_seconds": {
        "en": "Temporary ban duration in seconds",
        "zh": "暫時封禁時長 (秒，僅暫時封禁時填寫)",
    },
    "report.example_86400_1_day_3600_1": {
        "en": "Example: 86400 (1 day) / 3600 (1 hour)",
        "zh": "例如: 86400 (1天) / 3600 (1小時)",
    },
    "report.delete_messages_from_the_past_0": {
        "en": "Delete messages from the past 0–7 days",
        "zh": "刪除幾天內的訊息 (0-7)",
    },
    "report.enter_a_reason_for_the_ban": {
        "en": "Enter a reason for the ban…",
        "zh": "請輸入封禁原因...",
    },
    "report.warning_count": {"en": "Warning count", "zh": "警告次數"},
    "report.enter_a_reason_for_the_warning": {
        "en": "Enter a reason for the warning…",
        "zh": "請輸入警告原因...",
    },
    "report.mute": {"en": "Mute", "zh": "禁言"},
    "report.ban": {"en": "Ban", "zh": "封禁"},
    "report.warn": {"en": "Warn", "zh": "警告"},
    "report.no_text_content": {"en": "(No text content)", "zh": "(無文字內容)"},
    "report.no_report_channel_is_configured_use": {
        "en": "No report channel is configured. Use `/report_channel set`",
        "zh": "尚未設定舉報頻道，請使用 `/report_channel set` 設定",
    },
    "report.report_new_message_report": {
        "en": "[Report] New message report",
        "zh": "[舉報] 新的訊息舉報",
    },
    "report.reported_user": {"en": "Reported user", "zh": "被舉報者"},
    "report.reported_by": {"en": "Reported by", "zh": "舉報人"},
    "report.message_content": {"en": "Message content", "zh": "訊息內容"},
    "report.message_link": {"en": "Message link", "zh": "訊息連結"},
    "report.open_message": {"en": "[Open message]({v0})", "zh": "[點擊跳轉]({v0})"},
    "report.message_id_server": {
        "en": "Message ID: {v0} | Server: {v1}",
        "zh": "訊息 ID: {v0} | 伺服器: {v1}",
    },
    "report.success_report_submitted_for_moderator_review": {
        "en": "[Success] Report submitted for moderator review",
        "zh": "[成功] 你的舉報已送出，管理員將會進行審查",
    },
    "report.success_report_channel_saved": {
        "en": "[Success] Report channel saved",
        "zh": "[成功] 舉報頻道已設定",
    },
    "report.reports_will_be_sent_to": {
        "en": "Reports will be sent to {v0}",
        "zh": "舉報訊息將發送至 {v0}",
    },
    "report.current_report_channel": {
        "en": "Current report channel: {v0}",
        "zh": "目前舉報頻道: {v0}",
    },
    "report.the_configured_channel_no_longer_exists": {
        "en": "The configured channel no longer exists. Configure another channel",
        "zh": "已設定的頻道不存在，請重新設定",
    },
    "report.reports_channel_settings": {
        "en": "[Reports] Channel settings",
        "zh": "[舉報系統] 頻道設定",
    },
    "report.failed_this_feature_is_only_available": {
        "en": "[Failed] This feature is only available in a server",
        "zh": "[失敗] 此功能僅限伺服器內使用",
    },
    "report.failed_reporting_one_s_own_messages": {
        "en": "[Failed] Reporting one's own messages is not allowed",
        "zh": "[失敗] 你不能舉報自己的訊息",
    },
    "report.failed_bot_messages_cannot_be_reported": {
        "en": "[Failed] Bot messages cannot be reported",
        "zh": "[失敗] 你不能舉報機器人的訊息",
    },
    "report.failed_no_report_channel_is_configured": {
        "en": "[Failed] No report channel is configured. An administrator can use `/report_channel set`",
        "zh": "[失敗] 此伺服器尚未設定舉報頻道，請管理員使用 `/report_channel set` 設定",
    },
    "report.failed_the_report_channel_does_not": {
        "en": "[Failed] The report channel does not exist. An administrator must configure another channel",
        "zh": "[失敗] 舉報頻道不存在或已被刪除，請管理員重新設定",
    },
    "report.attachments": {"en": "Attachments", "zh": "附件"},
    "report.notice": {"en": "Notice", "zh": "注意"},
    "report.the_reported_user_has_left_the": {
        "en": "The reported user has left the server. Moderation actions are unavailable",
        "zh": "被舉報的用戶已不在伺服器中，無法執行處理動作",
    },
    "report.failed_invalid_time_format_enter_numbers": {
        "en": "[Failed] Invalid time format. Enter numbers",
        "zh": "[失敗] 時間格式錯誤，請輸入數字",
    },
}
