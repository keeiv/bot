"""Arknights: Endfield profiles through Enka.Network and SKPORT.

A member can link just the UID from the game's profile menu: Enka.Network then
reads the public showcase (the business card and the operators the player chose
to show). Enka asks for a User-Agent and for each UID to be read again only after
the ``ttl`` it returns, so both are cached here. Its store files on GitHub name
the operators, weapons and gear sets.

A member can also link their SKPORT account token, which shows every operator
they own. The token is stored encrypted with the same key as the HoYoLAB cookies
and is only ever used for that member's own account.
"""

import asyncio
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
import json
import logging
import os
import re
import time
from typing import Any, Callable, Optional

import aiohttp
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from dotenv import dotenv_values

from src.services.skport_client import Login
from src.services.skport_client import parse_token
from src.services.skport_client import SkportClient
from src.services.skport_client import SkportError
from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

API = "https://enka.network/api/ef/uid/{uid}"
STORE = (
    "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/ef/{name}.json"
)
STORE_FILES = ("avatars", "weapons", "equips", "locs")
STORE_DIR = "data/cache/endfield_store"
STORE_SECONDS = 24 * 3600  # names change with game updates; once a day is plenty
STORE_RETRY_SECONDS = 3600
USER_AGENT = "BOT. Discord bot (+https://github.com/keeiv/new_bot)"
TIMEOUT = 10
MIN_TTL = 60  # never ask Enka about one UID more often than this
CACHE_LIMIT = 500  # UIDs kept in memory
UID_RE = re.compile(r"^\d{6,12}$")
BINDINGS = "data/storage/endfield_bindings.json"

# Enka's store keeps these as codes; the names are the game's own.
ELEMENTS = {
    "Physical": ("物理", "Physical"),
    "Fire": ("灼熱", "Heat"),
    "Cryst": ("寒冷", "Cryo"),
    "Pulse": ("電磁", "Electric"),
    "Natural": ("自然", "Nature"),
}
PROFESSIONS = {
    "GUARD": ("近衛", "Guard"),
    "CASTER": ("術師", "Caster"),
    "DEFENDER": ("重裝", "Defender"),
    "SUPPORTER": ("輔助", "Supporter"),
    "VANGUARD": ("先鋒", "Vanguard"),
    "ASSAULT": ("突擊", "Striker"),
}
WEAPON_TYPES = {
    "Sword": ("單手劍", "Sword"),
    "Claymores": ("雙手劍", "Great Sword"),
    "Lance": ("長柄武器", "Polearm"),
    "Pistol": ("手銃", "Handcannon"),
    "Wand": ("施術單元", "Arts Unit"),
}
SKILLS = {
    "NormalAttack": ("普通攻擊", "Basic attack"),
    "NormalSkill": ("戰技", "Battle skill"),
    "ComboSkill": ("連攜技", "Combo skill"),
    "UltimateSkill": ("終結技", "Ultimate"),
}
# What SKPORT calls these (in English), to the codes above
SKPORT_ELEMENTS = {
    "Physical": "Physical",
    "Heat": "Fire",
    "Cryo": "Cryst",
    "Electric": "Pulse",
    "Nature": "Natural",
}
SKPORT_PROFESSIONS = {
    "Guard": "GUARD",
    "Caster": "CASTER",
    "Defender": "DEFENDER",
    "Supporter": "SUPPORTER",
    "Vanguard": "VANGUARD",
    "Striker": "ASSAULT",
}
SKPORT_SKILLS = {
    "skill_type_normal_attack": "NormalAttack",
    "skill_type_normal_skill": "NormalSkill",
    "skill_type_combo_skill": "ComboSkill",
    "skill_type_ultimate_skill": "UltimateSkill",
}
GEAR_SLOTS = ("bodyEquip", "armEquip", "firstAccessory", "secondAccessory")
LOGIN_SECONDS = 1800  # SKPORT's credential is reused this long
ACCOUNT_SECONDS = 300  # a linked account is read at most this often
ACCOUNT_CACHE_LIMIT = 500  # members' cards kept in memory, the oldest read leaves
MAX_ROSTER = 60  # operators listed for the AI, the highest first
REGIONS = {
    "ASIA": ("亞洲", "Asia"),
    "NA": ("美洲", "Americas"),
    "EU": ("歐洲", "Europe"),
}


