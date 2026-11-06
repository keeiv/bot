"""Arknights: Endfield through Enka.Network: parsing, caching, links and the AI part."""

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from src.services import endfield_service as ef
from src.services.endfield_service import EndfieldError
from src.services.endfield_service import EndfieldService

UID = "4225399080"

# The shape of Enka's answer, trimmed from a real one (2026-11, game 1.6).
ANSWER = {
    "uid": UID,
    "ttl": 50,
    "region": "ASIA",
    "playerInfo": {
        "businessCard": {
            "name": "Nova",
            "signature": "Hello Beautiful",
            "adventureLevel": 60,
            "worldLevel": 7,
            "platformRoleId": UID,
            "statistic": {"charNum": 26, "weaponNum": 57, "docNum": 155},
        },
        "charData": [
            {
                "templateId": 23,
                "level": 90,
                "potentialLevel": 1,
                "equip": [
                    {"key": 1, "value": {"templateid": 3116}},
                    {"key": 2, "value": {"templateid": 3116}},
                    {"key": 3, "value": {"templateid": 3023}},
                ],
                "weapon": {"templateId": 1797, "weaponLv": 90, "refineLv": 2},
                "skillInfo": {
                    "levelInfo": [
                        {"skillId": "chr_0016_laevat_NormalSkill", "skillLevel": 11},
                        {"skillId": "chr_0016_laevat_UltimateSkill", "skillLevel": 10},
                    ]
                },
            },
            {"templateId": 999999, "level": 1},  # newer than the store: left out
        ],
    },
}
TABLES = {
    "avatars": {
        "23": {
            "StrId": "chr_0016_laevat",
            "NameHash": "1",
            "Rarity": 6,
            "Element": "Fire",
            "Profession": "ASSAULT",
            "WeaponType": "Sword",
        }
    },
    "weapons": {"1797": {"NameHash": "2", "Rarity": 6}},
    "equips": {
        "Items": {
            "3116": {"SuitId": "suit_fire_natr01"},
            "3023": {"SuitId": "suit_other"},
        },
        "Suits": {
            "suit_fire_natr01": {"NameHash": "3"},
            "suit_other": {"NameHash": "4"},
        },
    },
    "locs": {
        "zh-tw": {"1": "萊萬汀", "2": "熔鑄火焰", "3": "焰息", "4": "長息"},
        "en": {
            "1": "Laevatain",
            "2": "Forgeborn Scathe",
            "3": "Flamebreath",
            "4": "Long",
        },
    },
}


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def text(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class Session:
    """Answers like Enka and GitHub; records each URL asked."""

    def __init__(self, status=200, answer=ANSWER):
        self.status = status
        self.answer = answer
        self.asked = []
        self.closed = False

    def get(self, url):
        self.asked.append(url)
        if url.startswith("https://raw.githubusercontent.com/"):
            name = url.rsplit("/", 1)[-1].removesuffix(".json")
            return Response(200, json.dumps(TABLES[name]))
        if isinstance(self.status, BaseException):
            raise self.status
        body = json.dumps(self.answer) if self.status == 200 else ""
        return Response(self.status, body)

    async def close(self):
        self.closed = True


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def service(session=None, clock=None):
    session = session or Session()
    return EndfieldService(lambda **_: session, clock or Clock()), session


def enka_calls(session):
    return [url for url in session.asked if "enka.network" in url]


# ── parsing ───────────────────────────────────────────────────────
async def test_a_showcase_is_named_from_the_store_in_the_member_s_language():
    svc, _ = service()
    profile = await svc.profile(UID, "zh")
    assert (profile.name, profile.region, profile.adventure_level) == (
        "Nova",
        "亞洲",
        60,
    )
    assert (profile.operators_owned, profile.weapons_owned) == (26, 57)
    [op] = profile.showcase  # the unknown operator is left out
    assert (op.name, op.rarity, op.element, op.profession) == (
        "萊萬汀",
        6,
        "灼熱",
        "突擊",
    )
    assert op.weapon.name == "熔鑄火焰" and op.weapon.potential == 2
    assert op.sets == [("焰息", 2), ("長息", 1)]
    assert op.skills == [("戰技", 11), ("終結技", 10)]
    english = await svc.profile(UID, "en")
    assert english.showcase[0].name == "Laevatain"
    assert english.showcase[0].element == "Heat"


async def test_the_ai_gets_the_operators_but_never_the_uid():
    svc, _ = service()
    profile = await svc.profile(UID, "zh")
    text = ef.describe(profile, profile.read_at + 5)
    assert "萊萬汀" in text and "熔鑄火焰" in text and "read just now" in text
    assert UID not in text
    assert "min ago" in ef.describe(profile, profile.read_at + 600)


# ── Enka's rules: a User-Agent, and each UID once per ttl ─────────
async def test_a_uid_is_asked_again_only_after_its_ttl():
    clock = Clock()
    svc, session = service(clock=clock)
    await svc.profile(UID)
    await svc.profile(UID)
    assert len(enka_calls(session)) == 1
    clock.now += ef.MIN_TTL + 1  # Enka's ttl (50 s) is raised to the floor
    await svc.profile(UID)
    assert len(enka_calls(session)) == 2


async def test_requests_carry_bot_s_user_agent():
    made = {}

    def factory(**kwargs):
        made.update(kwargs)
        return Session()

    svc = EndfieldService(factory, Clock())
    await svc.profile(UID)
    assert made["headers"]["User-Agent"] == ef.USER_AGENT


@pytest.mark.parametrize(
    "status, code",
    [
        (400, "bad_uid"),
        (404, "not_found"),
        (424, "maintenance"),
        (429, "rate_limited"),
        (500, "unavailable"),
    ],
)
async def test_enka_s_answers_become_clear_errors(status, code):
    svc, _ = service(Session(status))
    with pytest.raises(EndfieldError) as caught:
        await svc.profile(UID)
    assert caught.value.code == code


async def test_a_busy_enka_falls_back_to_the_last_read_but_never_hides_a_wrong_uid():
    clock = Clock()
    session = Session()
    svc, _ = service(session, clock)
    first = await svc.profile(UID)
    clock.now += 3600
    session.status = 429
    assert (await svc.profile(UID)).read_at == first.read_at
    session.status = 404
    with pytest.raises(EndfieldError):
        await svc.profile(UID)


async def test_a_malformed_uid_is_refused_without_asking_enka():
    svc, session = service()
    for uid in ("12ab", "../../etc", "1" * 20, ""):
        with pytest.raises(EndfieldError):
            await svc.profile(uid)
    assert enka_calls(session) == []


# ── the store ─────────────────────────────────────────────────────
async def test_the_store_is_read_from_disk_and_downloaded_once_a_day():
    clock = Clock()
    svc, session = service(clock=clock)
    await svc.store()
    downloads = len(session.asked)
    assert downloads == len(ef.STORE_FILES)
    assert os.path.exists(os.path.join(ef.STORE_DIR, "avatars.json"))
    again, session2 = service(clock=clock)  # a restart: the files on disk are fresh
    await again.store()
    assert session2.asked == []


async def test_without_a_store_the_lookup_says_unavailable():
    session = Session()
    session.get = lambda url: (_ for _ in ()).throw(OSError("offline"))
    svc, _ = service(session)
    with pytest.raises(EndfieldError) as caught:
        await svc.store()
    assert caught.value.code == "unavailable"


# ── links ─────────────────────────────────────────────────────────
def test_a_link_is_one_uid_per_member():
    svc, _ = service()
    assert svc.bound_uid(1) is None
    svc.bind(1, UID)
    svc.bind(2, "123456789")
    assert (svc.bound_uid(1), svc.bound_uid(2)) == (UID, "123456789")
    with pytest.raises(EndfieldError):
        svc.bind(1, "not a uid")
    assert svc.unbind(1) and not svc.unbind(1)
    assert svc.bound_uid(1) is None


# ── commands ──────────────────────────────────────────────────────
def interaction(user_id=7):
    sent = []

    async def followup(*args, **kwargs):
        sent.append((args, kwargs))

    return (
        SimpleNamespace(
            user=SimpleNamespace(id=user_id),
            guild_id=None,
            locale=discord.Locale.taiwan_chinese,
            client=SimpleNamespace(
                get_guild=lambda _: None, dispatch=lambda *a: sent.append(a)
            ),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=followup),
        ),
        sent,
    )


