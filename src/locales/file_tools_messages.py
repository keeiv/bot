"""English and Traditional Chinese copy for file_tools."""

MESSAGES: dict[str, dict[str, str]] = {
    "file_tools.confirm_voucher_use": {
        "en": "Confirm voucher use",
        "zh": "確認使用重置券",
    },
    "file_tools.no_records": {"en": "No records", "zh": "目前無紀錄"},
    "file_tools.unused": {"en": "Unused", "zh": "尚未使用"},
    "file_tools.usage_history": {"en": "Usage history", "zh": "歷史使用"},
    "file_tools.previous": {"en": "Previous", "zh": "上一頁"},
    "file_tools.next": {"en": "Next", "zh": "下一頁"},
    "file_tools.completed_points_charged_seconds": {
        "en": "Completed · {v0} points charged · {v1:.2f} seconds",
        "zh": "處理完成 · 扣除 {v0} 點 · 處理 {v1:.2f} 秒",
    },
    "file_tools.confirm_processing": {"en": "Confirm processing", "zh": "確認處理"},
    "file_tools.this_action_is_restricted_to_the": {
        "en": "This action is restricted to the account that made the request",
        "zh": "此操作僅限原請求帳號",
    },
    "file_tools.page_vouchers_vouchers_do_not_change": {
        "en": "Page {v0} · {v1} vouchers · Vouchers do not change account tenure",
        "zh": "第 {v0} 頁 · 共 {v1} 張 · 重置券不改變使用年資",
    },
    "file_tools.choose_a_reset_voucher": {
        "en": "Choose a reset voucher",
        "zh": "選擇重置券",
    },
    "file_tools.reset_vouchers": {"en": "Reset vouchers · ", "zh": "重置券背包 · "},
    "file_tools.reset_voucher": {"en": "Reset voucher · {v0}", "zh": "重置券 · {v0}"},
    "file_tools.at_t_f": {"en": "{v0} at: <t:{v1}:f>", "zh": "{v0}時間：<t:{v1}:f>"},
    "file_tools.job_already_submitted": {
        "en": "Job already submitted",
        "zh": "工作已提交",
    },
    "file_tools.file_processing_estimate": {
        "en": "File processing estimate",
        "zh": "檔案處理預估",
    },
    "file_tools.files_input_mib_maximum_reservation_points": {
        "en": "Files: {v0}\nInput: {v1:.2f} MiB\nMaximum reservation: {v2} points\nOutput: {v3}\n\nPoints depend on actual file size and processing time. Failed jobs or compression without size reduction are not charged.",
        "zh": "檔案：{v0} 件\n輸入：{v1:.2f} MiB\n最多預留：{v2} 點\n輸出：{v3}\n\n依實際檔案大小與處理時間計點。失敗或壓縮未縮小不扣點。",
    },
    "file_tools.results_are_stored_for_20_minutes": {
        "en": "Results are stored for 20 minutes",
        "zh": "結果暫存 20 分鐘",
    },
    "file_tools.attach_files_and_use_convert_png": {
        "en": "Attach files and use !convert png / jpg / webp / pdf / csv / tsv / json / compress.",
        "zh": "附加檔案後使用 !convert png／jpg／webp／pdf／csv／tsv／json／compress。",
    },
    "file_tools.file_processing_files_up_to_points": {
        "en": "File processing · {v0} files · Up to {v1} points reserved\nThe final charge depends on file size and processing time.",
        "zh": "檔案處理 · {v0} 件 · 最多預留 {v1} 點\n實際扣點依檔案大小與處理時間計算。",
    },
    "file_tools.developers_only": {"en": "Developers only", "zh": "僅限開發者使用"},
    "file_tools.syntax_reset_ureset_userid_sreset_serverid": {
        "en": "Syntax: >>>reset / >>>ureset [userid] / >>>sreset [serverid] / >>>ireset / >>>nova [userid] / >>>unova [userid]",
        "zh": "格式：>>>reset／>>>ureset [userid]／>>>sreset [serverid]／>>>ireset／>>>nova [userid]／>>>unova [userid]",
    },
    "file_tools.completed_accounts_account_tenure_is_preserved": {
        "en": "{v0} completed · {v1} accounts. Account tenure is preserved.",
        "zh": "{v0}完成 · {v1} 個帳號。使用年資保留。",
    },
    "file_tools.weekly_and_three_hour_usage_reset": {
        "en": "Weekly and three-hour usage reset. Jobs in progress are charged when completed.",
        "zh": "本週與近三小時已用額度已重置。處理中的工作仍於完成後計點。",
    },
    "file_tools.this_voucher_resets_weekly_and_three": {
        "en": "This voucher resets weekly and three-hour usage. Redemption history is retained permanently.",
        "zh": "使用後將重置本週與近三小時已用額度，使用紀錄永久保留。",
    },
    "file_tools.file_processing_failed": {
        "en": "File processing failed",
        "zh": "檔案處理失敗",
    },
    "file_tools.the_file_job_response_was_not": {
        "en": "The file job response was not completed. Results can be checked in the website job history.",
        "zh": "檔案工作未完成回覆。處理結果可於網站工作紀錄查詢。",
    },
    "file_tools.tier_updated_account_tenure_usage_and": {
        "en": "Tier updated · {v0} · {v1}. Account tenure, usage and vouchers are preserved.",
        "zh": "等級授權已更新 · {v0} · {v1}。年資、用量與重置券保留。",
    },
    "file_tools.operation_incomplete_the_same_message_event": {
        "en": "Operation incomplete. The same message event can be used to verify unconfirmed results.",
        "zh": "操作未完成，未確認的結果可使用相同訊息事件重新核對。",
    },
    "file_tools.attachment_size_mismatch": {
        "en": "Attachment size mismatch",
        "zh": "附件大小不符",
    },
    "file_tools.download_result_valid_for_15_minutes": {
        "en": "\n[Download result (valid for 15 minutes)]({v0}/tools/download?ticket={v1})",
        "zh": "\n[下載結果（15 分鐘內有效）]({v0}/tools/download?ticket={v1})",
    },
    "file_tools.the_bot_has_not_joined_this": {
        "en": "The bot has not joined this server",
        "zh": "機器人未加入此伺服器",
    },
    "file_tools.reset_voucher_40a182": {
        "en": "Reset voucher · {v0:%Y/%m/%d %H:%M}",
        "zh": "重置券 · {v0:%Y/%m/%d %H:%M}",
    },
    "file_tools.serial": {"en": "Serial {v0}", "zh": "序號 {v0}"},
    "file_tools.used": {"en": "Used", "zh": "使用"},
    "file_tools.issued": {"en": "Issued", "zh": "發放"},
    "file_tools.voucher_distribution": {
        "en": "Voucher distribution",
        "zh": "重置券發放",
    },
    "file_tools.usage_reset": {"en": "Usage reset", "zh": "用量重置"},
    "file_tools.the_file_service_is_not_ready": {
        "en": "The file service is not ready",
        "zh": "檔案服務尚未就緒",
    },
    "file_tools.the_processing_queue_is_full_retry": {
        "en": "The processing queue is full. Retry later",
        "zh": "處理佇列已滿，稍後可重新提交",
    },
    "file_tools.output_quality_or_dimensions_are_outside": {
        "en": "Output quality or dimensions are outside the allowed range",
        "zh": "輸出品質或尺寸不符合要求",
    },
    "file_tools.the_batch_exceeds_the_processing_limit": {
        "en": "The batch exceeds the processing limit",
        "zh": "批次超過處理上限",
    },
    "file_tools.usage_records_are_being_verified_downloads": {
        "en": "Usage records are being verified. Downloads become available after confirmation",
        "zh": "用量紀錄核對中，結果將於確認後開放下載",
    },
    "file_tools.the_file_job_does_not_exist": {
        "en": "The file job does not exist or has expired",
        "zh": "檔案工作不存在或已到期",
    },
    "file_tools.the_file_is_not_ready": {
        "en": "The file is not ready",
        "zh": "檔案尚未完成",
    },
    "file_tools.file_authorization_has_expired": {
        "en": "File authorization has expired",
        "zh": "檔案授權已失效",
    },
    "file_tools.conversion_failed_format_content_or_processing": {
        "en": "Conversion failed: format, content or processing limits are not supported",
        "zh": "轉換失敗：格式、內容或處理上限不符合要求",
    },
    "file_tools.file_processing_failed_or_timed_out": {
        "en": "File processing failed or timed out; no points were charged",
        "zh": "檔案處理失敗或超時；本次未扣點",
    },
}
