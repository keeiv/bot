"""The companion game as members meet it: copy, art, the card and the commands."""

import inspect
import random
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from src.cogs.games import pet as module
from src.cogs.games.pet import PanelView
from src.cogs.games.pet import Pet
from src.cogs.games.pet import refusal
from src.locales import MESSAGES
from src.services import pet_art
from src.services import pet_rules as rules
from src.services import pet_service
from src.services.pet_card import status_card
from src.services.pet_service import PetError
from src.services.pet_service import PetService
from src.utils.i18n import language_scope


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

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


def edit(service, user_id, **pet):
    data = service._read(user_id)
    data["pet"].update(pet)
    service._write(user_id, data)


# ── copy ──────────────────────────────────────────────────────────
def test_every_name_and_refusal_has_copy_in_both_languages():
    keys = [f"pet.species.{name}" for name in rules.SPECIES]
    keys += [f"pet.about.{name}" for name in rules.SPECIES]
    keys += [f"pet.form.{s}.{f}" for s in rules.SPECIES for f in (1, 2, 3, "m")]
    keys += [f"pet.material.{name}" for name in rules.MATERIALS]
    keys += [f"pet.zone.{name}" for name in rules.ZONES]
    keys += [f"pet.nature.{name}" for name in rules.NATURES]
    keys += [f"pet.stat.{name}" for name in rules.STATS]
    keys += [f"pet.need.{name}" for name in ("satiety", "mood", "energy")]
    codes = set(re.findall(r'PetError\(\s*"(\w+)"', inspect.getsource(pet_service)))
    assert len(codes) > 25
    keys += [f"pet.error.{name}" for name in codes | {"storage"}]
    assert [key for key in keys if key not in MESSAGES] == []


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_refusal_reads_as_a_sentence(lang):
    values = {"need": 5, "until": 1_800_000_000, "cap": 31}
    with language_scope(lang):
        short = refusal(PetError("short", cost={}, short={rules.SILVER: 2}))
        assert ("Streamsilver x2" if lang == "en" else "流光銀 ×2") in short
        for name in ("no_coins", "on_trip", "zone_locked", "aptitude_max", "full"):
            text = refusal(PetError(name, **values))
            assert text and "{" not in text


# ── art ───────────────────────────────────────────────────────────
def test_twelve_sprites_drawn_here_each_different():
    seen = set()
    for species in rules.SPECIES:
        for stage, mutated in ((1, False), (2, False), (3, False), (3, True)):
            sprite = pet_art.sprite(species, stage, mutated)
            assert sprite.size == (48, 48) and sprite.mode == "RGBA"
            opaque = sum(sprite.getchannel("A").histogram()[1:])
            assert 250 < opaque < 48 * 48  # a figure, not a blank or a block
            seen.add(sprite.tobytes())
    assert len(seen) == 12
    assert pet_art.enlarged("nova", 2, scale=4).size == (192, 192)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_status_card_renders_for_every_state(service, clock, lang):
    service.adopt(1, "ark", "方舟")
    with language_scope(lang):
        fresh = Image.open(status_card(service.view(1)))
        assert fresh.size == (900, 460)
        edit(service, 1, level=100, breaks=9, mutated=True)
        Image.open(status_card(service.view(1))).verify()
        clock.pass_(31 * rules.DAY)
        away = Image.open(status_card(service.view(1)))
        assert away.tobytes() != fresh.tobytes()


# ── commands ──────────────────────────────────────────────────────
def test_the_command_group_is_complete_and_within_discord_limits():
    names = {command.name: command for command in Pet.pet.commands}
    assert set(names) == {
        "adopt",
        "panel",
        "recall",
        "rename",
        "daily",
        "expedition",
        "collect",
        "boss",
        "bag",
        "shop",
        "breakthrough",
        "train",
        "nature",
        "mutate",
        "duel",
        "rank",
        "guide",
    }
    assert all(len(command.description) <= 100 for command in names.values())
    natures = {choice.value for choice in names["nature"].parameters[0].choices}
    assert natures == set(rules.NATURES)
    zones = [choice.value for choice in names["expedition"].parameters[0].choices]
    assert zones == list(rules.ZONES)
    trips = {float(c.value) for c in names["expedition"].parameters[1].choices}
    assert trips == set(rules.TRIPS)


class FakeInteraction:
    def __init__(self, user_id, guild_id=None):
        self.user = SimpleNamespace(id=user_id, display_name=f"user{user_id}")
        self.guild_id = guild_id
        self.guild = None
        self.locale = None
        self.client = SimpleNamespace(get_guild=lambda _: None)
        self.response = SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock())
        self.followup = SimpleNamespace(send=AsyncMock())
        self.edit_original_response = AsyncMock()


