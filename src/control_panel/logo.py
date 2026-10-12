"""The BOT. logo drawn with half-block characters.

A terminal cannot show a picture, but every character cell can hold two pixels
(``▀`` with a foreground and a background colour), which is enough for the
logo's flat colours to stay recognisable.
"""

from functools import lru_cache
from pathlib import Path
from typing import cast

from rich.style import Style
from rich.text import Text

from src.control_panel import theme

ASSET = Path(__file__).parent / "assets" / "bot-logo.png"
_OPAQUE = 96  # alpha above this counts as a solid pixel


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


@lru_cache(maxsize=8)
def _pixels(size: int) -> tuple[tuple[tuple[int, int, int, int], ...], ...]:
    """The logo as ``size`` x ``size`` RGBA pixels, resized without dark fringes."""
    from PIL import Image  # imported lazily: the panel works without a logo

    image = Image.open(ASSET).convert("RGBA")
    alpha = image.getchannel("A")
    # Resize the colour premultiplied by alpha, so transparent edges do not bleed
    # black into the logo's colours, then divide the alpha back out.
    colour = Image.composite(image.convert("RGB"), Image.new("RGB", image.size), alpha)
    small = Image.merge("RGBA", (*colour.split(), alpha)).resize(
        (size, size), Image.Resampling.LANCZOS
    )
    loaded = small.load()
    assert loaded is not None
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            r, g, b, a = cast(tuple[int, int, int, int], loaded[x, y])
            if a:
                r, g, b = (min(round(v * 255 / a), 255) for v in (r, g, b))
            row.append((r, g, b, a))
        rows.append(tuple(row))
    return tuple(rows)


def logo_text(size: int = 16, *, visible_rows: int | None = None) -> Text:
    """The logo ``size`` columns wide and ``size // 2`` rows tall.

    ``visible_rows`` reveals only the first rows, which the boot animation uses
    to draw the logo in from the top.
    """
    try:
        pixels = _pixels(size)
    except (OSError, ImportError):
        return Text("BOT.", style=f"bold {theme.ACCENT}")
    text = Text(no_wrap=True)
    rows = size // 2
    shown = rows if visible_rows is None else max(min(visible_rows, rows), 0)
    for row in range(rows):
        if row >= shown:
            text.append(" " * size)
        else:
            for x in range(size):
                top = pixels[row * 2][x]
                bottom = pixels[row * 2 + 1][x]
                top_on, bottom_on = top[3] >= _OPAQUE, bottom[3] >= _OPAQUE
                if top_on and bottom_on:
                    text.append(
                        "▀", Style(color=_hex(top[:3]), bgcolor=_hex(bottom[:3]))
                    )
                elif top_on:
                    text.append("▀", Style(color=_hex(top[:3])))
                elif bottom_on:
                    text.append("▄", Style(color=_hex(bottom[:3])))
                else:
                    text.append(" ")
        if row < rows - 1:
            text.append("\n")
    return text
