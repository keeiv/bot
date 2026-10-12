"""English and Traditional Chinese copy for tool_quota."""

MESSAGES: dict[str, dict[str, str]] = {
    "tool_quota.invalid_discord_id": {
        "en": "Invalid Discord ID",
        "zh": "無效的 Discord ID",
    },
    "tool_quota.points_ceil_input_mib_processing_seconds": {
        "en": "Points = ceil(input MiB + processing seconds × 2). Failed jobs or compression without size reduction are not charged.",
        "zh": "點數＝向上取整（輸入 MiB＋實際處理秒數×2）；失敗或壓縮未縮小不扣點。",
    },
    "tool_quota.invalid_files_or_output_format": {
        "en": "Invalid files or output format",
        "zh": "檔案或輸出格式無效",
    },
    "tool_quota.unknown_administration_operation": {
        "en": "Unknown administration operation",
        "zh": "未知管理操作",
    },
    "tool_quota.only_developers_can_grant_or_revoke": {
        "en": "Only developers can grant or revoke hidden tiers",
        "zh": "僅限開發者授予或撤銷隱藏等級",
    },
    "tool_quota.invalid_authorization_operation": {
        "en": "Invalid authorization operation",
        "zh": "無效的授權操作",
    },
    "tool_quota.developers_receive_nova_20x_by_default": {
        "en": "Developers receive Nova 20x. by default; no additional grant is required",
        "zh": "開發者預設為 Nova 20x.，不需要額外授權",
    },
    "tool_quota.invalid_operation_id": {
        "en": "Invalid operation ID",
        "zh": "無效的操作識別碼",
    },
    "tool_quota.only_developer_accounts_can_use_test": {
        "en": "Only developer accounts can use test tiers",
        "zh": "僅限開發者帳號使用測試等級",
    },
    "tool_quota.tier_free_run_dash_grow_ultra": {
        "en": "Tier: Free. / Run. / Dash. / Grow. / Ultra. / Nova / auto",
        "zh": "等級：Free.／Run.／Dash.／Grow.／Ultra.／Nova／auto",
    },
    "tool_quota.the_batch_exceeds_this_tier_s": {
        "en": "The batch exceeds this tier's limit",
        "zh": "超過目前等級的批次上限",
    },
    "tool_quota.the_file_exceeds_the_current_size": {
        "en": "The file exceeds the current size limit",
        "zh": "檔案大小超過目前上限",
    },
    "tool_quota.insufficient_allowance_to_reserve_the_maximum": {
        "en": "Insufficient allowance to reserve the maximum processing charge",
        "zh": "剩餘額度不足以預留本次處理上限",
    },
    "tool_quota.the_tier_has_changed_request_a": {
        "en": "The tier has changed. Request a new usage estimate",
        "zh": "等級已更新，需重新估算本次用量",
    },
    "tool_quota.this_processing_request_has_already_been": {
        "en": "This processing request has already been submitted",
        "zh": "此處理請求已提交",
    },
    "tool_quota.a_file_job_is_already_in": {
        "en": "A file job is already in progress",
        "zh": "已有處理中的檔案工作",
    },
    "tool_quota.processing_record_not_found": {
        "en": "Processing record not found",
        "zh": "找不到處理紀錄",
    },
    "tool_quota.the_reset_voucher_does_not_exist": {
        "en": "The reset voucher does not exist or has already been used",
        "zh": "重置券不存在或已使用",
    },
    "tool_quota.there_is_no_recorded_usage_to": {
        "en": "There is no recorded usage to reset",
        "zh": "目前沒有需要重置的已用額度",
    },
    "tool_quota.this_operation_id_was_used_for": {
        "en": "This operation ID was used for another action",
        "zh": "操作識別碼已用於其他操作",
    },
}
