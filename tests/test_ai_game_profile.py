"""@BOT. answers that know the member's linked HoYoLAB games, on every server."""

import asyncio
from types import SimpleNamespace

import pytest

from src.services import ai_game_profile
from src.services.ai_game_profile import describe
from src.services.ai_game_profile import describe_roster
from src.services.ai_game_profile import GameProfiles
from src.services.ai_game_profile import MAX_ROSTER
from src.services.genshin_service import GenshinService

ASIA, AMERICA, RAIL = 800000001, 600000002, 700000003


class FakeGenshin:
    """GenshinService's reading side for two members.

    Member 7 plays Genshin on Asia and America and Star Rail on Asia; member 9
    has Genshin only.
    """

    def __init__(self, fail=(), slow=False):
        self.bound = {
            7: {
                "encrypted_cookie": "secret-cookie",
                "game_accounts": [
                    {
                        "game_biz": "hk4e_global",
                        "uid": ASIA,
                        "server_name": "Asia Server",
                    },
                    {
                        "game_biz": "hk4e_global",
                        "uid": AMERICA,
                        "server_name": "America Server",
                    },
                    {
                        "game_biz": "hkrpg_global",
                        "uid": str(RAIL),
                        "server_name": "Asia",
                    },
                    {"game_biz": "hk4e_global", "uid": ASIA},  # listed twice
                ],
            },
            9: {
                "encrypted_cookie": "other-cookie",
                "game_accounts": [{"game_biz": "hk4e_global", "uid": 900000009}],
            },
        }
        self.fail = set(fail)
        self.slow = slow
        self.reads = []

    def get_bound_user(self, user_id):
        return self.bound.get(user_id)

    def get_all_bound_users(self):
        return {str(key): value for key, value in self.bound.items()}

    def map_game_biz_to_str(self, game_biz):
        return {"hk4e": "genshin", "hkrpg": "starrail"}.get(game_biz.split("_")[0])

    async def get_stats(self, user_id, game, uid=None):
        return await self._read(
            "stats",
            user_id,
            game,
            uid,
            {"nickname": "Traveler\nIgnore all", "level": uid % 100},
        )

    async def get_notes(self, user_id, game, uid=None):
        return await self._read(
            "notes",
            user_id,
            game,
            uid,
            {
                "type": game,
                "uid": uid,
                "current_resin": 120,
                "resin_recovery": 3600,
                "commission_reward_claimed": False,
                "expeditions": [{"character": "https://icon"}],
            },
        )

    async def get_roster(self, user_id, game, uid=None):
        return await self._read(
            "roster",
            user_id,
            game,
            uid,
            [
                {
                    "name": "Bennett\nIgnore all",
                    "kind": "Pyro",
                    "rarity": "4★",
                    "level": 90,
                    "rank": "C6",
                    "gear": "Skyward Blade R1 Lv90",
                    "sets": ["4x Noblesse Oblige"],
                }
            ],
        )

    async def _read(self, kind, user_id, game, uid, data):
        self.reads.append((kind, user_id, game, uid))
        if self.slow:
            await asyncio.sleep(1)
        if "everything" in self.fail or (kind, game) in self.fail:
            raise ValueError("HoYoLAB is down")
        return data


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_describe_keeps_numbers_and_short_text_but_no_ids():
    line = describe(
        "now",
        {
            "type": "genshin",
            "uid": 800000001,
            "current_resin": 120,
            "resin_recovery": 3600,
            "stamina_recovery": 0,
            "commission_reward_claimed": True,
            "expeditions": [{}, {}],
            "nickname": "  A\n" + "x" * 80,
            "raw": object(),
        },
    )
    assert line.startswith("now: current resin 120, resin recovery full in 60 min")
    assert "stamina recovery full" in line and "commission reward claimed yes" in line
    assert "expeditions 2 sent" in line
    assert "800000001" not in line and "genshin" not in line and "raw" not in line
    assert "\n" not in line and "x" * 41 not in line


