"""Dashboard privacy, validation, and persistent observation regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient
from aiohttp.test_utils import TestServer
import discord
import pytest

from src.cogs.core.dashboard_api import DashboardAPI
from src.services.dashboard_account import DashboardAccount
from src.services.dashboard_checks import inspect_settings
from src.services.dashboard_history import StatusHistory
from src.services.dashboard_service import MAPPINGS


def test_history_survives_restart_retains_gaps_and_prunes_old_samples():
    history = StatusHistory()
    history.record(True, 42, now=1000020)
    history.record(False, 999, now=1000080)
    history.record(True, 51, now=1000320)
    history.record(True, 52, now=1000321)  # One observation per minute.
    loaded = StatusHistory().read(now=1000380)
    assert len(loaded["samples"]) == 3
    assert loaded["samples"][1]["latencyMs"] is None
    assert loaded["samples"][-1]["latencyMs"] == 52
    assert loaded["samples"][-1]["timestamp"] - loaded["samples"][1]["timestamp"] == 240
    history.record(True, 40, now=1700000)
    assert len(history.read(hours=168, now=1700001)["samples"]) == 1


def account_bot():
    osu = SimpleNamespace(service=MagicMock())
    osu.service.get_bound_username.side_effect = lambda actor: (
        "Alex" if actor == 123456789012345678 else None
    )
    hoyo = SimpleNamespace(service=MagicMock())
    hoyo.service.get_bound_user.side_effect = lambda actor: (
        {
            "encrypted_cookie": "must-never-leave-server",
            "region": "global",
            "game_accounts": [{"uid": 1000, "nickname": "Alex", "secret": "private"}],
        }
        if actor == 123456789012345678
        else None
    )
    hoyo.service.bind_account = AsyncMock(return_value=[])
    cogs = {"OsuInfo": osu, "GenshinCog": hoyo}
    bot = MagicMock()
    bot.get_cog.side_effect = cogs.get
    return bot, osu.service, hoyo.service


def test_account_response_is_scoped_and_strips_all_credentials():
    bot, _, _ = account_bot()
    service = DashboardAccount(bot)
    own = service.read(123456789012345678)
    assert own["hoyolab"]["accounts"][0]["uid"] == 1000
    assert "must-never" not in str(own)
    assert "secret" not in str(own)
    assert service.read(223456789012345678)["osu"]["username"] is None
    assert not service.read(223456789012345678)["hoyolab"]["bound"]


async def test_account_binding_validates_before_write_and_sanitizes_failure():
    bot, osu, hoyo = account_bot()
    service = DashboardAccount(bot)
    actor = 123456789012345678
    osu.api.user.return_value = SimpleNamespace(username="CanonicalName")
    await service.update(actor, {"game": "osu", "action": "bind", "username": "Alex"})
    osu.bind.assert_called_once_with(actor, "CanonicalName")
    with pytest.raises(ValueError):
        await service.update(actor, {"game": "osu", "action": "unbind", "userId": 111})
    hoyo.bind_account.side_effect = ValueError("private-cookie-value")
    with pytest.raises(ValueError, match="^Unable to verify HoYoLAB account$"):
        await service.update(
            actor,
            {
                "game": "hoyolab",
                "action": "bind",
                "cookie": "private-cookie-value",
                "region": "global",
            },
        )
    hoyo.bind_account.assert_awaited_once_with(actor, "private-cookie-value", "global")
    with pytest.raises(ValueError, match="Invalid HoYoLAB"):
        await service.update(
            actor,
            {"game": "hoyolab", "action": "bind", "cookie": "test", "region": "other"},
        )


async def test_new_routes_require_secret_verified_actor_and_apply_rate_limit():
    bot, _, _ = account_bot()
    bot.is_ready.return_value = True
    api = DashboardAPI(bot)
    api.history = StatusHistory()
    async with TestClient(TestServer(api.create_app("secret"))) as client:
        for path in (
            "/account",
            "/status/history",
            "/guilds/123456789012345678/resources",
        ):
            assert (await client.get(path)).status == 401
        headers = {"X-Bot-Secret": "secret"}
        assert (await client.get("/account", headers=headers)).status == 403
        headers["X-Discord-User"] = "123456789012345678"
        response = await client.get("/account", headers=headers)
        assert response.status == 200
        assert "encrypted_cookie" not in await response.text()
        payload = {"game": "osu", "action": "unbind"}
        assert (
            await client.post("/account", headers=headers, json=payload)
        ).status == 200
        assert (
            await client.post("/account", headers=headers, json=payload)
        ).status == 429
        assert (
            await client.get("/status/history?hours=999", headers=headers)
        ).status == 400
        bot.is_ready.return_value = False
        assert (await client.get("/status/history", headers=headers)).status == 200
        assert (await client.get("/account", headers=headers)).status == 503


def test_diagnostics_explain_permissions_without_writing():
    service = MagicMock()
    service.bot.intents.message_content = False
    service.validate.return_value = None
    guild = MagicMock()
    guild.me.guild_permissions = discord.Permissions.none()
    settings = {section: {"enabled": False} for section in MAPPINGS}
    settings["antispam"] = {
        "enabled": True,
        "action": "ban",
        "inviteAutoDelete": True,
        "raidEnabled": False,
    }
    checks = inspect_settings(service, guild, settings)["checks"]
    assert any(
        check.get("detail") == "ban_members" and not check["ok"] for check in checks
    )
    assert any(
        check.get("detail") == "message_content" and not check["ok"] for check in checks
    )
    service.write.assert_not_called()
    with pytest.raises(ValueError):
        inspect_settings(service, guild, {"unknown": {}})
