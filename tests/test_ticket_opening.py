"""Opening a ticket: a double click makes one thread, and a thread that cannot be recorded is removed."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pytest

from src.cogs.features import ticket as module
from src.cogs.features.ticket import TicketOpenView
from src.services.ticket_service import TicketService
from src.utils.document_store import StorageError

GUILD = 900
CHANNEL = 901
USER = 902


@pytest.fixture
def service(monkeypatch):
    fresh = TicketService()
    fresh.save_guild_config(GUILD, CHANNEL, 903, 904)
    monkeypatch.setattr(module, "_service", fresh)
    monkeypatch.setattr(module, "_opening", {})
    return fresh


def make_channel():
    channel = Mock(spec=discord.TextChannel)
    channel.id = CHANNEL
    made = []

    async def create_thread(**_):
        await asyncio.sleep(
            0.05
        )  # Discord takes a moment; the second click arrives meanwhile
        thread = Mock(spec=discord.Thread)
        thread.id = 950 + len(made)
        thread.mention = f"<#{thread.id}>"
        thread.send = AsyncMock()
        thread.add_user = AsyncMock()
        thread.delete = AsyncMock()
        made.append(thread)
        return thread

    channel.create_thread = create_thread
    return channel, made


def click(channel):
    guild = SimpleNamespace(
        id=GUILD, name="test guild", get_role=lambda _: None, me=None
    )
    return SimpleNamespace(
        guild=guild,
        guild_id=GUILD,
        channel=channel,
        channel_id=CHANNEL,
        user=SimpleNamespace(id=USER, display_name="kei", mention="<@902>"),
        locale=None,
        client=SimpleNamespace(get_guild=lambda _: None),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


async def press(view, interaction):
    await TicketOpenView.open_button(view, interaction, None)


@pytest.fixture(autouse=True)
def english(monkeypatch):
    async def lang(*_args, **_kwargs):
        return "en"

    monkeypatch.setattr("src.utils.lang_context.interaction_lang", lang)


async def test_a_double_click_opens_one_ticket(service):
    channel, made = make_channel()
    view = TicketOpenView()
    first, second = click(channel), click(channel)
    await asyncio.gather(press(view, first), press(view, second))
    assert len(made) == 1
    assert service.find_open_ticket(GUILD, USER) == made[0].id
    told = second.followup.send.await_args.args[0]
    assert str(made[0].id) in told


async def test_a_thread_that_cannot_be_recorded_is_removed(service, monkeypatch):
    channel, made = make_channel()

    def broken(**_):
        raise StorageError("MySQL commit failed")

    monkeypatch.setattr(service, "create_ticket", broken)
    view = TicketOpenView()
    interaction = click(channel)
    await press(view, interaction)
    assert len(made) == 1
    made[0].delete.assert_awaited_once()
    assert service.find_open_ticket(GUILD, USER) is None
    assert interaction.followup.send.await_args.kwargs.get("ephemeral") is True