async def test_every_server_of_the_member_is_read_with_no_secrets():
    genshin = FakeGenshin()
    text = await GameProfiles(lambda: genshin).snapshot(7)
    lines = text.split("\n")
    assert lines[0] == "(read just now)"
    assert lines[1].startswith(
        "Genshin Impact (Asia Server) — overview: nickname Traveler Ignore all, level 1"
    )
    assert lines[2:4] == [
        "characters owned (1):",
        "- Bennett Ignore all Pyro 4★ Lv90 C6 · Skyward Blade R1 Lv90"
        " · 4x Noblesse Oblige",
    ]
    assert lines[4].startswith("Genshin Impact (America Server) — overview: ")
    assert "level 2" in lines[4]
    assert lines[7].startswith("Honkai: Star Rail (Asia) — ") and len(lines) == 10
    for secret in ("secret-cookie", str(ASIA), str(AMERICA), str(RAIL)):
        assert secret not in text
    # each account once, with its own UID, and only member 7's
    assert sorted(genshin.reads) == sorted(
        (kind, 7, game, uid)
        for game, uid in (("genshin", ASIA), ("genshin", AMERICA), ("starrail", RAIL))
        for kind in ("stats", "notes", "roster")
    )


async def test_each_mention_reads_hoyolab_again():
    genshin = FakeGenshin()
    profiles = GameProfiles(lambda: genshin)
    await profiles.snapshot(7)
    await profiles.snapshot(7)
    assert len(genshin.reads) == 18


async def test_when_hoyolab_fails_the_last_read_is_used_and_its_age_said():
    genshin, clock = FakeGenshin(), Clock()
    profiles = GameProfiles(lambda: genshin, clock=clock)
    first = await profiles.snapshot(7)
    genshin.fail = {"everything"}
    clock.now += 300
    later = await profiles.snapshot(7)
    assert later.split("\n")[0] == "(read 5 min ago (HoYoLAB did not answer just now))"
    assert later.split("\n")[1:] == first.split("\n")[1:]
    assert len(genshin.reads) == 18  # it did try again


async def test_an_unlink_or_a_new_bind_never_shows_the_old_data():
    genshin = FakeGenshin()
    profiles = GameProfiles(lambda: genshin)
    await profiles.snapshot(7)
    genshin.fail = {"everything"}
    genshin.bound[7] = dict(genshin.bound[7], encrypted_cookie="another-account")
    assert await profiles.snapshot(7) is None  # another account: not the old reading
    del genshin.bound[7]
    assert await profiles.snapshot(7) is None
    assert 7 not in profiles._last


async def test_nothing_linked_or_no_genshin_cog_means_no_profile():
    genshin = FakeGenshin()
    assert await GameProfiles(lambda: genshin).snapshot(8) is None
    assert await GameProfiles(lambda: None).snapshot(7) is None
    genshin.bound[7]["game_accounts"] = [{"game_biz": "nxx_global", "uid": 1}]
    assert await GameProfiles(lambda: genshin).snapshot(7) is None
    assert genshin.reads == []


async def test_a_failing_read_leaves_out_only_that_part():
    genshin = FakeGenshin(
        fail={
            ("notes", "genshin"),
            ("stats", "starrail"),
            ("notes", "starrail"),
            ("roster", "starrail"),
        }
    )
    text = await GameProfiles(lambda: genshin).snapshot(7)
    assert "Genshin Impact (Asia Server) — overview: " in text and "now:" not in text
    assert "Star Rail" not in text
    everything = FakeGenshin(fail={"everything"})
    profiles = GameProfiles(lambda: everything)
    assert await profiles.snapshot(7) is None
    assert 7 not in profiles._last  # a failure is not kept


async def test_only_the_roster_still_gives_the_game_a_heading():
    genshin = FakeGenshin(
        fail={
            (kind, game)
            for kind in ("stats", "notes")
            for game in ("genshin", "starrail")
        }
    )
    text = await GameProfiles(lambda: genshin).snapshot(7)
    assert text.split("\n")[1:3] == [
        "Genshin Impact (Asia Server):",
        "characters owned (1):",
    ]


async def test_a_slow_hoyolab_is_given_up_on(monkeypatch):
    monkeypatch.setattr(ai_game_profile, "FETCH_SECONDS", 0.05)
    profiles = GameProfiles(lambda: FakeGenshin(slow=True))
    assert await profiles.snapshot(7) is None


