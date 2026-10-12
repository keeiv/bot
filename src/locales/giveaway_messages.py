"""English and Traditional Chinese copy for giveaway."""

MESSAGES: dict[str, dict[str, str]] = {
    "giveaway.enter_giveaway": {"en": "Enter giveaway", "zh": "參加抽獎"},
    "giveaway.giveaway": {"en": "{v0} giveaway", "zh": "{v0} 抽獎活動"},
    "giveaway.winner_count": {"en": "Winner count", "zh": "得獎人數"},
    "giveaway.ends_at": {"en": "Ends at", "zh": "結束時間"},
    "giveaway.participants": {"en": "Participants", "zh": "參與人數"},
    "giveaway.0_members": {"en": "0 members", "zh": "0 人"},
    "giveaway.hosted_by": {"en": "Hosted by", "zh": "主辦者"},
    "giveaway.id_ends_at": {"en": "ID: {v0} | Ends at", "zh": "ID: {v0} | 結束於"},
    "giveaway.success_giveaway_created": {
        "en": "[Success] Giveaway created",
        "zh": "[成功] 抽獎已建立",
    },
    "giveaway.prize_channel_ends_t_r": {
        "en": "Prize: **{v0}**\nChannel: {v1}\nEnds: <t:{v2}:R>",
        "zh": "獎品: **{v0}**\n頻道: {v1}\n結束: <t:{v2}:R>",
    },
    "giveaway.success_giveaway_ended_early_and_winners": {
        "en": "[Success] Giveaway ended early and winners selected",
        "zh": "[成功] 抽獎已提前結束並抽出得獎者",
    },
    "giveaway.success_winners_redrawn": {
        "en": "[Success] Winners redrawn: {v0}",
        "zh": "[成功] 重新抽取完成！得獎者: {v0}",
    },
    "giveaway.active_giveaways": {
        "en": "{v0} active giveaways",
        "zh": "{v0} 進行中的抽獎",
    },
    "giveaway.info_this_giveaway_has_ended": {
        "en": "[Info] This giveaway has ended",
        "zh": "[提示] 此抽獎已結束",
    },
    "giveaway.info_entry_withdrawn": {
        "en": "[Info] Entry withdrawn",
        "zh": "[提示] 你已退出抽獎",
    },
    "giveaway.success_giveaway_entered_participants": {
        "en": "[Success] Giveaway entered. Participants: {v0}",
        "zh": "[成功] 你已參加抽獎！目前共 {v0} 位參與者",
    },
    "giveaway.failed_invalid_duration_examples_1h_30m": {
        "en": "[Failed] Invalid duration (examples: 1h, 30m, 1d, 2d6h). Minimum: 1 minute",
        "zh": "[失敗] 無效時長格式 (例: 1h, 30m, 1d, 2d6h)，最短 1 分鐘",
    },
    "giveaway.failed_winner_count_must_be_between": {
        "en": "[Failed] Winner count must be between 1 and 50",
        "zh": "[失敗] 得獎人數必須在 1~50 之間",
    },
    "giveaway.select_a_text_channel_or_thread": {
        "en": "Select a text channel or thread.",
        "zh": "請選擇文字頻道或討論串。",
    },
    "giveaway.prize_details": {"en": "Prize details", "zh": "獎品說明"},
    "giveaway.failed_giveaway_not_found": {
        "en": "[Failed] Giveaway not found",
        "zh": "[失敗] 找不到此抽獎",
    },
    "giveaway.failed_this_giveaway_has_ended": {
        "en": "[Failed] This giveaway has ended",
        "zh": "[失敗] 此抽獎已結束",
    },
    "giveaway.failed_finished_giveaway_not_found": {
        "en": "[Failed] Finished giveaway not found",
        "zh": "[失敗] 找不到已結束的抽獎",
    },
    "giveaway.failed_no_participants": {
        "en": "[Failed] No participants",
        "zh": "[失敗] 沒有參與者",
    },
    "giveaway.info_no_active_giveaways": {
        "en": "[Info] No active giveaways",
        "zh": "[提示] 目前沒有進行中的抽獎",
    },
    "giveaway.id_winners_participants_ends_t_r": {
        "en": "ID: `{v0}`\nWinners: {v1} | Participants: {v2}\nEnds: <t:{v3}:R>",
        "zh": "ID: `{v0}`\n得獎人數: {v1} | 參與: {v2} 人\n結束: <t:{v3}:R>",
    },
    "giveaway.giveaway_ended": {"en": "{v0} giveaway ended!", "zh": "{v0} 抽獎結束！"},
    "giveaway.prize_winners": {
        "en": "Prize: **{v0}**\n\nWinners: {v1}",
        "zh": "獎品: **{v0}**\n\n得獎者: {v1}",
    },
    "giveaway.giveaway_ended_9e59c1": {
        "en": "{v0} giveaway ended",
        "zh": "{v0} 抽獎結束",
    },
    "giveaway.prize_not_enough_participants": {
        "en": "Prize: **{v0}**\n\nNot enough participants",
        "zh": "獎品: **{v0}**\n\n沒有足夠的參與者",
    },
    "giveaway.redraw_results": {"en": "{v0} redraw results", "zh": "{v0} 重新抽獎結果"},
    "giveaway.prize_new_winners": {
        "en": "Prize: **{v0}**\nNew winners: {v1}",
        "zh": "獎品: **{v0}**\n新得獎者: {v1}",
    },
    "giveaway.giveaway_has_ended": {
        "en": "{v0} giveaway has ended",
        "zh": "{v0} 抽獎已結束",
    },
    "giveaway.winners": {"en": "Winners", "zh": "得獎者"},
    "giveaway.id_ended": {"en": "ID: {v0} | Ended", "zh": "ID: {v0} | 已結束"},
    "giveaway.congratulations_on_winning_contact_to_claim": {
        "en": "Congratulations {v0} on winning **{v1}**! Contact <@{v2}> to claim the prize",
        "zh": "恭喜 {v0} 獲得 **{v1}**！請聯繫 <@{v2}> 領取獎品",
    },
    "giveaway.no_participants": {"en": "No participants", "zh": "無人參與"},
}
