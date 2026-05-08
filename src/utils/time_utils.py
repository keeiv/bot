"""時間工具函式 - 統一管理時區與格式化邏輯"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))


def get_current_time_str() -> str:
    """取得格式化的當前時間 (月/日 時:分)"""
    return datetime.now(TZ_OFFSET).strftime("%m/%d %H:%M")


def format_datetime(dt: datetime) -> str:
    """將 datetime 物件格式化為完整時間字串 (年/月/日 時:分:秒)，自動轉換至 UTC+8"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")


def get_now() -> datetime:
    """取得目前 UTC+8 的 datetime 物件"""
    return datetime.now(TZ_OFFSET)
