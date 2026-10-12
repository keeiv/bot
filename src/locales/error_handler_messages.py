"""English and Traditional Chinese copy for error_handler."""

MESSAGES: dict[str, dict[str, str]] = {
    "error_handler.error_an_unexpected_error_occurred_the": {
        "en": "[Error] An unexpected error occurred. The error has been logged",
        "zh": "[錯誤] 發生未預期的錯誤，已記錄錯誤資訊",
    },
    "error_handler.error_unexpected_command_error": {
        "en": "[Error] Unexpected command error",
        "zh": "[錯誤] 未預期的指令錯誤",
    },
    "error_handler.command": {"en": "Command", "zh": "指令"},
    "error_handler.user": {"en": "User", "zh": "使用者"},
    "error_handler.error": {"en": "Error", "zh": "錯誤"},
    "error_handler.failed_missing_permissions": {
        "en": "[Failed] Missing permissions: {v0}",
        "zh": "[失敗] 你缺少以下權限: {v0}",
    },
    "error_handler.failed_the_bot_is_missing_permissions": {
        "en": "[Failed] The bot is missing permissions: {v0}",
        "zh": "[失敗] 機器人缺少以下權限: {v0}",
    },
    "error_handler.info_command_on_cooldown_retry_in": {
        "en": "[Info] Command on cooldown. Retry in {v0:.1f} seconds",
        "zh": "[提示] 指令冷卻中，請在 {v0:.1f} 秒後重試",
    },
    "error_handler.failed_permission_to_use_this_command": {
        "en": "[Failed] Permission to use this command is required",
        "zh": "[失敗] 您沒有使用此指令的權限",
    },
    "error_handler.failed_invalid_argument_format": {
        "en": "[Failed] Invalid argument format: {v0}",
        "zh": "[失敗] 參數格式錯誤: {v0}",
    },
    "error_handler.failed_required_argument_missing": {
        "en": "[Failed] Required argument missing: {v0}",
        "zh": "[失敗] 缺少必要參數: {v0}",
    },
}
