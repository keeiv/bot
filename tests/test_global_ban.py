"""global_ban bans in every server BOT. is in, and only BOT.'s own bans are lifted again."""

from datetime import datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from discord.guild import BulkBanResult

from src.services.global_ban_service import GlobalBanEnforcer
from src.services.global_ban_service import SINGLE_LIMIT
from src.utils.blacklist_manager import BlacklistManager
from src.utils.blacklist_manager import TZ_OFFSET


class Lists:
    def __init__(self, targets, mori=True):
        self.targets = targets
        self.mori = mori

    async def global_ban_targets(self):
        return None if self.targets is None else dict(self.targets)

    def _configured(self, source):
        return self.mori


def server(guild_id=1, owner_id=10, manage_guild=True, ban_members=True, bans=None):
    bans = {} if bans is None else bans  # user_id -> reason

    async def bulk_ban(users, *, reason, delete_message_seconds):
        for user in users:
            bans[user.id] = reason
        return BulkBanResult(banned=list(users), failed=[])

    async def fetch_ban(user):
        if user.id not in bans:
            raise discord.NotFound(
                SimpleNamespace(status=404, reason="nf"), "Unknown Ban"
            )
        return SimpleNamespace(reason=bans[user.id])

    async def unban(user, *, reason):
        bans.pop(user.id, None)

    return SimpleNamespace(
        id=guild_id,
        owner_id=owner_id,
        me=SimpleNamespace(
            guild_permissions=discord.Permissions(
                ban_members=ban_members, manage_guild=manage_guild
            )
        ),
        bans=bans,
        bulk_ban=AsyncMock(side_effect=bulk_ban),
        ban=AsyncMock(),
        fetch_ban=AsyncMock(side_effect=fetch_ban),
        unban=AsyncMock(side_effect=unban),
    )


async def test_listed_users_are_banned_in_every_server_once():
    lists = Lists({5: "mori", 6: "local", 10: "local", 999: "mori"})
    enforcer = GlobalBanEnforcer(lists, bot_user_id=999)
    a, b = server(1), server(2)
    await enforcer.reconcile([a, b])
    assert set(a.bans) == set(b.bans) == {5, 6}  # never the owner (10) or BOT. (999)
    await enforcer.reconcile([a, b])
    assert a.bulk_ban.await_count == b.bulk_ban.await_count == 1


