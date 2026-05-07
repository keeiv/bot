"""osu! 業務邏輯服務"""

import json
import os
from typing import Optional

_DATA_FILE = "data/storage/osu_links.json"


class OsuService:
    """osu! 帳號綁定資料存取與 API 初始化"""

    def __init__(self) -> None:
        self._api = None
        self._api_error: Optional[str] = None
        self._links: dict = self._load_links()
        self._init_api()

    def _init_api(self) -> None:
        """初始化 osu! API 客戶端"""
        try:
            from ossapi import Ossapi
        except ImportError:
            self._api_error = "ossapi 套件無法載入，osu! 功能已禁用"
            return

        client_id = os.getenv("OSU_CLIENT_ID")
        client_secret = os.getenv("OSU_CLIENT_SECRET")
        if not client_id or not client_secret:
            self._api_error = "缺少 OSU_CLIENT_ID 或 OSU_CLIENT_SECRET 環境變數"
            return

        self._api = Ossapi(int(client_id), client_secret)

    # ─────────────── 資料存取 ───────────────

    def _load_links(self) -> dict:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        if not os.path.exists(_DATA_FILE):
            return {}
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_links(self) -> None:
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._links, f, ensure_ascii=False, indent=2)

    # ─────────────── 綁定 ───────────────

    def bind(self, user_id: int, username: str) -> None:
        """綁定 Discord 用戶與 osu! 帳號"""
        self._links[str(user_id)] = username
        self._save_links()

    def unbind(self, user_id: int) -> bool:
        """解除綁定，回傳是否有綁定存在"""
        if str(user_id) not in self._links:
            return False
        del self._links[str(user_id)]
        self._save_links()
        return True

    def get_bound_username(self, user_id: int) -> Optional[str]:
        """取得綁定的 osu! 使用者名稱"""
        return self._links.get(str(user_id))

    # ─────────────── API ───────────────

    @property
    def api(self):
        """osu! API 客戶端"""
        return self._api

    @property
    def api_error(self) -> Optional[str]:
        """API 初始化錯誤訊息"""
        return self._api_error

    def ensure_api(self) -> None:
        """確認 API 可用，否則拋出 RuntimeError"""
        if self._api is None:
            raise RuntimeError(
                "osu! 功能尚未啟用。"
                "請在 .env 加上 OSU_CLIENT_ID 與 OSU_CLIENT_SECRET 後重啟 bot。"
            )

    @staticmethod
    def format_playtime(seconds: Optional[int]) -> str:
        """格式化遊戲時間"""
        if not seconds:
            return "0 小時"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours:
            return f"{hours} 小時 {minutes} 分鐘"
        return f"{minutes} 分鐘"
