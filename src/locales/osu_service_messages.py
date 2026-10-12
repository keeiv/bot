"""English and Traditional Chinese copy for osu_service."""

MESSAGES: dict[str, dict[str, str]] = {
    "osu_service.minutes": {"en": "{v0} minutes", "zh": "{v0} 分鐘"},
    "osu_service.osu_client_id_or_osu_client": {
        "en": "OSU_CLIENT_ID or OSU_CLIENT_SECRET is missing",
        "zh": "缺少 OSU_CLIENT_ID 或 OSU_CLIENT_SECRET 環境變數",
    },
    "osu_service.0_hours": {"en": "0 hours", "zh": "0 小時"},
    "osu_service.hours_minutes": {
        "en": "{v0} hours, {v1} minutes",
        "zh": "{v0} 小時 {v1} 分鐘",
    },
    "osu_service.the_ossapi_package_could_not_be": {
        "en": "The ossapi package could not be loaded. osu! features are disabled",
        "zh": "ossapi 套件無法載入，osu! 功能已禁用",
    },
    "osu_service.osu_is_unavailable_osu_client_id": {
        "en": "osu! is unavailable. OSU_CLIENT_ID and OSU_CLIENT_SECRET must be configured before restarting the bot.",
        "zh": "osu! 功能尚未啟用。請在 .env 加上 OSU_CLIENT_ID 與 OSU_CLIENT_SECRET 後重啟 bot。",
    },
}
