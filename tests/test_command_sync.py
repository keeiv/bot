"""Syncing global commands keeps the activity's Entry Point command."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from discord import app_commands
import pytest

from src.utils.command_sync import entry_points
from src.utils.command_sync import sync_global

APP_ID = 1464919774655156224
ENTRY = {
    "id": "1500000000000000001",
    "application_id": str(APP_ID),
    "version": "1500000000000000002",
    "name": "launch",
    "description": "",
    "type": 4,
    "handler": 2,
    "integration_types": [0, 1],
    "contexts": [0, 1, 2],
    "default_member_permissions": None,
}


def slash(name):
    return {
        "id": "1500000000000000100",
        "application_id": str(APP_ID),
        "version": "1",
        "name": name,
        "description": "d",
        "type": 1,
    }


@pytest.fixture
async def tree():
    client = discord.Client(intents=discord.Intents.none())
    client._connection.application_id = APP_ID
    made = app_commands.CommandTree(client)

    @made.command(name="ping", description="Ping")
    async def ping(interaction: discord.Interaction) -> None:
        """Answer."""

    yield made
    await client.close()


def test_entry_points_keep_only_what_an_overwrite_accepts():
    kept = entry_points([slash("ping"), ENTRY])
    assert kept == [
        {
            "id": ENTRY["id"],
            "name": "launch",
            "description": "",
            "type": 4,
            "handler": 2,
            "integration_types": [0, 1],
            "contexts": [0, 1, 2],
        }
    ]
    assert entry_points([slash("ping")]) == []


async def test_the_entry_point_rides_along_with_the_bots_commands(tree):
    http = tree.client.http
    http.get_global_commands = AsyncMock(return_value=[slash("ping"), ENTRY])
    http.bulk_upsert_global_commands = AsyncMock(return_value=[slash("ping"), ENTRY])
    synced = await sync_global(tree)
    payload = http.bulk_upsert_global_commands.await_args.kwargs["payload"]
    assert [item["name"] for item in payload] == ["ping", "launch"]
    assert payload[1]["type"] == 4 and payload[1]["id"] == ENTRY["id"]
    assert [command.name for command in synced] == ["ping"]


async def test_without_an_entry_point_the_payload_is_discord_pys_own(tree):
    http = tree.client.http
    http.get_global_commands = AsyncMock(return_value=[slash("old")])
    http.bulk_upsert_global_commands = AsyncMock(return_value=[slash("ping")])
    await sync_global(tree)
    payload = http.bulk_upsert_global_commands.await_args.kwargs["payload"]
    expected = [command.to_dict(tree) for command in tree._get_all_commands()]
    assert payload == expected


async def test_an_invalid_payload_is_reported_like_discord_py_does(tree):
    http = tree.client.http
    http.get_global_commands = AsyncMock(return_value=[])
    response = SimpleNamespace(status=400, reason="Bad Request")
    http.bulk_upsert_global_commands = AsyncMock(
        side_effect=discord.HTTPException(response, {"code": 50035, "message": "x"})
    )
    with pytest.raises(app_commands.CommandSyncFailure):
        await sync_global(tree)
