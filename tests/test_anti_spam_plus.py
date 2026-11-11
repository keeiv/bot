"""Spam protection additions.

Similar messages across channels and accounts, attachment floods, malicious links,
new accounts and raids, lockdowns that lift themselves, anti-nuke.
"""

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import total_ordering
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import discord
import pytest

from src.utils import anti_spam as spam
from src.utils.anti_spam import AntiSpamManager
from src.utils.anti_spam import Evidence

GUILD = 77


def manager(**settings):
    m = AntiSpamManager()
    if settings:
        m.update_settings(GUILD, settings)
    return m


def post(m, user, channel, content, message_id, evidence=None, **kwargs):
    return [
        t[0]
        for t in m.check_message(
            GUILD,
            user,
            content,
            channel,
            message_id=message_id,
            evidence=evidence,
            **kwargs,
        )
    ]


def ago(**delta):
    return datetime.now(timezone.utc) - timedelta(**delta)


# ── settings saved before these options existed ───────────────────
def test_a_server_saved_before_the_new_options_gets_their_defaults():
    m = AntiSpamManager()
    m._settings[GUILD] = {"enabled": True, "flood_messages": 10, "flood_window": 10}
    assert m.get_settings(GUILD)["nuke_enabled"] is True
    assert post(m, 1, 10, "hello", 1) == []  # no KeyError on the new checks


# ── similar messages ──────────────────────────────────────────────
def test_alike_messages_in_three_channels_are_caught_and_all_of_them_removed():
    m = manager(flood_messages=100, duplicate_enabled=False)
    evidence = Evidence()
    assert post(m, 1, 10, "join my server now", 1) == []
    assert (
        post(m, 1, 11, "JOIN  my\u200b server now", 2) == []
    )  # case, spaces, zero-width
    assert spam.DETECT_SIMILAR in post(m, 1, 12, "join my server now!", 3, evidence)
    assert evidence.messages == {(10, 1), (11, 2), (12, 3)}


def test_different_messages_in_many_channels_are_fine():
    m = manager(flood_messages=100)
    for channel, text in enumerate(["morning all", "anyone up for a match?", "gg"]):
        assert post(m, 1, channel, text, channel + 1) == []


def test_near_repeats_in_one_channel_count_as_duplicates():
    m = manager(flood_messages=100, similar_enabled=False, duplicate_count=4)
    found = []
    for n in range(4):
        found = post(m, 1, 10, f"cheap followers at my shop {n}", n + 1)
    assert spam.DETECT_DUPLICATE in found


def test_short_greetings_are_only_repeats_when_identical():
    assert spam.is_similar("ok", "ok")
    assert not spam.is_similar("ok", "oh")
    assert not spam.is_similar("", "")


def test_four_accounts_posting_the_same_text_are_caught_together():
    m = manager(flood_messages=100, similar_users=4)
    text = "free giveaway in my profile, check it out"
    for user in (1, 2, 3):
        assert post(m, user, 10 + user, text, user) == []
    evidence = Evidence()
    assert spam.DETECT_COORDINATED in post(m, 4, 14, text, 4, evidence)
    assert evidence.users == {2, 3}  # the first may be the one being copied
    assert evidence.messages >= {(12, 2), (13, 3), (14, 4)}
    assert (11, 1) not in evidence.messages
    # whoever joins the wave afterwards is caught at once, alone
    later = Evidence()
    assert spam.DETECT_COORDINATED in post(m, 5, 15, text + "!", 5, later)
    assert later.users == set()


def test_many_people_saying_good_morning_is_not_a_wave():
    m = manager(flood_messages=100, similar_users=3)
    for user in range(1, 8):
        assert post(m, user, 10, "good morning", user) == []


def test_attachment_floods_are_caught():
    m = manager(flood_messages=100, attachment_limit=6)
    assert post(m, 1, 10, "", 1, attachments=["a.png:1", "b.png:2", "c.png:3"]) == []
    found = post(m, 1, 10, "", 2, attachments=["d.png:4", "e.png:5"], stickers=["99"])
    assert spam.DETECT_ATTACHMENT in found


def test_one_file_posted_in_three_channels_is_cross_channel_spam():
    m = manager(flood_messages=100, attachment_enabled=False)
    for channel in (10, 11):
        assert post(m, 1, channel, "", channel, attachments=["scam.exe:4096"]) == []
    assert spam.DETECT_SIMILAR in post(m, 1, 12, "", 12, attachments=["scam.exe:4096"])


