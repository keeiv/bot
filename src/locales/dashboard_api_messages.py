"""English and Traditional Chinese copy for dashboard_api."""

MESSAGES: dict[str, dict[str, str]] = {
    "dashboard_api.bot_api_secret_must_contain_at": {
        "en": "BOT_API_SECRET must contain at least 32 characters",
        "zh": "BOT_API_SECRET 至少需要 32 字元",
    },
    "dashboard_api.section_values_and_revision_are_required": {
        "en": "section, values and revision are required",
        "zh": "請提供 section、values、revision",
    },
    "dashboard_api.save_and_enable_the_ticket_settings": {
        "en": "Save and enable the ticket settings first",
        "zh": "請先儲存並啟用工單設定",
    },
    "dashboard_api.the_bot_is_not_ready": {
        "en": "The bot is not ready",
        "zh": "機器人尚未就緒",
    },
    "dashboard_api.these_settings_have_changed_reload_before": {
        "en": "These settings have changed. Reload before saving",
        "zh": "設定已被其他人修改，請重新載入後再儲存",
    },
    "dashboard_api.the_bot_lacks_the_required_permissions": {
        "en": "The bot lacks the required permissions",
        "zh": "機器人權限不足",
    },
    "dashboard_api.the_bot_operation_failed_check_the": {
        "en": "The bot operation failed. Check the local logs",
        "zh": "機器人操作失敗，請查看本機日誌",
    },
    "dashboard_api.support_tickets": {"en": "Support tickets", "zh": "支援工單"},
    "dashboard_api.use_the_button_below_to_create": {
        "en": "Use the button below to create a private support ticket.",
        "zh": "點擊下方按鈕建立私人工單。",
    },
}
