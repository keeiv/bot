"""Both ways a global ban is made act the same: no messages removed, one reason prefix."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from src.bot import global_ban
from src.services.global_ban_service import DELETE_SECONDS
from src.services.global_ban_service import REASON


async def test_the_immediate_ban_matches_the_scheduled_round():
    guild = SimpleNamespace(id=5, ban=AsyncMock())
    remember = AsyncMock()
    bot = SimpleNamespace(get_cog=lambda _: SimpleNamespace(remember=remember))
    user = SimpleNamespace(id=7)
    await global_ban(bot, guild, user, {"reason": "raid", "source": "mori"})
    kwargs = guild.ban.await_args.kwargs
    assert kwargs["delete_message_seconds"] == DELETE_SECONDS == 0
    assert kwargs["reason"].startswith(REASON)  # so the round can lift it later
    remember.assert_awaited_once_with(5, 7, "mori")


async def test_a_refused_immediate_ban_is_not_recorded():
    refused = discord.Forbidden(SimpleNamespace(status=403, reason="x"), "x")
    guild = SimpleNamespace(id=5, ban=AsyncMock(side_effect=refused))
    remember = AsyncMock()
    bot = SimpleNamespace(get_cog=lambda _: SimpleNamespace(remember=remember))
    await global_ban(bot, guild, SimpleNamespace(id=7), {})
    remember.assert_not_awaited()
