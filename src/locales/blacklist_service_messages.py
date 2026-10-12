"""English and Traditional Chinese copy for blacklist_service."""

MESSAGES: dict[str, dict[str, str]] = {
    "blacklist_service.accepted_by_at": {
        "en": "Accepted by {v0} at {v1}",
        "zh": "由 {v0} 於 {v1} 接受",
    },
    "blacklist_service.rejected_by_at": {
        "en": "Rejected by {v0} at {v1}",
        "zh": "由 {v0} 於 {v1} 駁回",
    },
    "blacklist_service.no_reason_given": {"en": "No reason given", "zh": "未提供原因"},
    "blacklist_service.reason": {"en": " | Reason: {v0}", "zh": " | 原因: {v0}"},
    "blacklist_service.review_blacklist_appeal": {
        "en": "[Review] Blacklist appeal",
        "zh": "[審核] 黑名單申訴",
    },
    "blacklist_service.appellant": {"en": "Appellant", "zh": "申訴者"},
    "blacklist_service.blacklist_source": {
        "en": "Blacklist source",
        "zh": "黑名單來源",
    },
    "blacklist_service.block_reason": {"en": "Block reason", "zh": "封鎖原因"},
    "blacklist_service.block_mode": {"en": "Block mode", "zh": "封鎖模式"},
    "blacklist_service.accepted": {"en": "Accepted", "zh": "已接受"},
    "blacklist_service.the_appeal_was_accepted_the_local": {
        "en": "The appeal was **accepted**. The local blacklist entry has been removed.",
        "zh": "申訴已被 **接受**，本地黑名單紀錄已移除。",
    },
    "blacklist_service.the_appeal_was_accepted_the_cathome": {
        "en": "The appeal was **accepted**. The CatHome API block remains until its external administrator removes it.",
        "zh": "申訴已被 **接受**。CatHome API 的封鎖尚未解除，需由外部黑名單管理者處理。",
    },
    "blacklist_service.rejected": {"en": "Rejected", "zh": "已駁回"},
    "blacklist_service.notice_appeal_result": {
        "en": "[Notice] Appeal result",
        "zh": "[通知] 申訴結果",
    },
    "blacklist_service.the_appeal_was_rejected": {
        "en": "The appeal was **rejected**.",
        "zh": "您的申訴已被 **駁回**。",
    },
}
