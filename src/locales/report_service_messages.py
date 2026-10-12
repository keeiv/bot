"""English and Traditional Chinese copy for report_service."""

MESSAGES: dict[str, dict[str, str]] = {
    "report_service.failed_the_moderator_must_be_a": {
        "en": "[Failed] The moderator must be a member of the same server",
        "zh": "[失敗] 操作者必須是同一伺服器的成員",
    },
    "report_service.failed_the_moderator_lacks_the_permission": {
        "en": "[Failed] The moderator lacks the permission required for this action",
        "zh": "[失敗] 操作者缺少此動作所需權限",
    },
    "report_service.failed_this_action_cannot_target_the": {
        "en": "[Failed] This action cannot target the server owner or the moderator",
        "zh": "[失敗] 無法對伺服器擁有者或自己執行此操作",
    },
    "report_service.failed_the_target_s_highest_role": {
        "en": "[Failed] The target's highest role is not below the moderator's",
        "zh": "[失敗] 目標身份組不低於操作者",
    },
    "report_service.failed_the_bot_lacks_the_required": {
        "en": "[Failed] The bot lacks the required permission or role position",
        "zh": "[失敗] 機器人權限或身份組層級不足",
    },
    "report_service.failed_mute_duration_must_be_greater": {
        "en": "[Failed] Mute duration must be greater than zero",
        "zh": "[失敗] 禁言時間不能為零",
    },
    "report_service.failed_mute_duration_must_not_exceed": {
        "en": "[Failed] Mute duration must not exceed 28 days",
        "zh": "[失敗] 禁言時間不能超過 28 天",
    },
    "report_service.muted_report_action_completed": {
        "en": "[Muted] Report action completed",
        "zh": "[禁言] 舉報處理完成",
    },
    "report_service.target_moderator_duration_reason": {
        "en": "**Target:** {v0} ({v1})\n**Moderator:** {v2}\n**Duration:** {v3}\n**Reason:** {v4}",
        "zh": "**被處理成員:** {v0} ({v1})\n**處理人:** {v2}\n**禁言時長:** {v3}\n**原因:** {v4}",
    },
    "report_service.banned_report_action_completed": {
        "en": "[Banned] Report action completed",
        "zh": "[封禁] 舉報處理完成",
    },
    "report_service.target_moderator_ban_type_delete_messages": {
        "en": "**Target:** {v0} ({v1})\n**Moderator:** {v2}\n**Ban type:** {v3}\n**Delete messages:** Past {v4} days\n**Reason:** {v5}",
        "zh": "**被處理成員:** {v0} ({v1})\n**處理人:** {v2}\n**封禁類型:** {v3}\n**刪除訊息:** {v4} 天內\n**原因:** {v5}",
    },
    "report_service.warning_member_warning": {
        "en": "[Warning] Member warning",
        "zh": "[警告] 你已被警告",
    },
    "report_service.server_warning_count_reason": {
        "en": "**Server:** {v0}\n**Warning count:** {v1}\n**Reason:** {v2}",
        "zh": "**伺服器:** {v0}\n**警告次數:** {v1} 次\n**原因:** {v2}",
    },
    "report_service.warned_report_action_completed": {
        "en": "[Warned] Report action completed",
        "zh": "[警告] 舉報處理完成",
    },
    "report_service.target_moderator_warnings_reason_dm_notification": {
        "en": "**Target:** {v0} ({v1})\n**Moderator:** {v2}\n**Warnings:** {v3}\n**Reason:** {v4}\n**DM notification:** {v5}",
        "zh": "**被處理成員:** {v0} ({v1})\n**處理人:** {v2}\n**警告次數:** {v3} 次\n**原因:** {v4}\n**私訊通知:** {v5}",
    },
    "report_service.failed_could_not_verify_current_member": {
        "en": "[Failed] Could not verify current member permissions",
        "zh": "[失敗] 無法確認目前成員權限",
    },
    "report_service.failed_the_bot_cannot_mute_this": {
        "en": "[Failed] The bot cannot mute this member",
        "zh": "[失敗] 機器人權限不足，無法禁言此成員",
    },
    "report_service.failed_mute_failed": {
        "en": "[Failed] Mute failed: {v0}",
        "zh": "[失敗] 禁言失敗: {v0}",
    },
    "report_service.failed_the_bot_cannot_ban_this": {
        "en": "[Failed] The bot cannot ban this member",
        "zh": "[失敗] 機器人權限不足，無法封禁此成員",
    },
    "report_service.failed_ban_failed": {
        "en": "[Failed] Ban failed: {v0}",
        "zh": "[失敗] 封禁失敗: {v0}",
    },
    "report_service.temporary_ban_duration": {
        "en": "Temporary ban duration",
        "zh": "暫時封禁時長",
    },
    "report_service.seconds_hours": {
        "en": "{v0} seconds ({v1:.1f} hours)",
        "zh": "{v0} 秒 ({v1:.1f} 小時)",
    },
    "report_service.temporary_bans_require_manual_removal_or": {
        "en": "Temporary bans require manual removal or a separate scheduler",
        "zh": "注意: 暫時封禁需手動解除或使用排程",
    },
    "report_service.temporary_ban": {"en": "Temporary ban", "zh": "暫時封禁"},
    "report_service.permanent_ban": {"en": "Permanent ban", "zh": "永久封禁"},
    "report_service.delivered": {"en": "Delivered", "zh": "已送達"},
    "report_service.not_delivered_dms_may_be_disabled": {
        "en": "Not delivered (DMs may be disabled)",
        "zh": "無法送達 (對方可能關閉私訊)",
    },
}
