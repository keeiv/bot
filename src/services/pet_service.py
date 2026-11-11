"""Companions: one per member, the same in every server.

A companion's needs and trips are settled from timestamps whenever its keeper
looks, so nothing here depends on a background task. Every public method is one
read-modify-write of the keeper's own document and is meant to run through
``run_storage``, which serializes them.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import os
import random
import re
import time
from typing import Any, Callable, Optional

from src.services import pet_rules as rules
from src.utils.document_store import read_document
from src.utils.document_store import write_document

ROOT = os.path.join("data", "storage", "pets")
TZ = timezone(timedelta(hours=8))
NAME_RE = re.compile(r"^[^\s@#`*_~|<>:/\\\[\]()]{1,12}$")
START_COINS = 100
START_BAG = {rules.SAND: 5}
RENAME_COINS = 100
DAILY_COINS = 50
DAILY_XP = 30
CARE_XP = 5  # keeper experience for a feed, a play session or a nap
CARE_PET_XP = 6
FEED_SATIETY, FEED_MOOD = 35, 5
PLAY_MOOD, PLAY_ENERGY = 30, 10
BOSS_ENERGY = 10
BOSS_OWNER_XP = 15
DUEL_OWNER_XP = 8


class PetError(Exception):
    """A refusal the keeper can read; ``code`` names the message."""

    # The values fill the message; this is never pickled or copied.
    def __init__(self, code: str, **values: Any) -> None:  # noqa: B042
        super().__init__(code)
        self.code = code
        self.values = values


def valid_name(name: str) -> str:
    name = name.strip()
    if not NAME_RE.match(name):
        raise PetError("bad_name")
    return name


class PetService:
    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        rng: Optional[random.Random] = None,
        root: str = ROOT,
    ) -> None:
        self.clock = clock
        self.rng = rng or random.Random()
        self.root = root

    # ── storage ───────────────────────────────────────────────────────
    def _path(self, name: str) -> str:
        return os.path.join(self.root, f"{name}.json")

    def _read(self, user_id: int) -> Optional[dict[str, Any]]:
        try:
            data = read_document(self._path(str(int(user_id))))
        except FileNotFoundError:
            return None
        if not isinstance(data, dict) or "pet" not in data:
            raise TypeError("Stored companion must be an object")
        return data

    def _write(self, user_id: int, data: dict[str, Any]) -> None:
        write_document(self._path(str(int(user_id))), data)
        pet = data["pet"]
        row = [
            pet["name"],
            pet["species"],
            pet["level"],
            bool(pet["mutated"]),
            rules.power_of(self._stats(pet)),
        ]
        index = self._index()
        if index.get(str(int(user_id))) != row:
            index[str(int(user_id))] = row
            write_document(self._path("_index"), index)

    def _index(self) -> dict[str, Any]:
        try:
            data = read_document(self._path("_index"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise TypeError("Stored companion index must be an object")
        return data

    # ── time ──────────────────────────────────────────────────────────
    def _today(self, now: float) -> str:
        return datetime.fromtimestamp(now, TZ).strftime("%Y-%m-%d")

    @staticmethod
    def _away(pet: dict[str, Any], now: float) -> bool:
        return now - pet["cared"] >= rules.RUNAWAY_SECONDS

    def _settle(self, data: dict[str, Any], now: float) -> None:
        """Bring the needs up to ``now``. Time stands still for one that left."""
        pet = data["pet"]
        if self._away(pet, now):
            return
        hours = max(0.0, now - pet["at"]) / rules.HOUR
        pet["satiety"] = max(0.0, pet["satiety"] - rules.SATIETY_PER_HOUR * hours)
        pet["mood"] = max(0.0, pet["mood"] - rules.MOOD_PER_HOUR * hours)
        if not data.get("trip"):
            pet["energy"] = min(100.0, pet["energy"] + rules.ENERGY_PER_HOUR * hours)
        if pet.get("nap") and now >= pet["nap"]:
            pet["energy"] = min(100.0, pet["energy"] + rules.NAP_ENERGY)
            pet["nap"] = None
        pet["at"] = now

    def _open(
        self, user_id: int, *, touch: bool = True, allow_away: bool = False
    ) -> tuple[dict[str, Any], float]:
        data = self._read(user_id)
        if data is None:
            raise PetError("no_pet")
        now = self.clock()
        if self._away(data["pet"], now):
            if not allow_away:
                raise PetError("away")
        else:
            self._settle(data, now)
            if touch:
                data["pet"]["cared"] = now
        return data, now

    # ── derived numbers ───────────────────────────────────────────────
    @staticmethod
    def _stats(pet: dict[str, Any]) -> dict[str, int]:
        return rules.stats_of(
            pet["species"], pet["level"], pet["aptitudes"], pet["mutated"]
        )

    @staticmethod
    def _take(bag: dict[str, int], cost: dict[str, int]) -> None:
        short = {
            material: amount - bag.get(material, 0)
            for material, amount in cost.items()
            if bag.get(material, 0) < amount
        }
        if short:
            raise PetError("short", cost=cost, short=short)
        for material, amount in cost.items():
            bag[material] -= amount

    @staticmethod
    def _give(bag: dict[str, int], loot: dict[str, int]) -> None:
        for material, amount in loot.items():
            bag[material] = bag.get(material, 0) + amount

    @staticmethod
    def _owner_xp(data: dict[str, Any], amount: int) -> int:
        before = rules.owner_level(data["owner"]["xp"])[0]
        data["owner"]["xp"] += amount
        return rules.owner_level(data["owner"]["xp"])[0] - before

    @staticmethod
    def _pet_xp(pet: dict[str, Any], amount: int) -> dict[str, Any]:
        """Add experience up to the current cap; report levels, stage and cap."""
        cap = min(rules.level_cap(pet["breaks"]), rules.PET_XP_CAP)
        before, stage = pet["level"], rules.stage_of(pet["level"])
        pet["xp"] += max(0, amount)
        while pet["level"] < cap and pet["xp"] >= rules.pet_xp_to_next(pet["level"]):
            pet["xp"] -= rules.pet_xp_to_next(pet["level"])
            pet["level"] += 1
        capped = pet["level"] >= cap
        if capped:
            pet["xp"] = 0
        after = rules.stage_of(pet["level"])
        return {
            "levels": pet["level"] - before,
            "evolved": after if after > stage else None,
            "capped": capped,
        }

    # ── reading ───────────────────────────────────────────────────────
    def has_pet(self, user_id: int) -> bool:
        return self._read(user_id) is not None

    def view(self, user_id: int, *, touch: bool = True) -> dict[str, Any]:
        """Everything a panel shows. Looking in counts as company."""
        data, now = self._open(user_id, touch=touch, allow_away=True)
        if touch and not self._away(data["pet"], now):
            self._write(user_id, data)
        return self._snapshot(data, now)

    def _snapshot(self, data: dict[str, Any], now: float) -> dict[str, Any]:
        pet = data["pet"]
        level, into, needed = rules.owner_level(data["owner"]["xp"])
        stats = self._stats(pet)
        breaks = pet["breaks"]
        following = (
            rules.BREAKTHROUGHS[breaks] if breaks < len(rules.BREAKTHROUGHS) else None
        )
        cap = min(rules.level_cap(breaks), rules.PET_XP_CAP)
        return {
            "now": now,
            "pet": dict(pet),
            "stage": rules.stage_of(pet["level"]),
            "stats": stats,
            "power": rules.power_of(stats),
            "caps": rules.aptitude_caps(pet["nature"]),
            "xp_needed": (
                0 if pet["level"] >= cap else rules.pet_xp_to_next(pet["level"])
            ),
            "at_cap": pet["level"] >= cap and pet["level"] < rules.PET_MAX_LEVEL,
            "next_break": following,
            "away": self._away(pet, now),
            "trip": dict(data["trip"]) if data.get("trip") else None,
            "owner": {"level": level, "into": into, "needed": needed},
            "coins": data["owner"]["coins"],
            "bag": dict(data["bag"]),
            "daily_done": data["owner"].get("daily") == self._today(now),
            "streak": data["owner"].get("streak", 0),
            "bosses": (
                list(data.get("boss", {}).get("zones", []))
                if data.get("boss", {}).get("day") == self._today(now)
                else []
            ),
        }

    def ranking(self, user_ids: list[int], limit: int = 10) -> list[dict[str, Any]]:
        """The strongest companions among these members."""
        index = self._index()
        wanted = {int(user_id) for user_id in user_ids}
        rows = [
            {
                "user_id": int(uid),
                "name": row[0],
                "species": row[1],
                "level": row[2],
                "mutated": row[3],
                "power": row[4],
            }
            for uid, row in index.items()
            if int(uid) in wanted
        ]
        rows.sort(key=lambda row: (-row["power"], -row["level"], row["user_id"]))
        return rows[:limit]

    # ── beginning and coming home ─────────────────────────────────────
    def adopt(self, user_id: int, species: str, name: str) -> dict[str, Any]:
        if species not in rules.SPECIES:
            raise PetError("bad_species")
        name = valid_name(name)
        if self._read(user_id) is not None:
            raise PetError("has_pet")
        now = self.clock()
        nature = self.rng.choice(sorted(rules.NATURES))
        data = {
            "v": 1,
            "owner": {"xp": 0, "coins": START_COINS, "daily": "", "streak": 0},
            "pet": {
                "species": species,
                "name": name,
                "nature": nature,
                "aptitudes": rules.roll_aptitudes(nature, self.rng),
                "level": rules.PET_MIN_LEVEL,
                "xp": 0,
                "breaks": 0,
                "mutated": False,
                "satiety": 80.0,
                "mood": 80.0,
                "energy": 80.0,
                "at": now,
                "cared": now,
                "born": now,
                "nap": None,
                "fed": 0.0,
                "played": 0.0,
                "nature_at": None,
            },
            "bag": dict(START_BAG),
            "trip": None,
            "boss": {"day": "", "zones": []},
            "duel": {"day": "", "count": 0},
        }
        self._write(user_id, data)
        return self._snapshot(data, now)

    def recall(self, user_id: int) -> dict[str, Any]:
        """Call a companion that wandered off back home. It always comes."""
        data, now = self._open(user_id, allow_away=True)
        pet = data["pet"]
        if not self._away(pet, now):
            raise PetError("not_away")
        for need in ("satiety", "mood", "energy"):
            pet[need] = float(rules.RECALL_NEEDS)
        pet["at"] = pet["cared"] = now
        pet["nap"] = None
        self._write(user_id, data)
        return self._snapshot(data, now)

    def rename(self, user_id: int, name: str) -> dict[str, Any]:
        name = valid_name(name)
        data, now = self._open(user_id)
        if data["owner"]["coins"] < RENAME_COINS:
            raise PetError("no_coins", need=RENAME_COINS)
        data["owner"]["coins"] -= RENAME_COINS
        data["pet"]["name"] = name
        self._write(user_id, data)
        return self._snapshot(data, now)

    # ── care ──────────────────────────────────────────────────────────
    def _busy(self, data: dict[str, Any], now: float) -> None:
        if data.get("trip"):
            raise PetError("on_trip", until=int(data["trip"]["ends"]))
        if data["pet"].get("nap"):
            raise PetError("napping", until=int(data["pet"]["nap"]))

    def _care(
        self, user_id: int, data: dict[str, Any], now: float, pet_xp: int
    ) -> dict[str, Any]:
        result = self._pet_xp(data["pet"], pet_xp)
        result["owner_levels"] = self._owner_xp(data, CARE_XP)
        self._write(user_id, data)
        result["view"] = self._snapshot(data, now)
        return result

    def feed(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        pet = data["pet"]
        self._busy(data, now)
        if now - pet["fed"] < rules.CARE_COOLDOWN:
            raise PetError("too_soon", until=int(pet["fed"] + rules.CARE_COOLDOWN))
        if pet["satiety"] >= 95:
            raise PetError("full")
        pet["satiety"] = min(100.0, pet["satiety"] + FEED_SATIETY)
        pet["mood"] = min(100.0, pet["mood"] + FEED_MOOD)
        pet["fed"] = now
        return self._care(user_id, data, now, CARE_PET_XP)

    def play(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        pet = data["pet"]
        self._busy(data, now)
        if now - pet["played"] < rules.CARE_COOLDOWN:
            raise PetError("too_soon", until=int(pet["played"] + rules.CARE_COOLDOWN))
        if pet["energy"] < PLAY_ENERGY:
            raise PetError("tired")
        pet["energy"] -= PLAY_ENERGY
        pet["mood"] = min(100.0, pet["mood"] + PLAY_MOOD)
        pet["played"] = now
        return self._care(user_id, data, now, CARE_PET_XP)

    def nap(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        pet = data["pet"]
        self._busy(data, now)
        if pet["energy"] >= 90:
            raise PetError("rested")
        pet["nap"] = now + rules.NAP_SECONDS
        return self._care(user_id, data, now, 0)

    def daily(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        owner, today = data["owner"], self._today(now)
        if owner.get("daily") == today:
            raise PetError("daily_done")
        yesterday = self._today(now - rules.DAY)
        owner["streak"] = (
            owner.get("streak", 0) + 1 if owner["daily"] == yesterday else 1
        )
        owner["daily"] = today
        coins = DAILY_COINS + 10 * min(owner["streak"], 7)
        owner["coins"] += coins
        loot = {rules.FROST: 2} if owner["streak"] % 7 == 0 else {}
        self._give(data["bag"], loot)
        levels = self._owner_xp(data, DAILY_XP)
        self._write(user_id, data)
        return {
            "coins": coins,
            "loot": loot,
            "streak": owner["streak"],
            "owner_levels": levels,
            "view": self._snapshot(data, now),
        }

    # ── expeditions ───────────────────────────────────────────────────
    def _zone(self, data: dict[str, Any], zone_id: str) -> rules.Zone:
        zone = rules.ZONES.get(zone_id)
        if zone is None:
            raise PetError("bad_zone")
        if rules.owner_level(data["owner"]["xp"])[0] < zone.owner:
            raise PetError("zone_locked", need=zone.owner)
        return zone

    def _fit(self, data: dict[str, Any], energy: int) -> float:
        """Refuse a sulking or worn-out companion; return its condition factor."""
        pet = data["pet"]
        if (pet["satiety"] + pet["mood"]) / 2 < rules.SULK_BELOW:
            raise PetError("sulking")
        if pet["energy"] < energy:
            raise PetError("tired")
        return rules.condition_factor(pet["satiety"], pet["mood"])

    def depart(self, user_id: int, zone_id: str, hours: float) -> dict[str, Any]:
        data, now = self._open(user_id)
        self._busy(data, now)
        zone = self._zone(data, zone_id)
        if hours not in rules.TRIPS:
            raise PetError("bad_trip")
        units, energy = rules.TRIPS[hours]
        condition = self._fit(data, energy)
        pet = data["pet"]
        pet["energy"] -= energy
        strength = rules.strength_factor(
            rules.power_of(self._stats(pet)), zone.difficulty
        )
        # The outcome is fixed when the trip begins, so it cannot be re-rolled.
        data["trip"] = {
            "zone": zone_id,
            "hours": hours,
            "units": units,
            "factor": round(condition * strength, 4),
            "started": now,
            "ends": now + hours * rules.HOUR,
            "seed": self.rng.getrandbits(48),
        }
        self._write(user_id, data)
        return self._snapshot(data, now)

    def collect(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        trip = data.get("trip")
        if not trip:
            raise PetError("no_trip")
        if now < trip["ends"]:
            raise PetError("on_trip", until=int(trip["ends"]))
        zone = rules.ZONES[trip["zone"]]
        rng = random.Random(trip["seed"])
        loot = rules.roll_loot(zone, trip["units"], trip["factor"], rng)
        coins = round(zone.coins * trip["units"] * trip["factor"])
        self._give(data["bag"], loot)
        data["owner"]["coins"] += coins
        result = self._pet_xp(
            data["pet"], round(zone.xp * trip["units"] * trip["factor"])
        )
        result["owner_levels"] = self._owner_xp(
            data, round(rules.OWNER_XP_PER_UNIT * trip["units"])
        )
        data["trip"] = None
        self._write(user_id, data)
        result.update(
            zone=trip["zone"], loot=loot, coins=coins, view=self._snapshot(data, now)
        )
        return result

    def challenge(self, user_id: int, zone_id: str) -> dict[str, Any]:
        """Fight a zone's guardian; the first win of a day pays out."""
        data, now = self._open(user_id)
        self._busy(data, now)
        zone = self._zone(data, zone_id)
        today = self._today(now)
        if data["boss"].get("day") != today:
            data["boss"] = {"day": today, "zones": []}
        if zone_id in data["boss"]["zones"]:
            raise PetError("boss_done")
        condition = self._fit(data, BOSS_ENERGY)
        pet = data["pet"]
        pet["energy"] -= BOSS_ENERGY
        fight = rules.battle(
            rules.Fighter(pet["name"], pet["species"], self._stats(pet)),
            rules.boss_of(zone_id),
            self.rng,
        )
        result: dict[str, Any] = {"won": fight["winner"] == 0, "fight": fight}
        if result["won"]:
            data["boss"]["zones"].append(zone_id)
            factor = rules.BOSS_BONUS * condition
            loot = rules.roll_loot(zone, rules.BOSS_UNITS, factor, self.rng)
            coins = round(zone.coins * rules.BOSS_UNITS)
            self._give(data["bag"], loot)
            data["owner"]["coins"] += coins
            result.update(self._pet_xp(pet, zone.xp * 2), loot=loot, coins=coins)
            result["owner_levels"] = self._owner_xp(data, BOSS_OWNER_XP)
        self._write(user_id, data)
        result.update(zone=zone_id, view=self._snapshot(data, now))
        return result

    # ── raising ───────────────────────────────────────────────────────
    def breakthrough(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        pet = data["pet"]
        if pet["breaks"] >= len(rules.BREAKTHROUGHS):
            raise PetError("max_level")
        step = rules.BREAKTHROUGHS[pet["breaks"]]
        if pet["level"] < step.at:
            raise PetError("level_low", need=step.at)
        if rules.owner_level(data["owner"]["xp"])[0] < step.owner:
            raise PetError("owner_low", need=step.owner)
        self._take(data["bag"], step.cost)
        pet["breaks"] += 1
        if step.late:
            pet["level"] = min(rules.PET_MAX_LEVEL, pet["level"] + rules.LATE_STEP)
        pet["xp"] = 0
        self._write(user_id, data)
        return {
            "late": step.late,
            "cap": rules.level_cap(pet["breaks"]),
            "view": self._snapshot(data, now),
        }

    def train(self, user_id: int, stat: str) -> dict[str, Any]:
        if stat not in rules.STATS:
            raise PetError("bad_stat")
        data, now = self._open(user_id)
        pet = data["pet"]
        value = pet["aptitudes"][stat]
        cap = rules.aptitude_caps(pet["nature"])[stat]
        if value >= cap:
            raise PetError("aptitude_max", cap=cap)
        self._take(data["bag"], rules.training_cost(value))
        pet["aptitudes"][stat] = value + 1
        self._write(user_id, data)
        return {
            "stat": stat,
            "value": value + 1,
            "cap": cap,
            "view": self._snapshot(data, now),
        }

    def change_nature(
        self, user_id: int, nature: Optional[str] = None
    ) -> dict[str, Any]:
        """Re-roll the nature, or choose one for two Streamsilver more."""
        if nature is not None and nature not in rules.NATURES:
            raise PetError("bad_nature")
        data, now = self._open(user_id)
        pet = data["pet"]
        if nature == pet["nature"]:
            raise PetError("same_nature")
        if pet["nature_at"] and now - pet["nature_at"] < rules.NATURE_COOLDOWN:
            raise PetError(
                "nature_cooldown", until=int(pet["nature_at"] + rules.NATURE_COOLDOWN)
            )
        cost = dict(rules.NATURE_COST)
        if nature is not None:
            cost.update(rules.NATURE_PICK_COST)
        self._take(data["bag"], cost)
        before = pet["nature"]
        pet["nature"] = nature or self.rng.choice(
            sorted(name for name in rules.NATURES if name != before)
        )
        pet["aptitudes"] = rules.refit_aptitudes(pet["aptitudes"], pet["nature"])
        pet["nature_at"] = now
        self._write(user_id, data)
        return {"before": before, "view": self._snapshot(data, now)}

    def mutate(self, user_id: int) -> dict[str, Any]:
        data, now = self._open(user_id)
        pet = data["pet"]
        if pet["mutated"]:
            raise PetError("mutated")
        if pet["level"] < rules.MUTATION_LEVEL:
            raise PetError("level_low", need=rules.MUTATION_LEVEL)
        self._take(data["bag"], rules.MUTATION_COST)
        pet["mutated"] = True
        self._write(user_id, data)
        return {"view": self._snapshot(data, now)}

    def buy(self, user_id: int, material: str, amount: int) -> dict[str, Any]:
        if material not in rules.SHOP or not 1 <= amount <= 99:
            raise PetError("bad_purchase")
        data, now = self._open(user_id)
        price = rules.SHOP[material] * amount
        if data["owner"]["coins"] < price:
            raise PetError("no_coins", need=price)
        data["owner"]["coins"] -= price
        self._give(data["bag"], {material: amount})
        self._write(user_id, data)
        return {"price": price, "view": self._snapshot(data, now)}

    # ── friendly duels ────────────────────────────────────────────────
    def duel(self, user_id: int, other_id: int) -> dict[str, Any]:
        """Fight another member's companion. Theirs is only read, never changed."""
        if int(user_id) == int(other_id):
            raise PetError("duel_self")
        data, now = self._open(user_id)
        other = self._read(other_id)
        if other is None:
            raise PetError("duel_no_pet")
        if self._away(other["pet"], now):
            raise PetError("duel_away")
        mine, theirs = data["pet"], other["pet"]
        fight = rules.battle(
            rules.Fighter(mine["name"], mine["species"], self._stats(mine)),
            rules.Fighter(theirs["name"], theirs["species"], self._stats(theirs)),
            self.rng,
        )
        today = self._today(now)
        if data["duel"].get("day") != today:
            data["duel"] = {"day": today, "count": 0}
        data["duel"]["count"] += 1
        rewarded = data["duel"]["count"] <= rules.DUELS_WITH_REWARD
        levels = self._owner_xp(data, DUEL_OWNER_XP) if rewarded else 0
        self._write(user_id, data)
        return {
            "won": fight["winner"] == 0,
            "fight": fight,
            "rewarded": rewarded,
            "owner_levels": levels,
            "mine": self._snapshot(data, now),
            "theirs": self._snapshot(other, now),
        }