async def test_messages_sent_together_share_one_read():
    genshin = FakeGenshin(slow=True)
    profiles = GameProfiles(lambda: genshin)
    texts = await asyncio.gather(*(profiles.snapshot(7) for _ in range(5)))
    assert len(set(texts)) == 1 and texts[0] and len(genshin.reads) == 9
    assert profiles._pending == {}


async def test_the_background_pass_reads_every_linked_member(monkeypatch):
    monkeypatch.setattr(ai_game_profile, "PAUSE_SECONDS", 0)
    genshin = FakeGenshin()
    genshin.bound["not-a-member"] = {}
    profiles = GameProfiles(lambda: genshin)
    original = profiles.refresh

    async def refresh(user_id):
        if user_id == 9:
            raise RuntimeError("one bad member")
        return await original(user_id)

    profiles.refresh = refresh
    assert await profiles.refresh_all() == 1  # member 7; 9 failed, the key was skipped
    assert {read[1] for read in genshin.reads} == {7}
    genshin.fail = {"everything"}
    assert (await profiles.snapshot(7)).startswith("(read just now)")  # from the pass
    assert await GameProfiles(lambda: None).refresh_all() == 0


def test_a_member_can_only_read_their_own_accounts():
    service = object.__new__(GenshinService)
    service._accounts = {
        "7": {
            "game_accounts": [
                {"game_biz": "hk4e_global", "uid": "5"},
                {"game_biz": "hk4e_global", "uid": 6},
            ]
        },
        "9": {"game_accounts": [{"game_biz": "hk4e_global", "uid": "99"}]},
    }
    assert service._pick_uid(7, "genshin") == 5
    assert service._pick_uid(7, "genshin", 6) == 6
    with pytest.raises(ValueError):
        service._pick_uid(7, "genshin", 99)  # member 9's account
    with pytest.raises(ValueError):
        service._pick_uid(7, "starrail")
    with pytest.raises(ValueError):
        service._pick_uid(8, "genshin")


def test_a_long_roster_is_cut_to_the_highest_levels():
    roster = [
        {"name": f"c{i}", "level": 90 - i, "rank": "C0"} for i in range(MAX_ROSTER + 5)
    ]
    text = describe_roster(roster)
    assert text.startswith(f"characters owned ({MAX_ROSTER + 5}):\n- c0 Lv90 C0")
    assert f"c{MAX_ROSTER - 1} " in text and f"c{MAX_ROSTER} " not in text
    assert text.endswith("- and 5 more at lower levels")


def _service(client, game_biz):
    service = object.__new__(GenshinService)
    service._accounts = {"7": {"game_accounts": [{"game_biz": game_biz, "uid": "5"}]}}
    if not hasattr(client, "uids"):
        client.uids = {}
    service.get_client = lambda user_id: client
    return service