def cog(session=None):
    from src.cogs.features.endfield_cog import EndfieldCog

    c = EndfieldCog(SimpleNamespace())
    c.service, _ = service(session)
    return c


async def test_binding_an_unknown_uid_is_refused():
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog(Session(404))
    inter, sent = interaction()
    await EndfieldCog.bind.callback(c, inter, UID)
    assert c.service.bound_uid(7) is None
    assert "找不到" in sent[0][0][0]


async def test_binding_shows_the_card_and_tells_the_ai():
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog()
    inter, sent = interaction()
    await EndfieldCog.bind.callback(c, inter, f" {UID} ")
    assert c.service.bound_uid(7) == UID
    assert ("endfield_bound", 7) in sent
    card = next(
        s[1]["embed"] for s in sent if isinstance(s[1], dict) and "embed" in s[1]
    )
    assert "萊萬汀" in card.fields[-1].value


async def test_looking_up_without_a_link_explains_how_to_link():
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog()
    inter, sent = interaction()
    await EndfieldCog.profile.callback(c, inter, None)
    assert "/endfield bind" in sent[0][0][0]


async def test_an_operator_is_found_by_part_of_the_name():
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog()
    inter, sent = interaction()
    await EndfieldCog.operator.callback(c, inter, "萊萬", UID)
    assert sent[0][1]["embed"].title.startswith("萊萬汀")
    inter, sent = interaction()
    await EndfieldCog.operator.callback(c, inter, "陳千語", UID)
    assert "萊萬汀" in sent[0][0][0]  # says who is shown instead


