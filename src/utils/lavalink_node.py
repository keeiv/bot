from __future__ import annotations

import importlib
from typing import Any

import discord


class LavalinkManager:
    """Lavalink 節點管理：封裝 wavelink 節點建立與銷毀流程

    以非同步方法建立節點，若系統未安裝 `wavelink` 則會拋出錯誤。
    """

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.node: Any = None

    async def create_node(
        self,
        host: str = "127.0.0.1",
        port: int = 2333,
        password: str = "youshallnotpass",
        identifier: str = "Lavalink",
    ) -> Any:
        """建立並註冊 Lavalink 節點，成功回傳節點物件。

        參數使用常見預設值，部署時請以環境變數或設定檔覆寫。
        """
        try:
            wavelink = importlib.import_module("wavelink")
        except ImportError as exc:
            raise RuntimeError("請安裝音樂依賴：pip install -e .[music]") from exc

        if self.node is not None:
            return self.node
        node = wavelink.Node(
            uri=f"http://{host}:{port}", password=password, identifier=identifier
        )
        try:
            await wavelink.Pool.connect(client=self.bot, nodes=[node])
        except BaseException:
            await node.close(eject=True)
            raise
        self.node = node
        return self.node

    async def destroy_node(self) -> None:
        """安全銷毀已建立的節點"""
        if self.node is None:
            return
        try:
            await self.node.close(eject=True)
        finally:
            self.node = None


def get_manager(
    bot: discord.Client,
) -> LavalinkManager:
    """建立或取得 Lavalink 管理器實例（簡單工廠）"""
    return LavalinkManager(bot)
