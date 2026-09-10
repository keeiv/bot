"""Basic startup checks for the Discord bot.

These tests are designed to run in CI without requiring a real Discord token
or network connection. They verify that the core bot class and all cogs can
be imported and loaded without raising unexpected exceptions.
"""

from pathlib import Path
import pkgutil
from unittest.mock import AsyncMock

import pytest

from src.bot import Bot


async def test_bot_class_can_be_instantiated() -> None:
    """Ensure the core Bot class can be instantiated."""
    async with Bot() as bot:
        assert bot.intents is not None


async def test_cogs_can_be_loaded_without_running(monkeypatch) -> None:
    """Ensure all configured cogs can be loaded without starting the bot."""
    import genshin

    monkeypatch.setattr(genshin.utility, "update_characters_any", AsyncMock())
    cogs_path = Path(__file__).resolve().parents[1] / "src" / "cogs"
    expected = {
        m.name
        for m in pkgutil.walk_packages([str(cogs_path)], "src.cogs.")
        if not m.ispkg
    }
    async with Bot() as bot:
        await bot.load_cogs()
        assert set(bot.extensions) == expected


async def test_failed_cog_cannot_report_success(monkeypatch):
    async with Bot() as bot:
        monkeypatch.setattr(
            bot, "load_extension", AsyncMock(side_effect=RuntimeError("broken"))
        )
        with pytest.raises(RuntimeError, match="Cog 載入失敗"):
            await bot.load_cogs()