# ── malicious links ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "content",
    [
        "https://discord-nitro.gift/claim",
        "https://discordgift.site/abc",
        "https://dlscord.com/gifts/abc",
        "https://discrod.com/abc",
        "https://dscord.com/abc",
        "https://steamcomunity.com/id/x",
        "check [discord.gg/nitro](https://claim-here.example/x)",
        "https://disc0rd.com/login",
        "https://dіscord.com/nitro",  # Cyrillic і
        "https://xn--dscord-6ve.com/nitro",  # the same, as the browser sends it
        "https://steamcommunity.ru/tradeoffer/new",
        "https://steamcommunlty.com/id/x",
        "look [https://discord.com/gifts/abc](https://evil.example/x)",
        "free nitro for everyone https://bit.ly/3abc",
        "免費領取 Nitro https://bit.ly/3abc",
        "free nitro https://nitro-drop.example/x",
        "https://disc0rd.example\\@discord.com/gift",  # a browser opens disc0rd.example
    ],
)
def test_malicious_links_are_caught(content):
    m = manager(flood_messages=100)
    assert spam.DETECT_PHISHING in post(m, 1, 10, content, 1)


@pytest.mark.parametrize(
    "content",
    [
        "https://discord.com/channels/1/2",
        "https://discord.gg/abc",
        "https://discord.js.org/docs/packages/discord.js/main",
        "https://discordbotlist.com/bots/x",
        "https://top.gg/bot/1",
        "https://store.steampowered.com/app/570",
        "https://steamdb.info/app/570/",
        "https://www.discogs.com/release/1",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "[the docs](https://discord.com/developers/docs)",
        "[example.com](https://example.com/page)",
        "[www.example.com](https://shop.example.com/)",
        "[README.md](https://github.com/keeiv/new_bot/blob/main/README.md)",
        "[socket.io](https://github.com/socketio/socket.io)",
        "https://discard.app/",
        "https://discordia.example/",
        "free nitro scam explained https://www.youtube.com/watch?v=1",
        "不要相信免費 Nitro https://example.org/security-guide",
        "is free nitro real? https://discord.com/nitro",
        "https://台灣.tw/",  # an honest IDN
    ],
)
def test_honest_links_are_left_alone(content):
    m = manager(flood_messages=100, link_limit=100)
    assert spam.DETECT_PHISHING not in post(m, 1, 10, content, 1)


def test_a_server_can_trust_and_block_domains():
    m = manager(flood_messages=100)
    m.update_list(GUILD, "allowed_domains", "add", "discord-gift-event.example")
    m.update_list(GUILD, "blocked_domains", "add", "shady.example")
    assert post(m, 1, 10, "https://discord-gift-event.example/", 1) == []
    assert spam.DETECT_PHISHING in post(m, 2, 10, "https://cdn.shady.example/a", 2)
    assert m.update_list(GUILD, "blocked_domains", "add", "shady.example") is False


# ── new accounts and raids ────────────────────────────────────────
def test_new_accounts_are_caught_only_when_the_rule_is_on():
    assert manager().check_new_account(GUILD, ago(hours=1)) is None  # off by default
    m = manager(new_account_hours=24, new_account_action="kick")
    det, action, _ = m.check_new_account(GUILD, ago(hours=2))
    assert (det, action) == (spam.DETECT_NEW_ACCOUNT, "kick")
    assert m.check_new_account(GUILD, ago(days=3)) is None


def test_a_raid_wave_names_its_new_accounts_then_new_joiners_are_removed():
    m = manager(raid_joins=3, raid_window=30, raid_age_days=7, raid_lift_minutes=30)
    assert m.check_member_join(GUILD, 1, ago(days=1)) is None
    assert m.check_member_join(GUILD, 2, ago(days=900)) is None
    evidence = Evidence()
    det, action, _ = m.check_member_join(GUILD, 3, ago(hours=1), evidence)
    assert (det, action) == (spam.DETECT_RAID, "lockdown")
    assert evidence.wave and evidence.users == {1, 3}  # the old account is spared
    # raid mode: a new account joining now is removed on its own
    later = Evidence()
    assert m.check_member_join(GUILD, 4, ago(hours=2), later)[1] == "kick"
    assert not later.wave
    assert m.check_member_join(GUILD, 5, ago(days=400)) is None
    m.end_raid(GUILD)
    m.join_log[GUILD].clear()  # (three more joins here would be a new wave)
    assert m.check_member_join(GUILD, 6, ago(hours=2)) is None


