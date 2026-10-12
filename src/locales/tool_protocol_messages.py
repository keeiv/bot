"""English and Traditional Chinese copy for tool_protocol."""

MESSAGES: dict[str, dict[str, str]] = {
    "tool_protocol.invalid_processing_request": {
        "en": "Invalid processing request",
        "zh": "處理請求格式無效",
    },
    "tool_protocol.invalid_job_id": {"en": "Invalid job ID", "zh": "工作識別碼無效"},
    "tool_protocol.invalid_output_format": {
        "en": "Invalid output format",
        "zh": "輸出格式無效",
    },
    "tool_protocol.invalid_batch_limit": {
        "en": "Invalid batch limit",
        "zh": "批次上限無效",
    },
    "tool_protocol.the_batch_exceeds_64_mib": {
        "en": "The batch exceeds 64 MiB",
        "zh": "批次超過 64 MiB 上限",
    },
    "tool_protocol.invalid_engine_id": {
        "en": "Invalid engine ID",
        "zh": "引擎識別碼無效",
    },
    "tool_protocol.invalid_processing_result_metadata": {
        "en": "Invalid processing result metadata",
        "zh": "處理結果資訊無效",
    },
    "tool_protocol.processing_result_verification_failed": {
        "en": "Processing result verification failed",
        "zh": "處理結果校驗失敗",
    },
    "tool_protocol.invalid_processing_limit": {
        "en": "Invalid processing limit",
        "zh": "處理上限無效",
    },
    "tool_protocol.invalid_file_metadata": {
        "en": "Invalid file metadata",
        "zh": "檔案資訊無效",
    },
    "tool_protocol.invalid_filename_or_file_size": {
        "en": "Invalid filename or file size",
        "zh": "檔名或檔案大小無效",
    },
}
