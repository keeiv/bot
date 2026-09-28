from datetime import datetime
from datetime import timezone
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pytest

from src.cogs.features.user_server_info import UserServerInfo
from src.services.achievement_service import AchievementService
from src.services.osu_service import OsuService


def setup_case():
    achievement = Mock(spec=AchievementService)
    achievement.get_progress.return_value = {
        "percentage": 50,
        "unlocked": 1,
        "total": 2,
    }
    achievement.get_progress_bar.return_value = "progress"
    osu = Mock(spec=OsuService)
    osu.get_bound_username.return_value = "bound-player"
    cogs = {
        "Achievements": SimpleNamespace(service=achievement, unlock_achievement=Mock()),
        "OsuInfo": SimpleNamespace(service=osu),
    }
    cog = UserServerInfo(SimpleNamespace(get_cog=cogs.get))
    user = SimpleNamespace(
        id=42, display_name="tester", created_at=datetime.now(timezone.utc), bot=False
    )
    interaction = SimpleNamespace(
        user=user,
        guild=Mock(),
        guild_id=9,
        response=SimpleNamespace(
            defer=AsyncMock(), send_message=AsyncMock(), is_done=Mock(return_value=True)
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )

    async def get_member(*args):
        interaction.response.defer.assert_awaited_once()
        return None

    cog.get_member = get_member
    cog.build_user_info_view = Mock(return_value=Mock())
    return cog, interaction, achievement, osu


async def test_services_and_defer_before_lookup():
    cog, interaction, achievement, osu = setup_case()
    main_thread = threading.get_ident()

    def lookup(username):
        assert threading.get_ident() != main_thread
        assert username == "bound-player"
        return SimpleNamespace(username=username, id=123, statistics=SimpleNamespace())

    osu.api.user.side_effect = lookup
    await cog.user_info.callback(cog, interaction)
    achievement.get_progress.assert_called_once_with(42, 9)
    assert "bound-player" in cog.build_user_info_view.call_args.args[7]
    interaction.followup.send.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()


@pytest.mark.parametrize("disabled", [False, True])
async def test_api_failure_preserves_binding(disabled):
    cog, interaction, _, osu = setup_case()
    if disabled:
        osu.ensure_api.side_effect = RuntimeError("disabled")
    else:
        osu.api.user.side_effect = TimeoutError()
    await cog.user_info.callback(cog, interaction)
    assert "已綁定: bound-player" in cog.build_user_info_view.call_args.args[7]
    interaction.followup.send.assert_awaited_once()


async def test_unbound_user_does_not_need_api():
    cog, interaction, _, osu = setup_case()
    osu.get_bound_username.return_value = None
    await cog.user_info.callback(cog, interaction)
    osu.ensure_api.assert_not_called()
    osu.api.user.assert_not_called()
    assert cog.build_user_info_view.call_args.args[7] is None


async def test_expired_interaction_does_not_retry_response():
    cog, interaction, _, osu = setup_case()
    interaction.response.defer.side_effect = discord.NotFound(
        SimpleNamespace(status=404, reason="Not Found"),
        {"code": 10062, "message": "Unknown interaction"},
    )
    await cog.user_info.callback(cog, interaction)
    interaction.response.send_message.assert_not_awaited()
    interaction.followup.send.assert_not_awaited()
    osu.get_bound_username.assert_not_called()
