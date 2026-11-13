from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord

from src.cogs.features.user_server_info import UserServerInfo
from src.services.achievement_service import AchievementService


def setup_case():
    achievement = Mock(spec=AchievementService)
    achievement.get_progress.return_value = {
        "percentage": 50,
        "unlocked": 1,
        "total": 2,
    }
    achievement.get_progress_bar.return_value = "progress"
    cogs = {
        "Achievements": SimpleNamespace(service=achievement, unlock_achievement=Mock()),
    }
    cog = UserServerInfo(SimpleNamespace(get_cog=cogs.get))
    user = SimpleNamespace(
        id=42, display_name="tester", created_at=datetime.now(timezone.utc), bot=False
    )
    interaction = SimpleNamespace(
        user=user,
        guild=Mock(),
        guild_id=9,
        locale=discord.Locale.taiwan_chinese,
        client=SimpleNamespace(get_guild=lambda guild_id: object()),
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
    return cog, interaction, achievement


async def test_services_and_defer_before_lookup():
    cog, interaction, achievement = setup_case()
    await cog.user_info.callback(cog, interaction)
    achievement.get_progress.assert_called_once_with(42, 9)
    assert "progress" in cog.build_user_info_view.call_args.args[6]
    interaction.followup.send.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()


async def test_expired_interaction_does_not_retry_response():
    cog, interaction, achievement = setup_case()
    interaction.response.defer.side_effect = discord.NotFound(
        SimpleNamespace(status=404, reason="Not Found"),
        {"code": 10062, "message": "Unknown interaction"},
    )
    await cog.user_info.callback(cog, interaction)
    interaction.response.send_message.assert_not_awaited()
    interaction.followup.send.assert_not_awaited()
    achievement.get_progress.assert_not_called()