class EndfieldError(Exception):
    """Why a profile could not be read: ``code`` is one of the keys below."""

    # bad_uid, not_found, maintenance, rate_limited, unavailable,
    # bad_token, no_role, no_key
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Weapon:
    name: str
    rarity: int
    level: int
    potential: int


@dataclass
class Operator:
    name: str
    rarity: int
    element: str
    profession: str
    weapon_type: str
    level: int
    potential: int
    weapon: Optional[Weapon]
    sets: list[tuple[str, int]] = field(default_factory=list)  # (set, pieces)
    skills: list[tuple[str, int]] = field(default_factory=list)  # (kind, level)


@dataclass
class Profile:
    uid: str
    name: str
    region: str
    signature: str
    adventure_level: int
    world_level: int
    operators_owned: int
    weapons_owned: int
    showcase: list[Operator]
    read_at: float


@dataclass
class Account:
    """A member's own game card, read with their SKPORT token."""

    uid: str
    name: str
    operators: list[Operator]
    stamina: Optional[int]
    stamina_max: Optional[int]
    read_at: float


def _pick(names: tuple[str, str], lang: str) -> str:
    return names[1] if lang == "en" else names[0]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any, limit: int = 60) -> str:
    return " ".join(str(value or "").split())[:limit]


def _rarity(value: Any) -> int:
    """``{"key": "rarity_6"}``, ``{"value": "6"}`` or ``6`` -> 6."""
    if isinstance(value, dict):
        value = value.get("key") or value.get("value")
    found = re.search(r"(\d+)$", str(value or ""))
    return int(found.group(1)) if found else 0


