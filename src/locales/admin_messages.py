"""English and Traditional Chinese copy for admin."""

MESSAGES: dict[str, dict[str, str]] = {
    "admin.no_reason_given": {"en": "No reason given", "zh": "沒有提供原因"},
    "admin.success_deleted_messages": {
        "en": "[Success] Deleted {v0} messages",
        "zh": "[成功] 已清除 {v0} 則訊息",
    },
    "admin.warning_member_warning": {
        "en": "[Warning] Member warning",
        "zh": "[警告] 警告成員",
    },
    "admin.was_warned_for_the_following_reason": {
        "en": "{v0} was warned for the following reason:\n{v1}",
        "zh": "{v0} 已被警告，原因如下:\n{v1}",
    },
    "admin.failed_the_manage_messages_permission_is": {
        "en": "[Failed] The Manage Messages permission is required",
        "zh": "[失敗] 你需要「管理訊息」權限",
    },
    "admin.failed_the_count_must_be_between": {
        "en": "[Failed] The count must be between 1 and 100",
        "zh": "[失敗] 數量必須在 1-100 之間",
    },
    "admin.failed_the_kick_members_permission_is": {
        "en": "[Failed] The Kick Members permission is required",
        "zh": "[失敗] 你需要「踢出成員」權限",
    },
    "admin.failed_self_kicking_is_not_allowed": {
        "en": "[Failed] Self-kicking is not allowed",
        "zh": "[失敗] 你不能踢出自己",
    },
    "admin.failed_insufficient_permission_to_kick_this": {
        "en": "[Failed] Insufficient permission to kick this member",
        "zh": "[失敗] 你的權限不足以踢出此成員",
    },
    "admin.success_member_kicked": {
        "en": "[Success] Member kicked",
        "zh": "[成功] 成員已被踢出",
    },
    "admin.member_reason": {
        "en": "Member: {v0}\nReason: {v1}",
        "zh": "成員: {v0}\n原因: {v1}",
    },
    "admin.failed_the_ban_members_permission_is": {
        "en": "[Failed] The Ban Members permission is required",
        "zh": "[失敗] 你需要「封禁成員」權限",
    },
    "admin.failed_self_banning_is_not_allowed": {
        "en": "[Failed] Self-banning is not allowed",
        "zh": "[失敗] 你不能封禁自己",
    },
    "admin.failed_insufficient_permission_to_ban_this": {
        "en": "[Failed] Insufficient permission to ban this member",
        "zh": "[失敗] 你的權限不足以封禁此成員",
    },
    "admin.success_member_banned": {
        "en": "[Success] Member banned",
        "zh": "[成功] 成員已被封禁",
    },
    "admin.failed_the_moderate_members_permission_is": {
        "en": "[Failed] The Moderate Members permission is required",
        "zh": "[失敗] 你需要有管理成員的權限",
    },
    "admin.failed_self_muting_is_not_allowed": {
        "en": "[Failed] Self-muting is not allowed",
        "zh": "[失敗] 你不能禁言自己",
    },
    "admin.failed_insufficient_permission_to_mute_this": {
        "en": "[Failed] Insufficient permission to mute this member",
        "zh": "[失敗] 你的權限不足以禁言此成員",
    },
    "admin.success_member_muted": {
        "en": "[Success] Member muted",
        "zh": "[成功] 成員已被禁言",
    },
    "admin.member_duration_minutes_reason": {
        "en": "Member: {v0}\nDuration: {v1} minutes\nReason: {v2}",
        "zh": "成員: {v0}\n持續時間: {v1} 分鐘\n原因: {v2}",
    },
    "admin.success_warned": {"en": "[Success] Warned {v0}", "zh": "[成功] 已警告 {v0}"},
    "admin.denied_access_denied": {
        "en": "[Denied] Access denied",
        "zh": "[拒絕] 存取被拒",
    },
    "admin.bot_commands_are_unavailable_for_this": {
        "en": "Bot commands are unavailable for this account. Contact a server administrator.",
        "zh": "你已被禁止使用機器人指令，請聯繫管理員。",
    },
    "admin.failed_could_not_kick_member": {
        "en": "[Failed] Could not kick member: {v0}",
        "zh": "[失敗] 無法踢出成員: {v0}",
    },
    "admin.failed_could_not_ban_member": {
        "en": "[Failed] Could not ban member: {v0}",
        "zh": "[失敗] 無法封禁成員: {v0}",
    },
    "admin.failed_could_not_mute_member": {
        "en": "[Failed] Could not mute member: {v0}",
        "zh": "[失敗] 無法禁言成員: {v0}",
    },
    "admin.warning_member_warned_but_the_dm": {
        "en": "[Warning] Member warned, but the DM could not be sent: {v0}",
        "zh": "[警告] 成員已被警告，但無法發送私訊: {v0}",
    },
}
