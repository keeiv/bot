import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient
from aiohttp.test_utils import TestServer
import discord
import pytest

from src.cogs.core.dashboard_api import DashboardAPI
from src.services.age_guard_service import AgeGuardService
from src.services.audit_log_service import AuditLogService
from src.services.dashboard_service import DashboardService
from src.services.dashboard_service import MAPPINGS
from src.services.dashboard_service import revision
from src.services.management_service import ManagementService
from src.services.temp_voice_service import TempVoiceService
from src.services.ticket_service import TicketService
from src.utils.anti_spam import AntiSpamManager

GUILD = 123456789012345678
CHANNEL = 223456789012345678
ROLE = 323456789012345678
SECRET = "test-secret-" * 4


@pytest.fixture
def setup_bot():
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = CHANNEL
    channel.permissions_for.return_value = discord.Permissions.all()
    role = MagicMock(spec=discord.Role)
    role.is_default.return_value = False
    role.managed = False
    role.permissions = discord.Permissions.none()
    role.__ge__.return_value = False
    guild = MagicMock()
    guild.id = GUILD
    guild.get_channel.return_value = channel
    guild.get_role.return_value = role
    guild.me.guild_permissions = discord.Permissions.all()
    guild.fetch_member = AsyncMock(
        return_value=SimpleNamespace(guild_permissions=discord.Permissions.all())
    )
    cogs = {
        "Management": SimpleNamespace(service=ManagementService()),
        "AntiSpam": SimpleNamespace(manager=AntiSpamManager()),
        "AgeGuard": SimpleNamespace(service=AgeGuardService()),
        "TempVoice": SimpleNamespace(service=TempVoiceService()),
        "Ticket": SimpleNamespace(service=TicketService()),
        "GithubWatch": SimpleNamespace(_config={}, _last_poll={}),
        "AuditLog": SimpleNamespace(service=AuditLogService()),
    }
    bot = MagicMock()
    bot.get_cog.side_effect = cogs.get
    bot.get_guild.return_value = guild
    bot.guilds = [guild]
    bot.is_ready.return_value = True
    return bot, guild, cogs


def test_all_sections_roundtrip_and_preserve_other_guilds(setup_bot):
    bot, guild, cogs = setup_bot
    service = DashboardService(bot)
    cogs["Management"].service.config["other"] = {"welcome": {"message": "keep"}}
    cogs["Management"].service.config[str(GUILD)] = {"tracked_repos": {"keep": {}}}
    for section in MAPPINGS:
        values = service.read(GUILD)[section]
        values["enabled"] = False
        service.write(guild, section, values)
        assert service.read(GUILD)[section]["enabled"] is False
        assert (
            json.loads(open(MAPPINGS[section][1], encoding="utf-8").read()) is not None
        )
    assert cogs["Management"].service.config["other"]["welcome"]["message"] == "keep"
    assert cogs["Management"].service.config[str(GUILD)]["tracked_repos"] == {
        "keep": {}
    }


def test_welcome_reaches_live_cog_and_disk(setup_bot):
    bot, guild, cogs = setup_bot
    service = DashboardService(bot)
    values = service.read(GUILD)["welcome"]
    values.update(
        enabled=True,
        channel=str(CHANNEL),
        autoRole=str(ROLE),
        message="歡迎 {username}",
    )
    service.write(guild, "welcome", values)
    stored = cogs["Management"].service.get_welcome_config(str(GUILD))
    assert stored["channel_id"] == CHANNEL
    assert stored["auto_role_id"] == ROLE
    assert ManagementService().get_welcome_config(str(GUILD)) == stored


@pytest.mark.parametrize(
    "field,value",
    [
        ("floodMessages", True),
        ("floodMessages", 0),
        ("action", "execute"),
        ("unknown", 1),
    ],
)
def test_reject_invalid_settings(setup_bot, field, value):
    bot, guild, _ = setup_bot
    service = DashboardService(bot)
    values = service.read(GUILD)["antispam"]
    values[field] = value
    with pytest.raises(ValueError):
        service.write(guild, "antispam", values)


def test_reject_foreign_channel_and_unsafe_template(setup_bot):
    bot, guild, _ = setup_bot
    service = DashboardService(bot)
    values = service.read(GUILD)["welcome"]
    values.update(enabled=True, channel=str(CHANNEL))
    guild.get_channel.return_value = None
    with pytest.raises(ValueError, match="頻道"):
        service.write(guild, "welcome", values)
    values.update(enabled=False, channel="", message="{user.__class__}")
    with pytest.raises(ValueError, match="變數"):
        service.write(guild, "welcome", values)


def test_failed_disk_commit_does_not_change_live_state(setup_bot, monkeypatch):
    bot, guild, _ = setup_bot
    service = DashboardService(bot)
    before = service.read(GUILD)
    values = copy.deepcopy(before["antispam"])
    values["enabled"] = False
    monkeypatch.setattr(
        "src.services.dashboard_service.os.replace",
        MagicMock(side_effect=OSError("disk full")),
    )
    with pytest.raises(OSError):
        service.write(guild, "antispam", values)
    assert service.read(GUILD) == before


