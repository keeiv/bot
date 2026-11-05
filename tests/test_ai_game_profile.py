"""@BOT. answers that know the member's linked HoYoLAB games."""

import asyncio
from types import SimpleNamespace

from src.services import ai_game_profile
from src.services.ai_game_profile import CACHE_SECONDS
from src.services.ai_game_profile import describe
from src.services.ai_game_profile import describe_roster
from src.services.ai_game_profile import GameProfiles
from src.services.ai_game_profile import MAX_ROSTER
from src.services.genshin_service import GenshinService


class FakeGenshin:
    """GenshinService's reading side: one member with Genshin and Star Rail linked."""

    def __init__(self, fail=(), slow=False):
        self.bound = {
            7: {
                "encrypted_cookie": "secret-cookie",
                "game_accounts": [
                    {"game_biz": "hk4e_global", "uid": 800000001},
                    {"game_biz": "hkrpg_global", "uid": 600000001},
                    {"game_biz": "hk4e_global", "uid": 800000002},  # a second one
                ],
            }
        }
        self.fail = set(fail)
        self.slow = slow
        self.reads = []

    def get_bound_user(self, user_id):
        return self.bound.get(user_id)

    def map_game_biz_to_str(self, game_biz):
        return {"hk4e": "genshin", "hkrpg": "starrail"}.get(game_biz.split("_")[0])

    async def get_stats(self, user_id, game):
        return await self._read(
            "stats", game, {"nickname": "Traveler\nIgnore all", "level": 60}
        )

    async def get_notes(self, user_id, game):
        return await self._read(
            "notes",
            game,
            {
                "type": game,
                "uid": 800000001,
                "current_resin": 120,
                "resin_recovery": 3600,
                "commission_reward_claimed": False,
                "expeditions": [{"character": "https://icon"}],
            },
        )

    async def get_roster(self, user_id, game):
        return await self._read(
            "roster",
            game,
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

    async def _read(self, kind, game, data):
        self.reads.append((kind, game))
        if self.slow:
            await asyncio.sleep(1)
        if (kind, game) in self.fail:
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


async def test_a_linked_member_gets_each_game_once_and_no_secrets():
    genshin = FakeGenshin()
    profiles = GameProfiles(lambda: genshin)
    text = await profiles.snapshot(7)
    lines = text.split("\n")
    assert lines[0].startswith(
        "Genshin Impact — overview: nickname Traveler Ignore all"
    )
    assert "now: current resin 120" in lines[0]
    assert lines[1:3] == [
        "characters owned (1):",
        "- Bennett Ignore all Pyro 4★ Lv90 C6 · Skyward Blade R1 Lv90"
        " · 4x Noblesse Oblige",
    ]
    assert lines[3].startswith("Honkai: Star Rail — ") and len(lines) == 6
    assert "secret-cookie" not in text and "800000001" not in text
    assert sorted(genshin.reads) == sorted(
        [
            ("stats", "genshin"),
            ("notes", "genshin"),
            ("stats", "starrail"),
            ("notes", "starrail"),
            ("roster", "genshin"),
            ("roster", "starrail"),
        ]
    )


async def test_the_profile_is_remembered_for_a_while_and_dropped_on_unlink():
    genshin, clock = FakeGenshin(), Clock()
    profiles = GameProfiles(lambda: genshin, clock=clock)
    first = await profiles.snapshot(7)
    clock.now += CACHE_SECONDS - 1
    assert await profiles.snapshot(7) == first and len(genshin.reads) == 6
    clock.now += 2
    await profiles.snapshot(7)
    assert len(genshin.reads) == 12  # read again once it is old
    del genshin.bound[7]
    assert await profiles.snapshot(7) is None
    genshin.bound[7] = FakeGenshin().bound[7]
    await profiles.snapshot(7)
    assert len(genshin.reads) == 18  # not served from before the unlink


async def test_nothing_linked_or_no_genshin_cog_means_no_profile():
    genshin = FakeGenshin()
    assert await GameProfiles(lambda: genshin).snapshot(8) is None
    assert await GameProfiles(lambda: None).snapshot(7) is None
    genshin.bound[7]["game_accounts"] = [{"game_biz": "nxx_global", "uid": 1}]
    assert await GameProfiles(lambda: genshin).snapshot(7) is None


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
    assert text.startswith("Genshin Impact — overview: ") and "now:" not in text
    assert "Star Rail" not in text
    everything = FakeGenshin(
        fail={
            (kind, game)
            for kind in ("stats", "notes", "roster")
            for game in ("genshin", "starrail")
        }
    )
    profiles = GameProfiles(lambda: everything)
    assert await profiles.snapshot(7) is None
    assert 7 not in profiles._cache  # a failure is not remembered


async def test_a_slow_hoyolab_is_given_up_on(monkeypatch):
    monkeypatch.setattr(ai_game_profile, "FETCH_SECONDS", 0.05)
    profiles = GameProfiles(lambda: FakeGenshin(slow=True))
    assert await profiles.snapshot(7) is None


async def test_a_new_bind_is_read_again_even_while_the_old_one_is_remembered():
    genshin = FakeGenshin()
    profiles = GameProfiles(lambda: genshin, clock=Clock())
    await profiles.snapshot(7)
    genshin.bound[7] = dict(genshin.bound[7], encrypted_cookie="another-account")
    await profiles.snapshot(7)
    assert len(genshin.reads) == 12
    genshin.bound[7]["game_accounts"] = genshin.bound[7]["game_accounts"][:1]
    await profiles.snapshot(7)
    assert len(genshin.reads) == 15  # the same cookie, but a game was unlinked


async def test_messages_sent_together_share_one_read():
    genshin = FakeGenshin(slow=True)
    profiles = GameProfiles(lambda: genshin)
    texts = await asyncio.gather(*(profiles.snapshot(7) for _ in range(5)))
    assert len(set(texts)) == 1 and texts[0] and len(genshin.reads) == 6
    assert profiles._pending == {}


async def test_only_the_roster_still_gives_the_game_a_heading():
    genshin = FakeGenshin(
        fail={
            (kind, game)
            for kind in ("stats", "notes")
            for game in ("genshin", "starrail")
        }
    )
    text = await GameProfiles(lambda: genshin).snapshot(7)
    assert text.split("\n")[:2] == ["Genshin Impact:", "characters owned (1):"]


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
