from __future__ import annotations

import importlib
from typing import Any

import discord


class LavalinkManager:
    """Lavalink node management: wraps creating and destroying wavelink nodes.

    Nodes are created by async methods; an error is raised if `wavelink` is not installed.
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
        """Create and register a Lavalink node; return the node on success.

        The parameters use common defaults; override them with environment variables or a config file when deploying.
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
        """Destroy the created nodes safely."""
        if self.node is None:
            return
        try:
            await self.node.close(eject=True)
        finally:
            self.node = None


def get_manager(
    bot: discord.Client,
) -> LavalinkManager:
    """Create or return the Lavalink manager instance (a simple factory)."""
    return LavalinkManager(bot)
