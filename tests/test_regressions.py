import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest


def test_cleanup_nonempty_logs():
    from src.services.message_log_service import MessageLogService

    service = MessageLogService()
    service.load_message_log = lambda: {
        "1_2": {"created_at": "2000-01-01T00:00:00+08:00"}
    }
    service.save_message_log = lambda logs: None
    assert service.cleanup_old_logs() == 1


async def test_network_default_session():
    from src.utils.network_optimizer import ConnectionPool
    from src.utils.network_optimizer import NetworkConfig

    pool = ConnectionPool(NetworkConfig())
    try:
        session = await pool.get_session("https://example.com")
        assert not session.closed
    finally:
        await pool.close_all()


async def test_config_missing_file_completes(tmp_path):
    from src.utils.config_optimizer import OptimizedConfigManager

    manager = OptimizedConfigManager(str(tmp_path))
    try:
        assert await asyncio.wait_for(
            manager.load_config("new.json", {"ok": True}), 1
        ) == {"ok": True}
        payload = {"items": [1]}
        await manager.save_config("saved.json", payload)
        payload["items"].append(2)
    finally:
        await manager.close()
    import json

    assert json.loads((tmp_path / "saved.json").read_text()) == {"items": [1]}


def test_unused_type_module_imports():
    importlib.import_module("src.bot_types.bot_types")


async def test_giveaway_restart_keeps_both_views():
    from src.cogs.features.giveaway import Giveaway

    bot = discord.Client(intents=discord.Intents.default())
    cog = object.__new__(Giveaway)
    cog.bot = bot
    cog.service = SimpleNamespace(
        _load=lambda: {
            "first": {"ended": False, "message_id": 111},
            "second": {"ended": False, "message_id": 222},
        }
    )
    try:
        await cog.on_ready()
        assert len(bot.persistent_views) == 2
        views = bot._connection._view_store._views
        assert views[111][(2, "giveaway_enter")].view.giveaway_id == "first"
        assert views[222][(2, "giveaway_enter")].view.giveaway_id == "second"
        await cog.on_ready()
        assert len(bot.persistent_views) == 2
    finally:
        await bot.close()


def make_game():
    from src.services.game_service import RouletteGame

    p1 = SimpleNamespace(id=1, mention="p1", display_name="p1")
    p2 = SimpleNamespace(id=2, mention="p2", display_name="p2")
    game = RouletteGame(SimpleNamespace(id=3, send=AsyncMock()), p1, p2)
    interaction = SimpleNamespace(
        user=p1, response=SimpleNamespace(send_message=AsyncMock())
    )
    return game, interaction


async def test_shuffle_item():
    from src.cogs.games.russian_roulette import RussianRoulette

    game, interaction = make_game()
    game.player1_items = ["命運洗牌"]
    view = RussianRoulette.ItemSelectView(game, None, game.player1_items)
    await view._use_item(interaction, "命運洗牌")
    assert 1 <= game.bullet_position <= 6


async def test_activated_blank_halves_damage():
    from src.cogs.games.russian_roulette import RussianRoulette

    game, interaction = make_game()
    game.player1_items = ["空包彈"]
    game.bullet_position = game.current_chamber = 1
    cog = SimpleNamespace(active_games={})
    itemview = RussianRoulette.ItemSelectView(game, cog, game.player1_items)
    await itemview._use_item(interaction, "空包彈")
    view = RussianRoulette.GameView(game, cog)
    await view.pull_trigger.callback(interaction)
    assert game.player1_chips == 4250


async def test_repeated_initialization_no_task_leak():
    from src.utils.config_optimizer import get_config_manager
    from src.utils.database_manager import get_database_manager
    from src.utils.runtime import close_optimizations
    from src.utils.runtime import initialize_optimizations

    try:
        await initialize_optimizations()
        first = (get_config_manager(), get_database_manager())
        task = first[1]._cleanup_task
        await initialize_optimizations()
        assert first == (get_config_manager(), get_database_manager())
        assert get_database_manager()._cleanup_task is task
    finally:
        await close_optimizations()
    assert task.done()
    assert first[0]._writer_task.done()
    await close_optimizations()


async def test_rate_limit_returns_http_error():
    from src.utils.api_optimizer import APIOptimizer
    from src.utils.api_optimizer import RateLimitError

    optimizer = APIOptimizer(None)
    optimizer.check_rate_limit = AsyncMock(return_value=False)
    with pytest.raises(RateLimitError):
        await optimizer.optimized_send_message(
            SimpleNamespace(send=AsyncMock()), "hello"
        )


async def test_auto_role_verification_member_api():
    from unittest.mock import Mock

    from src.cogs.features.management import Management

    role = object()
    member = Mock(spec=discord.Member)
    member.pending = True
    member.roles = []
    member.guild = SimpleNamespace(id=1, member_count=2, get_role=lambda _: role)
    member.add_roles = AsyncMock()
    cog = object.__new__(Management)
    cog.service = SimpleNamespace(
        config={"1": {"auto_roles": [{"require_verification": True, "role_id": 3}]}}
    )
    await cog.on_member_join(member)
    member.add_roles.assert_not_awaited()
    member.pending = False
    await cog.on_member_update(SimpleNamespace(pending=True), member)
    member.add_roles.assert_awaited_once_with(role, reason="自動角色分配")
