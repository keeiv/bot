"""Colours shared by the control panel.

The BOT. logo's seven colours plus a warm dark UI palette (the same one the
website uses in dark mode).
"""

from rich.text import Text

BRAND = (
    "#f5a838",  # sun
    "#fa8a40",  # orange
    "#fc4f50",  # coral
    "#ec2b6e",  # crimson
    "#d24ed8",  # magenta
    "#2dceca",  # teal
    "#4f7ded",  # blue
)

ACCENT = "#f99549"
OK = "#72d48a"
WARN = "#f4c352"
ERR = "#f5746d"
INFO = "#57d4d4"
ROSE = "#f38abe"
TEXT = "#f2eeea"
MUTED = "#a9a39e"
DIM = "#8b857f"
BORDER = "#5d5550"

LEVEL_STYLES = {
    "DEBUG": f"{DIM}",
    "INFO": f"{INFO}",
    "WARNING": f"bold {WARN}",
    "ERROR": f"bold {ERR}",
    "CRITICAL": f"bold white on {ERR}",
}
LEVEL_TAGS = {
    "DEBUG": "DEBUG",
    "INFO": "INFO ",
    "WARNING": "WARN ",
    "ERROR": "ERROR",
    "CRITICAL": "CRIT ",
}


def _rgb(colour: str) -> tuple[int, int, int]:
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def gradient_colour(position: float) -> str:
    """Colour at ``position`` (0..1) along the seven logo colours."""
    position = min(max(position, 0.0), 1.0) * (len(BRAND) - 1)
    index = min(int(position), len(BRAND) - 2)
    fraction = position - index
    first, second = _rgb(BRAND[index]), _rgb(BRAND[index + 1])
    mixed = (round(a + (b - a) * fraction) for a, b in zip(first, second))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def gradient(text: str, *, bold: bool = True) -> Text:
    """``text`` with each character coloured along the logo gradient."""
    result = Text()
    last = max(len(text) - 1, 1)
    for index, char in enumerate(text):
        style = gradient_colour(index / last)
        result.append(char, style=f"bold {style}" if bold else style)
    return result


def brand_bar(width: int, char: str = "▂") -> Text:
    """A thin bar in the seven logo colours (the logo's own signature)."""
    result = Text()
    last = max(width - 1, 1)
    for index in range(width):
        result.append(char, style=gradient_colour(index / last))
    return result