# ── anti-nuke counting ────────────────────────────────────────────
def test_anti_nuke_counts_dangerous_actions_per_member():
    m = manager(nuke_limit=3, nuke_window=30)
    assert m.check_nuke(GUILD, 5, "channel_delete") is None
    assert m.check_nuke(GUILD, 6, "channel_delete") is None  # someone else
    assert m.check_nuke(GUILD, 5, "role_delete") is None
    det, action, detail = m.check_nuke(GUILD, 5, "channel_delete")
    assert (det, action) == (spam.DETECT_NUKE, "strip")
    assert m.check_nuke(GUILD, 5, "ban") is None  # counting starts over
    # moderators banning the raid's own accounts do not count; anyone else does
    m.raid_until[GUILD] = float("inf")
    m.raiders[GUILD] = {100, 101, 102, 103, 104}
    for raider in range(100, 105):
        assert m.check_nuke(GUILD, 7, "ban", raider) is None
    assert m.check_nuke(GUILD, 7, "ban", 1) is None
    assert m.check_nuke(GUILD, 7, "ban", 2) is None
    assert m.check_nuke(GUILD, 7, "ban", 3) is not None
    m.update_list(GUILD, "nuke_trusted", "add", 6)
    for _ in range(5):
        assert m.check_nuke(GUILD, 6, "ban") is None


def test_old_records_are_pruned():
    m = manager()
    post(m, 1, 10, "hello there", 1)
    m.check_nuke(GUILD, 5, "ban")
    m.prune(now=datetime.now(timezone.utc).timestamp() + 7200)
    assert not m.recent_messages and not m.nuke_log and not m.message_log


# ── cog: fakes ────────────────────────────────────────────────────
@total_ordering
class Role:
    def __init__(self, role_id, position, perms=None, managed=False, default=False):
        self.id = role_id
        self.position = position
        self.permissions = perms or discord.Permissions.none()
        self.managed = managed
        self._default = default

    def is_default(self):
        return self._default

    def __eq__(self, other):
        return isinstance(other, Role) and other.id == self.id

    def __lt__(self, other):
        return self.position < other.position

    def __hash__(self):
        return self.id


def make_guild(owner_id=1):
    members = {}
    guild = SimpleNamespace(
        id=GUILD,
        name="Mori",
        owner_id=owner_id,
        owner=None,
        me=SimpleNamespace(top_role=Role(900, 50)),
        default_role=Role(GUILD, 0, default=True),
        text_channels=[],
        kick=AsyncMock(),
        ban=AsyncMock(),
        members=members,
        get_member=members.get,
        get_role=lambda role_id: None,
    )
    channels = {}
    guild.channels = channels
    guild.get_channel_or_thread = channels.get
    return guild


def make_member(guild, user_id, *, roles=(), created=None, bot=False):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.bot = bot
    member.guild = guild
    member.mention = f"<@{user_id}>"
    member.roles = [guild.default_role, *roles]
    member.top_role = max(member.roles)
    member.guild_permissions = discord.Permissions.none()
    member.created_at = created or ago(days=400)
    for name in ("send", "timeout", "remove_roles", "add_roles"):
        setattr(member, name, AsyncMock())
    guild.members[user_id] = member
    return member


def make_channel(guild, channel_id):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.purge = AsyncMock()
    channel.delete_messages = AsyncMock()
    channel.get_partial_message = MagicMock(
        side_effect=lambda _: SimpleNamespace(delete=AsyncMock())
    )
    guild.channels[channel_id] = channel
    return channel


def make_message(member, channel, content, message_id):
    return SimpleNamespace(
        id=message_id,
        author=member,
        guild=member.guild,
        channel=channel,
        content=content,
        attachments=[],
        stickers=[],
        delete=AsyncMock(),
    )


def cog():
    from src.cogs.features.anti_spam import AntiSpam

    bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        get_channel=lambda _: None,
        get_guild=lambda _: None,
        fetch_user=AsyncMock(),
    )
    return AntiSpam(bot)


@pytest.fixture(autouse=True)
def quick_reports(monkeypatch):
    import src.cogs.features.anti_spam as cog_module

    monkeypatch.setattr(cog_module, "JOIN_REPORT_DELAY", 0)


# ── cog: messages ─────────────────────────────────────────────────
async def test_a_malicious_link_is_deleted_even_when_the_action_is_a_warning():
    c = cog()
    c.manager.update_settings(GUILD, {"phishing_action": "warn"})
    guild = make_guild()
    message = make_message(
        make_member(guild, 5), make_channel(guild, 10), "https://disc0rd.com/gift", 1
    )
    await c.on_message(message)
    message.delete.assert_awaited()
    message.author.send.assert_awaited()  # the warning