class Store:
    """Enka.Network's tables: template id -> operator, weapon and gear names."""

    def __init__(self, tables: dict[str, Any]) -> None:
        self.avatars = tables["avatars"]
        self.weapons = tables["weapons"]
        self.equips = tables["equips"]
        self.locs = tables["locs"]
        self._english: Optional[dict[str, str]] = None

    def name(self, name_hash: Any, lang: str) -> str:
        table = self.locs.get("en" if lang == "en" else "zh-tw", {})
        return table.get(str(name_hash)) or self.locs.get("en", {}).get(
            str(name_hash), "?"
        )

    def translated(self, english: str, lang: str) -> str:
        """A name SKPORT gave in English, in the member's language."""
        if self._english is None:
            self._english = {v: k for k, v in self.locs.get("en", {}).items()}
        key = self._english.get(english)
        return self.name(key, lang) if key else english

    def account_operator(self, raw: dict[str, Any], lang: str) -> Optional[Operator]:
        """One entry of SKPORT's ``chars``."""
        data = raw.get("charData") or {}
        english = _text(data.get("name"), 40)
        if not english:
            return None
        hash_of_name = (self._english or {}).get(english)
        avatar = next(
            (
                a
                for a in self.avatars.values()
                if hash_of_name is not None and a.get("NameHash") == hash_of_name
            ),
            {},
        )
        element = SKPORT_ELEMENTS.get(
            str((data.get("property") or {}).get("value")), ""
        )
        profession = SKPORT_PROFESSIONS.get(
            str((data.get("profession") or {}).get("value")), ""
        )
        weapon_type = avatar.get("WeaponType", "")
        weapon = None
        raw_weapon = raw.get("weapon") or {}
        weapon_data = raw_weapon.get("weaponData") or {}
        if weapon_data:
            weapon = Weapon(
                name=self.translated(_text(weapon_data.get("name"), 40), lang),
                rarity=_rarity(weapon_data.get("rarity")),
                level=_int(raw_weapon.get("level")),
                potential=_int(raw_weapon.get("refineLevel")),
            )
        pieces: dict[str, int] = {}
        for slot in GEAR_SLOTS:
            suit = ((raw.get(slot) or {}).get("equipData") or {}).get("suit") or {}
            if suit.get("name"):
                name = self.translated(_text(suit["name"], 40), lang)
                pieces[name] = pieces.get(name, 0) + 1
        user_skills = raw.get("userSkills") or {}
        skills = []
        for skill in data.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            kind = SKPORT_SKILLS.get(str((skill.get("type") or {}).get("key")))
            if kind:
                level = (user_skills.get(str(skill.get("id"))) or {}).get("level", 1)
                skills.append((_pick(SKILLS[kind], lang), _int(level)))
        return Operator(
            name=self.translated(english, lang),
            rarity=_rarity(data.get("rarity")),
            element=_pick(ELEMENTS.get(element, (element, element)), lang),
            profession=_pick(
                PROFESSIONS.get(profession, (profession, profession)), lang
            ),
            weapon_type=_pick(
                WEAPON_TYPES.get(weapon_type, (weapon_type, weapon_type)), lang
            ),
            level=_int(raw.get("level")),
            potential=_int(raw.get("potentialLevel")),
            weapon=weapon,
            sets=sorted(pieces.items(), key=lambda item: -item[1]),
            skills=skills,
        )

    def operator(self, raw: dict[str, Any], lang: str) -> Optional[Operator]:
        avatar = self.avatars.get(str(raw.get("templateId")))
        if not avatar:
            return None  # an operator newer than the store: left out, not guessed
        weapon = None
        raw_weapon = raw.get("weapon") or {}
        meta = self.weapons.get(str(raw_weapon.get("templateId")))
        if meta:
            weapon = Weapon(
                name=self.name(meta.get("NameHash"), lang),
                rarity=_int(meta.get("Rarity")),
                level=_int(raw_weapon.get("weaponLv")),
                potential=_int(raw_weapon.get("refineLv")),
            )
        pieces: dict[str, int] = {}
        items = self.equips.get("Items", {})
        suits = self.equips.get("Suits", {})
        for slot in raw.get("equip") or []:
            item = items.get(str((slot.get("value") or {}).get("templateid")))
            suit = suits.get(str((item or {}).get("SuitId")))
            if suit:
                set_name = self.name(suit.get("NameHash"), lang)
                pieces[set_name] = pieces.get(set_name, 0) + 1
        skills = []
        for info in (raw.get("skillInfo") or {}).get("levelInfo") or []:
            kind = str(info.get("skillId", "")).rsplit("_", 1)[-1]
            if kind in SKILLS:
                skills.append((_pick(SKILLS[kind], lang), _int(info.get("skillLevel"))))
        element = avatar.get("Element", "")
        profession = avatar.get("Profession", "")
        weapon_type = avatar.get("WeaponType", "")
        return Operator(
            name=self.name(avatar.get("NameHash"), lang),
            rarity=_int(avatar.get("Rarity")),
            element=_pick(ELEMENTS.get(element, (element, element)), lang),
            profession=_pick(
                PROFESSIONS.get(profession, (profession, profession)), lang
            ),
            weapon_type=_pick(
                WEAPON_TYPES.get(weapon_type, (weapon_type, weapon_type)), lang
            ),
            level=_int(raw.get("level")),
            potential=_int(raw.get("potentialLevel")),
            weapon=weapon,
            sets=sorted(pieces.items(), key=lambda item: -item[1]),
            skills=skills,
        )


def parse(data: dict[str, Any], store: Store, lang: str, read_at: float) -> Profile:
    info = data.get("playerInfo") or {}
    card = info.get("businessCard") or {}
    counts = card.get("statistic") or {}
    region = str(data.get("region") or "")
    return Profile(
        uid=str(data.get("uid") or card.get("platformRoleId") or ""),
        name=_text(card.get("name"), 40),
        region=_pick(REGIONS.get(region, (region, region)), lang),
        signature=_text(card.get("signature"), 100),
        adventure_level=_int(card.get("adventureLevel")),
        world_level=_int(card.get("worldLevel")),
        operators_owned=_int(counts.get("charNum")),
        weapons_owned=_int(counts.get("weaponNum")),
        showcase=[
            op
            for raw in info.get("charData") or []
            if (op := store.operator(raw, lang)) is not None
        ],
        read_at=read_at,
    )


