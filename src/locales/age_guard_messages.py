"""English and Traditional Chinese copy for age_guard."""

MESSAGES: dict[str, dict[str, str]] = {
    "age_guard.success_adult_role_saved": {
        "en": "[Success] Adult role saved",
        "zh": "[成功] 成人身份組已設定",
    },
    "age_guard.adult_role_this_role_is_removed": {
        "en": "Adult role: {v0}\nThis role is removed when an underage declaration is detected.",
        "zh": "成人身份組已設為 {v0}\n偵測到未成年宣告時將自動移除此身份組。",
    },
    "age_guard.success_penalty_role_saved": {
        "en": "[Success] Penalty role saved",
        "zh": "[成功] 懲罰身份組已設定",
    },
    "age_guard.penalty_role_this_role_is_added": {
        "en": "Penalty role: {v0}\nThis role is added when an underage declaration is detected.",
        "zh": "懲罰身份組已設為 {v0}\n偵測到未成年宣告時將自動附加此身份組。",
    },
    "age_guard.success_age_guard": {
        "en": "[Success] Age guard: {v0}",
        "zh": "[成功] 年齡守門員已{v0}",
    },
    "age_guard.server": {"en": "Server: {v0}", "zh": "伺服器: {v0}"},
    "age_guard.age_guard_underage_declaration_detected": {
        "en": "[Age guard] Underage declaration detected",
        "zh": "[年齡守門員] 偵測到未成年宣告",
    },
    "age_guard.member": {"en": "Member", "zh": "成員"},
    "age_guard.declared_age": {"en": "Declared age", "zh": "宣告年齡"},
    "age_guard.original_message": {"en": "Original message", "zh": "原始訊息"},
    "age_guard.actions_taken": {"en": "Actions taken", "zh": "已執行動作"},
    "age_guard.server_user_id": {
        "en": "Server: {v0} | User ID: {v1}",
        "zh": "伺服器: {v0} | 使用者 ID: {v1}",
    },
    "age_guard.removed_adult_role": {
        "en": "Removed adult role {v0}",
        "zh": "移除成人身份組 {v0}",
    },
    "age_guard.added_penalty_role": {
        "en": "Added penalty role {v0}",
        "zh": "附加懲罰身份組 {v0}",
    },
    "age_guard.age_guard_member_declared_age_underage": {
        "en": "Age guard: member declared age {v0} (underage)",
        "zh": "年齡守門員: 成員宣告 {v0} 歲 (未成年)",
    },
}
