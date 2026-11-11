"""The numbers of the companion game: species, natures, materials, zones, formulas.

Everything here is a pure function of its arguments, so the balance can be read
in one place and tested without storage or Discord.
"""

from dataclasses import dataclass
import random

STATS = ("hp", "atk", "def", "spd")

OWNER_MAX_LEVEL = 60
PET_MIN_LEVEL = 2  # a companion is never below level 2
PET_XP_CAP = 90  # experience carries a companion this far
PET_MAX_LEVEL = 100  # the rest comes from late breakthroughs, two levels each
LATE_STEP = 2

HOUR = 3600
DAY = 86400
RUNAWAY_SECONDS = 30 * DAY  # left alone this long, the companion wanders off
NATURE_COOLDOWN = 7 * DAY
CARE_COOLDOWN = 30 * 60  # between two feeds, and between two play sessions
NAP_SECONDS = HOUR
NAP_ENERGY = 45
SATIETY_PER_HOUR = 4.0
MOOD_PER_HOUR = 3.0
ENERGY_PER_HOUR = 6.0
RECALL_NEEDS = 50  # what a recalled companion comes home with
DUELS_WITH_REWARD = 5  # a day; further duels are still allowed

# ── materials, lowest tier first ──────────────────────────────────
SAND = "stardust_sand"
IRON = "aether_iron"
FROST = "frostvein_crystal"
GOLD = "corona_gold"
SILVER = "streamsilver"
MATERIALS = (SAND, IRON, FROST, GOLD, SILVER)
SHOP = {SAND: 15, IRON: 60}  # coins each; the higher tiers are only found

# ── species: the same total, spent differently ────────────────────
SPECIES = {
    "fable": {"hp": 50, "atk": 48, "def": 41, "spd": 61},
    "ark": {"hp": 59, "atk": 45, "def": 56, "spd": 40},
    "nova": {"hp": 48, "atk": 60, "def": 35, "spd": 57},
}
STAGE_LEVELS = (PET_MIN_LEVEL, 30, 60)  # stage 1, 2 and 3 begin here
STAGE_FACTOR = (1.0, 1.15, 1.3)
MUTATION_FACTOR = 1.04
MUTATION_LEVEL = 70
MUTATION_COST = {SILVER: 2, GOLD: 6}

# ── natures: one aptitude raised, one lowered, the sum always equal ─
NATURES = {
    "brave": ("atk", "def"),
    "fierce": ("atk", "spd"),
    "bold": ("atk", "hp"),
    "steady": ("def", "spd"),
    "patient": ("def", "atk"),
    "guarded": ("def", "hp"),
    "lively": ("spd", "hp"),
    "nimble": ("spd", "def"),
    "restless": ("spd", "atk"),
    "hardy": ("hp", "atk"),
    "calm": ("hp", "spd"),
    "gentle": ("hp", "def"),
}
CAP_STRONG, CAP_NORMAL, CAP_WEAK = 31, 26, 20
BORN_BELOW_CAP = (16, 8)  # an aptitude starts this far under its cap
NATURE_COST = {GOLD: 1, IRON: 5}
NATURE_PICK_COST = {SILVER: 2}  # on top of NATURE_COST, to choose the nature


def aptitude_caps(nature: str) -> dict[str, int]:
    strong, weak = NATURES[nature]
    return {
        stat: CAP_STRONG if stat == strong else CAP_WEAK if stat == weak else CAP_NORMAL
        for stat in STATS
    }


def roll_aptitudes(nature: str, rng: random.Random) -> dict[str, int]:
    far, near = BORN_BELOW_CAP
    return {
        stat: rng.randint(cap - far, cap - near)
        for stat, cap in aptitude_caps(nature).items()
    }


def refit_aptitudes(aptitudes: dict[str, int], nature: str) -> dict[str, int]:
    """Carry trained aptitudes into a new nature, inside its bounds."""
    far, _ = BORN_BELOW_CAP
    return {
        stat: max(cap - far, min(aptitudes[stat], cap))
        for stat, cap in aptitude_caps(nature).items()
    }


