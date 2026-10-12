"""Present domain identifiers without changing their stored values."""

from src.utils.i18n import text as tx

ITEM_KEYS = {
    "側錄器": "item.recorder.name",
    "漏氣針": "item.leak_needle.name",
    "透視眼鏡": "item.xray.name",
    "命運洗牌": "item.shuffle.name",
    "空包彈": "item.blank.name",
    "強制轉向": "item.redirect.name",
    "加倍賭注": "item.double.name",
}


def item_name(item: str) -> str:
    key = ITEM_KEYS.get(item)
    return tx(key) if key else item


def items_text(items: list[str]) -> str:
    return ", ".join(item_name(item) for item in items) or tx("info.none")


def appeal_status(status: str) -> str:
    key = {
        "待處理": "appeal.pending",
        "已接受": "appeal.accepted",
        "已駁回": "appeal.rejected",
    }.get(status)
    return tx(key) if key else status