@pytest.fixture
def cog(service, monkeypatch):
    async def english(*args, **kwargs):
        return "en"

    monkeypatch.setattr("src.utils.lang_context.interaction_lang", english)
    bot = SimpleNamespace(get_cog=lambda name: None, get_guild=lambda _: None)
    made = module.Pet(bot)
    made.service = service
    return made


async def open_panel(cog, user_id):
    interaction = FakeInteraction(user_id)
    await cog.panel_command.callback(cog, interaction)
    return interaction.followup.send.await_args.kwargs


async def test_adopting_shows_a_card_with_buttons_only_the_keeper_can_press(cog):
    interaction = FakeInteraction(1)
    await cog.adopt.callback(cog, interaction, "nova", None)
    sent = interaction.followup.send.await_args.kwargs
    assert sent["embed"].title == "Nova" and sent["file"].filename == "pet.png"
    assert "Nova" in sent["embed"].description
    view = sent["view"]
    assert isinstance(view, PanelView)
    assert [item.label for item in view.children] == [
        "Feed",
        "Play",
        "Rest",
        "Collect",
        "Refresh",
    ]
    assert view.collect.disabled

    stranger = FakeInteraction(2)
    assert not await view.interaction_check(stranger)
    assert stranger.response.send_message.await_args.kwargs["ephemeral"]
    assert await view.interaction_check(FakeInteraction(1))


async def test_a_refusal_is_private_and_changes_nothing(cog, service):
    interaction = FakeInteraction(1)
    await cog.collect.callback(cog, interaction)
    args = interaction.followup.send.await_args
    assert "adopt" in args.args[0] and args.kwargs["ephemeral"]
    assert not service.has_pet(1)


async def test_pressing_feed_redraws_the_panel(cog, clock):
    await cog.adopt.callback(cog, FakeInteraction(1), "fable", "Quill")
    clock.pass_(6 * rules.HOUR)
    view = (await open_panel(cog, 1))["view"]
    press = FakeInteraction(1)
    await view.feed.callback(press)
    edited = press.edit_original_response.await_args.kwargs
    assert "ate well" in edited["embed"].description
    assert edited["attachments"][0].filename == "pet.png"
    again = FakeInteraction(1)
    await edited["view"].feed.callback(again)
    assert again.followup.send.await_args.kwargs["ephemeral"]
    again.edit_original_response.assert_not_awaited()


async def test_an_expedition_is_sent_and_collected_from_the_panel(cog, clock):
    await cog.adopt.callback(cog, FakeInteraction(1), "ark", None)
    leaving = FakeInteraction(1)
    await cog.expedition.callback(cog, leaving, "breeze_meadow", "0.5")
    sent = leaving.followup.send.await_args.kwargs
    assert "Breeze Meadow" in sent["embed"].description
    assert not sent["view"].collect.disabled
    clock.pass_(rules.HOUR)
    press = FakeInteraction(1)
    await sent["view"].collect.callback(press)
    edited = press.edit_original_response.await_args.kwargs
    assert "is back from" in edited["embed"].description
    assert "coins" in edited["embed"].description
    assert edited["view"].collect.disabled


async def test_a_companion_that_left_gets_a_recall_button(cog, clock):
    await cog.adopt.callback(cog, FakeInteraction(1), "ark", None)
    clock.pass_(40 * rules.DAY)
    sent = await open_panel(cog, 1)
    assert [item.label for item in sent["view"].children] == [
        "Call it home",
        "Refresh",
    ]
    press = FakeInteraction(1)
    await sent["view"].recall.callback(press)
    edited = press.edit_original_response.await_args.kwargs
    assert "home again" in edited["embed"].description
    assert len(edited["view"].children) == 5


async def test_a_duel_reply_pings_nobody(cog):
    await cog.adopt.callback(cog, FakeInteraction(1), "fable", None)
    await cog.adopt.callback(cog, FakeInteraction(2), "nova", None)
    interaction = FakeInteraction(1)
    other = SimpleNamespace(id=2, display_name="user2")
    await cog.duel.callback(cog, interaction, other)
    sent = interaction.followup.send.await_args.kwargs
    assert sent["allowed_mentions"].to_dict() == {"parse": []}
    assert sent["embed"].title == "Fable vs Nova"


async def test_a_storage_failure_is_a_plain_refusal(cog, monkeypatch):
    from src.utils.document_store import StorageError

    def down(user_id):
        raise StorageError("MySQL connection failed; JSON fallback is disabled")

    monkeypatch.setattr(cog.service, "view", down)
    interaction = FakeInteraction(1)
    await cog.panel_command.callback(cog, interaction)
    args = interaction.followup.send.await_args
    assert "Nothing changed" in args.args[0] and args.kwargs["ephemeral"]
