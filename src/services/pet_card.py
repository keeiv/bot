"""The companion's status card: its sprite beside its needs and numbers."""

import io
from typing import Any

from PIL import Image
from PIL import ImageDraw
from PIL import ImageEnhance

from src.services import pet_art
from src.services import pet_rules as rules
from src.services.tool_card import font
from src.utils.i18n import text as tx

WIDTH, HEIGHT = 900, 460
PAPER = "#12151d"
PANEL = "#1a1f2b"
RULE = "#2c3445"
INK = "#f4f1ed"
MUTED = "#9aa1ad"
TRACK = "#262d3b"
ACCENT = {"fable": "#E9A14D", "ark": "#42A9A4", "nova": "#FFD44F"}
NEED_COLORS = {"satiety": "#F2943B", "mood": "#F06C8D", "energy": "#5CC8E8"}


def form_name(species: str, stage: int, mutated: bool) -> str:
    return tx(f"pet.form.{species}.{'m' if mutated else stage}")


def _bar(draw, box, share, color) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=(bottom - top) // 2, fill=TRACK)
    if share > 0:
        width = max(bottom - top, round((right - left) * min(1.0, share)))
        draw.rounded_rectangle(
            (left, top, left + width, bottom), radius=(bottom - top) // 2, fill=color
        )


def status_card(view: dict[str, Any]) -> io.BytesIO:
    pet = view["pet"]
    species, accent = pet["species"], ACCENT[pet["species"]]
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)

    # the left third: the companion on its patch of ground
    draw.rounded_rectangle((24, 24, 324, HEIGHT - 24), radius=24, fill=PANEL)
    draw.ellipse((74, 330, 274, 372), fill="#141822")
    sprite = pet_art.enlarged(species, view["stage"], pet["mutated"], 5)
    if view["away"]:
        sprite = ImageEnhance.Brightness(sprite.convert("LA").convert("RGBA")).enhance(
            0.45
        )
    image.paste(sprite, (54, 100), sprite)
    draw.text(
        (174, 396),
        (
            tx("pet.card.away")
            if view["away"]
            else tx("pet.card.power", power=view["power"])
        ),
        font=font(20),
        fill=MUTED if view["away"] else INK,
        anchor="mm",
    )

    # the name, what it is, and its keeper
    left = 356
    draw.text((left, 30), pet["name"], font=font(40), fill=INK)
    level = tx("pet.card.level", level=pet["level"])
    draw.rounded_rectangle((left, 92, left + 92, 126), radius=17, fill=accent)
    draw.text((left + 46, 109), level, font=font(20), fill=PAPER, anchor="mm")
    draw.text(
        (left + 106, 109),
        form_name(species, view["stage"], pet["mutated"])
        + "   "
        + tx("pet.card.nature", nature=tx(f"pet.nature.{pet['nature']}")),
        font=font(20),
        fill=MUTED,
        anchor="lm",
    )
    draw.text(
        (WIDTH - 40, 50),
        tx("pet.card.keeper", level=view["owner"]["level"]),
        font=font(20),
        fill=MUTED,
        anchor="rm",
    )

    # experience
    top = 150
    if pet["level"] >= rules.PET_MAX_LEVEL:
        note, share = tx("pet.card.max"), 1.0
    elif view["at_cap"]:
        note, share = tx("pet.card.capped"), 1.0
    else:
        note = f"{pet['xp']}/{view['xp_needed']}"
        share = pet["xp"] / view["xp_needed"]
    draw.text((left, top), tx("pet.card.xp"), font=font(18), fill=MUTED)
    draw.text((WIDTH - 40, top), note, font=font(18), fill=MUTED, anchor="ra")
    _bar(draw, (left, top + 30, WIDTH - 40, top + 40), share, accent)

    # the three needs
    top = 214
    for index, need in enumerate(("satiety", "mood", "energy")):
        y = top + index * 40
        value = round(pet[need])
        draw.text((left, y), tx(f"pet.need.{need}"), font=font(20), fill=INK)
        _bar(
            draw, (left + 86, y + 8, WIDTH - 96, y + 22), value / 100, NEED_COLORS[need]
        )
        draw.text((WIDTH - 40, y), str(value), font=font(20), fill=INK, anchor="ra")

    # stats, each with its aptitude and that nature's ceiling
    draw.line((left, 346, WIDTH - 40, 346), fill=RULE, width=1)
    column = (WIDTH - 40 - left) / 4
    for index, stat in enumerate(rules.STATS):
        x = left + index * column
        draw.text((x, 360), tx(f"pet.stat.{stat}"), font=font(17), fill=MUTED)
        draw.text((x, 382), str(view["stats"][stat]), font=font(30), fill=INK)
        draw.text(
            (x, 420),
            f"{pet['aptitudes'][stat]}/{view['caps'][stat]}",
            font=font(15),
            fill=accent if pet["aptitudes"][stat] >= view["caps"][stat] else MUTED,
        )

    output = io.BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return output