async def test_http_permissions_revision_and_save(setup_bot):
    bot, guild, _ = setup_bot
    api = DashboardAPI(bot)
    async with TestClient(TestServer(api.create_app(SECRET))) as client:
        url = f"/guilds/{GUILD}/settings"
        assert (await client.get(url)).status == 401
        headers = {"X-Bot-Secret": SECRET, "X-Discord-User": str(ROLE)}
        guild.fetch_member.return_value.guild_permissions = discord.Permissions.none()
        assert (await client.get(url, headers=headers)).status == 403
        guild.fetch_member.return_value.guild_permissions = discord.Permissions.all()
        current = await (await client.get(url, headers=headers)).json()
        values = current["settings"]["antispam"]
        values["enabled"] = False
        payload = {
            "section": "antispam",
            "values": values,
            "revision": current["revision"],
        }
        saved = await client.patch(url, headers=headers, json=payload)
        assert saved.status == 200
        updated = await saved.json()
        assert updated["settings"]["antispam"]["enabled"] is False
        assert updated["revision"] == revision(updated["settings"])
        assert (await client.patch(url, headers=headers, json=payload)).status == 409
        assert (await client.patch(url, headers=headers, data="not json")).status == 400
        bot.is_ready.return_value = False
        assert (await client.get(url, headers=headers)).status == 503


async def test_api_disabled_by_default(setup_bot, monkeypatch):
    monkeypatch.delenv("BOT_API_ENABLED", raising=False)
    api = DashboardAPI(setup_bot[0])
    await api.cog_load()
    assert api.runner is None


async def test_status_reports_safe_runtime_metrics(setup_bot, monkeypatch):
    bot, guild, _ = setup_bot
    bot.latency = 0.042
    bot.shard_count = None
    guild.member_count = 12
    monkeypatch.setenv("BOT_REGION", "Taipei, Taiwan")
    api = DashboardAPI(bot)
    headers = {"X-Bot-Secret": SECRET}
    async with TestClient(TestServer(api.create_app(SECRET))) as client:
        response = await client.get("/status", headers=headers)
        assert response.status == 200
        data = await response.json()
        assert data["online"] is True
        assert data["latencyMs"] == 42
        assert data["guildCount"] == 1
        assert data["memberCount"] == 12
        assert data["region"] == "Taipei, Taiwan"
        assert "token" not in str(data).lower()


async def test_api_rejects_weak_secret(setup_bot, monkeypatch):
    monkeypatch.setenv("BOT_API_ENABLED", "true")
    monkeypatch.setenv("BOT_API_SECRET", "short")
    with pytest.raises(RuntimeError, match="32"):
        await DashboardAPI(setup_bot[0]).cog_load()


@pytest.mark.parametrize(
    "section,fields",
    [
        ("ageguard", {"adultRole": str(ROLE), "punishRole": str(ROLE)}),
        ("tempvoice", {"triggerChannel": str(CHANNEL)}),
        ("ticket", {"channel": str(CHANNEL), "staffRole": str(ROLE)}),
        ("github", {"channel": str(CHANNEL), "owner": "keeiv", "repo": "bot"}),
        ("audit", {"channel": str(CHANNEL)}),
    ],
)
def test_enabled_module_uses_real_store(setup_bot, section, fields):
    bot, guild, _ = setup_bot
    if section == "tempvoice":
        voice = MagicMock(spec=discord.VoiceChannel)
        voice.category_id = None
        voice.permissions_for.return_value = discord.Permissions.all()
        guild.get_channel.return_value = voice
    service = DashboardService(bot)
    values = service.read(GUILD)[section]
    values.update(enabled=True, **fields)
    service.write(guild, section, values)
    assert service.read(GUILD)[section] == values


async def test_ticket_deploy_is_repeatable_and_disabled_is_rejected(setup_bot):
    bot, guild, _ = setup_bot
    api = DashboardAPI(bot)
    values = api.service.read(GUILD)["ticket"]
    values.update(enabled=True, channel=str(CHANNEL), staffRole=str(ROLE))
    api.service.write(guild, "ticket", values)
    channel = guild.get_channel(CHANNEL)
    message = SimpleNamespace(id=423456789012345678, edit=AsyncMock())
    channel.send = AsyncMock(return_value=message)
    channel.fetch_message = AsyncMock(return_value=message)
    headers = {"X-Bot-Secret": SECRET, "X-Discord-User": str(ROLE)}
    async with TestClient(TestServer(api.create_app(SECRET))) as client:
        url = f"/guilds/{GUILD}/panel"
        assert (await client.post(url, headers=headers)).status == 200
        assert (await client.post(url, headers=headers)).status == 200
        channel.send.assert_awaited_once()
        message.edit.assert_awaited_once()
        values["enabled"] = False
        api.service.write(guild, "ticket", values)
        assert (await client.post(url, headers=headers)).status == 400


async def test_github_interval_is_per_guild(setup_bot, monkeypatch):
    from src.cogs.features.github_watch import GithubWatch

    cfg = {"enabled": True, "owner": "keeiv", "repo": "bot", "channel_id": CHANNEL}
    cog = object.__new__(GithubWatch)
    cog._config = {
        "1": {**cfg, "interval_minutes": 2},
        "2": {**cfg, "interval_minutes": 10},
    }
    cog._last_poll = {}
    cog._fetch_latest_commit = AsyncMock(return_value=None)
    monkeypatch.setattr("src.cogs.features.github_watch.time.monotonic", lambda: 1000)
    await GithubWatch._poll_task.coro(cog)
    assert cog._fetch_latest_commit.await_count == 2
    monkeypatch.setattr("src.cogs.features.github_watch.time.monotonic", lambda: 1120)
    await GithubWatch._poll_task.coro(cog)
    assert cog._fetch_latest_commit.await_count == 3
