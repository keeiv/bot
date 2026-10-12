"""English and Traditional Chinese copy for management."""

MESSAGES: dict[str, dict[str, str]] = {
    "management.welcome_to": {
        "en": "Welcome {user} to {server}!",
        "zh": "歡迎 {user} 來到 {server}！",
    },
    "management.success_welcome_messages_will_be_sent": {
        "en": "[Success] Welcome messages will be sent to {v0}",
        "zh": "[成功] 歡迎訊息將發送至 {v0}",
    },
    "management.the_keeiv_bot_repository_is_not": {
        "en": "The keeiv/bot repository is not being tracked",
        "zh": "keeiv/bot 倉庫目前未被追蹤",
    },
    "management.automatic_role": {
        "en": "\nAutomatic role: {v0}",
        "zh": "\n自動角色: {v0}",
    },
    "management.dm_notifications_enabled": {
        "en": "\nDM notifications enabled",
        "zh": "\n已啟用私訊通知",
    },
    "management.deleted_role": {
        "en": "Deleted role ({v0})",
        "zh": "已刪除的角色 ({v0})",
    },
    "management.success_tracking_updates_for_in": {
        "en": "[Success] Tracking updates for {v1} in {v0}",
        "zh": "[成功] 已開始在 {v0} 追蹤 {v1} 的更新",
    },
    "management.keeiv_bot_tracking_status": {
        "en": "keeiv/bot tracking status",
        "zh": "keeiv/bot 倉庫追蹤狀態",
    },
    "management.unknown_channel": {
        "en": "Unknown channel ({v0})",
        "zh": "未知頻道 ({v0})",
    },
    "management.basic": {"en": "Basic", "zh": "基本"},
    "management.welcome_to_there_are_now_members": {
        "en": "Welcome {user} to {server}! There are now {count} members!",
        "zh": "歡迎 {user} 來到 {server}！我們現在有 {count} 位成員！",
    },
    "management.friendly": {"en": "Friendly", "zh": "友善"},
    "management.hello_welcome_to_introductions_are_welcome": {
        "en": "Hello {user}! Welcome to {server}! Introductions are welcome.",
        "zh": "你好 {user}！歡迎來到 {server}！請隨意介紹你自己。",
    },
    "management.formal": {"en": "Formal", "zh": "正式"},
    "management.welcome_to_please_read_the_rules": {
        "en": "Welcome to {server}, {user}. Please read the rules before participating.",
        "zh": "{user} 您好，歡迎來到 {server}。請先閱讀規則，祝您在此愚快。",
    },
    "management.gaming": {"en": "Gaming", "zh": "遊戲"},
    "management.joined_the_game_welcome_to_ready": {
        "en": "{user} joined the game! Welcome to {server}! Ready to play?",
        "zh": "{user} 加入了遊戲！歡迎來到 {server}！準備好了嗎？",
    },
    "management.community": {"en": "Community", "zh": "社群"},
    "management.welcome_to_the_community_member_number": {
        "en": "Welcome {user} to the {server} community! Member number: {count}.",
        "zh": "歡迎 {user} 加入我們的社群 {server}！你是第 {count} 位成員！",
    },
    "management.welcome_messages_default_templates": {
        "en": "[Welcome messages] Default templates",
        "zh": "[歡迎訊息] 預設模板",
    },
    "management.available_variables": {
        "en": "Available variables: {user}, {server}, {count}, {created_at}",
        "zh": "可使用變數: {user}, {server}, {count}, {created_at}",
    },
    "management.success_automatic_role_saved": {
        "en": "[Success] Automatic role saved",
        "zh": "[成功] 自動角色已設定",
    },
    "management.role_will_be_assigned_to_new": {
        "en": "Role {v0} will be assigned to new members",
        "zh": "角色 {v0} 將自動分配給新成員",
    },
    "management.delay": {"en": "[Delay]", "zh": "[延遲]"},
    "management.minimum_members": {"en": "[Minimum members]", "zh": "[最少成員數]"},
    "management.verification_required": {
        "en": "[Verification required]",
        "zh": "[需要驗證]",
    },
    "management.automatic_roles_rules": {
        "en": "[Automatic roles] Rules",
        "zh": "[自動角色] 規則列表",
    },
    "management.assigned_immediately": {"en": "Assigned immediately", "zh": "立即分配"},
    "management.success_removed_automatic_role_rule": {
        "en": "[Success] Removed automatic role rule: {v0}",
        "zh": "[成功] 已移除自動角色規則: {v0}",
    },
    "management.failed_the_manage_channels_permission_is": {
        "en": "[Failed] The Manage Channels permission is required",
        "zh": "[失敗] 你需要「管理頻道」權限",
    },
    "management.success_stopped_tracking": {
        "en": "[Success] Stopped tracking {v0}",
        "zh": "[成功] 已停止追蹤 {v0}",
    },
    "management.info_is_not_being_tracked": {
        "en": "[Info] {v0} is not being tracked",
        "zh": "[提示] {v0} 目前未被追蹤",
    },
    "management.info_no_repositories_are_being_tracked": {
        "en": "[Info] No repositories are being tracked",
        "zh": "[提示] 目前沒有追蹤任何倉庫",
    },
    "management.channel_last_commit_last_pr": {
        "en": "Channel: {v0}\nLast commit: {v1}\nLast PR: {v2}",
        "zh": "頻道: {v0}\n最後 Commit: {v1}\n最後 PR: {v2}",
    },
    "management.failed_the_manage_roles_permission_is": {
        "en": "[Failed] The Manage Roles permission is required",
        "zh": "[失敗] 你需要「管理身份組」權限",
    },
    "management.failed_the_everyone_role_cannot_be": {
        "en": "[Failed] The @everyone role cannot be changed",
        "zh": "[失敗] 無法操作 @everyone 身份組",
    },
    "management.failed_roles_managed_by_bots_or": {
        "en": "[Failed] Roles managed by bots or integrations cannot be changed",
        "zh": "[失敗] 無法操作由機器人/整合管理的身份組",
    },
    "management.failed_roles_at_or_above_the": {
        "en": "[Failed] Roles at or above the highest assigned role cannot be assigned",
        "zh": "[失敗] 你無法分配高於或等於你最高身份組的角色",
    },
    "management.success_assigned_to": {
        "en": "[Success] Assigned {v0} to {v1}",
        "zh": "[成功] 已將 {v0} 分配給 {v1}",
    },
    "management.failed_roles_at_or_above_the_5af74a": {
        "en": "[Failed] Roles at or above the highest assigned role cannot be removed",
        "zh": "[失敗] 你無法移除高於或等於你最高身份組的角色",
    },
    "management.success_removed_from": {
        "en": "[Success] Removed {v1} from {v0}",
        "zh": "[成功] 已從 {v0} 移除 {v1}",
    },
    "management.emoji_full_size_image": {
        "en": "[Emoji] Full-size image",
        "zh": "[表情符號] 大圖",
    },
    "management.failed_the_manage_expressions_permission_is": {
        "en": "[Failed] The Manage Expressions permission is required",
        "zh": "[失敗] 你需要「管理表情符號」權限",
    },
    "management.failed_upload_an_image_file": {
        "en": "[Failed] Upload an image file",
        "zh": "[失敗] 請上傳圖片檔案",
    },
    "management.success_emoji_uploaded": {
        "en": "[Success] Emoji uploaded: {v0}",
        "zh": "[成功] 已上傳表情符號: {v0}",
    },
    "management.failed_welcome_messages_are_not_configured": {
        "en": "[Failed] Welcome messages are not configured",
        "zh": "[失敗] 尚未設定歡迎訊息",
    },
    "management.member_number": {"en": "Member number {v0}", "zh": "第 {v0} 位成員"},
    "management.preview": {"en": "[Preview] {v0}", "zh": "[預覽] {v0}"},
    "management.success_welcome_messages_disabled": {
        "en": "[Success] Welcome messages disabled",
        "zh": "[成功] 已停用歡迎訊息",
    },
    "management.failed_welcome_messages_are_not_enabled": {
        "en": "[Failed] Welcome messages are not enabled",
        "zh": "[失敗] 歡迎訊息尚未啟用",
    },
    "management.failed_the_everyone_role_cannot_be_9e2c5a": {
        "en": "[Failed] The @everyone role cannot be used as an automatic role",
        "zh": "[失敗] 無法將 @everyone 設為自動角色",
    },
    "management.failed_managed_roles_cannot_be_used": {
        "en": "[Failed] Managed roles cannot be used as automatic roles",
        "zh": "[失敗] 無法設定由機器人/整合管理的身份組為自動角色",
    },
    "management.failed_roles_at_or_above_the_7790b2": {
        "en": "[Failed] Roles at or above the highest assigned role cannot be configured",
        "zh": "[失敗] 你無法設定高於或等於你最高身份組的角色",
    },
    "management.failed_no_automatic_role_rules_are": {
        "en": "[Failed] No automatic role rules are configured",
        "zh": "[失敗] 尚未設定自動角色規則",
    },
    "management.delay_seconds": {"en": "Delay: {v0} seconds", "zh": "延遲: {v0} 秒"},
    "management.minimum_members_1e794c": {
        "en": "Minimum members: {v0}",
        "zh": "最少成員: {v0}",
    },
    "management.verification_required_686d9b": {
        "en": "Verification required",
        "zh": "需要驗證",
    },
    "management.rule": {"en": "Rule {v0}: {v1}", "zh": "規則 {v0}: {v1}"},
    "management.failed_invalid_rule_number": {
        "en": "[Failed] Invalid rule number",
        "zh": "[失敗] 無效的規則編號",
    },
    "management.failed_the_bot_cannot_assign_this": {
        "en": "[Failed] The bot cannot assign this role",
        "zh": "[失敗] 機器人沒有權限分配該身份組",
    },
    "management.failed_the_bot_cannot_remove_this": {
        "en": "[Failed] The bot cannot remove this role",
        "zh": "[失敗] 機器人沒有權限移除該身份組",
    },
    "management.failed_could_not_retrieve_emoji": {
        "en": "[Failed] Could not retrieve emoji: {v0}",
        "zh": "[失敗] 取得表情符號失敗: {v0}",
    },
    "management.uploaded_by": {"en": "Uploaded by {v0}", "zh": "由 {v0} 上傳"},
    "management.failed_the_bot_cannot_upload_emoji": {
        "en": "[Failed] The bot cannot upload emoji",
        "zh": "[失敗] 機器人沒有權限上傳表情符號",
    },
    "management.failed_could_not_upload_emoji": {
        "en": "[Failed] Could not upload emoji: {v0}",
        "zh": "[失敗] 上傳表情符號失敗: {v0}",
    },
    "management.failed_invalid_emoji_format": {
        "en": "[Failed] Invalid emoji format",
        "zh": "[失敗] 無效的表情符號格式",
    },
    "management.failed_a_custom_emoji_is_required": {
        "en": "[Failed] A custom emoji is required",
        "zh": "[失敗] 請使用自訂表情符號",
    },
    "management.failed_invalid_color_use_a_hexadecimal": {
        "en": "[Failed] Invalid color. Use a hexadecimal value such as #FF5733",
        "zh": "[失敗] 無效的顏色格式，請使用十六進位格式，例如 #FF5733",
    },
    "management.none_yet": {"en": "None yet", "zh": "尚無"},
    "management.automatic_role_assignment": {
        "en": "Automatic role assignment",
        "zh": "自動角色分配",
    },
    "management.date": {"en": "[Date]", "zh": "[日期]"},
    "management.pr_number": {"en": "[PR number]", "zh": "[PR 編號]"},
    "management.status": {"en": "[Status]", "zh": "[狀態]"},
    "management.automatic_welcome_role": {
        "en": "Automatic welcome role",
        "zh": "歡迎自動分配",
    },
}
