"""Present domain identifiers without changing their stored values."""

from src.utils.i18n import text as tx


def appeal_status(status: str) -> str:
    key = {
        "待處理": "appeal.pending",
        "已接受": "appeal.accepted",
        "已駁回": "appeal.rejected",
    }.get(status)
    return tx(key) if key else status
