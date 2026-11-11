"""The companion game: the rules the owner set, and that it stays fair."""

import itertools
import random

import pytest

from src.services import pet_rules as rules
from src.services.pet_service import PetError
from src.services.pet_service import PetService


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def pass_(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def service(tmp_path, clock, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    return PetService(clock=clock, rng=random.Random(7), root=str(tmp_path / "pets"))


def edit(service, user_id, change):
    """Reach into a stored companion, the way long play would have shaped it."""
    data = service._read(user_id)
    change(data)
    service._write(user_id, data)


def grant(service, user_id, **bag):
    edit(service, user_id, lambda data: data["bag"].update(bag))


def owner_at(service, user_id, level):
    xp = sum(rules.owner_xp_to_next(n) for n in range(1, level))
    edit(service, user_id, lambda data: data["owner"].update(xp=xp))


def code(error):
    return error.value.code


# ── the ranges the owner fixed ────────────────────────────────────
def test_a_companion_starts_at_level_two_and_is_never_lower(service):
    view = service.adopt(1, "fable", "小寓")
    assert view["pet"]["level"] == rules.PET_MIN_LEVEL == 2
    assert view["stage"] == 1 and not view["pet"]["mutated"]


def test_the_three_species_are_fable_ark_and_nova():
    assert set(rules.SPECIES) == {"fable", "ark", "nova"}
    totals = {sum(base.values()) for base in rules.SPECIES.values()}
    assert len(totals) == 1  # the same budget, spent differently


def test_keeper_levels_run_from_one_to_sixty():
    assert rules.owner_level(0)[0] == 1
    assert rules.owner_level(10**9) == (60, 0, 0)
    total = sum(rules.owner_xp_to_next(n) for n in range(1, 60))
    assert rules.owner_level(total - 1)[0] == 59
    assert rules.owner_level(total)[0] == 60


def test_experience_stops_at_the_cap_until_a_breakthrough(service):
    service.adopt(1, "ark", "方舟")
    edit(service, 1, lambda data: data["pet"].update(level=19, xp=0))
    data = service._read(1)
    result = service._pet_xp(data["pet"], 10**6)
    assert data["pet"]["level"] == 20 and result["capped"]
    assert data["pet"]["xp"] == 0


def test_experience_alone_never_passes_ninety(service):
    service.adopt(1, "nova", "諾瓦")
    edit(service, 1, lambda data: data["pet"].update(level=85, breaks=9))
    data = service._read(1)
    service._pet_xp(data["pet"], 10**9)
    assert data["pet"]["level"] == rules.PET_XP_CAP == 90


def test_late_breakthroughs_need_keeper_sixty_and_give_two_levels_each(service):
    service.adopt(1, "fable", "寓言")
    edit(service, 1, lambda data: data["pet"].update(level=90, breaks=4))
    grant(service, 1, streamsilver=15, corona_gold=20)

    owner_at(service, 1, 59)
    with pytest.raises(PetError) as error:
        service.breakthrough(1)
    assert code(error) == "owner_low" and error.value.values["need"] == 60

    owner_at(service, 1, 60)
    levels = []
    for _ in range(5):
        result = service.breakthrough(1)
        assert result["late"]
        levels.append(result["view"]["pet"]["level"])
    assert levels == [92, 94, 96, 98, 100]
    assert service.view(1)["bag"]["streamsilver"] == 0  # 1+2+3+4+5
    with pytest.raises(PetError) as error:
        service.breakthrough(1)
    assert code(error) == "max_level"


def test_streamsilver_is_the_highest_material_and_only_found():
    assert rules.MATERIALS[-1] == rules.SILVER
    assert rules.SILVER not in rules.SHOP and rules.GOLD not in rules.SHOP
    late = [step for step in rules.BREAKTHROUGHS if step.late]
    assert [step.at for step in late] == [90, 92, 94, 96, 98]
    assert all(rules.SILVER in step.cost for step in late)
    assert not any(rules.SILVER in s.cost for s in rules.BREAKTHROUGHS if not s.late)


def test_a_breakthrough_needs_the_level_the_keeper_and_the_materials(service):
    service.adopt(1, "ark", "方舟")
    with pytest.raises(PetError) as error:
        service.breakthrough(1)
    assert code(error) == "level_low"
    edit(service, 1, lambda data: data["pet"].update(level=20))
    with pytest.raises(PetError) as error:
        service.breakthrough(1)
    assert code(error) == "owner_low"
    owner_at(service, 1, 5)
    with pytest.raises(PetError) as error:
        service.breakthrough(1)
    assert code(error) == "short"
    grant(service, 1, stardust_sand=20, aether_iron=5)
    result = service.breakthrough(1)
    assert result["cap"] == 40 and result["view"]["pet"]["level"] == 20


# ── natures and aptitudes ─────────────────────────────────────────
@pytest.mark.parametrize("nature", sorted(rules.NATURES))
def test_a_nature_sets_where_aptitudes_start_and_how_high_they_go(nature):
    caps = rules.aptitude_caps(nature)
    strong, weak = rules.NATURES[nature]
    assert caps[strong] == 31 and caps[weak] == 20
    assert sum(caps.values()) == 31 + 20 + 26 + 26  # no nature is richer
    for seed in range(40):
        born = rules.roll_aptitudes(nature, random.Random(seed))
        assert all(caps[s] - 16 <= born[s] <= caps[s] - 8 for s in rules.STATS)


def test_training_stops_at_the_natures_cap(service):
    view = service.adopt(1, "nova", "諾瓦")
    stat = rules.NATURES[view["pet"]["nature"]][1]  # the lowered one
    grant(service, 1, stardust_sand=99, aether_iron=99)
    value = view["pet"]["aptitudes"][stat]
    while value < 20:
        value = service.train(1, stat)["value"]
    with pytest.raises(PetError) as error:
        service.train(1, stat)
    assert code(error) == "aptitude_max"


def test_changing_nature_costs_gold_and_iron_and_waits_seven_days(service, clock):
    view = service.adopt(1, "fable", "寓言")
    before = view["pet"]["nature"]
    with pytest.raises(PetError) as error:
        service.change_nature(1)
    assert code(error) == "short"
    grant(service, 1, corona_gold=2, aether_iron=10)
    result = service.change_nature(1)
    after = result["view"]["pet"]["nature"]
    assert result["before"] == before and after != before
    caps = rules.aptitude_caps(after)
    assert all(result["view"]["pet"]["aptitudes"][s] <= caps[s] for s in rules.STATS)

    clock.pass_(7 * rules.DAY - 60)
    with pytest.raises(PetError) as error:
        service.change_nature(1)
    assert code(error) == "nature_cooldown"
    clock.pass_(60)
    service.change_nature(1)


def test_choosing_the_nature_takes_two_streamsilver_more(service):
    view = service.adopt(1, "ark", "方舟")
    target = next(n for n in sorted(rules.NATURES) if n != view["pet"]["nature"])
    grant(service, 1, corona_gold=1, aether_iron=5, streamsilver=1)
    with pytest.raises(PetError) as error:
        service.change_nature(1, target)
    assert code(error) == "short" and error.value.values["short"] == {"streamsilver": 1}
    grant(service, 1, streamsilver=2)
    assert service.change_nature(1, target)["view"]["pet"]["nature"] == target
    assert service.view(1)["bag"]["streamsilver"] == 0


def test_a_new_nature_keeps_training_inside_its_bounds():
    trained = {"hp": 26, "atk": 31, "def": 20, "spd": 26}  # brave, fully trained
    refit = rules.refit_aptitudes(trained, "calm")  # hp up, spd down
    assert refit == {"hp": 26, "atk": 26, "def": 20, "spd": 20}


# ── needs, leaving and coming home ────────────────────────────────
def test_needs_fall_with_time_and_never_below_zero(service, clock):
    service.adopt(1, "fable", "寓言")
    clock.pass_(5 * rules.HOUR)
    pet = service.view(1, touch=False)["pet"]
    assert pet["satiety"] == pytest.approx(60) and pet["mood"] == pytest.approx(65)
    clock.pass_(10 * rules.DAY)
    pet = service.view(1, touch=False)["pet"]
    assert pet["satiety"] == 0 and pet["mood"] == 0 and pet["energy"] == 100


def test_left_alone_thirty_days_it_leaves_and_recall_always_brings_it_back(
    service, clock
):
    service.adopt(1, "nova", "諾瓦")
    edit(service, 1, lambda data: data["pet"].update(level=44, xp=12))
    grant(service, 1, corona_gold=3)
    clock.pass_(30 * rules.DAY - 1)
    assert not service.view(1, touch=False)["away"]
    with pytest.raises(PetError) as error:
        service.recall(1)
    assert code(error) == "not_away"

    clock.pass_(400 * rules.DAY)  # however long it has been
    assert service.view(1)["away"]  # looking does not bring it home
    for action in (service.feed, service.play, service.nap, service.daily):
        with pytest.raises(PetError) as error:
            action(1)
        assert code(error) == "away"

    view = service.recall(1)
    assert not view["away"]
    assert view["pet"]["level"] == 44 and view["bag"]["corona_gold"] == 3
    assert [view["pet"][n] for n in ("satiety", "mood", "energy")] == [50, 50, 50]
    service.feed(1)


def test_care_has_a_cooldown_and_teaches_both(service, clock):
    service.adopt(1, "ark", "方舟")
    clock.pass_(6 * rules.HOUR)
    result = service.feed(1)
    assert result["view"]["pet"]["satiety"] == pytest.approx(91)
    with pytest.raises(PetError) as error:
        service.feed(1)
    assert code(error) == "too_soon"
    service.play(1)
    assert service.view(1)["owner"]["into"] == 10
    clock.pass_(31 * 60)
    assert service.feed(1)["view"]["pet"]["satiety"] == 100
    clock.pass_(31 * 60)
    with pytest.raises(PetError) as error:
        service.feed(1)
    assert code(error) == "full"


def test_a_nap_gives_energy_back_when_it_ends(service, clock):
    service.adopt(1, "fable", "寓言")
    edit(service, 1, lambda data: data["pet"].update(energy=20.0))
    service.nap(1)
    with pytest.raises(PetError) as error:
        service.play(1)
    assert code(error) == "napping"
    clock.pass_(rules.HOUR)
    assert service.view(1)["pet"]["energy"] == pytest.approx(20 + 6 + 45)


# ── expeditions ───────────────────────────────────────────────────
def test_a_trip_cannot_be_collected_early_or_twice(service, clock):
    service.adopt(1, "nova", "諾瓦")
    service.depart(1, "breeze_meadow", 2)
    with pytest.raises(PetError) as error:
        service.collect(1)
    assert code(error) == "on_trip"
    with pytest.raises(PetError) as error:
        service.depart(1, "breeze_meadow", 0.5)
    assert code(error) == "on_trip"
    clock.pass_(2 * rules.HOUR)
    result = service.collect(1)
    assert result["coins"] > 0 and result["view"]["pet"]["xp"] > 0
    with pytest.raises(PetError) as error:
        service.collect(1)
    assert code(error) == "no_trip"


def test_a_trips_outcome_is_fixed_when_it_leaves(service, clock, tmp_path):
    service.adopt(1, "fable", "寓言")
    service.depart(1, "breeze_meadow", 8)
    clock.pass_(8 * rules.HOUR)
    saved = service._read(1)
    first = service.collect(1)
    service._write(1, saved)  # as if the reply had been lost and asked again
    service.rng = random.Random(999)
    again = service.collect(1)
    assert (again["loot"], again["coins"]) == (first["loot"], first["coins"])


def test_zones_open_with_the_keepers_level(service):
    service.adopt(1, "ark", "方舟")
    with pytest.raises(PetError) as error:
        service.depart(1, "streamsilver_abyss", 2)
    assert code(error) == "zone_locked" and error.value.values["need"] == 48
    owner_at(service, 1, 48)
    service.depart(1, "streamsilver_abyss", 2)


def test_a_neglected_companion_refuses_to_go(service, clock):
    service.adopt(1, "nova", "諾瓦")
    clock.pass_(3 * rules.DAY)
    with pytest.raises(PetError) as error:
        service.depart(1, "breeze_meadow", 2)
    assert code(error) == "sulking"


def test_longer_trips_pay_less_per_hour_and_strength_is_bounded():
    per_hour = [units / hours for hours, (units, _) in sorted(rules.TRIPS.items())]
    assert per_hour == sorted(per_hour, reverse=True)
    assert rules.strength_factor(0, 500) == 0.5
    assert rules.strength_factor(10**6, 500) == 1.25


def test_the_guardian_pays_once_a_day(service, clock):
    service.adopt(1, "fable", "寓言")
    edit(service, 1, lambda data: data["pet"].update(level=20))
    result = service.challenge(1, "breeze_meadow")
    assert result["won"] and result["coins"] > 0
    with pytest.raises(PetError) as error:
        service.challenge(1, "breeze_meadow")
    assert code(error) == "boss_done"
    clock.pass_(rules.DAY)
    edit(
        service,
        1,
        lambda data: data["pet"].update(satiety=80.0, mood=80.0, at=clock.now),
    )
    assert service.challenge(1, "breeze_meadow")["won"]


# ── evolution and mutation ────────────────────────────────────────
def test_three_stages_and_a_mutation(service):
    assert [rules.stage_of(level) for level in (2, 29, 30, 59, 60, 100)] == [
        1,
        1,
        2,
        2,
        3,
        3,
    ]
    service.adopt(1, "ark", "方舟")
    edit(service, 1, lambda data: data["pet"].update(level=29, breaks=1))
    data = service._read(1)
    result = service._pet_xp(data["pet"], rules.pet_xp_to_next(29))
    assert result["evolved"] == 2

    edit(service, 1, lambda data: data["pet"].update(level=69, breaks=3))
    grant(service, 1, streamsilver=2, corona_gold=6)
    with pytest.raises(PetError) as error:
        service.mutate(1)
    assert code(error) == "level_low"
    edit(service, 1, lambda data: data["pet"].update(level=70))
    plain = service.view(1)["power"]
    view = service.mutate(1)["view"]
    assert view["pet"]["mutated"] and view["power"] > plain
    assert view["bag"]["streamsilver"] == 0 and view["bag"]["corona_gold"] == 0
    with pytest.raises(PetError) as error:
        service.mutate(1)
    assert code(error) == "mutated"


# ── fairness ──────────────────────────────────────────────────────
@pytest.mark.parametrize("level", [10, 50, 100])
def test_no_species_beats_another_much_more_often_than_not(level):
    even = dict.fromkeys(rules.STATS, 20)
    for one, two in itertools.combinations(sorted(rules.SPECIES), 2):
        rng, wins, fights = random.Random(level), 0, 1200
        first = rules.Fighter("a", one, rules.stats_of(one, level, even))
        second = rules.Fighter("b", two, rules.stats_of(two, level, even))
        for turn in range(fights):
            if turn % 2:
                wins += rules.battle(second, first, rng)["winner"] == 1
            else:
                wins += rules.battle(first, second, rng)["winner"] == 0
        assert 0.38 <= wins / fights <= 0.62, (one, two, level, wins / fights)


def test_a_duel_changes_nothing_for_the_one_challenged(service):
    service.adopt(1, "fable", "寓言")
    service.adopt(2, "nova", "諾瓦")
    before = service._read(2)
    for count in range(1, 8):
        result = service.duel(1, 2)
        assert result["rewarded"] == (count <= rules.DUELS_WITH_REWARD)
    assert service._read(2) == before
    with pytest.raises(PetError) as error:
        service.duel(1, 1)
    assert code(error) == "duel_self"
    with pytest.raises(PetError) as error:
        service.duel(1, 3)
    assert code(error) == "duel_no_pet"


def test_nothing_can_be_spent_twice_or_into_debt(service):
    service.adopt(1, "ark", "方舟")
    with pytest.raises(PetError) as error:
        service.buy(1, rules.SAND, 99)
    assert code(error) == "no_coins"
    service.buy(1, rules.SAND, 6)  # 90 of the 100 starting coins
    view = service.view(1)
    assert view["coins"] == 10 and view["bag"][rules.SAND] == 11
    for bad in (("streamsilver", 1), (rules.SAND, 0), (rules.SAND, 100)):
        with pytest.raises(PetError) as error:
            service.buy(1, *bad)
        assert code(error) == "bad_purchase"
    assert all(amount >= 0 for amount in service.view(1)["bag"].values())


def test_one_companion_each_with_a_plain_name(service):
    service.adopt(1, "fable", "寓言")
    with pytest.raises(PetError) as error:
        service.adopt(1, "ark", "方舟")
    assert code(error) == "has_pet"
    for name in ("", "   ", "@everyone", "a" * 13, "<@1>", "x y", "**粗**"):
        with pytest.raises(PetError) as error:
            service.adopt(2, "ark", name)
        assert code(error) == "bad_name", name
    with pytest.raises(PetError) as error:
        service.adopt(2, "dragon", "龍")
    assert code(error) == "bad_species"


def test_daily_streak_and_ranking(service, clock):
    service.adopt(1, "fable", "寓言")
    service.adopt(2, "nova", "諾瓦")
    edit(service, 2, lambda data: data["pet"].update(level=50))
    first = service.daily(1)
    assert first["streak"] == 1 and first["coins"] == 60
    with pytest.raises(PetError) as error:
        service.daily(1)
    assert code(error) == "daily_done"
    for _ in range(6):
        clock.pass_(rules.DAY)
        result = service.daily(1)
    assert result["streak"] == 7 and result["loot"] == {rules.FROST: 2}
    clock.pass_(3 * rules.DAY)
    assert service.daily(1)["streak"] == 1

    ranking = service.ranking([1, 2, 3])
    assert [row["user_id"] for row in ranking] == [2, 1]
    assert service.ranking([1]) == [ranking[1]]
