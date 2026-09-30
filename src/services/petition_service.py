"""女裝請願書的資料存取與連續副署計算。"""

from datetime import date
import json
import os
from typing import Any, Optional

from src.utils.document_store import document_exists
from src.utils.document_store import open_document
from src.utils.document_store import using_mysql
from src.utils.document_store import write_document
from src.utils.time_utils import get_now

_DATA_FILE = "data/storage/petition.json"


class PetitionService:
    """管理請願書副署紀錄。"""

    def __init__(self, data_file: str = _DATA_FILE) -> None:
        self.data_file = data_file
        os.makedirs(os.path.dirname(data_file) or ".", exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[Any, Any]:
        if not document_exists(self.data_file):
            return {}
        try:
            with open_document(self.data_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        if using_mysql():
            write_document(self.data_file, self._data)
            return
        temporary_file = f"{self.data_file}.tmp"
        try:
            with open(temporary_file, "w", encoding="utf-8") as file:
                json.dump(self._data, file, ensure_ascii=False, indent=2)
            os.replace(temporary_file, self.data_file)
        except OSError as error:
            try:
                os.unlink(temporary_file)
            except OSError:
                pass
            raise OSError(f"無法儲存請願書資料: {error}") from error

    def sign(self, user_id: int, today: Optional[date] = None) -> int:
        """記錄一次副署並回傳目前連續天數。"""
        current_date = today or get_now().date()
        today_string = current_date.isoformat()
        key = str(user_id)
        user_data = self._data.get(key, {})
        last_sign = user_data.get("last_sign", "")
        streak = user_data.get("streak", 0)

        try:
            streak = int(streak)
        except (TypeError, ValueError):
            streak = 0

        if last_sign == today_string:
            return max(streak, 1)

        try:
            previous_date = date.fromisoformat(last_sign)
        except (TypeError, ValueError):
            previous_date = None

        streak = (
            streak + 1
            if previous_date and (current_date - previous_date).days == 1
            else 1
        )
        self._data[key] = {"streak": streak, "last_sign": today_string}
        self._save()
        return streak
