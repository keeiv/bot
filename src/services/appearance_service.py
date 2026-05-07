"""機器人外觀申請業務邏輯服務"""

from typing import Optional


class AppearanceService:
    """外觀變更申請的暫存管理"""

    def __init__(self) -> None:
        self._pending: dict[str, dict] = {}

    def add_request(self, request_id: str, data: dict) -> None:
        """新增待審核申請"""
        self._pending[request_id] = data

    def get_request(self, request_id: str) -> Optional[dict]:
        """取得申請資料"""
        return self._pending.get(request_id)

    def remove_request(self, request_id: str) -> Optional[dict]:
        """移除並回傳申請資料"""
        return self._pending.pop(request_id, None)
