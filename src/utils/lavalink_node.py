from __future__ import annotations
from typing import Optional
import asyncio

import discord

try:
    import wavelink
except Exception:  # wavelink 可能尚未安裝
    wavelink = None


class LavalinkManager:
    """Lavalink 節點管理：封裝 wavelink 節點建立與銷毀流程

    以非同步方法建立節點，若系統未安裝 `wavelink` 則會拋出錯誤。
    """

    def __init__(self, bot: discord.Client | discord.Bot | discord.AutoShardedClient):
        self.bot = bot
        self.node: Optional[object] = None

    async def create_node(self, host: str = "127.0.0.1", port: int = 2333, password: str = "youshallnotpass", identifier: str = "Lavalink"):
        """建立並註冊 Lavalink 節點，成功回傳節點物件。

        參數使用常見預設值，部署時請以環境變數或設定檔覆寫。
        """
        if wavelink is None:
            raise RuntimeError("wavelink 尚未安裝，請在 requirements.txt 安裝 wavelink")

        # wavelink 的 NodePool API 會在建立時完成連線註冊
        self.node = await wavelink.NodePool.create_node(bot=self.bot, host=host, port=port, password=password, identifier=identifier)
        return self.node

    async def destroy_node(self) -> None:
        """安全銷毀已建立的節點"""
        if self.node is None:
            return
        try:
            await self.node.destroy()
        except Exception:
            pass
        finally:
            self.node = None


def get_manager(bot: discord.Client | discord.Bot | discord.AutoShardedClient) -> LavalinkManager:
    """建立或取得 Lavalink 管理器實例（簡單工廠）"""
    return LavalinkManager(bot)
