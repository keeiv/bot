"""Arknights: Endfield through Enka.Network: parsing, caching, links and the AI part."""

import json
import json as _json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
from cryptography.fernet import Fernet
import discord
import pytest

from src.services import endfield_service as ef
from src.services import skport_client as sk
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


class Failing:
    """A request that fails on the way in, as aiohttp's do."""

    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        raise self.error

    async def __aexit__(self, *exc):
        return False


class Session:
    """Answers like Enka and GitHub; records each URL asked."""

    def __init__(self, status=200, answer=ANSWER):
        self.status = status
        self.answer = answer
        self.asked = []
        self.closed = False

    def get(self, url, headers=None):
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


# ── SKPORT accounts ───────────────────────────────────────────────
TOKEN = "account-token-secret"
CARD = {
    "dungeon": {"curStamina": "120", "maxStamina": "240"},
    "chars": [
        {
            "level": 40,
            "potentialLevel": 0,
            "charData": {
                "name": "Long",  # not an operator in the table: the name is kept
                "rarity": {"value": "4"},
                "property": {"value": "Cryo"},
                "profession": {"value": "Guard"},
            },
        },
        {
            "level": 90,
            "potentialLevel": 2,
            "charData": {
                "name": "Laevatain",
                "rarity": {"key": "rarity_6"},
                "property": {"value": "Heat"},
                "profession": {"value": "Striker"},
                "skills": [
                    {"id": "s1", "type": {"key": "skill_type_normal_skill"}},
                    {"id": "s2", "type": {"key": "skill_type_ultimate_skill"}},
                ],
            },
            "userSkills": {"s1": {"level": 11}},
            "weapon": {
                "level": 80,
                "refineLevel": 3,
                "weaponData": {"name": "Forgeborn Scathe", "rarity": {"value": "6"}},
            },
            "bodyEquip": {"equipData": {"suit": {"name": "Flamebreath"}}},
            "armEquip": {"equipData": {"suit": {"name": "Flamebreath"}}},
        },
    ],
}


class SkportSession(Session):
    """SKPORT as far as the bot sees it; every signed request is checked."""

    def __init__(self):
        super().__init__()
        self.logins = 0
        self.cards = 0
        self.card_failure = None  # a SKPORT code, or an exception to raise
        self.bad_login = False

    def post(self, url, json=None, headers=None):
        self.asked.append(url)
        if url == sk.GRANT_URL:
            assert json["appCode"] == sk.APP_CODE
            self.logins += 1
            good = json["token"] == TOKEN and not self.bad_login
            return Response(
                200,
                _json.dumps(
                    {"status": 0, "data": {"code": "grant"}}
                    if good
                    else {"status": 1, "msg": "no"}
                ),
            )
        return Response(
            200,
            _json.dumps({"code": 0, "data": {"cred": "cred", "token": "sign-token"}}),
        )

    def get(self, url, headers=None):
        if url.startswith(sk.HOST):
            self.asked.append(url)
            path, _, query = url[len(sk.HOST) :].partition("?")
            assert headers["cred"] == "cred"
            assert headers["sign"] == sk.sign(
                "sign-token", path, query, headers["timestamp"]
            )
            if path == sk.BINDING_PATH:
                role = {"roleId": UID, "serverId": "2", "nickname": "Nova"}
                body = {
                    "list": [
                        {"appCode": "endfield", "bindingList": [{"defaultRole": role}]}
                    ]
                }
            elif path == sk.ME_PATH:
                body = {"user": {"userId": "55"}}
            else:
                assert "roleId=" + UID in query and "userId=55" in query
                self.cards += 1
                if isinstance(self.card_failure, BaseException):
                    return Failing(self.card_failure)
                if self.card_failure is not None:
                    return Response(200, _json.dumps({"code": self.card_failure}))
                body = {"detail": CARD}
            return Response(200, _json.dumps({"code": 0, "data": body}))
        return super().get(url, headers)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GENSHIN_ENCRYPTION_KEY", Fernet.generate_key().decode())


def account_service():
    clock = Clock()
    session = SkportSession()
    svc, _ = service(session, clock)
    return svc, session, clock


@pytest.mark.parametrize(
    "pasted", [TOKEN, f"  {TOKEN}\n", '{"code":0,"data":{"content":"' + TOKEN + '"}}']
)
def test_a_token_comes_from_the_bare_value_or_the_page(pasted):
    assert sk.parse_token(pasted) == TOKEN


@pytest.mark.parametrize(
    "pasted", ["", "two words", "{not json", '{"data":{}}', "x" * 5000]
)
def test_anything_else_is_not_a_token(pasted):
    with pytest.raises(sk.SkportError):
        sk.parse_token(pasted)