async def test_cross_channel_spam_is_removed_from_every_channel():
    c = cog()
    c.manager.update_settings(
        GUILD,
        {"similar_action": "mute", "flood_messages": 100, "duplicate_enabled": False},
    )
    guild = make_guild()
    spammer = make_member(guild, 5)
    channels = [make_channel(guild, 10 + n) for n in range(3)]
    for n, channel in enumerate(channels):
        await c.on_message(
            make_message(spammer, channel, "join my raid server now", n + 1)
        )
    spammer.timeout.assert_awaited_once()
    for n, channel in enumerate(channels[:2]):
        channel.get_partial_message.assert_any_call(n + 1)  # the other channels too


async def test_every_account_of_a_wave_is_muted():
    c = cog()
    c.manager.update_settings(GUILD, {"similar_users": 3, "flood_messages": 100})
    guild = make_guild()
    channel = make_channel(guild, 10)
    author, *spammers = [make_member(guild, user) for user in (5, 6, 7, 8)]
    text = "check my profile for a free giveaway right now"
    for n, member in enumerate([author, *spammers]):
        await c.on_message(make_message(member, channel, text, n + 1))
    # three alike messages trip it, so the fourth is the one caught at once
    assert spammers[1].timeout.await_count == 1
    assert spammers[0].timeout.await_count == 1
    author.timeout.assert_not_awaited()
    channel.delete_messages.assert_awaited()


async def test_a_wave_spares_admins_and_members_above_the_bot():
    c = cog()
    c.manager.update_settings(GUILD, {"similar_users": 3, "flood_messages": 100})
    guild = make_guild()
    channel = make_channel(guild, 10)
    admin = make_member(guild, 5)
    admin.guild_permissions = discord.Permissions(administrator=True)
    high = make_member(guild, 6, roles=[Role(60, 99)])
    text = "check my profile for a free giveaway right now"
    c.manager.check_message(GUILD, 5, text, 10, message_id=1)  # they said it too
    c.manager.check_message(GUILD, 6, text, 10, message_id=2)
    await c.on_message(make_message(make_member(guild, 7), channel, text, 3))
    admin.timeout.assert_not_awaited()
    high.timeout.assert_not_awaited()


# ── cog: joins ────────────────────────────────────────────────────
async def test_a_new_account_is_told_why_then_kicked_and_reported():
    c = cog()
    c.manager.update_settings(GUILD, {"new_account_hours": 24})
    c._send_log = AsyncMock()
    guild = make_guild()
    member = make_member(guild, 5, created=ago(hours=3))
    await c.on_member_join(member)
    member.send.assert_awaited_once()
    guild.kick.assert_awaited_once()
    await asyncio.gather(*c._report_tasks)
    c._send_log.assert_awaited_once()


async def test_a_raid_removes_its_new_accounts_and_locks_down():
    c = cog()
    c.manager.update_settings(GUILD, {"raid_joins": 3, "raid_age_days": 7})
    c._send_log = AsyncMock()
    c._activate_lockdown = AsyncMock()
    guild = make_guild()
    young = [make_member(guild, n, created=ago(hours=n)) for n in (5, 6)]
    old = make_member(guild, 7, created=ago(days=800))
    for member in (*young, old):
        await c.on_member_join(member)
    kicked = {call.args[0].id for call in guild.kick.await_args_list}
    assert kicked == {5, 6}
    c._activate_lockdown.assert_awaited_once()
    # one more new account during the raid
    await c.on_member_join(make_member(guild, 8, created=ago(hours=1)))
    assert guild.kick.await_count == 3


# ── cog: lockdowns lift themselves ────────────────────────────────
class LockChannel:
    def __init__(self, channel_id):
        self.id = channel_id
        self.send_messages = None

    def overwrites_for(self, role):
        return discord.PermissionOverwrite(send_messages=self.send_messages)

    async def set_permissions(self, role, *, overwrite, reason):
        self.send_messages = overwrite.send_messages


async def test_a_lockdown_lifts_itself_when_due_even_after_a_restart():
    c = cog()
    c.manager.update_settings(GUILD, {"raid_lift_minutes": 10})
    c._send_log = AsyncMock()
    guild = make_guild()
    guild.text_channels = [LockChannel(1), LockChannel(2)]
    await c._activate_lockdown(guild)
    assert [ch.send_messages for ch in guild.text_channels] == [False, False]
    restarted = cog()
    restarted._send_log = AsyncMock()
    until = restarted.manager.lockdown_until[GUILD]
    assert until > datetime.now(timezone.utc).timestamp() + 500
    await restarted._auto_lift(guild)  # not due yet
    assert restarted.manager.is_lockdown(GUILD)
    restarted.manager.lockdown_until[GUILD] = 0
    await restarted._auto_lift(guild)
    assert [ch.send_messages for ch in guild.text_channels] == [None, None]
    assert not restarted.manager.is_lockdown(GUILD)
    restarted._send_log.assert_awaited_once()


