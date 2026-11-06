"""Regressions for the 2026-11-06 review: each test fails on the code before the fix."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest


def interaction_in(guild_id, user_id=4242):
    sent = []
    return (
        SimpleNamespace(
            guild_id=guild_id,
            guild=SimpleNamespace(id=guild_id),
            user=SimpleNamespace(id=user_id),
            locale=discord.Locale.taiwan_chinese,
            client=SimpleNamespace(get_guild=lambda _: None),
            response=SimpleNamespace(
                send_message=AsyncMock(side_effect=lambda *a, **k: sent.append(a)),
                defer=AsyncMock(),
            ),
            followup=SimpleNamespace(
                send=AsyncMock(side_effect=lambda *a, **k: sent.append(a))
            ),
        ),
        sent,
    )


# ── giveaways belong to their own server ──────────────────────────
def giveaway_cog():
    from src.cogs.features.giveaway import Giveaway
    from src.services.giveaway_service import GiveawayService

    cog = object.__new__(Giveaway)
    cog.bot = SimpleNamespace(get_channel=lambda _: None)
    cog.service = GiveawayService()
    cog._end_giveaway = AsyncMock()
    return cog


def make_giveaway(service, gid, guild_id, ended):
    service.create(
        gid,
        {
            "guild_id": guild_id,
            "channel_id": 5,
            "message_id": 6,
            "prize": "Nitro",
            "winners": 1,
            "ended": ended,
            "participants": ["1", "2", "attacker"],
            "winner_ids": ["1"],
            "host_id": 9,
            "end_time": 0,
        },
    )


async def test_another_servers_giveaway_cannot_be_rerolled_or_ended():
    from src.cogs.features.giveaway import Giveaway

    cog = giveaway_cog()
    make_giveaway(cog.service, "222_1", 222, ended=True)
    make_giveaway(cog.service, "222_2", 222, ended=False)
    outsider, _ = interaction_in(111)
    for _ in range(20):
        await Giveaway.reroll_cmd.callback(cog, outsider, "222_1", None)
    assert cog.service.get("222_1")["winner_ids"] == ["1"]  # untouched
    await Giveaway.end_cmd.callback(cog, outsider, "222_2")
    cog._end_giveaway.assert_not_awaited()
    # the server's own admins still can
    insider, _ = interaction_in(222)
    await Giveaway.end_cmd.callback(cog, insider, "222_2")
    cog._end_giveaway.assert_awaited_once()


# ── welcome templates cannot run format specs ─────────────────────
def test_a_welcome_template_fills_its_placeholders_and_nothing_else():
    from src.services.management_service import MAX_WELCOME
    from src.services.management_service import render_welcome

    values = {
        "user": "<@1>",
        "username": "Ann",
        "server": "Mori",
        "count": 42,
        "created_at": "d",
    }
    assert (
        render_welcome("Hi {user} ({username}), #{count} of {server}", **values)
        == "Hi <@1> (Ann), #42 of Mori"
    )
    # a format spec, an unknown name and a stray brace stay as written, quickly
    assert render_welcome("{count:>2000000000}{nope}{0}{user", **values) == (
        "{count:>2000000000}{nope}{0}{user"
    )
    assert len(render_welcome("{username}" * 500, **values)) <= MAX_WELCOME


# ── a lockdown can be lifted after a restart ──────────────────────
class LockChannel:
    def __init__(self, channel_id, send_messages):
        self.id = channel_id
        self.send_messages = send_messages

    def overwrites_for(self, role):
        return discord.PermissionOverwrite(send_messages=self.send_messages)

    async def set_permissions(self, role, *, overwrite, reason):
        self.send_messages = overwrite.send_messages


def anti_spam_cog():
    from src.cogs.features.anti_spam import AntiSpam

    return AntiSpam(SimpleNamespace())


async def test_a_lockdown_survives_a_restart_and_restores_every_channel():
    channels = [LockChannel(1, None), LockChannel(2, True), LockChannel(3, False)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    await anti_spam_cog()._activate_lockdown(guild)
    assert [c.send_messages for c in channels] == [False, False, False]
    restarted = anti_spam_cog()  # a new process reads the record back
    assert restarted.manager.is_lockdown(9)
    await restarted._deactivate_lockdown(guild)
    assert [c.send_messages for c in channels] == [None, True, False]
    assert not anti_spam_cog().manager.is_lockdown(9)  # and the record is gone


# ── /clear answers after purging ──────────────────────────────────
async def test_clear_answers_without_a_followup_attribute():
    from src.cogs.core.admin import Admin

    deleted = [object()] * 3
    ctx = SimpleNamespace(
        author=SimpleNamespace(
            id=1, guild_permissions=SimpleNamespace(manage_messages=True)
        ),
        guild=None,
        interaction=None,
        defer=AsyncMock(),
        channel=SimpleNamespace(purge=AsyncMock(return_value=deleted)),
        send=AsyncMock(),
    )
    cog = object.__new__(Admin)
    await Admin.clear.callback(cog, ctx, 3)
    ctx.channel.purge.assert_awaited_once_with(limit=3)
    assert "3" in ctx.send.await_args.args[0]


# ── appeal reviews keep working after a restart ───────────────────
def review_message(user_id):
    embed = discord.Embed()
    embed.add_field(name="Appellant", value=f"Some (one) ({user_id})")
    return SimpleNamespace(embeds=[embed], edit=AsyncMock())


def test_the_appellant_is_read_from_the_review_message():
    from src.cogs.core.blacklist import appellant_id

    assert appellant_id(review_message(241619561760292866)) == 241619561760292866
    assert appellant_id(SimpleNamespace(embeds=[])) is None
    assert appellant_id(None) is None


async def test_a_review_button_registered_at_start_up_rejects_the_right_appeal(
    monkeypatch,
):
    from src.cogs.core import blacklist as module
    from src.config.constants import DEVELOPER_IDS

    rejected = []
    monkeypatch.setattr(
        module._service,
        "reject_appeal",
        lambda manager, target, reviewer: rejected.append(target),
    )
    cog = SimpleNamespace(
        bot=SimpleNamespace(
            blacklist_manager=object(),
            fetch_user=AsyncMock(
                side_effect=discord.HTTPException(
                    SimpleNamespace(status=500, reason="x"), "x"
                )
            ),
        )
    )
    view = module.AppealReviewView(None, cog)  # as registered in on_ready
    interaction, _ = interaction_in(None, user_id=next(iter(DEVELOPER_IDS)))
    interaction.message = review_message(123456789012345678)
    await view.reject_button.callback(interaction)
    assert rejected == [123456789012345678]


async def test_the_blacklist_cog_registers_the_review_buttons():
    from src.cogs.core.blacklist import Blacklist

    bot = discord.Client(intents=discord.Intents.default())
    try:
        await Blacklist(bot).on_ready()
        custom_ids = {
            item.custom_id for view in bot.persistent_views for item in view.children
        }
        assert {"appeal_accept", "appeal_reject", "blacklist_appeal"} <= custom_ids
    finally:
        await bot.close()


# ── only servers with a log channel have their messages kept ──────
def message_in(guild_id, message_id):
    return SimpleNamespace(
        author=SimpleNamespace(id=7, bot=False),
        guild=SimpleNamespace(id=guild_id),
        id=message_id,
        content="secret",
        channel=SimpleNamespace(id=3),
        attachments=[],
    )


async def test_messages_are_kept_only_where_a_log_channel_is_set():
    from src.cogs.core.message_logger import MessageLogger

    logger = object.__new__(MessageLogger)
    from src.services.message_log_service import MessageLogService

    logger.service = MessageLogService()
    logger.service.set_log_channel_id(1, 99)
    await MessageLogger.on_message(logger, message_in(1, 10))
    await MessageLogger.on_message(logger, message_in(2, 20))
    assert logger.service.get_record(1, 10) is not None
    assert logger.service.get_record(2, 20) is None


def test_cleanup_drops_records_of_servers_without_a_log_channel():
    from datetime import datetime

    from src.services.message_log_service import MessageLogService

    service = MessageLogService()
    service.set_log_channel_id(1, 99)
    now = datetime.now().astimezone().isoformat()
    service.save_message_log(
        {
            "1_10": {"guild_id": 1, "created_at": now},
            "2_20": {"guild_id": 2, "created_at": now},
        }
    )
    assert service.cleanup_old_logs() == 1
    assert list(service.load_message_log(force=True)) == ["1_10"]


# ── the blacklist API never holds messages up ─────────────────────
class FakeSession:
    def __init__(self, fail=False, delay=0.0):
        self.calls = 0
        self.fail = fail
        self.delay = delay

    def get(self, url, headers):
        session = self

        class Response:
            status = 200

            async def __aenter__(self):
                session.calls += 1
                await asyncio.sleep(session.delay)
                if session.fail:
                    raise asyncio.TimeoutError()
                return self

            async def __aexit__(self, *exc):
                return False

            async def json(self, content_type=None):
                return {"item": None}

        return Response()


async def test_the_blacklist_api_has_a_timeout_and_backs_off_after_a_failure():
    from src.utils.blacklist_manager import BlacklistManager

    manager = BlacklistManager("key", "https://example.invalid")
    await manager.setup()
    try:
        assert manager.session.timeout.total == BlacklistManager.API_TIMEOUT.total
    finally:
        await manager.close()
    manager.session = FakeSession(fail=True)
    assert await manager.api_check(1) is None
    assert await manager.api_check(2) is None
    assert manager.session.calls == 1  # the second message did not wait on it


async def test_messages_sent_together_share_one_blacklist_lookup():
    from src.utils.blacklist_manager import BlacklistManager

    manager = BlacklistManager("key", "https://example.invalid")
    manager.session = FakeSession(delay=0.05)
    await asyncio.gather(*(manager.api_check(5) for _ in range(5)))
    await asyncio.gather(manager.api_check(6), manager.api_check(7))
    assert manager.session.calls == 3  # one per user, not one per message


async def test_the_blacklist_cache_does_not_grow_without_bound(monkeypatch):
    from src.utils.blacklist_manager import BlacklistManager

    monkeypatch.setattr(BlacklistManager, "API_CACHE_LIMIT", 10)
    manager = BlacklistManager("key", "https://example.invalid")
    manager.session = FakeSession()
    for user in range(30):
        await manager.api_check(user)
    assert len(manager._api_cache) <= 10


@pytest.fixture(autouse=True)
def json_storage(monkeypatch):
    monkeypatch.delenv("MYSQL_HOST", raising=False)


async def test_a_lockdown_that_cannot_be_saved_is_not_applied_and_can_retry(
    monkeypatch,
):
    channels = [LockChannel(1, None)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    cog = anti_spam_cog()
    calls = []

    def broken(guild_id, states):
        calls.append(guild_id)
        raise OSError("disk full")

    monkeypatch.setattr(cog.manager, "save_lockdown", broken)
    with pytest.raises(OSError):
        await cog._activate_lockdown(guild)
    assert channels[0].send_messages is None and not cog.manager.is_lockdown(9)
    with pytest.raises(OSError):
        await cog._activate_lockdown(guild)
    assert len(calls) == 2  # the next raid tried again


def test_a_welcome_template_keeps_escaped_braces_and_its_output_limit():
    from src.services.management_service import MAX_WELCOME_EMBED
    from src.services.management_service import render_welcome

    assert (
        render_welcome("Use {{user}}; welcome {user} }}{{", user="<@123>")
        == "Use {user}; welcome <@123> }{"
    )
    long = "x" * 3000
    assert len(render_welcome(long)) == 2000  # a message or a DM
    assert render_welcome(long, MAX_WELCOME_EMBED) == long  # an embed keeps it all


class FlakyChannel(LockChannel):
    """Locking it fails once, as an HTTP 500 or a restart mid-way would."""

    def __init__(self, channel_id, send_messages):
        super().__init__(channel_id, send_messages)
        self.failures = 1

    async def set_permissions(self, role, *, overwrite, reason):
        if self.failures:
            self.failures -= 1
            raise discord.HTTPException(SimpleNamespace(status=500, reason="x"), "x")
        await super().set_permissions(role, overwrite=overwrite, reason=reason)


async def test_a_lockdown_cut_short_is_finished_after_a_restart_and_lifted_exactly():
    channels = [LockChannel(1, None), FlakyChannel(2, True)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    with pytest.raises(discord.HTTPException):
        await anti_spam_cog()._activate_lockdown(guild)
    assert [c.send_messages for c in channels] == [False, True]  # half locked
    restarted = anti_spam_cog()
    guild.text_channels.append(LockChannel(3, None))  # made meanwhile
    await restarted._activate_lockdown(guild)  # the next raid finishes it
    assert [c.send_messages for c in channels] == [False, False, False]
    await anti_spam_cog()._deactivate_lockdown(guild)
    assert [c.send_messages for c in channels] == [None, True, None]


class SlowChannel(LockChannel):
    def __init__(self, channel_id, send_messages):
        super().__init__(channel_id, send_messages)
        self.updates = 0

    async def set_permissions(self, role, *, overwrite, reason):
        self.updates += 1
        await asyncio.sleep(0.02)
        await super().set_permissions(role, overwrite=overwrite, reason=reason)


async def test_raids_during_a_lockdown_do_not_lock_the_channels_again():
    channels = [SlowChannel(1, None), SlowChannel(2, True)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    cog = anti_spam_cog()
    first = asyncio.ensure_future(cog._activate_lockdown(guild))
    while channels[0].updates == 0:  # the first lockdown is changing channels now
        await asyncio.sleep(0)
    await asyncio.gather(first, cog._activate_lockdown(guild))
    assert [c.updates for c in channels] == [1, 1]


async def test_a_new_channel_is_remembered_only_once_its_original_is_saved(
    monkeypatch,
):
    channels = [LockChannel(1, None), FlakyChannel(2, True)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    with pytest.raises(discord.HTTPException):
        await anti_spam_cog()._activate_lockdown(guild)
    restarted = anti_spam_cog()
    guild.text_channels.append(LockChannel(3, False))  # made meanwhile, muted
    real_save = restarted.manager.save_lockdown
    monkeypatch.setattr(
        restarted.manager,
        "save_lockdown",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        await restarted._activate_lockdown(guild)
    assert 3 not in restarted._lockdown_states[9]  # not saved, not remembered
    monkeypatch.setattr(restarted.manager, "save_lockdown", real_save)
    await restarted._activate_lockdown(guild)
    await anti_spam_cog()._deactivate_lockdown(guild)
    assert [c.send_messages for c in channels] == [None, True, False]


async def test_a_raid_after_a_lift_that_could_not_be_saved_still_locks(monkeypatch):
    channels = [LockChannel(1, None), LockChannel(2, True)]
    guild = SimpleNamespace(id=9, default_role=object(), text_channels=channels)
    cog = anti_spam_cog()
    await cog._activate_lockdown(guild)
    real_save = cog.manager.save_lockdown

    def broken(guild_id, states, complete=False):
        if states is None:
            raise OSError("disk full")
        return real_save(guild_id, states, complete=complete)

    monkeypatch.setattr(cog.manager, "save_lockdown", broken)
    with pytest.raises(OSError):
        await cog._deactivate_lockdown(guild)
    assert [c.send_messages for c in channels] == [None, True]  # opened
    await cog._activate_lockdown(guild)  # the next raid
    assert [c.send_messages for c in channels] == [False, False]
    monkeypatch.setattr(cog.manager, "save_lockdown", real_save)
    await cog._deactivate_lockdown(guild)
    assert [c.send_messages for c in channels] == [None, True]
