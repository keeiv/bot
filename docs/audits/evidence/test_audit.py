import asyncio
import importlib
import pkgutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

async def test_all_extensions_registered():
    from src.bot import Bot
    bot = Bot()
    expected = {m.name for m in pkgutil.walk_packages(['src/cogs'], 'src.cogs.') if not m.ispkg}
    try:
        async with bot:
            await bot.load_cogs()
            assert set(bot.extensions) == expected
    finally:
        await bot.close()

def test_cleanup_nonempty_logs():
    from src.services.message_log_service import MessageLogService
    service = MessageLogService()
    service.load_message_log = lambda: {'1_2': {'created_at':'2000-01-01T00:00:00+08:00'}}
    service.save_message_log = lambda logs: None
    assert service.cleanup_old_logs() == 1

async def test_network_default_session():
    from src.utils.network_optimizer import ConnectionPool, NetworkConfig
    pool = ConnectionPool(NetworkConfig())
    try:
        session = await pool.get_session('https://example.com')
        assert not session.closed
    finally:
        await pool.close_all()

def test_config_missing_file_completes(tmp_path):
    code = 'import asyncio\nfrom src.utils.config_optimizer import OptimizedConfigManager\nasync def run():\n m=OptimizedConfigManager('+repr(str(tmp_path))+')\n await m.load_config("new.json", {"ok":True})\nasyncio.run(run())'
    subprocess.run([sys.executable, '-c', code], timeout=3, check=True, capture_output=True)

def test_unused_type_module_imports():
    importlib.import_module('src.bot_types.bot_types')

async def test_giveaway_restart_keeps_both_views():
    from src.cogs.features.giveaway import GiveawayView
    bot = discord.Client(intents=discord.Intents.none())
    first, second = GiveawayView('first'), GiveawayView('second')
    bot.add_view(first)
    bot.add_view(second)
    try:
        assert len(bot.persistent_views) == 2
    finally:
        await bot.close()

def make_game():
    from src.services.game_service import RouletteGame
    p1=SimpleNamespace(id=1,mention='p1',display_name='p1')
    p2=SimpleNamespace(id=2,mention='p2',display_name='p2')
    game=RouletteGame(SimpleNamespace(id=3,send=AsyncMock()),p1,p2)
    interaction=SimpleNamespace(user=p1,response=SimpleNamespace(send_message=AsyncMock()))
    return game,interaction

async def test_shuffle_item():
    from src.cogs.games.russian_roulette import RussianRoulette
    game,interaction=make_game()
    game.player1_items=['命運洗牌']
    view=RussianRoulette.ItemSelectView(game,None,game.player1_items)
    await view._use_item(interaction,'命運洗牌')
    assert 1 <= game.bullet_position <= 6

async def test_activated_blank_halves_damage():
    from src.cogs.games.russian_roulette import RussianRoulette
    game,interaction=make_game()
    game.player1_items=['空包彈']
    game.bullet_position=game.current_chamber=1
    cog=SimpleNamespace(active_games={})
    itemview=RussianRoulette.ItemSelectView(game,cog,game.player1_items)
    await itemview._use_item(interaction,'空包彈')
    view=RussianRoulette.GameView(game,cog)
    await view.pull_trigger.callback(interaction)
    assert game.player1_chips == 4250

async def test_repeated_initialization_no_task_leak():
    from src.main import initialize_optimizations
    await initialize_optimizations()
    await asyncio.sleep(0)
    first=len(asyncio.all_tasks())
    await initialize_optimizations()
    await asyncio.sleep(0)
    assert len(asyncio.all_tasks()) == first

async def test_rate_limit_returns_http_error():
    from src.utils.api_optimizer import APIOptimizer
    optimizer=APIOptimizer(None)
    optimizer.check_rate_limit=AsyncMock(return_value=False)
    with pytest.raises(discord.HTTPException):
        await optimizer.optimized_send_message(SimpleNamespace(send=AsyncMock()),'hello')

async def test_auto_role_verification_member_api():
    from src.cogs.features.management import Management
    # A spec prevents a mock from inventing a nonexistent Discord API field.
    from unittest.mock import Mock
    member=Mock(spec=discord.Member)
    member.guild=SimpleNamespace(id=1,member_count=2,get_role=lambda _:None)
    cog=object.__new__(Management)
    cog.service=SimpleNamespace(config={'1':{'auto_roles':[{'require_verification':True,'role_id':3}]}})
    await cog.on_member_join(member)