async def test_another_raid_during_a_lockdown_puts_the_lift_off():
    c = cog()
    c.manager.update_settings(GUILD, {"raid_lift_minutes": 10})
    guild = make_guild()
    guild.text_channels = [LockChannel(1)]
    await c._activate_lockdown(guild)
    c.manager.lockdown_until[GUILD] = 1.0
    await c._activate_lockdown(guild)
    assert c.manager.lockdown_until[GUILD] > 1.0
    assert cog().manager.lockdown_until[GUILD] > 1.0  # saved


async def test_a_lockdown_without_a_time_waits_for_a_person():
    c = cog()
    c.manager.update_settings(GUILD, {"raid_lift_minutes": 0})
    guild = make_guild()
    guild.text_channels = [LockChannel(1)]
    await c._activate_lockdown(guild)
    assert c.manager.due_lockdowns(now=10**12) == []


# ── cog: anti-nuke ────────────────────────────────────────────────
def audit(guild, user_id, action=discord.AuditLogAction.channel_delete):
    return SimpleNamespace(action=action, guild=guild, user_id=user_id)


async def test_mass_deletion_by_an_admin_strips_their_roles_and_tells_the_owner():
    c = cog()
    c.manager.update_settings(GUILD, {"nuke_limit": 3})
    c._send_log = AsyncMock()
    guild = make_guild(owner_id=1)
    owner = SimpleNamespace(send=AsyncMock())
    guild.owner = owner
    mod = Role(30, 20, discord.Permissions(manage_channels=True))
    helper = Role(31, 10)
    rogue = make_member(guild, 5, roles=[mod, helper])
    for _ in range(3):
        await c.on_audit_log_entry_create(audit(guild, 5))
    rogue.remove_roles.assert_awaited_once()
    assert set(rogue.remove_roles.await_args.args) == {mod, helper}
    guild.kick.assert_not_awaited()  # nothing dangerous left
    owner.send.assert_awaited_once()
    c._send_log.assert_awaited_once()
    assert c.manager.get_strip(GUILD, 5) == [30, 31]


async def test_a_nuking_bot_keeps_its_own_role_so_it_is_kicked():
    c = cog()
    c.manager.update_settings(GUILD, {"nuke_limit": 2})
    c._send_log = AsyncMock()
    guild = make_guild()
    integration = Role(40, 30, discord.Permissions(administrator=True), managed=True)
    bot = make_member(guild, 6, roles=[integration], bot=True)
    for _ in range(2):
        await c.on_audit_log_entry_create(audit(guild, 6, discord.AuditLogAction.ban))
    guild.kick.assert_awaited_once()
    assert guild.kick.await_args.args[0] is bot


async def test_the_owner_bot_itself_and_trusted_members_are_never_stopped():
    c = cog()
    c.manager.update_settings(GUILD, {"nuke_limit": 2, "nuke_trusted": [7]})
    c._stop_nuker = AsyncMock()
    guild = make_guild(owner_id=1)
    for actor in (1, 999, 7):
        for _ in range(5):
            await c.on_audit_log_entry_create(audit(guild, actor))
    c._stop_nuker.assert_not_awaited()
    # actions that do not count
    for _ in range(5):
        await c.on_audit_log_entry_create(
            audit(guild, 5, discord.AuditLogAction.message_delete)
        )
    c._stop_nuker.assert_not_awaited()


async def test_a_member_above_the_bot_is_reported_not_touched():
    c = cog()
    guild = make_guild()
    boss = make_member(
        guild, 5, roles=[Role(50, 99, discord.Permissions(administrator=True))]
    )
    outcome = await c._disarm(guild, boss, "strip")
    boss.remove_roles.assert_not_awaited()
    assert outcome  # explains why


def interaction(guild, user_id):
    sent = []
    return (
        SimpleNamespace(
            guild_id=guild.id,
            guild=guild,
            user=make_member(guild, user_id),
            locale=discord.Locale.taiwan_chinese,
            client=SimpleNamespace(get_guild=lambda _: None),
            response=SimpleNamespace(
                send_message=AsyncMock(side_effect=lambda *a, **k: sent.append(a)),
                defer=AsyncMock(),
            ),
            followup=SimpleNamespace(
                send=AsyncMock(side_effect=lambda *a, **k: sent.append((a, k)))
            ),
        ),
        sent,
    )


