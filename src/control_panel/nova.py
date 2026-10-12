"""Nova (諾瓦), the BOT. mascot, as a 16 x 12 pixel sprite.

Nova is the logo turned into a character, with the NovaGrid engine built in:

- The logo's frame is Nova's hood: the sun-to-orange top bar is the brim, the
  orange-to-coral left bar its side. A hood that keeps watch at the door, like
  the bot itself.
- The logo's round centre is Nova's face, with a blush for greeting guests.
- The logo's crimson-to-teal swoosh is the scarf that sweeps along the bottom:
  the bot tidies up after.
- The blue right bar is drawn as a column of tiles, the sampling grid NovaGrid
  reads an image through.
- The star at the corner is the "nova" itself. It lights up when an AI model is
  connected; with none, the star is unlit and Nova rests with closed eyes.

Each letter is one pixel; two pixel rows share one character cell (``▀``), the
same way the logo is drawn in :mod:`src.control_panel.logo`.
"""

from rich.style import Style
from rich.text import Text

try:
    from src.control_panel import theme
except ImportError:  # the review worker package ships these files side by side
    import theme

SUN, ORANGE, CORAL, CRIMSON, MAGENTA, TEAL, BLUE = theme.BRAND

PALETTE: dict[str, str] = {
    "S": SUN,
    "O": ORANGE,
    "C": CORAL,
    "R": CRIMSON,
    "M": MAGENTA,
    "T": TEAL,
    "B": BLUE,
    "b": "#8bacf7",  # the lighter grid tile
    "Y": "#ffd678",  # the lit star's centre
    "y": SUN,  # the lit star's points
    "G": "#8b857f",  # the unlit star's centre
    "g": "#5d5550",  # the unlit star's points
    "W": "#f2eeea",  # eye highlight
    "K": "#221a1e",  # eyes
    "P": "#f078be",  # blush
}

AWAKE: tuple[str, ...] = (
    "............y...",
    "...........yYy..",
    ".SSSSSSOOOO.y...",
    "OSSSSSSOOOOO.BB.",
    "OO...MMMM....bB.",
    ".OC.MMMMMM...Bb.",
    ".OCMMWMMWMM..bB.",
    ".CCMMKMMKMM..Bb.",
    ".CCMPMRRMPM..bB.",
    ".CR.MMMMMM..TT..",
    "..RRRRMMMRRTTT..",
    "...RRRRRRTTT....",
)

RESTING: tuple[str, ...] = (
    "............g...",
    "...........gGg..",
    ".SSSSSSOOOO.g...",
    "OSSSSSSOOOOO.BB.",
    "OO...MMMM....bB.",
    ".OC.MMMMMM...Bb.",
    ".OCMMMMMMMM..bB.",
    ".CCMKKMKKMM..Bb.",
    ".CCMPMMMMPM..bB.",
    ".CR.MMMMMM..TT..",
    "..RRRRMMMRRTTT..",
    "...RRRRRRTTT....",
)

FRAMES: dict[str, tuple[str, ...]] = {"awake": AWAKE, "resting": RESTING}
WIDTH = len(AWAKE[0])  # character cells
ROWS = len(AWAKE) // 2  # character rows


def sprite(frame: str = "resting") -> Text:
    """Nova as ``WIDTH`` x ``ROWS`` character cells."""
    pixels = FRAMES[frame]
    text = Text(no_wrap=True)
    for row in range(ROWS):
        top_row, bottom_row = pixels[row * 2], pixels[row * 2 + 1]
        for top, bottom in zip(top_row, bottom_row):
            top_colour, bottom_colour = PALETTE.get(top), PALETTE.get(bottom)
            if top_colour and bottom_colour:
                text.append("▀", Style(color=top_colour, bgcolor=bottom_colour))
            elif top_colour:
                text.append("▀", Style(color=top_colour))
            elif bottom_colour:
                text.append("▄", Style(color=bottom_colour))
            else:
                text.append(" ")
        if row < ROWS - 1:
            text.append("\n")
    return text