async def test_a_linked_account_lists_every_operator_in_the_member_s_language(key):
    svc, _, _ = account_service()
    account = await svc.link_account(7, TOKEN, "zh")
    assert (account.uid, account.name) == (UID, "Nova")
    assert (account.stamina, account.stamina_max) == (120, 240)
    assert [op.name for op in account.operators] == ["萊萬汀", "長息"]  # best first
    best = account.operators[0]
    assert (best.element, best.profession, best.rarity) == ("灼熱", "突擊", 6)
    assert best.weapon_type == "單手劍"  # from the table, SKPORT does not say
    assert (best.weapon.name, best.weapon.potential) == ("熔鑄火焰", 3)
    assert best.sets == [("焰息", 2)]
    assert best.skills == [("戰技", 11), ("終結技", 1)]
    assert svc.bound_uid(7) == UID


async def test_the_token_is_stored_encrypted(key):
    svc, _, _ = account_service()
    await svc.link_account(7, TOKEN)
    assert TOKEN not in json_text()
    assert svc.has_account(7)


def json_text():
    from pathlib import Path

    return Path(ef.BINDINGS).read_text(encoding="utf-8")


async def test_a_bad_token_is_refused_and_not_kept_or_repeated(key):
    svc, session, _ = account_service()
    session.bad_login = True
    with pytest.raises(EndfieldError) as caught:
        await svc.link_account(7, TOKEN)
    assert caught.value.code == "bad_token"
    assert TOKEN not in str(caught.value)
    assert not svc.has_account(7)


async def test_linking_without_the_key_keeps_nothing(monkeypatch):
    monkeypatch.delenv("GENSHIN_ENCRYPTION_KEY", raising=False)
    svc, _, _ = account_service()
    with pytest.raises(EndfieldError) as caught:
        await svc.link_account(7, TOKEN)
    assert caught.value.code == "no_key"
    assert svc.bound_uid(7) is None


async def test_an_account_is_read_at_most_every_few_minutes(key):
    svc, session, clock = account_service()
    await svc.link_account(7, TOKEN)
    await svc.account(7)
    assert session.cards == 1
    clock.now += ef.ACCOUNT_SECONDS + 1
    await svc.account(7)
    assert (session.cards, session.logins) == (2, 1)  # the credential is reused


async def test_a_new_credential_is_tried_once_when_the_old_one_fails(key):
    svc, session, clock = account_service()
    await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    answers = [10003, None]
    real_detail = svc.skport.detail

    async def detail(login):
        session.card_failure = answers.pop(0)
        return await real_detail(login)

    svc.skport.detail = detail
    assert (await svc.account(7)).operators
    assert session.logins == 2


async def test_skport_being_down_shows_the_last_read_but_a_dead_token_is_reported(key):
    svc, session, clock = account_service()
    first = await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    session.card_failure = aiohttp.ClientError("down")
    assert (await svc.account(7)).read_at == first.read_at
    session.card_failure = None
    session.bad_login = True
    svc._logins.clear()
    with pytest.raises(EndfieldError) as caught:
        await svc.account(7)
    assert caught.value.code == "bad_token"


async def test_one_member_never_gets_another_s_account(key):
    svc, _, _ = account_service()
    await svc.link_account(7, TOKEN)
    assert await svc.account(8) is None


async def test_binding_a_uid_or_unbinding_drops_the_token(key):
    svc, _, _ = account_service()
    await svc.link_account(7, TOKEN)
    svc.bind(7, "123456789")
    assert not svc.has_account(7)
    assert await svc.account(7) is None
    await svc.link_account(7, TOKEN)
    assert svc.unbind(7)
    assert '"token"' not in json_text()


def test_the_ai_gets_the_roster_but_never_the_uid_or_token():
    profile_card = ef.Account(
        uid=UID,
        name="Nova",
        operators=[
            ef.Operator("萊萬汀", 6, "灼熱", "突擊", "單手劍", 90, 2, None),
        ],
        stamina=1,
        stamina_max=2,
        read_at=100.0,
    )
    text = ef.describe_account(profile_card, 101.0)
    assert "operators owned (1)" in text and "萊萬汀" in text and "stamina 1/2" in text
    assert UID not in text


async def test_bot_reads_the_whole_roster_when_an_account_is_linked(key):
    from src.cogs.features.ai_chat import AiChat

    endfield = cog(SkportSession())
    await endfield.service.link_account(7, TOKEN)
    chat = SimpleNamespace(bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get))
    text = await AiChat.endfield_profile(chat, 7)
    assert "operators owned (2)" in text
    assert UID not in text and TOKEN not in text


async def test_a_dead_token_falls_back_to_the_public_showcase(key):
    from src.cogs.features.ai_chat import AiChat

    session = SkportSession()
    endfield = cog(session)
    await endfield.service.link_account(7, TOKEN)
    endfield.service._cards.clear()
    endfield.service._logins.clear()
    session.bad_login = True
    chat = SimpleNamespace(bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get))
    assert "public showcase" in await AiChat.endfield_profile(chat, 7)


async def test_roster_without_a_link_explains_how():
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog()
    inter, sent = interaction()
    inter.response.defer = AsyncMock()
    await EndfieldCog.roster.callback(c, inter)
    assert "/endfield link" in sent[0][0][0]


async def test_the_token_is_asked_for_in_a_private_window_only():
    from src.cogs.features.endfield_cog import EndfieldCog

    params = [p.name for p in EndfieldCog.link.parameters]
    assert params == []  # never a slash option, which Discord would show back


