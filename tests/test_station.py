"""The two table commands open the activity, or say where it can be opened."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from src.cogs.games.station import Station


class FakeInteraction:
    def __init__(self, launch):
        self.user = SimpleNamespace(id=1, display_name="user1")
        self.guild_id = None
        self.guild = None
        self.locale = None
        self.client = SimpleNamespace(get_guild=lambda _: None)
        self.response = SimpleNamespace(
            launch_activity=launch, send_message=AsyncMock()
        )


@pytest.fixture
def cog(monkeypatch):
    async def english(*args, **kwargs):
        return "en"

    monkeypatch.setattr("src.utils.lang_context.interaction_lang", english)
    return Station(SimpleNamespace())


@pytest.mark.parametrize("command", ["roulette", "dive"])
async def test_each_command_launches_the_activity(cog, command):
    interaction = FakeInteraction(AsyncMock())
    await getattr(cog, command).callback(cog, interaction)
    interaction.response.launch_activity.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()


@pytest.mark.parametrize(
    ("command", "table"), [("roulette", "Rust Wheel"), ("dive", "Sunken Bell")]
)
async def test_a_refused_launch_explains_where_to_open_it(cog, command, table):
    refused = discord.HTTPException(
        SimpleNamespace(status=400, reason="Bad Request"), "activity"
    )
    interaction = FakeInteraction(AsyncMock(side_effect=refused))
    await getattr(cog, command).callback(cog, interaction)
    sent = interaction.response.send_message.await_args
    assert table in sent.args[0]
    assert sent.kwargs["ephemeral"] is True


def test_the_commands_keep_their_names_and_lose_the_opponent():
    names = {command.name: command for command in Station.__cog_app_commands__}
    assert set(names) == {"russian-roulette", "deep-sea-oxygen"}
    assert all(not command.parameters for command in names.values())
