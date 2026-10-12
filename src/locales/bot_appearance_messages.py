"""English and Traditional Chinese copy for bot_appearance."""

MESSAGES: dict[str, dict[str, str]] = {
    "bot_appearance.approve": {"en": "Approve", "zh": "核准"},
    "bot_appearance.reject": {"en": "Reject", "zh": "拒絕"},
    "bot_appearance.avatar": {"en": "Avatar", "zh": "頭像"},
    "bot_appearance.banner": {"en": "Banner", "zh": "橫幅"},
    "bot_appearance.avatar_and_banner": {"en": "Avatar and banner", "zh": "頭像與橫幅"},
    "bot_appearance.review_bot_change_request": {
        "en": "[Review] Bot {v0} change request",
        "zh": "[審核] 機器人{v0}變更請求",
    },
    "bot_appearance.server": {"en": "Server", "zh": "伺服器"},
    "bot_appearance.requester": {"en": "Requester", "zh": "申請者"},
    "bot_appearance.change_type": {"en": "Change type", "zh": "變更類型"},
    "bot_appearance.request_id": {"en": "Request ID", "zh": "請求 ID"},
    "bot_appearance.this_change_request_is_awaiting_review": {
        "en": "This change request is awaiting review",
        "zh": "請審核此變更請求",
    },
    "bot_appearance.this_feature_is_only_available_in": {
        "en": "This feature is only available in a server.",
        "zh": "此功能只能在伺服器內使用。",
    },
    "bot_appearance.could_not_notify_developers": {
        "en": "Could not notify developers: {v0}",
        "zh": "無法通知開發者: {v0}",
    },
    "bot_appearance.failed_this_request_has_expired_or": {
        "en": "[Failed] This request has expired or does not exist",
        "zh": "[失敗] 此請求已過期或不存在",
    },
    "bot_appearance.rejected_change": {
        "en": "[Rejected] {v0} change",
        "zh": "[已拒絕] {v0}變更",
    },
    "bot_appearance.the_request_from_was_rejected": {
        "en": "The request from {v0} was rejected",
        "zh": "來自 {v0} 的請求已拒絕",
    },
    "bot_appearance.failed_administrator_permission_is_required": {
        "en": "[Failed] Administrator permission is required",
        "zh": "[失敗] 你需要管理員權限",
    },
    "bot_appearance.failed_upload_a_valid_image_file": {
        "en": "[Failed] Upload a valid image file",
        "zh": "[失敗] 請上傳有效的圖片檔案",
    },
    "bot_appearance.failed_the_image_must_not_exceed": {
        "en": "[Failed] The image must not exceed 8 MB",
        "zh": "[失敗] 圖片大小不能超過 8MB",
    },
    "bot_appearance.pending_avatar_change_submitted": {
        "en": "[Pending] Avatar change submitted",
        "zh": "[待審核] 頭像變更已提交",
    },
    "bot_appearance.the_avatar_change_request_has_been": {
        "en": "The avatar change request has been submitted for developer review",
        "zh": "你的頭像變更請求已發送給開發者審核，請耐心等待",
    },
    "bot_appearance.pending_banner_change_submitted": {
        "en": "[Pending] Banner change submitted",
        "zh": "[待審核] 橫幅變更已提交",
    },
    "bot_appearance.the_banner_change_request_has_been": {
        "en": "The banner change request has been submitted for developer review",
        "zh": "你的橫幅變更請求已發送給開發者審核，請耐心等待",
    },
    "bot_appearance.success_appearance_reset": {
        "en": "[Success] Appearance reset",
        "zh": "[成功] 外觀已還原",
    },
    "bot_appearance.the_bot_s_in_this_server": {
        "en": "The bot's {v0} in this server has been reset to the global default",
        "zh": "機器人在此伺服器的{v0}已還原為全域預設",
    },
    "bot_appearance.performed_by": {"en": "Performed by", "zh": "操作者"},
    "bot_appearance.failed_server_not_found": {
        "en": "[Failed] Server not found",
        "zh": "[失敗] 找不到伺服器",
    },
    "bot_appearance.approved_change": {
        "en": "[Approved] {v0} change",
        "zh": "[已核准] {v0}變更",
    },
    "bot_appearance.applied_to": {"en": "Applied to {v0}", "zh": "已套用至 {v0}"},
    "bot_appearance.success_name_changed": {
        "en": "[Success] Name changed",
        "zh": "[成功] 名稱已更改",
    },
    "bot_appearance.the_bot_s_name_in_this": {
        "en": "The bot's name in this server is now **{v0}**",
        "zh": "機器人在此伺服器的名稱已更改為: **{v0}**",
    },
    "bot_appearance.success_name_reset": {
        "en": "[Success] Name reset",
        "zh": "[成功] 名稱已還原",
    },
    "bot_appearance.the_bot_s_name_has_been": {
        "en": "The bot's name has been reset to the default",
        "zh": "機器人名稱已還原為預設",
    },
    "bot_appearance.failed_the_bot_lacks_permission_to": {
        "en": "[Failed] The bot lacks permission to change its nickname",
        "zh": "[失敗] 機器人缺少更改暱稱的權限",
    },
    "bot_appearance.failed_could_not_change_name": {
        "en": "[Failed] Could not change name: {v0}",
        "zh": "[失敗] 無法更改名稱: {v0}",
    },
    "bot_appearance.failed_could_not_submit_for_review": {
        "en": "[Failed] Could not submit for review: {v0}",
        "zh": "[失敗] 提交審核失敗: {v0}",
    },
    "bot_appearance.failed_the_bot_lacks_the_required": {
        "en": "[Failed] The bot lacks the required permissions",
        "zh": "[失敗] 機器人缺少必要權限",
    },
    "bot_appearance.failed_api_request_failed": {
        "en": "[Failed] API request failed: {v0}",
        "zh": "[失敗] API 請求失敗: {v0}",
    },
    "bot_appearance.failed_could_not_apply_change": {
        "en": "[Failed] Could not apply change: {v0}",
        "zh": "[失敗] 套用失敗: {v0}",
    },
    "bot_appearance.rejected_change_not_approved": {
        "en": "[Rejected] {v0} change not approved",
        "zh": "[拒絕] {v0}變更未通過",
    },
    "bot_appearance.the_change_requested_by_was_rejected": {
        "en": "The {v1} change requested by <@{v0}> was rejected by a developer",
        "zh": "<@{v0}> 申請的{v1}變更已被開發者拒絕",
    },
    "bot_appearance.success_updated": {
        "en": "[Success] {v0} updated",
        "zh": "[成功] {v0}已更新",
    },
    "bot_appearance.the_change_requested_by_was_approved": {
        "en": "The {v1} change requested by <@{v0}> was approved and applied",
        "zh": "<@{v0}> 申請的{v1}變更已通過審核並套用",
    },
}
