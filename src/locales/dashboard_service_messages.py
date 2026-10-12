"""English and Traditional Chinese copy for dashboard_service."""

MESSAGES: dict[str, dict[str, str]] = {
    "dashboard_service.unknown_settings_section": {
        "en": "Unknown settings section",
        "zh": "未知的設定區塊",
    },
    "dashboard_service.missing_or_unknown_settings_fields": {
        "en": "Missing or unknown settings fields",
        "zh": "設定欄位不完整或含未知欄位",
    },
    "dashboard_service.invalid_spam_protection_action": {
        "en": "Invalid spam protection action",
        "zh": "無效的防炸群動作",
    },
    "dashboard_service.complete_all_required_fields_before_enabling": {
        "en": "Complete all required fields before enabling",
        "zh": "啟用前請填妥必要欄位",
    },
    "dashboard_service.voice_channel_names_must_not_exceed": {
        "en": "Voice channel names must not exceed 100 characters",
        "zh": "語音頻道名稱上限 100 字",
    },
    "dashboard_service.invalid_format": {
        "en": "Invalid {v0} format",
        "zh": "{v0} 格式錯誤",
    },
    "dashboard_service.is_too_long": {"en": "{v0} is too long", "zh": "{v0} 太長"},
    "dashboard_service.must_be_between_and": {
        "en": "{v0} must be between {v1} and {v2}",
        "zh": "{v0} 必須介於 {v1}–{v2}",
    },
    "dashboard_service.invalid_github_owner_or_repository_name": {
        "en": "Invalid GitHub owner or repository name",
        "zh": "GitHub 擁有者或倉庫名稱格式錯誤",
    },
    "dashboard_service.must_be_a_discord_id": {
        "en": "{v0} must be a Discord ID",
        "zh": "{v0} 必須是 Discord ID",
    },
    "dashboard_service.the_welcome_message_contains_unsupported_variables": {
        "en": "The welcome message contains unsupported variables",
        "zh": "歡迎訊息含不支援的變數",
    },
    "dashboard_service.the_role_does_not_belong_to": {
        "en": "The {v0} role does not belong to this server",
        "zh": "{v0} 身份組不屬於此伺服器",
    },
    "dashboard_service.the_role_must_be_manageable_by": {
        "en": "The {v0} role must be manageable by the bot and must not have Administrator permission",
        "zh": "{v0} 必須是機器人可管理且不含管理員權限的身份組",
    },
    "dashboard_service.the_channel_has_the_wrong_type": {
        "en": "The {v0} channel has the wrong type or does not belong to this server",
        "zh": "{v0} 頻道類型錯誤或不屬於此伺服器",
    },
    "dashboard_service.the_bot_lacks_required_permissions_in": {
        "en": "The bot lacks required permissions in the {v0} channel",
        "zh": "機器人在 {v0} 頻道缺少必要權限",
    },
}