# ── the AI part ───────────────────────────────────────────────────
async def test_bot_reads_the_member_s_own_showcase_with_their_hoyolab_games():
    from src.cogs.features.ai_chat import AiChat

    endfield = cog()
    endfield.service.bind(7, UID)
    chat = SimpleNamespace(
        bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get),
        profiles=SimpleNamespace(
            snapshot=AsyncMock(return_value="(read just now)\nGenshin")
        ),
    )
    chat.endfield_profile = lambda user_id: AiChat.endfield_profile(chat, user_id)
    text = await AiChat.game_profile(chat, 7)
    assert text.startswith("(read just now)\nGenshin")
    assert "萊萬汀" in text and UID not in text
    assert await AiChat.endfield_profile(chat, 8) is None  # someone else: nothing


async def test_one_game_failing_does_not_hide_the_other():
    from src.cogs.features.ai_chat import AiChat

    endfield = cog()
    endfield.service.bind(7, UID)
    chat = SimpleNamespace(
        bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get),
        profiles=SimpleNamespace(
            snapshot=AsyncMock(side_effect=RuntimeError("HoYoLAB down"))
        ),
    )
    chat.endfield_profile = lambda user_id: AiChat.endfield_profile(chat, user_id)
    assert "萊萬汀" in await AiChat.game_profile(chat, 7)


# ── review ────────────────────────────────────────────────────────
async def test_a_read_finished_after_unlinking_never_reaches_the_ai():
    from src.cogs.features.ai_chat import AiChat

    endfield = cog()
    endfield.service.bind(7, UID)
    real = endfield.service.profile

    async def unlink_meanwhile(uid, lang):
        found = await real(uid, lang)
        endfield.service.bind(7, "123456789")
        return found

    endfield.service.profile = unlink_meanwhile
    chat = SimpleNamespace(bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get))
    assert await AiChat.endfield_profile(chat, 7) is None


async def test_a_full_cache_never_drops_a_uid_before_its_ttl(monkeypatch):
    monkeypatch.setattr(ef, "CACHE_LIMIT", 3)
    long_lived = {**ANSWER, "ttl": 3600}
    svc, session = service(Session(answer=long_lived))
    for uid in ("100000001", "100000002", "100000003"):
        await svc.raw(uid)
    with pytest.raises(EndfieldError) as caught:
        await svc.raw("100000004")
    assert caught.value.code == "rate_limited"
    await svc.raw("100000001")
    assert len(enka_calls(session)) == 3  # the first was not asked again


async def test_a_full_cache_makes_room_once_entries_expire(monkeypatch):
    monkeypatch.setattr(ef, "CACHE_LIMIT", 2)
    clock = Clock()
    svc, session = service(clock=clock)
    await svc.raw("100000001")
    await svc.raw("100000002")
    clock.now += ef.MIN_TTL + 1
    await svc.raw("100000003")
    assert len(svc._raw) == 1


async def test_a_player_found_gone_stays_gone():
    clock = Clock()
    session = Session()
    svc, _ = service(session, clock)
    await svc.profile(UID)
    clock.now += 3600
    session.status = 404
    with pytest.raises(EndfieldError):
        await svc.profile(UID)
    session.status = 429
    with pytest.raises(EndfieldError) as caught:
        await svc.profile(UID)  # no old card to fall back on
    assert caught.value.code == "rate_limited"


async def test_tables_loaded_from_disk_keep_their_real_age(monkeypatch):
    clock = Clock()
    svc, session = service(clock=clock)
    await svc.store()
    downloads = len(session.asked)
    monkeypatch.setattr(ef.time, "time", lambda: clock.now)
    path = os.path.join(ef.STORE_DIR, "avatars.json")
    os.utime(path, (clock.now - 23 * 3600, clock.now - 23 * 3600))
    restarted, session2 = service(clock=clock)
    await restarted.store()
    assert session2.asked == []  # 23 hours old: still fine
    clock.now += 2 * 3600
    await restarted.store()
    assert len(session2.asked) == downloads  # 25 hours old by now


async def test_a_failed_download_is_retried_after_an_hour_not_on_every_read(
    monkeypatch,
):
    clock = Clock()
    svc, _ = service(clock=clock)
    await svc.store()
    monkeypatch.setattr(ef.time, "time", lambda: clock.now)
    clock.now += ef.STORE_SECONDS + 1
    old = clock.now - 2 * ef.STORE_SECONDS
    os.utime(os.path.join(ef.STORE_DIR, "avatars.json"), (old, old))
    tries = []

    async def fail():
        tries.append(1)
        raise OSError("offline")

    svc._store_at = 0.0
    svc._download_store = fail
    await svc.store()
    await svc.store()
    assert len(tries) == 1
    clock.now += ef.STORE_RETRY_SECONDS + 1
    await svc.store()
    assert len(tries) == 2
