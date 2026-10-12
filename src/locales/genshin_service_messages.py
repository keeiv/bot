"""English and Traditional Chinese copy for genshin_service."""

MESSAGES: dict[str, dict[str, str]] = {
    "genshin_service.ready": {"en": "Ready", "zh": "已就緒"},
    "genshin_service.until_ready": {"en": "until ready", "zh": "後就緒"},
    "genshin_service.no_hoyolab_miyoushe_account_is_linked": {
        "en": "No HoYoLAB / Miyoushe account is linked. Use `/mhy bind` first.",
        "zh": "您尚未綁定 HoYoLAB/米游社 帳號，請使用 `/mhy bind` 指令進行綁定。",
    },
    "genshin_service.no_linked_account_was_found": {
        "en": "No linked {v0} account was found.",
        "zh": "沒有找到已綁定的 {v0} 帳號。",
    },
    "genshin_service.no_game_account_is_linked_to": {
        "en": "No {v0} game account is linked to this bot.",
        "zh": "您在此 Bot 中尚未綁定任何 {v0} 遊戲帳號。",
    },
    "genshin_service.apocalyptic_shadow": {
        "en": "Apocalyptic Shadow",
        "zh": "末日幻影",
    },
    "genshin_service.no_data": {"en": "No data", "zh": "無數據"},
    "genshin_service.anomaly_arbitration": {
        "en": "Anomaly Arbitration",
        "zh": "異相仲裁",
    },
    "genshin_service.d": {"en": "{v0}d", "zh": "{v0}天"},
    "genshin_service.h": {"en": "{v0}h", "zh": "{v0}小時"},
    "genshin_service.m": {"en": "{v0}m", "zh": "{v0}分鐘"},
    "genshin_service.existing_account_data_found_but_genshin": {
        "en": "Existing account data found but GENSHIN_ENCRYPTION_KEY is missing. Account service initialization stopped; restore the original encryption key.",
        "zh": "已有帳號資料但缺少 GENSHIN_ENCRYPTION_KEY，帳號服務初始化已中止，需恢復原加密金鑰。",
    },
    "genshin_service.could_not_save_genshin_encryption_key": {
        "en": "Could not save GENSHIN_ENCRYPTION_KEY. Account service initialization stopped.",
        "zh": "無法保存 GENSHIN_ENCRYPTION_KEY；帳號服務初始化已中止。",
    },
    "genshin_service.the_supplied_cookie_is_invalid_or": {
        "en": "The supplied cookie is invalid or expired. Obtain a new cookie.",
        "zh": "提供的 Cookie 無效或已過期，請重新獲取並輸入。",
    },
    "genshin_service.cookie_verification_failed": {
        "en": "Cookie verification failed: {v0}",
        "zh": "驗證 Cookie 時發生錯誤: {v0}",
    },
    "genshin_service.memory_of_chaos": {"en": "Memory of Chaos", "zh": "混沌回憶"},
    "genshin_service.pure_fiction": {"en": "Pure Fiction", "zh": "虛構敘事"},
    "genshin_service.knight_boss": {
        "en": "{v0} (Knight {v1} / Boss {v2})",
        "zh": "{v0} (騎士 {v1} / 首領 {v2})",
    },
    "genshin_service.could_not_verify_existing_account_data": {
        "en": "Could not verify existing account data. GENSHIN_ENCRYPTION_KEY is missing; account service initialization stopped.",
        "zh": "無法確認既有帳號資料；缺少 GENSHIN_ENCRYPTION_KEY，帳號服務初始化已中止。",
    },
    "genshin_service.code_redeemed": {"en": "Code redeemed!", "zh": "兌換成功！"},
    "genshin_service.boss_defeated": {
        "en": "Boss {v0} defeated",
        "zh": "首領 {v0} 已擊敗",
    },
    "genshin_service.knight_challenge_in_progress_3": {
        "en": "Knight challenge in progress ({v0}/3)",
        "zh": "騎士挑戰中 ({v0}/3)",
    },
    "genshin_service.this_game_is_unsupported_or_abyss": {
        "en": "This game is unsupported or abyss statistics are unavailable.",
        "zh": "該遊戲不支援或暫無深淵數據統計接口。",
    },
    "genshin_service.open_revenue_pending_collection": {
        "en": "Open (revenue pending collection)",
        "zh": "營業中 (有營業額待整理)",
    },
    "genshin_service.unsupported_game_type": {
        "en": "Unsupported game type.",
        "zh": "不支援的遊戲類型。",
    },
    "genshin_service.this_code_has_already_been_redeemed": {
        "en": "This code has already been redeemed.",
        "zh": "該兌換碼已被領取過。",
    },
    "genshin_service.redemption_requests_are_too_frequent_retry": {
        "en": "Redemption requests are too frequent. Retry later.",
        "zh": "兌換頻率太快，請稍後再試。",
    },
    "genshin_service.invalid_code_or_the_code_is": {
        "en": "Invalid code, or the code is unavailable on this server.",
        "zh": "無效的兌換碼或不適用於此伺服器。",
    },
    "genshin_service.error": {"en": "Error: {v0}", "zh": "錯誤: {v0}"},
    "genshin_service.unsupported_game_type_fdbb37": {
        "en": "Unsupported game type",
        "zh": "不支援的遊戲類型",
    },
    "genshin_service.boss": {"en": "Boss", "zh": "首領"},
    "genshin_service.check_in_successful_reward": {
        "en": "Check-in successful! Reward: {v0} ×{v1}",
        "zh": "簽到成功！獲得: {v0} x{v1}",
    },
    "genshin_service.check_in_successful": {
        "en": "Check-in successful!",
        "zh": "簽到成功！",
    },
    "genshin_service.already_checked_in_today": {
        "en": "Already checked in today.",
        "zh": "今日已簽到過。",
    },
    "genshin_service.check_in_failed": {
        "en": "Check-in failed: {v0}",
        "zh": "簽到失敗: {v0}",
    },
    "genshin_service.initialization_failed": {
        "en": "Initialization failed: {v0}",
        "zh": "初始化失敗: {v0}",
    },
    "genshin_service.open": {"en": "Open", "zh": "營業中"},
    "genshin_service.closed_waiting_to_open": {
        "en": "Closed (waiting to open)",
        "zh": "休息中 (等待開店)",
    },
}