def parse_account(
    detail: dict[str, Any], store: Store, lang: str, uid: str, name: str, read_at: float
) -> Account:
    store.translated("", lang)  # builds the English names
    operators = [
        op
        for raw in detail.get("chars") or []
        if isinstance(raw, dict)
        and (op := store.account_operator(raw, lang)) is not None
    ]
    operators.sort(key=lambda op: (-op.rarity, -op.level, op.name))
    dungeon = detail.get("dungeon") or {}
    return Account(
        uid=uid,
        name=_text(name, 40),
        operators=operators,
        stamina=_int(dungeon["curStamina"]) if "curStamina" in dungeon else None,
        stamina_max=_int(dungeon["maxStamina"]) if "maxStamina" in dungeon else None,
        read_at=read_at,
    )


class EndfieldService:
    def __init__(
        self,
        session_factory: Callable[[], Any] = aiohttp.ClientSession,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.session_factory = session_factory
        self.clock = clock
        self._session: Any = None
        self._store: Optional[Store] = None
        self._store_at = 0.0
        self._store_lock = asyncio.Lock()
        # uid -> (fresh until, raw answer, read at)
        self._raw: dict[str, tuple[float, dict[str, Any], float]] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self.skport = SkportClient(self._http, clock)
        # member -> (the stored token, credential good until, the login)
        self._logins: dict[int, tuple[str, float, Login]] = {}
        # member -> (the stored token, fresh until, card, read at, UID, name)
        self._cards: dict[int, tuple[str, float, dict[str, Any], float, str, str]] = {}
        # member -> [the lock, how many are using or waiting for it]
        self._account_locks: dict[int, list[Any]] = {}

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _http(self) -> Any:
        if self._session is None or getattr(self._session, "closed", False):
            self._session = self.session_factory(
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            )
        return self._session

    # ── links ─────────────────────────────────────────────────────────
    def _links(self) -> dict[str, dict[str, Any]]:
        try:
            raw = read_document(BINDINGS)
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            raise TypeError("Endfield links must be an object")
        return raw

    def bind(self, user_id: int, uid: str) -> None:
        if not UID_RE.match(uid):
            raise EndfieldError("bad_uid")
        links = self._links()
        # Linking a UID by hand replaces any linked account: the two must agree.
        links[str(user_id)] = {
            "uid": uid,
            "bound_at": datetime.now(timezone.utc).isoformat(),
        }
        write_document(BINDINGS, links)
        self._forget_account(user_id)

    def unbind(self, user_id: int) -> bool:
        links = self._links()
        self._forget_account(user_id)
        if links.pop(str(user_id), None) is None:
            return False
        write_document(BINDINGS, links)
        return True

    def _forget_account(self, user_id: int) -> None:
        self._logins.pop(user_id, None)
        self._cards.pop(user_id, None)

    def link_snapshot(self, user_id: int) -> tuple[Optional[str], Optional[str]]:
        """The member's UID and a mark that changes with their link, read together."""
        link = self._links().get(str(user_id))
        if not link:
            return None, None
        uid = str(link.get("uid") or "")
        mark = f"{uid}:{link.get('token')}:{link.get('bound_at')}"
        return (uid if UID_RE.match(uid) else None), mark

    def has_account(self, user_id: int) -> bool:
        return bool((self._links().get(str(user_id)) or {}).get("token"))

    def _cipher(self) -> Fernet:
        """The key that protects the HoYoLAB cookies; it is created with /mhy."""
        key = os.getenv("GENSHIN_ENCRYPTION_KEY")
        if not key:
            try:
                with open(".env", encoding="utf-8") as stream:
                    key = dotenv_values(stream=stream, interpolate=False).get(
                        "GENSHIN_ENCRYPTION_KEY"
                    )
            except OSError:
                key = None
        if not key:
            raise EndfieldError("no_key")
        return Fernet(key.encode())

    def _store_token(self, user_id: int, uid: str, token: str) -> str:
        """Save the token encrypted; returns what was saved, the mark of this link."""
        stored = self._cipher().encrypt(token.encode()).decode()
        links = self._links()
        links[str(user_id)] = {
            "uid": uid,
            "token": stored,
            "bound_at": datetime.now(timezone.utc).isoformat(),
        }
        write_document(BINDINGS, links)
        return stored

    def _stored_token(self, user_id: int) -> Optional[str]:
        return (self._links().get(str(user_id)) or {}).get("token")

    def _open_token(self, stored: str) -> str:
        try:
            return self._cipher().decrypt(stored.encode()).decode()
        except InvalidToken:
            raise EndfieldError("bad_token") from None

    def bound_uid(self, user_id: int) -> Optional[str]:
        link = self._links().get(str(user_id))
        uid = str((link or {}).get("uid") or "")
        return uid if UID_RE.match(uid) else None

    # ── Enka.Network ──────────────────────────────────────────────────
    async def store(self) -> Store:
        """The name tables: from disk, refreshed from GitHub once a day."""
        async with self._store_lock:
            now = self.clock()
            if self._store is not None and now - self._store_at < STORE_SECONDS:
                return self._store
            tables = await asyncio.to_thread(self._read_store_files)
            age = await asyncio.to_thread(self._store_files_age)
            if tables is None or age > STORE_SECONDS:
                try:
                    tables = await self._download_store()
                    age = 0.0
                except Exception:
                    logger.warning(
                        "Could not download the Endfield store", exc_info=True
                    )
                    if tables is None:
                        raise EndfieldError("unavailable") from None
            self._store = Store(tables)
            # By the tables' real age, so loading old files does not make them new;
            # after a failed download, try again in an hour rather than on every read.
            self._store_at = now - min(age, STORE_SECONDS - STORE_RETRY_SECONDS)
            return self._store

    def _read_store_files(self) -> Optional[dict[str, Any]]:
        tables = {}
        for name in STORE_FILES:
            path = os.path.join(STORE_DIR, f"{name}.json")
            try:
                with open(path, encoding="utf-8") as f:
                    tables[name] = json.load(f)
            except (OSError, ValueError):
                return None
        return tables

    def _store_files_age(self) -> float:
        try:
            oldest = min(
                os.path.getmtime(os.path.join(STORE_DIR, f"{name}.json"))
                for name in STORE_FILES
            )
        except OSError:
            return float("inf")
        return time.time() - oldest

    async def _download_store(self) -> dict[str, Any]:
        tables = {}
        http = self._http()
        for name in STORE_FILES:
            async with http.get(STORE.format(name=name)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"store {name}: HTTP {resp.status}")
                tables[name] = json.loads(await resp.text())
        await asyncio.to_thread(self._write_store_files, tables)
        return tables

    def _write_store_files(self, tables: dict[str, Any]) -> None:
        os.makedirs(STORE_DIR, exist_ok=True)
        for name, table in tables.items():
            path = os.path.join(STORE_DIR, f"{name}.json")
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(table, f, ensure_ascii=False)
            os.replace(path + ".tmp", path)

    async def raw(self, uid: str) -> tuple[dict[str, Any], float]:
        """Enka's answer for a UID and when it was read; cached until its ttl.

        When Enka is busy or down, the last good answer is used (its read time
        shows how old it is); a wrong or unknown UID is never covered up.
        """
        if not UID_RE.match(uid):
            raise EndfieldError("bad_uid")
        cached = self._raw.get(uid)
        now = self.clock()
        if cached and cached[0] > now:
            return cached[1], cached[2]
        pending = self._pending.get(uid)
        if pending is None:
            if cached is None and not self._room_for_one(now):
                # Dropping a live entry would ask Enka about that UID again before
                # its ttl; a new UID waits instead.
                raise EndfieldError("rate_limited")
            pending = asyncio.ensure_future(self._fetch(uid))
            self._pending[uid] = pending
            pending.add_done_callback(lambda _: self._pending.pop(uid, None))
        try:
            return await asyncio.shield(pending)
        except EndfieldError as error:
            if cached and error.code in ("maintenance", "rate_limited", "unavailable"):
                return cached[1], cached[2]
            if error.code in ("bad_uid", "not_found"):
                self._raw.pop(uid, None)  # that player is gone: never fall back to it
            raise

    def _room_for_one(self, now: float) -> bool:
        """Whether one more UID fits, once entries past their ttl are dropped."""
        if len(self._raw) + len(self._pending) < CACHE_LIMIT:
            return True
        for uid in [u for u, entry in self._raw.items() if entry[0] <= now]:
            del self._raw[uid]
        return len(self._raw) + len(self._pending) < CACHE_LIMIT

    async def _fetch(self, uid: str) -> tuple[dict[str, Any], float]:
        try:
            async with self._http().get(API.format(uid=uid)) as resp:
                status = resp.status
                body = await resp.text() if status == 200 else ""
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise EndfieldError("unavailable") from None
        if status != 200:
            raise EndfieldError(
                {
                    400: "bad_uid",
                    404: "not_found",
                    424: "maintenance",
                    429: "rate_limited",
                }.get(status, "unavailable")
            )
        try:
            data = json.loads(body)
        except ValueError:
            raise EndfieldError("unavailable") from None
        now = self.clock()
        ttl = max(MIN_TTL, _int(data.get("ttl")))
        self._raw[uid] = (now + ttl, data, now)
        return data, now

    # ── SKPORT ────────────────────────────────────────────────────────
    async def link_account(
        self, user_id: int, pasted: str, lang: str = "zh"
    ) -> Account:
        """Check a pasted account token against SKPORT, then keep it, encrypted."""
        try:
            token = parse_token(pasted)
            login = await self.skport.login(token)
            detail = await self.skport.detail(login)
        except SkportError as error:
            raise EndfieldError(error.code) from None
        if not UID_RE.match(login.role_id):
            raise EndfieldError("no_role")
        stored = await run_storage(self._store_token, user_id, login.role_id, token)
        now = self.clock()
        self._publish(user_id, stored, login, detail, now)
        return parse_account(
            detail, await self.store(), lang, login.role_id, login.nickname, now
        )

    def _publish(
        self,
        user_id: int,
        stored: str,
        login: Login,
        detail: dict[str, Any],
        now: float,
    ) -> tuple[str, float, dict[str, Any], float, str, str]:
        """Keep a read, tagged with the token it came from; returns it.

        The card carries its own UID and name, so nothing shown can come from two
        different links. The caller uses what is returned: a read older than the
        others may already have been dropped here.
        """
        held = self._logins.get(user_id)
        until = held[1] if held and held[0] == stored and held[2] is login else None
        card = (
            stored,
            now + ACCOUNT_SECONDS,
            detail,
            now,
            login.role_id,
            login.nickname,
        )
        self._logins[user_id] = (stored, until or now + LOGIN_SECONDS, login)
        self._cards[user_id] = card
        while len(self._cards) > ACCOUNT_CACHE_LIMIT:
            oldest = min(self._cards, key=lambda member: self._cards[member][3])
            self._forget_account(oldest)
        return card

    async def account(self, user_id: int, lang: str = "zh") -> Optional[Account]:
        """The member's own card; None when no token is linked.

        When SKPORT is unreachable, the last good read is used. A token SKPORT
        turned down raises ``bad_token``: the member has to link again.
        """
        stored = await run_storage(self._stored_token, user_id)
        if not stored:
            return None
        # One read per member at a time; messages sent meanwhile share it. The
        # entry goes with its last user, so idle members hold nothing here.
        entry = self._account_locks.setdefault(user_id, [asyncio.Lock(), 0])
        entry[1] += 1
        try:
            async with entry[0]:
                card = self._cards.get(user_id)
                usable = card if card and card[0] == stored else None
                if not usable or usable[1] <= self.clock():
                    read = None
                    try:
                        read = await self._read_card(user_id, stored)
                    except EndfieldError as error:
                        if not usable or error.code != "unavailable":
                            raise
                    # Unlinked or linked anew during the read: neither the new
                    # read nor the old card is theirs to see now.
                    if await run_storage(self._stored_token, user_id) != stored:
                        return None
                    if read:
                        usable = self._publish(user_id, stored, *read)
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                self._account_locks.pop(user_id, None)
        return parse_account(
            usable[2], await self.store(), lang, usable[4], usable[5], usable[3]
        )

    async def _read_card(
        self, user_id: int, stored: str
    ) -> tuple[Login, dict[str, Any], float]:
        now = self.clock()
        cached = self._logins.get(user_id)
        fresh = cached if cached and cached[0] == stored and cached[1] > now else None
        try:
            for attempt in (fresh[2] if fresh else None, None):
                login = attempt or await self.skport.login(
                    await asyncio.to_thread(self._open_token, stored)
                )
                try:
                    return login, await self.skport.detail(login), now
                except SkportError as error:
                    # an old credential is the likely cause: once more with a new one
                    if attempt is None or error.code != "bad_token":
                        raise
        except SkportError as error:
            raise EndfieldError(error.code) from None
        raise EndfieldError("unavailable")

    async def profile(self, uid: str, lang: str = "zh") -> Profile:
        data, read_at = await self.raw(uid)
        return parse(data, await self.store(), lang, read_at)


def _when(read_at: float, now: float, service: str) -> str:
    age = now - read_at
    if age < 600:  # a linked account is read every few minutes at most
        return "read just now"
    return f"read {int(age // 60)} min ago ({service} did not answer just now)"


def _operator_line(op: Operator) -> str:
    parts = [
        f"{op.name} {op.rarity}★ {op.element} {op.profession} Lv{op.level} potential {op.potential}"
    ]
    if op.weapon:
        parts.append(
            f"{op.weapon.name} {op.weapon.rarity}★ Lv{op.weapon.level} weapon potential {op.weapon.potential}"
        )
    if op.sets:
        parts.append(", ".join(f"{name} ×{count}" for name, count in op.sets))
    if op.skills:
        parts.append(" ".join(f"{kind} {level}" for kind, level in op.skills))
    return "- " + " · ".join(parts)


def describe_account(account: Account, now: float) -> str:
    """The member's whole roster for the AI characters; the UID and token stay out."""
    head = f"Arknights: Endfield — name {account.name or 'unknown'}"
    if account.stamina is not None:
        head += f", stamina {account.stamina}/{account.stamina_max}"
    lines = [
        f"({_when(account.read_at, now, 'SKPORT')})",
        head,
        f"operators owned ({len(account.operators)}):",
    ]
    lines += [_operator_line(op) for op in account.operators[:MAX_ROSTER]]
    if len(account.operators) > MAX_ROSTER:
        lines.append(
            f"- and {len(account.operators) - MAX_ROSTER} more at lower levels"
        )
    return "\n".join(lines)


def describe(profile: Profile, now: float) -> str:
    """The profile as plain lines for the AI characters (English labels, game names).

    The UID is left out: the model needs the operators, not the account.
    """
    age = now - profile.read_at
    when = (
        "read just now"
        if age < 120
        else f"read {int(age // 60)} min ago (Enka.Network did not answer just now)"
    )
    lines = [
        f"({when})",
        f"Arknights: Endfield ({profile.region}) — name {profile.name}, "
        f"authority level {profile.adventure_level}, world level {profile.world_level}, "
        f"{profile.operators_owned} operators and {profile.weapons_owned} weapons owned",
        f"operators in the public showcase ({len(profile.showcase)}; the others are not visible):",
    ]
    lines += [_operator_line(op) for op in profile.showcase]
    return "\n".join(lines)