async def test_only_the_owner_changes_anti_nuke_or_restores_roles():
    from src.cogs.features.anti_spam import AntiSpam

    c = cog()
    guild = make_guild(owner_id=1)
    admin, _ = interaction(guild, 2)
    await AntiSpam.nuke_cmd.callback(c, admin, False)
    assert c.manager.get_settings(GUILD)["nuke_enabled"] is True
    await AntiSpam.nuke_trust_cmd.callback(c, admin, "add", SimpleNamespace(id=2))
    assert c.manager.get_settings(GUILD)["nuke_trusted"] == []
    owner, _ = interaction(guild, 1)
    await AntiSpam.nuke_cmd.callback(c, owner, False)
    assert c.manager.get_settings(GUILD)["nuke_enabled"] is False


async def test_the_owner_gives_stripped_roles_back():
    from src.cogs.features.anti_spam import AntiSpam

    c = cog()
    guild = make_guild(owner_id=1)
    mod = Role(30, 20)
    guild.get_role = {30: mod}.get  # role 31 was deleted since
    member = make_member(guild, 5)
    c.manager.save_strip(GUILD, 5, [30, 31])
    owner, _ = interaction(guild, 1)
    await AntiSpam.nuke_restore_cmd.callback(c, owner, member)
    member.add_roles.assert_awaited_once()
    assert member.add_roles.await_args.args == (mod,)
    assert c.manager.get_strip(GUILD, 5) == []


async def test_a_domain_entry_is_stored_as_its_host():
    from src.cogs.features.anti_spam import AntiSpam

    c = cog()
    guild = make_guild()
    admin, _ = interaction(guild, 2)
    await AntiSpam.domain_cmd.callback(
        c, admin, "block", "add", "https://WWW.Shady.Example/x"
    )
    assert c.manager.get_settings(GUILD)["blocked_domains"] == ["shady.example"]
    await AntiSpam.domain_cmd.callback(c, admin, "block", "add", "not a domain")
    assert c.manager.get_settings(GUILD)["blocked_domains"] == ["shady.example"]


# ── Review round: Xiyu ────────────────────────────────────────────
def test_turning_spam_protection_off_does_not_turn_anti_nuke_off():
    m = manager(
        nuke_limit=3, enabled=False
    )  # what any admin can do with /anti_spam setup
    assert m.check_nuke(GUILD, 5, "channel_delete") is None
    assert m.check_nuke(GUILD, 5, "channel_delete") is None
    assert m.check_nuke(GUILD, 5, "channel_delete") is not None


def test_the_raid_accounts_are_remembered_for_anti_nuke():
    m = manager(raid_joins=3, raid_age_days=0)
    for user in (1, 2, 3):
        m.check_member_join(GUILD, user, ago(hours=1))
    m.check_member_join(GUILD, 4, ago(hours=1))  # during the raid
    assert m.raiders[GUILD] == {1, 2, 3, 4}
    m.end_raid(GUILD)
    assert GUILD not in m.raiders


def test_a_raid_set_to_warn_warns_and_one_set_to_delete_removes_nobody():
    warn = manager(raid_joins=3, raid_action="warn")
    for user in (1, 2):
        warn.check_member_join(GUILD, user, ago(hours=1))
    assert warn.check_member_join(GUILD, 3, ago(hours=1))[1] == "warn"
    assert warn.check_member_join(GUILD, 4, ago(hours=1))[1] == "warn"
    delete = manager(raid_joins=3, raid_action="delete")
    for user in (1, 2, 3):
        delete.check_member_join(GUILD, user, ago(hours=1))
    assert delete.check_member_join(GUILD, 4, ago(hours=1)) is None
    assert spam.raid_member_action(delete.get_settings(GUILD)) is None


def test_different_images_with_alike_names_are_not_a_wave():
    m = manager(flood_messages=100, similar_users=4, attachment_enabled=False)
    for user in (1, 2, 3, 4):
        found = post(m, user, 10, "", user, attachments=[f"image.png:{123450 + user}"])
        assert spam.DETECT_COORDINATED not in found


def test_the_similar_window_reaches_past_a_minute():
    m = manager(flood_messages=100, similar_window=300, duplicate_enabled=False)
    for n, channel in enumerate((10, 11)):
        assert post(m, 1, channel, "join my server now", n + 1) == []
        for user_log in m.recent_messages[GUILD].values():  # the clock moves 100 s
            user_log[:] = [(t - 100, *rest) for t, *rest in user_log]
    assert spam.DETECT_SIMILAR in post(m, 1, 12, "join my server now", 3)