async def test_linking_shows_the_roster_privately_and_tells_the_ai(key):
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog(SkportSession())
    inter, sent = interaction()
    await EndfieldCog.link_token(c, inter, TOKEN)
    assert ("endfield_bound", 7) in sent
    reply = next(s for s in sent if isinstance(s[1], dict))
    assert reply[1]["ephemeral"] is True
    assert "萊萬汀" in reply[1]["embed"].description
    assert TOKEN not in str(reply)


async def test_own_operator_lookup_reaches_those_not_on_show(key):
    from src.cogs.features.endfield_cog import EndfieldCog

    c = cog(SkportSession())
    await c.service.link_account(7, TOKEN)
    inter, sent = interaction()
    await EndfieldCog.operator.callback(c, inter, "長息", None)
    assert sent[0][1]["embed"].title.startswith("長息")


# ── review: SKPORT accounts ───────────────────────────────────────
async def test_two_links_at_once_cannot_mix_up_the_accounts(key):
    svc, _, _ = account_service()
    real_store = svc._store_token
    other = []

    def store_then_be_overtaken(user_id, uid, token):
        stored = real_store(user_id, uid, token)
        if not other:
            other.append(real_store(user_id, "123456789", "another-token"))
        return stored

    svc._store_token = store_then_be_overtaken
    await svc.link_account(7, TOKEN)
    assert svc._cards[7][0] != svc._stored_token(7)  # tagged with A, not B's
    assert svc.bound_uid(7) == "123456789"


async def test_unbinding_during_a_read_returns_nothing_and_rebuilds_nothing(key):
    svc, _, clock = account_service()
    await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    real_detail = svc.skport.detail

    async def unbind_meanwhile(login):
        found = await real_detail(login)
        svc.unbind(7)
        return found

    svc.skport.detail = unbind_meanwhile
    assert await svc.account(7) is None
    assert 7 not in svc._cards and 7 not in svc._logins


async def test_the_ai_never_reads_a_uid_from_a_link_already_gone():
    from src.cogs.features.ai_chat import AiChat

    endfield = cog()
    endfield.service.bind(7, UID)
    real = endfield.service.link_snapshot
    calls = []

    def gone_after_the_first_look(user_id):
        calls.append(user_id)
        if len(calls) > 1:
            endfield.service.unbind(7)
        return real(user_id)

    endfield.service.link_snapshot = gone_after_the_first_look
    chat = SimpleNamespace(bot=SimpleNamespace(get_cog={"EndfieldCog": endfield}.get))
    assert await AiChat.endfield_profile(chat, 7) is None


@pytest.mark.parametrize(
    "status, body",
    [
        (503, '{"code":500,"message":"maintenance"}'),
        (429, '{"code":0}'),
        (200, '{"code":503}'),
        (200, '{"code":429}'),
    ],
)
async def test_an_outage_is_not_a_dead_token(key, status, body):
    svc, session, clock = account_service()
    first = await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    real_get = session.get

    def failing(url, headers=None):
        if sk.DETAIL_PATH in url:
            return Response(status, body)
        return real_get(url, headers)

    session.get = failing
    assert (await svc.account(7)).read_at == first.read_at


async def test_account_memory_stays_bounded(key, monkeypatch):
    monkeypatch.setattr(ef, "ACCOUNT_CACHE_LIMIT", 3)
    svc, _, clock = account_service()
    for member in range(1, 7):
        clock.now += 1
        await svc.link_account(member, TOKEN)
        await svc.account(member)
    assert sorted(svc._cards) == [4, 5, 6]
    assert sorted(svc._logins) == [4, 5, 6]
    assert svc._account_locks == {}


async def test_an_outage_during_a_relink_does_not_mix_two_accounts(key):
    svc, session, clock = account_service()
    await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    real_detail = svc.skport.detail

    async def relinked_meanwhile(login):
        svc._store_token(7, "123456789", "another-token")
        raise sk.SkportError("unavailable")

    svc.skport.detail = relinked_meanwhile
    assert await svc.account(7) is None  # the old card is not theirs now
    svc.skport.detail = real_detail


async def test_an_outage_after_unbinding_shows_no_old_card(key):
    svc, _, clock = account_service()
    await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1

    async def unbound_meanwhile(login):
        svc.unbind(7)
        raise sk.SkportError("unavailable")

    svc.skport.detail = unbound_meanwhile
    assert await svc.account(7) is None


async def test_a_read_dropped_from_a_full_cache_is_still_returned(key, monkeypatch):
    monkeypatch.setattr(ef, "ACCOUNT_CACHE_LIMIT", 1)
    svc, _, clock = account_service()
    await svc.link_account(7, TOKEN)
    clock.now += ef.ACCOUNT_SECONDS + 1
    real_detail = svc.skport.detail

    async def another_member_links_meanwhile(login):
        found = await real_detail(login)
        clock.now += 5
        svc.skport.detail = real_detail
        await svc.link_account(8, TOKEN)
        return found

    svc.skport.detail = another_member_links_meanwhile
    account = await svc.account(7)
    assert account.uid == UID and account.operators
