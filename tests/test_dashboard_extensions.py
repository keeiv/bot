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


# ── Endfield in the account centre ────────────────────────────────
def endfield_bot(service):
    cog = SimpleNamespace(service=service)
    return SimpleNamespace(get_cog={"EndfieldCog": cog}.get, dispatch=MagicMock())


def endfield_service(uid=None, account=False):
    return SimpleNamespace(
        bound_uid=MagicMock(return_value=uid),
        has_account=MagicMock(return_value=account),
        profile=AsyncMock(),
        bind=MagicMock(),
        unbind=MagicMock(),
        link_account=AsyncMock(),
    )


def test_the_account_response_says_a_token_is_linked_but_not_what_it_is():
    bot = endfield_bot(endfield_service("4225399080", True))
    assert DashboardAccount(bot).read("7")["endfield"] == {
        "available": True,
        "uid": "4225399080",
        "account": True,
    }


async def test_endfield_binds_a_uid_after_checking_it():
    from src.services.endfield_service import EndfieldError

    service = endfield_service()
    bot = endfield_bot(service)
    accounts = DashboardAccount(bot)
    request = {"game": "endfield", "action": "bind", "uid": " 4225399080 "}
    await accounts.update("7", request)
    service.bind.assert_called_once_with(7, "4225399080")
    bot.dispatch.assert_called_once_with("endfield_bound", 7)
    service.bind.reset_mock()
    service.profile.side_effect = EndfieldError("not_found")
    with pytest.raises(ValueError, match="Unable to find Endfield player"):
        await accounts.update("7", request)
    service.bind.assert_not_called()
    with pytest.raises(ValueError, match="Invalid Endfield UID"):
        await accounts.update("7", {**request, "uid": "../etc"})


async def test_endfield_token_failures_name_no_credential():
    from src.services.endfield_service import EndfieldError

    service = endfield_service()
    accounts = DashboardAccount(endfield_bot(service))
    request = {"game": "endfield", "action": "bind", "token": "private-token"}
    await accounts.update("7", request)
    service.link_account.assert_awaited_once_with(7, "private-token")
    for failure in (EndfieldError("bad_token"), RuntimeError("private-token")):
        service.link_account.side_effect = failure
        with pytest.raises(ValueError) as caught:
            await accounts.update("7", request)
        assert str(caught.value) == "Unable to verify SKPORT account"


@pytest.mark.parametrize(
    "body",
    [
        {"game": "endfield", "action": "bind"},
        {"game": "endfield", "action": "bind", "uid": "1", "token": "x"},
        {"game": "endfield", "action": "bind", "cookie": "x"},
        {"game": "endfield", "action": "unbind", "uid": "1"},
    ],
)
async def test_endfield_requests_must_have_the_exact_fields(body):
    service = endfield_service()
    with pytest.raises(ValueError, match="Invalid account request"):
        await DashboardAccount(endfield_bot(service)).update("7", body)
    service.bind.assert_not_called()
    service.link_account.assert_not_awaited()


async def test_endfield_unbind_tells_the_ai():
    service = endfield_service("4225399080")
    bot = endfield_bot(service)
    await DashboardAccount(bot).update("7", {"game": "endfield", "action": "unbind"})
    service.unbind.assert_called_once_with("7")
    bot.dispatch.assert_called_once_with("endfield_unbound", 7)