async def test_only_the_owner_restores_roles():
    from src.cogs.features.anti_spam import AntiSpam

    c = cog()
    guild = make_guild(owner_id=1)
    guild.get_role = {30: Role(30, 20)}.get
    member = make_member(guild, 5)
    c.manager.save_strip(GUILD, 5, [30])
    admin, _ = interaction(guild, 2)
    await AntiSpam.nuke_restore_cmd.callback(c, admin, member)
    member.add_roles.assert_not_awaited()
    assert c.manager.get_strip(GUILD, 5) == [30]


# ── review round 2 ────────────────────────────────────────────────
def test_files_alone_never_make_a_wave_however_alike():
    m = manager(flood_messages=100, similar_users=4, attachment_enabled=False)
    for user in (1, 2, 3, 4):
        found = post(m, user, 10, "", user, attachments=["notes.txt:1024"])
        assert spam.DETECT_COORDINATED not in found


def test_a_wave_with_files_is_still_found_by_its_text():
    m = manager(flood_messages=100, similar_users=3, attachment_enabled=False)
    text = "check my profile for a free giveaway right now"
    found = []
    for user in (1, 2, 3):
        found = post(m, user, 10, text, user, attachments=[f"a{user}.png:{user}"])
    assert spam.DETECT_COORDINATED in found


def test_a_detection_removes_a_minute_of_messages_and_the_older_matches():
    m = manager(flood_messages=100, similar_window=300, duplicate_enabled=False)
    post(m, 1, 10, "an ordinary chat message here", 1)
    post(m, 1, 11, "join my server now", 2)
    post(m, 1, 12, "join my server now", 3)
    for log in m.recent_messages[GUILD].values():  # the clock moves two minutes
        log[:] = [(t - 120, *rest) for t, *rest in log]
    evidence = Evidence()
    assert spam.DETECT_SIMILAR in post(m, 1, 13, "join my server now", 4, evidence)
    assert (10, 1) not in evidence.messages  # unrelated and two minutes old
    assert evidence.messages == {(11, 2), (12, 3), (13, 4)}


def test_a_new_raid_does_not_inherit_the_last_one_s_accounts():
    m = manager(raid_joins=3, raid_age_days=0)
    for user in (1, 2, 3):
        m.check_member_join(GUILD, user, ago(hours=1))
    m.raid_until[GUILD] = 1.0  # that raid is over; nothing pruned it yet
    for user in (4, 5, 6):
        m.check_member_join(GUILD, user, ago(hours=1))
    assert m.raiders[GUILD] == {4, 5, 6}


async def test_raid_accounts_are_known_before_the_join_waits_on_anything():
    c = cog()
    c.manager.update_settings(GUILD, {"new_account_hours": 24, "raid_joins": 2})
    c._send_log = AsyncMock()
    guild = make_guild()
    seen = []

    async def direct_message(*_a, **_k):
        seen.append(set(c.manager.raiders.get(GUILD, ())))

    first = make_member(guild, 5, created=ago(hours=1))
    second = make_member(guild, 6, created=ago(hours=1))
    second.send = AsyncMock(side_effect=direct_message)
    await c.on_member_join(first)
    await c.on_member_join(second)
    assert {5, 6} <= seen[0]
    await asyncio.gather(*c._report_tasks)


@pytest.mark.parametrize(
    "content",
    [
        "不要相信免費 Nitro https://auth.example.org/security-guide",
        "free nitro warning https://login.example.org/help",
        "free nitro is a scam https://free.example.org/about",
    ],
)
def test_a_warning_about_the_scam_is_left_alone(content):
    m = manager(flood_messages=100)
    assert spam.DETECT_PHISHING not in post(m, 1, 10, content, 1)


# ── review round 3 ────────────────────────────────────────────────
async def test_the_raid_account_is_known_before_the_language_is_looked_up():
    c = cog()
    c.manager.update_settings(GUILD, {"raid_joins": 2, "raid_age_days": 0})
    c._send_log = AsyncMock()
    seen = []

    async def handle(member, gate, result, evidence):
        seen.append(set(c.manager.raiders.get(GUILD, ())))

    c._handle_join = handle
    guild = make_guild()
    await c.on_member_join(make_member(guild, 5))
    await c.on_member_join(make_member(guild, 6))
    assert seen == [{5, 6}]


