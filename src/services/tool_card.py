"""Render the private usage card from the same snapshot used by the website."""

import io
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from src.utils.i18n import text as tx


def font(size):
    for filename in (
        "C:/Windows/Fonts/msjh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(filename).exists():
            return ImageFont.truetype(filename, size)
    return ImageFont.load_default(size=size)


def usage_card(data):
    tier = data["tier"]
    accent = tier["color"]
    image = Image.new("RGB", (1100, 620), "#0b1019")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (22, 22, 1078, 598), radius=30, fill="#101927", outline="#26364a", width=2
    )
    draw.rounded_rectangle((56, 62, 62, 119), radius=3, fill=accent)
    draw.text((82, 59), "FILE TOOLS", font=font(17), fill="#8095ae")
    draw.text((80, 82), tx("tool_card.usage_allowance"), font=font(34), fill="#f3f7fc")
    badge_font = font(25)
    badge_width = max(163, round(draw.textlength(tier["name"], font=badge_font)) + 48)
    draw.rounded_rectangle((1028 - badge_width, 62, 1028, 113), radius=25, fill=accent)
    draw.text(
        (1028 - badge_width / 2, 87),
        tier["name"],
        font=badge_font,
        fill="#0b1019",
        anchor="mm",
    )
    for index, (key, label) in enumerate(
        (
            ("weekly", tx("tool_card.weekly_usage")),
            ("rolling", tx("tool_card.last_three_hours")),
        )
    ):
        top = 188 + index * 130
        item = data[key]
        draw.text((80, top), label, font=font(23), fill="#d8e3ef")
        value = f"{item['used']:,} / {item['limit']:,} PT"
        draw.text((1020, top), value, font=font(23), fill="#eaf0f9", anchor="ra")
        draw.rounded_rectangle(
            (80, top + 46, 1020, top + 66), radius=10, fill="#243248"
        )
        end = 80 + round(940 * min(1, item["used"] / max(1, item["limit"])))
        if end > 82:
            draw.rounded_rectangle(
                (80, top + 46, end, top + 66), radius=10, fill=accent
            )
        draw.text(
            (80, top + 76),
            tx(
                "tool_card.available_pt",
                v0=(max(0, item["limit"] - item["used"] - data["reserved"])),
            ),
            font=font(17),
            fill="#8297b1",
        )
    draw.line((80, 459, 1020, 459), fill="#27384e", width=1)
    draw.text(
        (80, 483),
        tx(
            "tool_card.tenure_days_vouchers_reserved_pt",
            v0=(data["days"]),
            v1=(data["coupons"]),
            v2=(data["reserved"]),
        ),
        font=font(19),
        fill="#c6d2e2",
    )
    draw.text(
        (80, 530),
        (
            tx("tool_card.assigned_tier_no_payment_required_points")
            if tier.get("hidden")
            else tx("tool_card.tiers_grow_with_tenure_no_payment")
        ),
        font=font(18),
        fill="#8297b1",
    )
    output = io.BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return output
