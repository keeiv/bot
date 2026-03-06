"""測試性 Lavalink 節點連線範例（不含播放功能）

說明：
- 這個檔案示範如何在 bot 啟動時初始化 Lavalink node（使用 wavelink 客戶端）。
- 需先安裝相依：`wavelink`。實際播放功能與事件處理請另行實作。
"""
from __future__ import annotations
import os
import asyncio
from typing import Optional

import discord
from discord.ext import commands

try:
    import wavelink
except Exception:  # pragma: no cover - optional dependency
    wavelink = None


class LavalinkNode:
    """簡單的封裝，初始化 wavelink node（示範）。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.node: Optional[wavelink.Node] = None if wavelink else None

    async def setup(self) -> None:
        if wavelink is None:
            self.bot.logger and self.bot.logger.warning("wavelink 未安裝，Lavalink 功能不可用")
            return

        # 讀取環境變數或使用預設值
        host = os.getenv("LAVALINK_HOST", "127.0.0.1")
        port = int(os.getenv("LAVALINK_PORT", "2333"))
        password = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

        # 初始化 wavelink
        try:
            await wavelink.NodePool.create_node(bot=self.bot, host=host, port=port, password=password)
            # 取得節點參考（第一個）
            nodes = wavelink.NodePool._nodes
            self.node = next(iter(nodes.values())) if nodes else None
            if self.node:
                self.bot.logger and self.bot.logger.info(f"Lavalink node 已連線: {host}:{port}")
        except Exception as e:
            self.bot.logger and self.bot.logger.exception(f"初始化 Lavalink node 失敗: {e}")


async def setup_lavalink(bot: commands.Bot) -> LavalinkNode:
    node = LavalinkNode(bot)
    # 延遲至 bot.ready 時呼叫以確保 event loop 與 intents 就緒
    bot.loop.create_task(node.setup())
    return node