async def test_a_heavier_rule_on_one_account_does_not_spare_the_rest_of_the_wave():
    c = cog()
    c.manager.update_settings(
        GUILD,
        {
            "similar_users": 3,
            "similar_action": "mute",
            "flood_messages": 1,
            "flood_action": "ban",
            "auto_escalate": False,
            "duplicate_enabled": False,
        },
    )
    guild = make_guild()
    channel = make_channel(guild, 10)
    first, second, third = [make_member(guild, user) for user in (5, 6, 7)]
    text = "check my profile for a free giveaway right now"
    await c.on_message(make_message(first, channel, text, 1))
    await c.on_message(make_message(second, channel, text, 2))
    await c.on_message(make_message(third, channel, "hello there", 3))
    await c.on_message(make_message(third, channel, text, 4))
    guild.ban.assert_awaited_once()
    second.timeout.assert_awaited_once()
    first.timeout.assert_not_awaited()  # said it first


async def test_lockdown_off_ends_a_raid_that_locked_nothing():
    from src.cogs.features.anti_spam import AntiSpam

    c = cog()
    c._send_log = AsyncMock()
    c.manager.update_settings(GUILD, {"raid_action": "kick", "raid_lift_minutes": 0})
    c.manager.raid_until[GUILD] = float("inf")
    c.manager.raiders[GUILD] = {1}
    guild = make_guild()
    guild.text_channels = [LockChannel(1)]
    guild.text_channels[0].send_messages = False  # someone's own setting: untouched
    admin, _ = interaction(guild, 2)
    await AntiSpam.lockdown_off_cmd.callback(c, admin)
    assert not c.manager.raid_active(GUILD)
    assert GUILD not in c.manager.raiders
    assert guild.text_channels[0].send_messages is False


# ── security review ───────────────────────────────────────────────
def test_a_backslash_cannot_hide_the_real_host():
    assert spam.link_host("https://evil.example\\@discord.com/") == "evil.example"
    m = manager(flood_messages=100)
    m.update_list(GUILD, "blocked_domains", "add", "evil.example")
    content = "https://evil.example\\@discord.com/x"
    assert spam.DETECT_PHISHING in post(m, 1, 10, content, 1)


async def test_copying_someone_s_post_does_not_get_them_punished():
    c = cog()
    c.manager.update_settings(GUILD, {"similar_users": 3, "flood_messages": 100})
    guild = make_guild()
    channel = make_channel(guild, 10)
    author, alt_one, alt_two = [make_member(guild, user) for user in (5, 6, 7)]
    text = "our server event starts on saturday at eight, everyone is welcome"
    original = make_message(author, channel, text, 1)
    await c.on_message(original)
    await c.on_message(make_message(alt_one, channel, text, 2))
    await c.on_message(make_message(alt_two, channel, text, 3))
    author.timeout.assert_not_awaited()
    original.delete.assert_not_awaited()
    assert all(
        1 not in [o.id for o in call.args[0]]
        for call in channel.delete_messages.await_args_list
    )


async def test_the_rest_of_a_wave_is_at_most_timed_out():
    c = cog()
    c.manager.update_settings(
        GUILD, {"similar_users": 3, "similar_action": "ban", "flood_messages": 100}
    )
    guild = make_guild()
    channel = make_channel(guild, 10)
    members = [make_member(guild, user) for user in (5, 6, 7)]
    text = "check my profile for a free giveaway right now"
    for n, member in enumerate(members):
        await c.on_message(make_message(member, channel, text, n + 1))
    assert [call.args[0].id for call in guild.ban.await_args_list] == [
        7
    ]  # caught in the act
    members[1].timeout.assert_awaited_once()


async def test_bans_through_bot_s_commands_count_for_the_moderator():
    c = cog()
    c.manager.update_settings(GUILD, {"nuke_limit": 3})
    c._stop_nuker = AsyncMock()
    guild = make_guild(owner_id=1)
    for target in (10, 11):
        await c.count_moderation(guild, 5, "ban", target)
    c._stop_nuker.assert_not_awaited()
    await c.count_moderation(guild, 5, "ban", 12)
    c._stop_nuker.assert_awaited_once()
    for target in (20, 21, 22):
        await c.count_moderation(guild, 1, "ban", target)  # the owner
    c._stop_nuker.assert_awaited_once()


def test_the_first_message_of_a_wave_of_links_does_not_stay_up():
    m = manager(flood_messages=100, similar_users=3)
    text = "come and see this https://example.org/landing"
    for user in (1, 2):
        assert post(m, user, 10 + user, text, user) == []
    evidence = Evidence()
    assert spam.DETECT_COORDINATED in post(m, 3, 13, text, 3, evidence)
    assert evidence.users == {2}  # copied or not, the first poster is not punished
    assert (11, 1) in evidence.messages
