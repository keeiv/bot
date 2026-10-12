"""English and Traditional Chinese copy for tool_worker."""

MESSAGES: dict[str, dict[str, str]] = {
    "tool_worker.supported_still_images_and_csv_tsv": {
        "en": "Supported: still images and CSV / TSV / JSON table conversion",
        "zh": "支援靜態圖片及 CSV／TSV／JSON 表格轉換",
    },
    "tool_worker.table_conversion_is_limited_to_8": {
        "en": "Table conversion is limited to 8 MiB",
        "zh": "表格轉換上限為 8 MiB",
    },
    "tool_worker.tables_are_limited_to_50_000": {
        "en": "Tables are limited to 50,000 rows",
        "zh": "表格上限為 50,000 列",
    },
    "tool_worker.tables_are_limited_to_256_columns": {
        "en": "Tables are limited to 256 columns",
        "zh": "表格上限為 256 欄",
    },
    "tool_worker.output_exceeds_64_mib": {
        "en": "Output exceeds 64 MiB",
        "zh": "輸出超過 64 MiB 上限",
    },
    "tool_worker.json_must_be_an_array_of": {
        "en": "JSON must be an array of objects",
        "zh": "JSON 必須為物件陣列",
    },
    "tool_worker.table_column_names_must_be_unique": {
        "en": "Table column names must be unique",
        "zh": "表格需要不重複的欄位名稱",
    },
    "tool_worker.nested_json_cannot_be_converted_to": {
        "en": "Nested JSON cannot be converted to a flat table",
        "zh": "巢狀 JSON 無法轉換為平面表格",
    },
    "tool_worker.only_still_images_are_supported": {
        "en": "Only still images are supported",
        "zh": "目前僅支援靜態圖片",
    },
    "tool_worker.this_output_format_is_not_supported": {
        "en": "This output format is not supported for images",
        "zh": "圖片不支援此輸出格式",
    },
    "tool_worker.table_rows_have_inconsistent_column_counts": {
        "en": "Table rows have inconsistent column counts",
        "zh": "表格欄位數不一致",
    },
}
