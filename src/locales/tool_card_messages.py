"""English and Traditional Chinese copy for tool_card."""

MESSAGES: dict[str, dict[str, str]] = {
    "tool_card.usage_allowance": {"en": "Usage allowance", "zh": "使用額度"},
    "tool_card.tenure_days_vouchers_reserved_pt": {
        "en": "Tenure: {v0} days  ·  Vouchers: {v1}  ·  Reserved: {v2} PT",
        "zh": "使用年資 {v0} 天  ·  重置券 {v1} 張  ·  預留 {v2} 點",
    },
    "tool_card.available_pt": {"en": "Available: {v0:,} PT", "zh": "可用 {v0:,} 點"},
    "tool_card.assigned_tier_no_payment_required_points": {
        "en": "Assigned tier · No payment required · Points track tool usage",
        "zh": "固定授權等級 · 無需付費 · 點數僅用於用量管理",
    },
    "tool_card.tiers_grow_with_tenure_no_payment": {
        "en": "Tiers grow with tenure · No payment required · Points track tool usage",
        "zh": "依使用天數自動升級 · 無需付費 · 點數僅用於用量管理",
    },
    "tool_card.weekly_usage": {"en": "Weekly usage", "zh": "本週用量"},
    "tool_card.last_three_hours": {"en": "Last three hours", "zh": "近三小時用量"},
}
