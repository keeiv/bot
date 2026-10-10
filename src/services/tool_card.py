"""Render the private usage card from the same snapshot used by the website."""

import io
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


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
    draw.text((80, 82), "使用額度", font=font(34), fill="#f3f7fc")
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
        (("weekly", "本週用量"), ("rolling", "近三小時用量"))
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
            f"可用 {max(0, item['limit'] - item['used'] - data['reserved']):,} 點",
            font=font(17),
            fill="#8297b1",
        )
    draw.line((80, 459, 1020, 459), fill="#27384e", width=1)
    draw.text(
        (80, 483),
        f"使用年資 {data['days']} 天  ·  重置券 {data['coupons']} 張  ·  預留 {data['reserved']} 點",
        font=font(19),
        fill="#c6d2e2",
    )
    draw.text(
        (80, 530),
        (
            "固定授權等級 · 無需付費 · 點數僅用於用量管理"
            if tier.get("hidden")
            else "依使用天數自動升級 · 無需付費 · 點數僅用於用量管理"
        ),
        font=font(18),
        fill="#8297b1",
    )
    output = io.BytesIO()
    image.save(output, "PNG")
    output.seek(0)
    return output
