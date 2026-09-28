import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import discord
import pytest

from src.cogs.core.settings import Settings
from src.cogs.features import translate
from src.cogs.features.management import Management
from src.cogs.features.osu_info import OsuInfo


def interaction():
    return SimpleNamespace(
        user=SimpleNamespace(id=42),
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def test_settings_uses_management_service_config():
    config = {
        "9": {
            "welcome": {"channel_id": 123, "message": "hello"},
            "tracked_repos": {"owner/repo": {}},
        }
    }
    management = SimpleNamespace(service=SimpleNamespace(config=config))
    cog = Settings(SimpleNamespace(get_cog=lambda _: management))
    assert cog._get_welcome_status(9) == "[啟用]"
    assert cog._get_repo_count(9) == 1
    assert cog.build_welcome_embed(9).fields[0].value == "<#123>"
    assert cog._get_welcome_status(10) == "[未設定]"


@pytest.mark.parametrize("command", ["osu_bind", "osu_best", "osu_recent"])
async def test_osu_network_runs_off_event_loop(command):
    cog = object.__new__(OsuInfo)
    service = Mock()
    cog.service = service
    event = interaction()
    main = threading.get_ident()

    def user_lookup(username):
        event.response.defer.assert_awaited_once()
        assert threading.get_ident() != main
        return SimpleNamespace(username="player", id=123, avatar_url=None)

    def scores(*args, **kwargs):
        assert threading.get_ident() != main
        return []

    service.api.user.side_effect = user_lookup
    service.api.user_scores.side_effect = scores
    await getattr(cog, command).callback(cog, event, username="player")
    service.api.user.assert_called_once_with("player")
    if command == "osu_bind":
        service.bind.assert_called_once_with(42, "player")
    else:
        service.api.user_scores.assert_called_once()
        assert event.followup.send.call_args.kwargs["embed"].title.startswith("osu!")


async def test_translation_runs_off_event_loop(monkeypatch):
    main = threading.get_ident()

    def translate_text(text):
        assert threading.get_ident() != main
        return "translated"

    monkeypatch.setattr(
        translate,
        "GoogleTranslator",
        Mock(return_value=SimpleNamespace(translate=translate_text)),
    )
    select = translate.LanguageSelect("original")
    select._values = ["en"]
    event = interaction()
    await select.callback(event)
    event.response.defer.assert_awaited_once()
    assert event.followup.send.call_args.kwargs["embed"].fields[1].value == "translated"


@pytest.mark.parametrize("content_type", [None, "image/png"])
async def test_emoji_upload_acknowledges_before_network(content_type):
    cog = object.__new__(Management)
    event = interaction()
    event.guild_id = 9
    event.user = Mock(spec=discord.Member)
    event.user.guild_permissions.manage_emojis = True
    event.guild = SimpleNamespace(create_custom_emoji=AsyncMock(return_value="emoji"))

    async def read():
        event.response.defer.assert_awaited_once()
        return b"image"

    image = SimpleNamespace(content_type=content_type, read=AsyncMock(side_effect=read))
    await cog.emoji_upload.callback(cog, event, "name", image)
    if content_type is None:
        image.read.assert_not_awaited()
        event.response.send_message.assert_awaited_once()
    else:
        event.followup.send.assert_awaited_once()
        event.response.send_message.assert_not_awaited()


@pytest.mark.parametrize(
    "modal_name,operation,result",
    [
        ("MuteModal", "execute_mute", (True, "")),
        ("BanModal", "execute_ban", (True, "")),
        ("WarnModal", "execute_warn", True),
    ],
)
async def test_moderation_defers_before_network(
    monkeypatch, modal_name, operation, result
):
    from src.cogs.core import report

    event = interaction()
    event.guild = SimpleNamespace(name="test")
    event.guild_id = 9
    event.user = Mock(spec=discord.Member)

    async def execute(*args):
        event.response.defer.assert_awaited_once()
        return result

    service = Mock()
    setattr(service, operation, AsyncMock(side_effect=execute))
    monkeypatch.setattr(report, "_service", service)
    modal = getattr(report, modal_name)(Mock(), Mock())
    await modal.on_submit(event)
    getattr(service, operation).assert_awaited_once()
    event.followup.send.assert_awaited_once()
    event.response.send_message.assert_not_awaited()
