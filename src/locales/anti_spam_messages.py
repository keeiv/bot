"""English and Traditional Chinese copy for anti_spam."""

MESSAGES: dict[str, dict[str, str]] = {
    "anti_spam.spam_protection": {
        "en": "Spam protection: {v0} — {v1}",
        "zh": "防炸群: {v0} — {v1}",
    },
    "anti_spam.enabled": {"en": "Enabled", "zh": "已啟用"},
    "anti_spam.disabled": {"en": "Disabled", "zh": "已禁用"},
    "anti_spam.enable": {"en": "Enable", "zh": "啟用"},
    "anti_spam.disable": {"en": "Disable", "zh": "禁用"},
    "anti_spam.added": {"en": "Added", "zh": "新增"},
    "anti_spam.removed": {"en": "Removed", "zh": "移除"},
    "anti_spam.active": {"en": "Active", "zh": "啟動中"},
    "anti_spam.normal": {"en": "Normal", "zh": "正常"},
    "anti_spam.on": {"en": "On", "zh": "開"},
    "anti_spam.off": {"en": "Off", "zh": "關"},
    "anti_spam.yes": {"en": "Yes", "zh": "是"},
    "anti_spam.no": {"en": "No", "zh": "否"},
    "anti_spam.unsupported_member_or_channel": {
        "en": "Unsupported member or channel",
        "zh": "不支援的成員或頻道",
    },
    "anti_spam.settings_spam_protection": {
        "en": "[Settings] Spam protection: {v0}",
        "zh": "[設定] 防炸群 {v0}",
    },
    "anti_spam.settings_flood_detection_updated": {
        "en": "[Settings] Flood detection updated",
        "zh": "[設定] 洪水偵測已更新",
    },
    "anti_spam.message_limit": {"en": "Message limit", "zh": "訊息上限"},
    "anti_spam.messages": {"en": "{v0} messages", "zh": "{v0} 條"},
    "anti_spam.time_window": {"en": "Time window", "zh": "時間視窗"},
    "anti_spam.action": {"en": "Action", "zh": "動作"},
    "anti_spam.settings_duplicate_detection": {
        "en": "[Settings] Duplicate detection: {v0}",
        "zh": "[設定] 重複偵測 — {v0}",
    },
    "anti_spam.trigger_count": {"en": "Trigger count", "zh": "觸發次數"},
    "anti_spam.times": {"en": "{v0} times", "zh": "{v0} 次"},
    "anti_spam.settings_mention_detection": {
        "en": "[Settings] Mention detection: {v0}",
        "zh": "[設定] 提及偵測 — {v0}",
    },
    "anti_spam.mention_limit": {"en": "Mention limit", "zh": "提及上限"},
    "anti_spam.items": {"en": "{v0} items", "zh": "{v0} 個"},
    "anti_spam.settings_link_detection": {
        "en": "[Settings] Link detection: {v0}",
        "zh": "[設定] 連結偵測 — {v0}",
    },
    "anti_spam.link_limit": {"en": "Link limit", "zh": "連結上限"},
    "anti_spam.automatically_delete_invites": {
        "en": "Automatically delete invites",
        "zh": "自動刪除邀請",
    },
    "anti_spam.settings_raid_detection": {
        "en": "[Settings] Raid detection: {v0}",
        "zh": "[設定] 突襲偵測 — {v0}",
    },
    "anti_spam.join_threshold": {"en": "Join threshold", "zh": "觸發人數"},
    "anti_spam.members": {"en": "{v0} members", "zh": "{v0} 人"},
    "anti_spam.settings_automatic_escalation": {
        "en": "[Settings] Automatic escalation: {v0}",
        "zh": "[設定] 自動升級 — {v0}",
    },
    "anti_spam.escalation_threshold": {"en": "Escalation threshold", "zh": "升級門檻"},
    "anti_spam.violations": {"en": "{v0} violations", "zh": "{v0} 次違規"},
    "anti_spam.tracking_window": {"en": "Tracking window", "zh": "記錄視窗"},
    "anti_spam.how_it_works": {"en": "How it works", "zh": "機制說明"},
    "anti_spam.reaching_the_violation_threshold_within_the": {
        "en": "Reaching the violation threshold within the window escalates the action by one level\n(warn → delete → mute → kick → ban)",
        "zh": "用戶在視窗內累積違規達門檻後，懲罰自動升一級\n(警告→刪除→禁言→踢出→封禁)",
    },
    "anti_spam.role_allowlist": {
        "en": "Role allowlist {v0}: {v1}",
        "zh": "{v0}角色白名單: {v1}",
    },
    "anti_spam.channel_allowlist": {
        "en": "Channel allowlist {v0}: {v1}",
        "zh": "{v0}頻道白名單: {v1}",
    },
    "anti_spam.settings_allowlist_updated": {
        "en": "[Settings] Allowlist updated",
        "zh": "[設定] 白名單已更新",
    },
    "anti_spam.success_lockdown_lifted": {
        "en": "[Success] Lockdown lifted",
        "zh": "[成功] 封鎖模式已解除",
    },
    "anti_spam.channel_sending_permissions_have_been_restored": {
        "en": "Channel sending permissions have been restored",
        "zh": "所有頻道的發言權限已恢復",
    },
    "anti_spam.status_spam_protection": {
        "en": "[Status] Spam protection",
        "zh": "[狀態] 防炸群系統",
    },
    "anti_spam.system_lockdown": {
        "en": "System: **{v0}** | Lockdown: **{v1}**",
        "zh": "系統狀態: **{v0}** | 封鎖模式: **{v1}**",
    },
    "anti_spam.message_flood": {"en": "Message flood", "zh": "訊息洪水"},
    "anti_spam.messages_s": {
        "en": "{v0} messages / {v1}s → {v2}",
        "zh": "{v0} 條 / {v1}s → {v2}",
    },
    "anti_spam.duplicate_content": {
        "en": "Duplicate content [{v0}]",
        "zh": "重複內容 [{v0}]",
    },
    "anti_spam.times_s": {
        "en": "{v0} times / {v1}s → {v2}",
        "zh": "{v0} 次 / {v1}s → {v2}",
    },
    "anti_spam.mention_spam": {"en": "Mention spam [{v0}]", "zh": "提及轟炸 [{v0}]"},
    "anti_spam.per_message": {
        "en": "{v0} per message → {v1}",
        "zh": "{v0} 個/條 → {v1}",
    },
    "anti_spam.link_spam": {"en": "Link spam [{v0}]", "zh": "連結轟炸 [{v0}]"},
    "anti_spam.links_s_delete_invites": {
        "en": "{v0} links / {v1}s → {v2}\nDelete invites: {v3}",
        "zh": "{v0} 個 / {v1}s → {v2}\n自動刪除邀請: {v3}",
    },
    "anti_spam.emoji_spam": {"en": "Emoji spam [{v0}]", "zh": "表情轟炸 [{v0}]"},
    "anti_spam.line_break_spam": {
        "en": "Line-break spam [{v0}]",
        "zh": "換行轟炸 [{v0}]",
    },
    "anti_spam.lines_per_message": {
        "en": "{v0} lines per message → {v1}",
        "zh": "{v0} 行/條 → {v1}",
    },
    "anti_spam.raid_detection": {
        "en": "Raid detection [{v0}]",
        "zh": "突襲偵測 [{v0}]",
    },
    "anti_spam.members_s": {
        "en": "{v0} members / {v1}s → {v2}",
        "zh": "{v0} 人 / {v1}s → {v2}",
    },
    "anti_spam.automatic_escalation": {
        "en": "Automatic escalation [{v0}]",
        "zh": "自動升級 [{v0}]",
    },
    "anti_spam.times_s_271f02": {"en": "{v0} times / {v1}s", "zh": "{v0} 次 / {v1}s"},
    "anti_spam.roles_channels": {
        "en": "Roles: {v0}\nChannels: {v1}",
        "zh": "角色: {v0}\n頻道: {v1}",
    },
    "anti_spam.mute_duration_s_message_deletion_on": {
        "en": "Mute duration: {v0}s | Message deletion on ban: {v1}d",
        "zh": "禁言時長: {v0}s | 封禁刪除天數: {v1}d",
    },
    "anti_spam.settings_mute_duration_updated": {
        "en": "[Settings] Mute duration updated",
        "zh": "[設定] 禁言時長已更新",
    },
    "anti_spam.mute_duration_seconds_h_m": {
        "en": "Mute duration: **{v0}** seconds ({v1}h {v2}m)",
        "zh": "禁言時長: **{v0}** 秒 ({v1}h {v2}m)",
    },
    "anti_spam.message_limit_7e55ac": {"en": "Message limit", "zh": "訊息限制"},
    "anti_spam.info_spam_protection_status": {
        "en": "[Info] Spam protection status",
        "zh": "[查詢] 防炸群狀態",
    },
    "anti_spam.use_anti_spam_status_to_view": {
        "en": "Use `/anti_spam status` to view all settings",
        "zh": "使用 `/anti_spam status` 查看完整設定",
    },
    "anti_spam.messages_s_0c1e04": {
        "en": "{v0} messages / {v1}s",
        "zh": "{v0} 條 / {v1}s",
    },
    "anti_spam.bot_lacks_permission": {
        "en": "Bot lacks permission",
        "zh": "Bot 缺少權限",
    },
    "anti_spam.other_trigger": {"en": "Other trigger", "zh": "其他觸發"},
    "anti_spam.warning_action_failed": {
        "en": "[Warning] Action failed",
        "zh": "[警告] 執行失敗",
    },
    "anti_spam.failed_invalid_action_available_actions": {
        "en": "[Failed] Invalid action. Available actions: {v0}",
        "zh": "[失敗] 無效動作，可選: {v0}",
    },
    "anti_spam.failed_action_must_be_add_or": {
        "en": "[Failed] action must be add or remove",
        "zh": "[失敗] action 必須為 add 或 remove",
    },
    "anti_spam.failed_specify_a_role_or_channel": {
        "en": "[Failed] Specify a role or channel",
        "zh": "[失敗] 請指定角色或頻道",
    },
    "anti_spam.info_no_changes": {"en": "[Info] No changes", "zh": "[提示] 無變更"},
    "anti_spam.info_lockdown_is_not_active": {
        "en": "[Info] Lockdown is not active",
        "zh": "[提示] 目前未處於封鎖模式",
    },
    "anti_spam.unknown_reason": {"en": "Unknown reason", "zh": "未知原因"},
    "anti_spam.spam_protection_lockdown_manually_lifted": {
        "en": "[Spam protection] Lockdown manually lifted",
        "zh": "[防炸群] 封鎖模式已手動解除",
    },
    "anti_spam.lifted_by": {"en": "Lifted by {v0}", "zh": "由 {v0} 解除"},
    "anti_spam.warning_spam_protection": {
        "en": "[Warning] Spam protection",
        "zh": "[警告] 防炸群系統",
    },
    "anti_spam.this_activity_triggered_detection_further_violations": {
        "en": "This activity triggered **{v0}** detection\nFurther violations may escalate the moderation action",
        "zh": "你的行為觸發了 **{v0}** 偵測\n請停止此行為，否則將自動升級懲罰",
    },
    "anti_spam.spam_protection_raid_lockdown_activated": {
        "en": "Spam protection: raid lockdown activated",
        "zh": "防炸群: 突襲封鎖模式啟動",
    },
    "anti_spam.spam_protection_lockdown_lifted": {
        "en": "Spam protection: lockdown lifted",
        "zh": "防炸群: 封鎖模式解除",
    },
}
