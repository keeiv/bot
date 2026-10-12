"""English and Traditional Chinese copy for temp_voice."""

MESSAGES: dict[str, dict[str, str]] = {
    "temp_voice.s_room": {"en": "{username}'s room", "zh": "{username}的家"},
    "temp_voice.no_category_root": {
        "en": "No category (root)",
        "zh": "無類別（根目錄）",
    },
    "temp_voice.success_temporary_voice_channels_configured": {
        "en": "[Success] Temporary voice channels configured",
        "zh": "[成功] 暫時語音頻道系統已設定",
    },
    "temp_voice.trigger_channel": {"en": "Trigger channel", "zh": "觸發頻道"},
    "temp_voice.channel_category": {"en": "Channel category", "zh": "建立類別"},
    "temp_voice.name_template": {"en": "Name template", "zh": "名稱範本"},
    "temp_voice.example": {
        "en": "`{v0}`\nExample: `{v1}`",
        "zh": "`{v0}`\n範例：`{v1}`",
    },
    "temp_voice.user_command_prefix": {
        "en": "User command prefix",
        "zh": "用戶指令前綴",
    },
    "temp_voice.use_help_for_instructions": {
        "en": "`{v0}` — Use `{v1}help` for instructions",
        "zh": "`{v0}` — 輸入 `{v1}help` 查看完整說明",
    },
    "temp_voice.configured_by_server": {
        "en": "Configured by {v0} | Server: {v1}",
        "zh": "由 {v0} 設定 | 伺服器：{v1}",
    },
    "temp_voice.info_temporary_voice_channel_status": {
        "en": "[Info] Temporary voice channel status",
        "zh": "[資訊] 暫時語音頻道系統狀態",
    },
    "temp_voice.value": {"en": "`{v0}`", "zh": "`{v0}`"},
    "temp_voice.active_temporary_channels": {
        "en": "Active temporary channels",
        "zh": "目前活躍暫時頻道數",
    },
    "temp_voice.server": {"en": "Server: {v0}", "zh": "伺服器：{v0}"},
    "temp_voice.success_temporary_voice_channels_disabled_in": {
        "en": "[Success] Temporary voice channels disabled in this server\n(Existing channels remain until they empty, then are deleted automatically)",
        "zh": "[成功] 已停用此伺服器的暫時語音頻道系統\n（現有暫時頻道不受影響，將在清空後自動刪除）",
    },
    "temp_voice.help_temporary_voice_channel_commands": {
        "en": "[Help] Temporary voice channel commands",
        "zh": "[說明] 暫時語音頻道指令",
    },
    "temp_voice.these_commands_apply_to_a_temporary": {
        "en": "These commands apply to a temporary voice channel owned or claimed by the caller.\n**Command prefix: `{v0}`**",
        "zh": "以下指令僅限你自己建立（或已接管）的暫時語音頻道使用。\n**指令前綴：`{v0}`**",
    },
    "temp_voice.basic_settings": {"en": "Basic settings", "zh": "基礎設定"},
    "temp_voice.name_name_rename_the_channel_limit": {
        "en": "`{v0}name <name>` — Rename the channel\n`{v1}limit <count>` — Set the member limit (0 = unlimited; maximum 99)\n`{v2}bitrate <bitrate>` — Set bitrate (8–96 kbps)",
        "zh": "`{v0}name <名稱>` — 更改頻道名稱\n`{v1}limit <人數>` — 設定人數上限（0 = 無限制，最大 99）\n`{v2}bitrate <位元率>` — 設定位元率（8～96，單位 kbps）",
    },
    "temp_voice.privacy_settings": {"en": "Privacy settings", "zh": "隱私設定"},
    "temp_voice.hide_hide_the_channel_unhide_make": {
        "en": "`{v0}hide` — Hide the channel\n`{v1}unhide` — Make the channel visible\n`{v2}lock` — Restrict joining to invited members\n`{v3}unlock` — Allow anyone to join",
        "zh": "`{v0}hide` — 隱藏頻道，其他玩家無法看見\n`{v1}unhide` — 取消隱藏，頻道恢復可見\n`{v2}lock` — 鎖定頻道，其他人無法加入（除非受邀）\n`{v3}unlock` — 解除鎖定，所有人可自由加入",
    },
    "temp_voice.participant_management": {
        "en": "Participant management",
        "zh": "管理頻道參與者",
    },
    "temp_voice.kick_member_disconnect_a_member_ban": {
        "en": "`{v0}kick <@member>` — Disconnect a member\n`{v1}ban <@member>` — Block a member from this channel\n`{v2}unban <@member>` — Unblock a member",
        "zh": "`{v0}kick <@成員>` — 將成員踢出頻道\n`{v1}ban <@成員>` — 永久封鎖成員加入此頻道\n`{v2}unban <@成員>` — 解除某成員的封鎖",
    },
    "temp_voice.ownership_management": {
        "en": "Ownership management",
        "zh": "擁有者管理",
    },
    "temp_voice.transfer_member_transfer_ownership_to_a": {
        "en": "`{v0}transfer <@member>` — Transfer ownership to a member in the channel\n`{v1}claim` — Claim ownership after the original owner leaves",
        "zh": "`{v0}transfer <@成員>` — 將管理權轉移給頻道內其他成員\n`{v1}claim` — 當原創建者已離開時，接管此頻道的管理權",
    },
    "temp_voice.server_commands_apply_to_the_current": {
        "en": "Server: {v0} | Commands apply to the current temporary voice channel",
        "zh": "伺服器：{v0} | 頻道 ID 僅限於你所在的暫時語音頻道有效",
    },
    "temp_voice.failed_the_manage_channels_permission_is": {
        "en": "[Failed] The Manage Channels permission is required for this command",
        "zh": "[失敗] 你需要「管理頻道」權限才能使用此指令",
    },
    "temp_voice.failed_the_name_template_must_not": {
        "en": "[Failed] The name template must not exceed 100 characters",
        "zh": "[失敗] 名稱範本不能超過 100 字元",
    },
    "temp_voice.info_temporary_voice_channels_are_not": {
        "en": "[Info] Temporary voice channels are not configured. Use `/temp_voice setup`",
        "zh": "[提示] 此伺服器尚未設定暫時語音頻道系統，請使用 `/temp_voice setup` 設定",
    },
    "temp_voice.deleted_id": {"en": "[Deleted] ID: {v0}", "zh": "[已刪除] ID: {v0}"},
    "temp_voice.info_temporary_voice_channels_are_not_c97b22": {
        "en": "[Info] Temporary voice channels are not enabled in this server",
        "zh": "[提示] 此伺服器尚未啟用暫時語音頻道系統",
    },
    "temp_voice.failed_unknown_command_use_help_to": {
        "en": "[Failed] Unknown command `{v0}{v1}`. Use `{v2}help` to list available commands",
        "zh": "[失敗] 未知指令 `{v0}{v1}`，輸入 `{v2}help` 查看所有可用指令",
    },
    "temp_voice.failed_this_command_requires_a_temporary": {
        "en": "[Failed] This command requires a temporary voice channel owned or claimed by the caller",
        "zh": "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
    },
    "temp_voice.failed_provide_a_new_name_for": {
        "en": "[Failed] Provide a new name, for example: `{v0}name My channel`",
        "zh": "[失敗] 請提供新頻道名稱，例如：`{v0}name 我的頻道`",
    },
    "temp_voice.failed_the_channel_name_must_not": {
        "en": "[Failed] The channel name must not exceed 100 characters",
        "zh": "[失敗] 頻道名稱不能超過 100 字元",
    },
    "temp_voice.success_channel_renamed_to": {
        "en": "[Success] Channel renamed to **{v0}**",
        "zh": "[成功] 頻道名稱已更改為：**{v0}**",
    },
    "temp_voice.failed_enter_a_valid_number_for": {
        "en": "[Failed] Enter a valid number, for example: `{v0}limit 5` (0 = unlimited)",
        "zh": "[失敗] 請輸入有效數字，例如：`{v0}limit 5`（0 表示無限制）",
    },
    "temp_voice.failed_the_member_limit_must_be": {
        "en": "[Failed] The member limit must be between 0 and 99 (0 = unlimited)",
        "zh": "[失敗] 人數限制必須在 0～99 之間（0 表示無限制）",
    },
    "temp_voice.success_channel_member_limit": {
        "en": "[Success] Channel member limit: **{v0}**",
        "zh": "[成功] 頻道人數上限已設定為：**{v0}**",
    },
    "temp_voice.failed_enter_a_valid_number_for_29f742": {
        "en": "[Failed] Enter a valid number, for example: `{v0}bitrate 64`",
        "zh": "[失敗] 請輸入有效數字，例如：`{v0}bitrate 64`",
    },
    "temp_voice.failed_bitrate_must_be_between_8": {
        "en": "[Failed] Bitrate must be between 8 and {v0} kbps (this server's boost limit)",
        "zh": "[失敗] 位元率必須在 8～{v0} kbps 之間（此伺服器加成等級上限）",
    },
    "temp_voice.success_channel_bitrate_kbps": {
        "en": "[Success] Channel bitrate: **{v0} kbps**",
        "zh": "[成功] 頻道位元率已設定為：**{v0} kbps**",
    },
    "temp_voice.success_channel_hidden_from_other_members": {
        "en": "[Success] Channel hidden from other members",
        "zh": "[成功] 頻道已隱藏，其他人無法看見此頻道",
    },
    "temp_voice.success_channel_is_visible": {
        "en": "[Success] Channel is visible",
        "zh": "[成功] 頻道已設為可見",
    },
    "temp_voice.success_channel_locked_only_invited_members": {
        "en": "[Success] Channel locked. Only invited members or members moved by moderators can join",
        "zh": "[成功] 頻道已鎖定，其他人無法加入（除非受邀或管理員強制移動）",
    },
    "temp_voice.success_channel_unlocked_anyone_can_join": {
        "en": "[Success] Channel unlocked. Anyone can join",
        "zh": "[成功] 頻道已解除鎖定，所有人可自由加入",
    },
    "temp_voice.failed_mention_the_member_to_disconnect": {
        "en": "[Failed] Mention the member to disconnect, for example: `{v0}kick @member`",
        "zh": "[失敗] 請 @ 提及要踢出的成員，例如：`{v0}kick @成員`",
    },
    "temp_voice.specify_a_member_of_this_server": {
        "en": "Specify a member of this server.",
        "zh": "請指定此伺服器的成員。",
    },
    "temp_voice.failed_self_kicking_is_not_allowed": {
        "en": "[Failed] Self-kicking is not allowed",
        "zh": "[失敗] 你無法踢出自己",
    },
    "temp_voice.failed_is_not_in_this_channel": {
        "en": "[Failed] {v0} is not in this channel",
        "zh": "[失敗] {v0} 目前不在此頻道內",
    },
    "temp_voice.failed_mention_the_member_to_block": {
        "en": "[Failed] Mention the member to block, for example: `{v0}ban @member`",
        "zh": "[失敗] 請 @ 提及要封鎖的成員，例如：`{v0}ban @成員`",
    },
    "temp_voice.failed_self_blocking_is_not_allowed": {
        "en": "[Failed] Self-blocking is not allowed",
        "zh": "[失敗] 你無法封鎖自己",
    },
    "temp_voice.success_is_blocked_from_this_channel": {
        "en": "[Success] {v0} is blocked from this channel",
        "zh": "[成功] 已永久封鎖 {v0} 加入此頻道",
    },
    "temp_voice.failed_mention_the_member_to_unblock": {
        "en": "[Failed] Mention the member to unblock, for example: `{v0}unban @member`",
        "zh": "[失敗] 請 @ 提及要解除封鎖的成員，例如：`{v0}unban @成員`",
    },
    "temp_voice.success_unblocked_and_able_to_join": {
        "en": "[Success] {v0} unblocked and able to join again",
        "zh": "[成功] 已解除 {v0} 的封鎖，對方可再次加入此頻道",
    },
    "temp_voice.failed_mention_the_new_owner_for": {
        "en": "[Failed] Mention the new owner, for example: `{v0}transfer @member`",
        "zh": "[失敗] 請 @ 提及要轉移給的成員，例如：`{v0}transfer @成員`",
    },
    "temp_voice.failed_this_account_already_owns_the": {
        "en": "[Failed] This account already owns the channel",
        "zh": "[失敗] 你已經是此頻道的擁有者",
    },
    "temp_voice.failed_must_be_in_this_channel": {
        "en": "[Failed] {v0} must be in this channel to receive ownership",
        "zh": "[失敗] {v0} 需要在此頻道內才能轉移管理權",
    },
    "temp_voice.success_channel_ownership_transferred_to": {
        "en": "[Success] Channel ownership transferred to {v0}",
        "zh": "[成功] 已將頻道管理權轉移給 {v0}",
    },
    "temp_voice.failed_this_command_requires_a_temporary_ea06f2": {
        "en": "[Failed] This command requires a temporary voice channel",
        "zh": "[失敗] 你需要在暫時語音頻道中才能使用此指令",
    },
    "temp_voice.info_this_account_already_owns_the": {
        "en": "[Info] This account already owns the channel",
        "zh": "[提示] 你已經是此頻道的擁有者",
    },
    "temp_voice.failed_the_original_owner_is_still": {
        "en": "[Failed] The original owner is still in the channel",
        "zh": "[失敗] 頻道的原擁有者仍在頻道內，無法接管",
    },
    "temp_voice.success_temporary_voice_channel_ownership_claimed": {
        "en": "[Success] Temporary voice channel ownership claimed",
        "zh": "[成功] 你已成功接管此暫時語音頻道的管理權",
    },
    "temp_voice.temporary_voice_channel_created": {
        "en": "Temporary voice channel created: {v0} ({v1})",
        "zh": "暫時語音頻道建立：{v0} ({v1})",
    },
    "temp_voice.moved_to_temporary_voice_channel": {
        "en": "Moved to temporary voice channel",
        "zh": "移入暫時語音頻道",
    },
    "temp_voice.failed_the_bot_lacks_permission_to": {
        "en": "[Failed] The bot lacks permission to edit this channel",
        "zh": "[失敗] 機器人缺少修改此頻道的權限",
    },
    "temp_voice.failed_update_failed_discord_error": {
        "en": "[Failed] Update failed (Discord error): {v0}",
        "zh": "[失敗] 修改失敗（Discord 錯誤）：{v0}",
    },
    "temp_voice.failed_the_bot_cannot_change_channel": {
        "en": "[Failed] The bot cannot change channel permissions",
        "zh": "[失敗] 機器人缺少設定頻道權限的能力",
    },
    "temp_voice.success_disconnected_from_the_channel": {
        "en": "[Success] Disconnected {v0} from the channel",
        "zh": "[成功] 已將 {v0} 踢出頻道",
    },
    "temp_voice.temporary_voice_channel_kick_by": {
        "en": "Temporary voice channel kick by {v0} ({v1})",
        "zh": "暫時語音頻道踢出：由 {v0} ({v1})",
    },
    "temp_voice.failed_the_bot_lacks_the_move": {
        "en": "[Failed] The bot lacks the Move Members permission",
        "zh": "[失敗] 機器人缺少移動成員的權限",
    },
    "temp_voice.temporary_voice_channel_block_by": {
        "en": "Temporary voice channel block by {v0} ({v1})",
        "zh": "暫時語音頻道封鎖：由 {v0} ({v1})",
    },
    "temp_voice.empty_temporary_voice_channel_deleted_automatically": {
        "en": "Empty temporary voice channel deleted automatically",
        "zh": "暫時語音頻道已清空，自動刪除",
    },
}