def training_cost(value: int) -> dict[str, int]:
    """What raising an aptitude from ``value`` by one point takes."""
    if value < 16:
        return {SAND: 3}
    if value < 24:
        return {IRON: 2}
    if value < 29:
        return {FROST: 2}
    return {GOLD: 1}


# ── levels ────────────────────────────────────────────────────────
def owner_xp_to_next(level: int) -> int:
    return 40 + 12 * level


def owner_level(xp: int) -> tuple[int, int, int]:
    """(level, experience into it, experience it takes), level 1 to 60."""
    level = 1
    while level < OWNER_MAX_LEVEL and xp >= owner_xp_to_next(level):
        xp -= owner_xp_to_next(level)
        level += 1
    if level == OWNER_MAX_LEVEL:
        return level, 0, 0
    return level, xp, owner_xp_to_next(level)


def pet_xp_to_next(level: int) -> int:
    return round(30 + 6 * level + 0.12 * level * level)


@dataclass(frozen=True)
class Breakthrough:
    at: int  # the level the companion must have reached
    owner: int  # the keeper level it takes
    cost: dict[str, int]
    late: bool = False  # a late breakthrough grants two levels itself


BREAKTHROUGHS = (
    Breakthrough(20, 5, {SAND: 20, IRON: 5}),
    Breakthrough(40, 15, {IRON: 20, FROST: 8}),
    Breakthrough(60, 30, {FROST: 20, GOLD: 5}),
    Breakthrough(80, 45, {FROST: 30, GOLD: 12}),
    *(
        Breakthrough(
            PET_XP_CAP + LATE_STEP * step,
            OWNER_MAX_LEVEL,
            {SILVER: step + 1, GOLD: 4},
            late=True,
        )
        for step in range((PET_MAX_LEVEL - PET_XP_CAP) // LATE_STEP)
    ),
)


def level_cap(breakthroughs: int) -> int:
    """How far experience may carry a companion after this many breakthroughs."""
    if breakthroughs >= len(BREAKTHROUGHS):
        return PET_MAX_LEVEL
    return BREAKTHROUGHS[breakthroughs].at


def stage_of(level: int) -> int:
    return sum(level >= start for start in STAGE_LEVELS)  # 1, 2 or 3


# ── combat numbers ────────────────────────────────────────────────
def stats_of(
    species: str, level: int, aptitudes: dict[str, int], mutated: bool = False
) -> dict[str, int]:
    factor = STAGE_FACTOR[stage_of(level) - 1] * (MUTATION_FACTOR if mutated else 1)
    result = {}
    for stat in STATS:
        value = (SPECIES[species][stat] * 2 + aptitudes[stat]) * level / 100
        value += level + 10 if stat == "hp" else 5
        result[stat] = int(value * factor)
    return result


def power_of(stats: dict[str, int]) -> int:
    return stats["hp"] // 2 + stats["atk"] + stats["def"] + stats["spd"]


# ── expeditions ───────────────────────────────────────────────────
@dataclass(frozen=True)
class Zone:
    owner: int  # keeper level that opens it
    difficulty: int  # companion power it is tuned for
    xp: int  # companion experience per unit
    coins: int
    loot: dict[str, float]  # expected finds per unit


ZONES = {
    "breeze_meadow": Zone(1, 40, 20, 12, {SAND: 1.6}),
    "mistveil_mine": Zone(8, 110, 34, 16, {SAND: 1.2, IRON: 0.7}),
    "frostvein_cavern": Zone(18, 230, 52, 20, {IRON: 0.9, FROST: 0.5}),
    "corona_ruins": Zone(32, 380, 75, 26, {FROST: 0.8, GOLD: 0.18}),
    "streamsilver_abyss": Zone(48, 520, 105, 32, {FROST: 0.6, GOLD: 0.3, SILVER: 0.04}),
}
# hours -> (reward units, energy it takes): a long trip pays less per hour
TRIPS = {0.5: (0.6, 10), 2: (2.0, 25), 8: (6.0, 50)}
OWNER_XP_PER_UNIT = 10
BOSS_UNITS = 3.0
BOSS_BONUS = 1.5
SULK_BELOW = 15  # below this the companion refuses to go out


def condition_factor(satiety: float, mood: float) -> float:
    average = (satiety + mood) / 2
    return 1.1 if average >= 70 else 1.0 if average >= 40 else 0.8


def strength_factor(power: int, difficulty: int) -> float:
    return max(0.5, min(1.25, 0.5 + 0.5 * power / difficulty))


def roll_loot(
    zone: Zone, units: float, factor: float, rng: random.Random
) -> dict[str, int]:
    found = {}
    for material, rate in zone.loot.items():
        expected = rate * units * factor
        count = int(expected) + (rng.random() < expected - int(expected))
        if count:
            found[material] = count
    return found


# ── automatic battles ─────────────────────────────────────────────
@dataclass
class Fighter:
    name: str
    species: str  # "fable", "ark", "nova", or "boss"
    stats: dict[str, int]


def boss_of(zone_id: str) -> Fighter:
    difficulty = ZONES[zone_id].difficulty
    return Fighter(
        zone_id,
        "boss",
        {
            "hp": round(difficulty * BOSS_SHAPE[0]),
            "atk": round(difficulty * BOSS_SHAPE[1]),
            "def": round(difficulty * BOSS_SHAPE[2]),
            "spd": round(difficulty * BOSS_SHAPE[3]),
        },
    )


BOSS_SHAPE = (0.5, 0.2, 0.2, 0.18)  # share of a zone's difficulty in each stat
MAX_ROUNDS = 30
SPECIAL_EVERY = 3  # each fighter's third action is its special
CRIT_CHANCE, CRIT_FACTOR = 0.1, 1.5
# Tuned by simulation so every pairing of species stays near even at any level.
ARK_MEND, ARK_HIT = 0.24, 0.98
FABLE_PIERCE, FABLE_HIT = 0.34, 1.3
NOVA_HIT = 1.28


def battle(first: Fighter, second: Fighter, rng: random.Random) -> dict:
    """Fight to a knockout or thirty rounds; the log is a list of plain events.

    Specials, so the three species differ without one being stronger: Fable's
    strike slips past most of the defence, Ark mends itself, Nova hits harder.
    """
    health = [first.stats["hp"], second.stats["hp"]]
    fighters = (first, second)
    actions = [0, 0]
    log = []
    for round_number in range(1, MAX_ROUNDS + 1):
        order = sorted(
            (0, 1), key=lambda i: -fighters[i].stats["spd"] * rng.uniform(0.8, 1.2)
        )
        for index in order:
            if min(health) <= 0:
                break
            me, foe = fighters[index], fighters[1 - index]
            actions[index] += 1
            special = actions[index] % SPECIAL_EVERY == 0
            attack, defence = me.stats["atk"], float(foe.stats["def"])
            event = {"round": round_number, "by": index, "special": special}
            scale = 1.0
            if special and me.species == "ark":
                mended = round(me.stats["hp"] * ARK_MEND)
                health[index] = min(me.stats["hp"], health[index] + mended)
                event["heal"] = mended
                scale = ARK_HIT
            elif special and me.species == "fable":
                defence *= FABLE_PIERCE
                scale = FABLE_HIT
            elif special:
                scale = NOVA_HIT
            crit = rng.random() < CRIT_CHANCE
            damage = max(
                1,
                round(
                    attack
                    * attack
                    / (attack + defence)
                    * scale
                    * (CRIT_FACTOR if crit else 1)
                    * rng.uniform(0.8, 1)
                ),
            )
            health[1 - index] -= damage
            event["damage"] = damage
            event["crit"] = crit
            log.append(event)
        if min(health) <= 0:
            break
    if health[0] <= 0 or health[1] <= 0:
        winner = 0 if health[1] <= 0 else 1
    else:  # nobody fell: whoever kept more of their health
        shares = [health[i] / fighters[i].stats["hp"] for i in (0, 1)]
        winner = 0 if shares[0] >= shares[1] else 1
    return {
        "winner": winner,
        "rounds": log[-1]["round"] if log else 0,
        "left": [max(0, value) for value in health],
        "log": log,
    }
