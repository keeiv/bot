"""English and Traditional Chinese copy for osu_info."""

MESSAGES: dict[str, dict[str, str]] = {
    "osu_info.username": {"en": "**Username**: {v0}\n", "zh": "**用戶名**: {v0}\n"},
    "osu_info.level": {"en": "**Level**: {v0}\n", "zh": "**等級**: {v0}\n"},
    "osu_info.accuracy": {
        "en": "**Accuracy**: {v0:.2f}%\n",
        "zh": "**準確度**: {v0:.2f}%\n",
    },
    "osu_info.play_time": {"en": "**Play time**: {v0}\n", "zh": "**遇戲時間**: {v0}\n"},
    "osu_info.supporter": {
        "en": "**Supporter**: {v0}",
        "zh": "**是否為 Supporter**: {v0}",
    },
    "osu_info.ss_gold": {"en": "**SS (gold)**: {v0}\n", "zh": "**SS (金)**: {v0}\n"},
    "osu_info.ss_silver_platinum": {
        "en": "**SS (silver / platinum)**: {v0}\n",
        "zh": "**SS (銀/白金)**: {v0}\n",
    },
    "osu_info.s_gold": {"en": "**S (gold)**: {v0}\n", "zh": "**S (金)**: {v0}\n"},
    "osu_info.s_silver_platinum": {
        "en": "**S (silver / platinum)**: {v0}\n",
        "zh": "**S (銀/白金)**: {v0}\n",
    },
    "osu_info.a_ranks": {"en": "**A ranks**: {v0}", "zh": "**A 等級**: {v0}"},
    "osu_info.play_count": {
        "en": "**Play count**: {v0}\n",
        "zh": "**遊戲次數**: {v0}\n",
    },
    "osu_info.total_score": {"en": "**Total score**: {v0}\n", "zh": "**總分**: {v0}\n"},
    "osu_info.ranked_score": {
        "en": "**Ranked score**: {v0}\n",
        "zh": "**排名後總分**: {v0}\n",
    },
    "osu_info.maximum_combo": {
        "en": "**Maximum combo**: {v0}\n",
        "zh": "**最高連擊**: {v0}\n",
    },
    "osu_info.total_hits": {"en": "**Total hits**: {v0}", "zh": "**總命中**: {v0}"},
    "osu_info.unknown_pp": {"en": "Unknown pp", "zh": "未知pp"},
    "osu_info.unknown": {"en": "Unknown %", "zh": "未知%"},
    "osu_info.global_rank": {
        "en": "**Global rank**: #{v0:,}\n",
        "zh": "**全球排名**: #{v0:,}\n",
    },
    "osu_info.global_rank_unranked": {
        "en": "**Global rank**: Unranked\n",
        "zh": "**全球排名**: 未排名\n",
    },
    "osu_info.country_rank": {
        "en": "**Country rank**: #{v0:,}\n",
        "zh": "**國家排名**: #{v0:,}\n",
    },
    "osu_info.country_rank_unranked": {
        "en": "**Country rank**: Unranked\n",
        "zh": "**國家排名**: 未排名\n",
    },
    "osu_info.user_was_not_found_or_an": {
        "en": "[Failed] User '{v0}' was not found, or an error occurred: {v1}",
        "zh": "[失敗] 無法找到用戶 '{v0}' 或發生錯誤: {v1}",
    },
    "osu_info.osu_account_unlinked": {
        "en": "[Success] osu! account unlinked: {v0}",
        "zh": "[成功] 已解除綁定 osu! 帳號: {v0}",
    },
    "osu_info.no_osu_account_is_linked_use": {
        "en": "[Info] No osu! account is linked. Use /osu bind <username> first",
        "zh": "[提示] 你尚未綁定 osu! 帳號，請先使用 /osu bind <username>",
    },
    "osu_info.unknown_beatmap": {"en": "Unknown beatmap", "zh": "未知圖譜"},
    "osu_info.osu_user_info": {
        "en": "osu! user info — {v0}",
        "zh": "osu! 用戶資訊 - {v0}",
    },
    "osu_info.basic_info": {"en": "Basic info", "zh": "基本資訊"},
    "osu_info.rank_statistics": {"en": "Rank statistics", "zh": "成績統計"},
    "osu_info.play_statistics": {"en": "Play statistics", "zh": "遊戲統計"},
    "osu_info.user_id_joined": {
        "en": "User ID: {v0} | Joined: {v1}",
        "zh": "用戶 ID: {v0} | 加入時間: {v1}",
    },
    "osu_info.osu_account_linked": {
        "en": "[Success] osu! account linked: {v0}",
        "zh": "[成功] 已綁定 osu! 帳號: {v0}",
    },
    "osu_info.no_osu_account_is_linked": {
        "en": "[Info] No osu! account is linked",
        "zh": "[提示] 你尚未綁定 osu! 帳號",
    },
    "osu_info.scores": {"en": "Scores", "zh": "成績"},
    "osu_info.osu_recent_plays": {
        "en": "osu! recent plays — {v0}",
        "zh": "osu! 最近遊玩 - {v0}",
    },
    "osu_info.linking_failed": {
        "en": "[Failed] Linking failed: {v0}",
        "zh": "[失敗] 綁定失敗: {v0}",
    },
    "osu_info.no_data": {"en": "No data", "zh": "無資料"},
    "osu_info.query_failed": {
        "en": "[Failed] Query failed: {v0}",
        "zh": "[失敗] 查詢失敗: {v0}",
    },
}