async def test_a_lifted_entry_lifts_only_bot_s_own_ban():
    lists = Lists({5: "mori", 6: "mori"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    await enforcer.reconcile([guild])
    guild.bans[6] = "raided our server"  # the server banned them itself meanwhile
    lists.targets = {}
    await enforcer.reconcile([guild])
    assert guild.bans == {6: "raided our server"}
    assert enforcer._load() == {}


async def test_nothing_happens_before_the_mori_list_first_loads():
    enforcer = GlobalBanEnforcer(Lists(None))
    guild = server(bans={5: "Global Ban: x"})
    await enforcer.reconcile([guild])
    guild.bulk_ban.assert_not_awaited()
    guild.unban.assert_not_awaited()


async def test_switching_mori_off_does_not_unban_its_users():
    lists = Lists({5: "mori", 6: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    await enforcer.reconcile([guild])
    lists.targets, lists.mori = {}, False
    await enforcer.reconcile([guild])
    assert set(guild.bans) == {
        5
    }  # the local entry was removed; Mori's state is unknown


async def test_without_manage_server_bans_go_one_by_one_a_few_at_a_time():
    lists = Lists(dict.fromkeys(range(100, 100 + SINGLE_LIMIT + 5), "local"))
    enforcer = GlobalBanEnforcer(lists)
    guild = server(manage_guild=False)
    guild.ban.side_effect = [
        discord.Forbidden(
            SimpleNamespace(status=403, reason="no"), "Missing Permissions"
        )
    ] + [None] * (SINGLE_LIMIT - 1)
    await enforcer.reconcile([guild])
    assert guild.ban.await_count == SINGLE_LIMIT
    guild.ban.reset_mock(side_effect=True)
    await enforcer.reconcile([guild])
    assert guild.ban.await_count == 5  # the rest; the refused one is not retried


async def test_servers_where_bot_cannot_ban_are_skipped():
    enforcer = GlobalBanEnforcer(Lists({5: "local"}))
    guild = server(ban_members=False)
    await enforcer.reconcile([guild])
    guild.bulk_ban.assert_not_awaited()


async def test_targets_come_from_both_lists_without_expired_or_block_entries(
    monkeypatch,
):
    manager = BlacklistManager(mori_token="t", mori_url="https://mori.example/v1")
    monkeypatch.setattr(manager, "_mori_fresh", AsyncMock())
    assert await manager.global_ban_targets() is None  # never synced
    manager._mori = {
        "5": [{"id": "1", "mode": "global_ban"}],
        "6": [{"id": "2", "mode": "block"}],
    }
    manager._mori_synced_at = 1.0
    past = (datetime.now(TZ_OFFSET) - timedelta(days=1)).isoformat()
    manager.local_add(7, "raid", mode="global_ban")
    manager.local_add(8, "old", mode="global_ban", expires_at=past)
    manager.local_add(9, "rude", mode="block")
    assert await manager.global_ban_targets() == {5: "mori", 7: "local"}


# ── Review round: Xiyu ────────────────────────────────────────────
async def test_a_ban_seen_on_mori_is_not_lifted_after_mori_is_switched_off():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    await enforcer.reconcile([guild])
    lists.targets = {5: "mori"}  # the local entry is gone; Mori.black still lists them
    await enforcer.reconcile([guild])
    lists.targets, lists.mori = {}, False
    await enforcer.reconcile([guild])
    assert 5 in guild.bans


async def test_a_batch_discord_refuses_does_not_hold_up_the_next():
    already = dict.fromkeys(range(1000, 1200), "Global Ban: earlier")
    lists = Lists(dict.fromkeys([*already, 5000], "local"))
    enforcer = GlobalBanEnforcer(lists)
    guild = server(bans=dict(already))
    original = guild.bulk_ban.side_effect

    async def bulk_ban(users, **kwargs):
        if all(u.id in guild.bans for u in users):
            raise discord.HTTPException(
                SimpleNamespace(status=400, reason="x"), {"code": 500000}
            )
        return await original(users, **kwargs)

    guild.bulk_ban.side_effect = bulk_ban
    await enforcer.reconcile([guild])
    assert 5000 in guild.bans
    assert list(enforcer._load()["1"]) == ["5000"]  # only the ban made here


async def test_a_ban_recorded_on_join_is_lifted_with_the_entry():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server(bans={5: "[BOT.] Global Ban: raider"})
    await enforcer.remember(1, 5, "local")
    await enforcer.reconcile([guild])
    guild.bulk_ban.assert_not_awaited()
    lists.targets = {}
    await enforcer.reconcile([guild])
    assert guild.bans == {}


async def test_a_cathome_ban_is_not_recorded_because_it_could_never_be_lifted():
    enforcer = GlobalBanEnforcer(Lists({}))
    await enforcer.remember(1, 5, "cathome")
    assert enforcer._load() == {}


async def test_an_admin_s_own_ban_with_the_same_words_is_never_lifted():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server(bans={5: "Global Ban: manually banned"})

    async def bulk_ban(users, **kwargs):  # already banned: nobody could be banned
        return BulkBanResult(banned=[], failed=list(users))

    guild.bulk_ban.side_effect = bulk_ban
    await enforcer.reconcile([guild])
    lists.targets = {}
    await enforcer.reconcile([guild])
    assert 5 in guild.bans
    guild.unban.assert_not_awaited()


async def test_a_passing_error_does_not_stop_the_next_try():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    original = guild.bulk_ban.side_effect
    guild.bulk_ban.side_effect = discord.HTTPException(
        SimpleNamespace(status=503, reason="busy"), {"code": 0}
    )
    await enforcer.reconcile([guild])
    guild.bulk_ban.side_effect = original
    await enforcer.reconcile([guild])
    assert 5 in guild.bans


async def test_refusals_expire_and_leave_with_the_entry(monkeypatch):
    import src.services.global_ban_service as service

    clock = SimpleNamespace(value=100.0)
    monkeypatch.setattr(service.time, "monotonic", lambda: clock.value)
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    original = guild.bulk_ban.side_effect

    async def refuse(users, **kwargs):
        return BulkBanResult(banned=[], failed=list(users))

    guild.bulk_ban.side_effect = refuse
    await enforcer.reconcile([guild])
    await enforcer.reconcile([guild])
    assert guild.bulk_ban.await_count == 1  # left alone for now
    clock.value += service.RETRY_SECONDS + 1
    guild.bulk_ban.side_effect = original
    await enforcer.reconcile([guild])
    assert 5 in guild.bans
    guild.bulk_ban.side_effect = refuse
    lists.targets = {6: "local"}
    await enforcer.reconcile([guild])
    lists.targets = {}
    await enforcer.reconcile([guild])
    assert enforcer._refused == {}


# ── review round 3 ────────────────────────────────────────────────
async def test_a_server_s_later_ban_is_not_taken_for_the_old_record():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    await enforcer.reconcile([guild])
    guild.bans[5] = "Global Ban: manually banned"  # unbanned, then banned by hand
    lists.targets = {}
    await enforcer.reconcile([guild])
    assert 5 in guild.bans


async def test_an_unban_retires_the_record_and_a_listed_user_is_banned_again():
    lists = Lists({5: "local"})
    enforcer = GlobalBanEnforcer(lists)
    guild = server()
    await enforcer.reconcile([guild])
    del guild.bans[5]
    await enforcer.forget(1, 5)
    assert enforcer._load() == {}
    await enforcer.reconcile([guild])
    assert 5 in guild.bans