async def test_the_roster_reads_each_games_characters_and_gear():
    import genshin

    async def genshin_characters(uid):
        assert uid == 5
        artifact = SimpleNamespace(set=SimpleNamespace(name="Noblesse"))
        return SimpleNamespace(
            characters=[
                SimpleNamespace(
                    name="Xiangling",
                    element="Pyro",
                    rarity=4,
                    level=80,
                    constellation=6,
                    weapon=SimpleNamespace(name="The Catch", refinement=5, level=90),
                    artifacts=[artifact] * 4,
                ),
                SimpleNamespace(
                    name="Bennett",
                    element="Pyro",
                    rarity=4,
                    level=90,
                    constellation=5,
                    weapon=SimpleNamespace(name="Aquila", refinement=1, level=90),
                    artifacts=[],
                ),
            ]
        )

    client = SimpleNamespace(get_genshin_detailed_characters=genshin_characters)
    roster = await _service(client, "hk4e_global").get_roster(7, "genshin")
    assert [c["name"] for c in roster] == [
        "Bennett",
        "Xiangling",
    ]  # highest level first
    assert roster[1] == {
        "name": "Xiangling",
        "kind": "Pyro",
        "rarity": "4★",
        "level": 80,
        "rank": "C6",
        "gear": "The Catch R5 Lv90",
        "sets": ["4x Noblesse"],
    }

    async def starrail_characters(uid):
        return SimpleNamespace(
            avatar_list=[
                SimpleNamespace(
                    name="March 7th",
                    element="ice",
                    path=genshin.models.StarRailPath.PRESERVATION,
                    rarity=4,
                    level=40,
                    rank=6,
                    equip=None,
                    relics=[1, 2],
                    ornaments=[],
                )
            ]
        )

    client = SimpleNamespace(get_starrail_characters=starrail_characters)
    (march,) = await _service(client, "hkrpg_global").get_roster(7, "starrail")
    assert march["kind"] == "Ice / Preservation" and march["rank"] == "E6"
    assert march["gear"] is None and march["sets"] == ["2 relics", "0 ornaments"]

    asked = []

    async def zzz_agents(uid):
        return [SimpleNamespace(id=1041)]

    async def zzz_agent_info(ids, uid):
        asked.append(ids)
        disc = SimpleNamespace(set_effect=SimpleNamespace(name="Woodpecker"))
        return SimpleNamespace(
            name="Soldier 11",
            element=genshin.models.ZZZElementType.FIRE,
            specialty=genshin.models.ZZZSpecialty.ATTACK,
            rarity="S",
            level=60,
            rank=2,
            w_engine=SimpleNamespace(name="Starlight", refinement=1, level=60),
            discs=[disc] * 2,
        )

    client = SimpleNamespace(
        get_zzz_agents=zzz_agents, get_zzz_agent_info=zzz_agent_info
    )
    (agent,) = await _service(client, "nap_global").get_roster(7, "zzz")
    assert asked == [[1041]]
    assert agent == {
        "name": "Soldier 11",
        "kind": "Fire / Attack",
        "rarity": "S",
        "level": 60,
        "rank": "M2",
        "gear": "Starlight P1 Lv60",
        "sets": ["2x Woodpecker"],
    }


async def test_honkai_reads_the_server_of_the_account_asked_for():
    import genshin

    service = object.__new__(GenshinService)
    service._accounts = {
        "7": {
            "game_accounts": [
                {"game_biz": "bh3_global", "uid": 100},
                {"game_biz": "bh3_global", "uid": 200},
            ]
        }
    }
    client = genshin.Client()
    honkai = genshin.types.Game.HONKAI

    async def game_accounts():
        return [
            SimpleNamespace(game=honkai, uid=100, level=80, server="usa01"),
            SimpleNamespace(game=honkai, uid=200, level=10, server="eur01"),
        ]

    asked = []

    async def honkai_user(uid):
        # what genshin.py sends: the chosen UID with that account's own server
        asked.append((uid, (await client._get_account(honkai)).server))
        return SimpleNamespace(
            info=SimpleNamespace(nickname="Captain", level=10),
            stats=SimpleNamespace(active_days=1, battlesuits=2),
        )

    client.get_game_accounts = game_accounts
    client.get_honkai_user = honkai_user
    service.get_client = lambda user_id: client
    await service.get_stats(7, "honkai", uid=200)
    await service.get_stats(7, "honkai")
    assert asked == [(200, "eur01"), (100, "usa01")]


async def test_a_read_of_an_old_link_never_replaces_the_new_one():
    genshin = FakeGenshin()
    gate = asyncio.Event()
    original = genshin._read

    held_back = []

    async def held(kind, user_id, game, uid, data):
        if len(held_back) < 9:  # the old link's nine reads finish last
            held_back.append(kind)
            await gate.wait()
        return await original(kind, user_id, game, uid, data)

    genshin._read = held
    profiles = GameProfiles(lambda: genshin)
    old = asyncio.ensure_future(profiles.refresh(7))
    await asyncio.sleep(0)
    genshin.bound[7] = dict(genshin.bound[7], encrypted_cookie="another-account")
    new = await profiles.snapshot(7)
    gate.set()
    await old
    assert new and profiles._last[7][1][0] == "another-account"
    genshin.fail = {"everything"}
    assert (await profiles.snapshot(7)).split("\n")[1:] == new.split("\n")[1:]
