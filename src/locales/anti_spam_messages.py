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
    # --- 跨頻道、附件、惡意連結、新帳號、防破壞 ---
    "anti_spam.detect_similar": {"en": "Cross-channel spam", "zh": "跨頻道洗版"},
    "anti_spam.detect_coordinated": {"en": "Multi-account spam", "zh": "多帳號洗版"},
    "anti_spam.detect_attachment": {"en": "Attachment spam", "zh": "附件轟炸"},
    "anti_spam.detect_phishing": {"en": "Malicious link", "zh": "惡意連結"},
    "anti_spam.detect_new_account": {"en": "New account", "zh": "新帳號"},
    "anti_spam.detect_nuke": {"en": "Anti-nuke", "zh": "防破壞"},
    "anti_spam.similar_detail": {
        "en": "Alike messages in {v1} channels within {v0}s",
        "zh": "{v0} 秒內在 {v1} 個頻道發送相似內容",
    },
    "anti_spam.coordinated_detail": {
        "en": "{v1} accounts posted alike messages within {v0}s",
        "zh": "{v0} 秒內有 {v1} 個帳號發送相似內容",
    },
    "anti_spam.coordinated_more": {
        "en": "Joined a multi-account spam wave already caught",
        "zh": "加入已確認的多帳號洗版",
    },
    "anti_spam.attachment_detail": {
        "en": "{v1} attachments or stickers within {v0}s",
        "zh": "{v0} 秒內 {v1} 個附件或貼圖",
    },
    "anti_spam.phishing_blocked": {
        "en": "Link to a blocked domain: {v0}",
        "zh": "連到封鎖清單上的網域：{v0}",
    },
    "anti_spam.phishing_lookalike": {
        "en": "Domain imitating {v1}: {v0}",
        "zh": "仿冒 {v1} 的網域：{v0}",
    },
    "anti_spam.phishing_masked": {
        "en": "Link shows {v0} but goes to {v1}",
        "zh": "連結顯示 {v0}，實際前往 {v1}",
    },
    "anti_spam.phishing_lure": {
        "en": "Free Nitro / Steam gift bait with a link to {v0}",
        "zh": "免費 Nitro／Steam 禮物誘餌，附連結 {v0}",
    },
    "anti_spam.new_account_detail": {
        "en": "Account is {v0} hours old (limit {v1} hours)",
        "zh": "帳號建立 {v0} 小時（門檻 {v1} 小時）",
    },
    "anti_spam.new_account_dm": {
        "en": "{v0} does not accept accounts younger than {v1} hours yet. Please try again later.",
        "zh": "{v0} 暫時不接受建立未滿 {v1} 小時的帳號加入，請晚點再試。",
    },
    "anti_spam.young_during_raid": {
        "en": "New account joined during a raid",
        "zh": "突襲期間加入的新帳號",
    },
    "anti_spam.raid_handled": {"en": "Raid accounts", "zh": "這一波的帳號"},
    "anti_spam.raid_handled_value": {
        "en": "{v0} of {v1} new accounts → {v2}",
        "zh": "{v1} 個新帳號中 {v0} 個 → {v2}",
    },
    "anti_spam.auto_lift": {"en": "Lifts by itself", "zh": "自動解除"},
    "anti_spam.after_minutes": {"en": "after {v0} minutes", "zh": "{v0} 分鐘後"},
    "anti_spam.by_hand": {"en": "By hand only", "zh": "只能手動"},
    "anti_spam.young_accounts": {"en": "New accounts", "zh": "新帳號"},
    "anti_spam.younger_than_days": {
        "en": "younger than {v0} days",
        "zh": "未滿 {v0} 天",
    },
    "anti_spam.younger_than_hours": {
        "en": "younger than {v0} hours",
        "zh": "未滿 {v0} 小時",
    },
    "anti_spam.success_raid_mode_ended": {
        "en": "[Success] Raid mode ended",
        "zh": "[成功] 突襲模式已結束",
    },
    "anti_spam.lockdown_auto_lifted": {
        "en": "[Spam protection] Lockdown lifted by itself",
        "zh": "[防炸群] 封鎖模式已自動解除",
    },
    "anti_spam.join_report_title": {
        "en": "[Spam protection] {v0} joins handled",
        "zh": "[防炸群] 處置了 {v0} 位加入者",
    },
    "anti_spam.join_report_line": {
        "en": "{v0} ({v1}) — {v2} → {v3} {v4}",
        "zh": "{v0}（{v1}）— {v2} → {v3} {v4}",
    },
    "anti_spam.done": {"en": "[Done]", "zh": "[成功]"},
    "anti_spam.not_done": {"en": "[Failed]", "zh": "[失敗]"},
    "anti_spam.and_more": {"en": "…and {v0} more", "zh": "…另有 {v0} 筆"},
    "anti_spam.also_handled": {"en": "Also handled", "zh": "一併處置"},
    "anti_spam.accounts": {"en": "{v0} accounts", "zh": "{v0} 個帳號"},
    "anti_spam.settings_similar_detection": {
        "en": "[Settings] Similar message detection: {v0}",
        "zh": "[設定] 相似內容偵測 — {v0}",
    },
    "anti_spam.channels_threshold": {
        "en": "Channels (one member)",
        "zh": "頻道數（同一人）",
    },
    "anti_spam.accounts_threshold": {"en": "Accounts", "zh": "帳號數"},
    "anti_spam.settings_attachment_detection": {
        "en": "[Settings] Attachment detection: {v0}",
        "zh": "[設定] 附件偵測 — {v0}",
    },
    "anti_spam.attachment_limit": {"en": "Attachment limit", "zh": "附件上限"},
    "anti_spam.settings_phishing_detection": {
        "en": "[Settings] Malicious link detection: {v0}",
        "zh": "[設定] 惡意連結偵測 — {v0}",
    },
    "anti_spam.failed_domain_usage": {
        "en": "[Failed] kind must be allow or block, and action add or remove",
        "zh": "[失敗] kind 必須為 allow 或 block，action 必須為 add 或 remove",
    },
    "anti_spam.failed_invalid_domain": {
        "en": "[Failed] That is not a domain, like example.com",
        "zh": "[失敗] 這不是網域，請輸入像 example.com 的格式",
    },
    "anti_spam.settings_domain_list_updated": {
        "en": "[Settings] Domain list updated",
        "zh": "[設定] 網域清單已更新",
    },
    "anti_spam.allowed_domains": {"en": "Trusted domains", "zh": "信任網域"},
    "anti_spam.blocked_domains": {"en": "Blocked domains", "zh": "封鎖網域"},
    "anti_spam.settings_new_account_updated": {
        "en": "[Settings] New account rule updated",
        "zh": "[設定] 新帳號門檻已更新",
    },
    "anti_spam.failed_owner_only": {
        "en": "[Failed] Only the server owner can change anti-nuke",
        "zh": "[失敗] 只有伺服器擁有者可以變更防破壞設定",
    },
    "anti_spam.settings_nuke": {
        "en": "[Settings] Anti-nuke: {v0}",
        "zh": "[設定] 防破壞 — {v0}",
    },
    "anti_spam.nuke_threshold": {"en": "Dangerous actions", "zh": "危險操作次數"},
    "anti_spam.settings_nuke_trust_updated": {
        "en": "[Settings] Anti-nuke trust list updated",
        "zh": "[設定] 防破壞信任名單已更新",
    },
    "anti_spam.nuke_trusted": {"en": "Trusted", "zh": "信任名單"},
    "anti_spam.info_nothing_to_restore": {
        "en": "[Info] Anti-nuke took no roles from this member",
        "zh": "[提示] 防破壞沒有拔過這位成員的身分組",
    },
    "anti_spam.nuke_restore_reason": {
        "en": "Anti-nuke: roles given back by the owner",
        "zh": "防破壞：擁有者還原身分組",
    },
    "anti_spam.success_roles_restored": {
        "en": "[Success] Gave {v0} back {v1} roles ({v2} no longer exist or are above BOT.)",
        "zh": "[成功] 已還原 {v0} 的 {v1} 個身分組（{v2} 個已不存在或高於 BOT.）",
    },
    "anti_spam.nuke_strip": {"en": "Take their roles", "zh": "拔除身分組"},
    "anti_spam.nuke_kind_channel_delete": {"en": "channel deleted", "zh": "刪除頻道"},
    "anti_spam.nuke_kind_channel_create": {"en": "channel created", "zh": "建立頻道"},
    "anti_spam.nuke_kind_role_delete": {"en": "role deleted", "zh": "刪除身分組"},
    "anti_spam.nuke_kind_ban": {"en": "ban", "zh": "封禁"},
    "anti_spam.nuke_kind_kick": {"en": "kick", "zh": "踢出"},
    "anti_spam.nuke_kind_prune": {"en": "prune", "zh": "清除成員"},
    "anti_spam.nuke_kind_webhook_create": {
        "en": "webhook created",
        "zh": "建立 Webhook",
    },
    "anti_spam.nuke_detail": {
        "en": "{v1} dangerous actions within {v0}s: {v2}",
        "zh": "{v0} 秒內 {v1} 次危險操作：{v2}",
    },
    "anti_spam.nuke_alert_title": {
        "en": "[Anti-nuke] Mass destruction stopped",
        "zh": "[防破壞] 偵測到大量破壞",
    },
    "anti_spam.nuke_actor": {"en": "Done by", "zh": "操作者"},
    "anti_spam.nuke_reason": {
        "en": "Anti-nuke: too many dangerous actions",
        "zh": "防破壞：短時間內過多危險操作",
    },
    "anti_spam.nuke_member_gone": {
        "en": "[Failed] They are no longer in the server",
        "zh": "[失敗] 對方已不在伺服器中",
    },
    "anti_spam.nuke_role_too_high": {
        "en": "[Failed] Their role is not below BOT.'s: move BOT.'s role higher",
        "zh": "[失敗] 對方的身分組不低於 BOT.，請把 BOT. 的身分組往上移",
    },
    "anti_spam.nuke_stripped": {
        "en": "Took {v0} roles",
        "zh": "已拔除 {v0} 個身分組",
    },
    "anti_spam.nuke_stripped_and_kicked": {
        "en": "Took {v0} roles; still had dangerous permissions (e.g. a bot's own role), so kicked",
        "zh": "已拔除 {v0} 個身分組；仍留有危險權限（例如機器人自己的身分組），已踢出",
    },
    "anti_spam.nuke_next_steps": {
        "en": "Check the audit log. If it was a mistake, give the roles back with /anti_spam nuke_restore; trusted members and bots go in /anti_spam nuke_trust.",
        "zh": "請檢查稽核日誌。若是誤判，用 /anti_spam nuke_restore 還原身分組；可信任的成員或機器人可加入 /anti_spam nuke_trust。",
    },
    "anti_spam.similar_status": {
        "en": "Similar messages ({v0})",
        "zh": "相似內容 ({v0})",
    },
    "anti_spam.similar_status_value": {
        "en": "{v0} channels or {v1} accounts / {v2}s → {v3}",
        "zh": "{v0} 個頻道或 {v1} 個帳號 / {v2}s → {v3}",
    },
    "anti_spam.attachment_status": {
        "en": "Attachments ({v0})",
        "zh": "附件轟炸 ({v0})",
    },
    "anti_spam.phishing_status": {
        "en": "Malicious links ({v0})",
        "zh": "惡意連結 ({v0})",
    },
    "anti_spam.phishing_status_value": {
        "en": "Delete + {v0}; {v1} trusted, {v2} blocked domains",
        "zh": "刪除 + {v0}；信任 {v1}、封鎖 {v2} 個網域",
    },
    "anti_spam.young_status_value": {
        "en": "On join: {v0} → {v1}\nDuring a raid: younger than {v2} days\nLockdown lifts: {v3}",
        "zh": "加入時：{v0} → {v1}\n突襲期間：未滿 {v2} 天\n封鎖解除：{v3}",
    },
    "anti_spam.nuke_status": {"en": "Anti-nuke ({v0})", "zh": "防破壞 ({v0})"},
    "anti_spam.nuke_status_value": {
        "en": "{v0} actions / {v1}s → {v2}; {v3} trusted",
        "zh": "{v0} 次 / {v1}s → {v2}；信任 {v3} 位",
    },
}
