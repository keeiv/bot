"""Pixel art for the companions, drawn here from shapes: no outside artwork.

Each sprite is painted on a 48 x 48 grid and enlarged without smoothing. Three
stages per species and one mutated form each; the mutated form is the third
stage in another palette with a mark of its own.
"""

from functools import lru_cache

from PIL import Image
from PIL import ImageDraw

GRID = 48
CLEAR = (0, 0, 0, 0)


def _rgb(value: str) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255)


PALETTES = {
    "fable": {
        "body": "#E9A14D",
        "light": "#FCEBC8",
        "dark": "#B4682A",
        "accent": "#3D4E93",
        "page": "#FFF7E0",
        "eye": "#2A2030",
        "line": "#4A2A14",
    },
    "fable_mutated": {
        "body": "#34324A",
        "light": "#8A86B0",
        "dark": "#1E1C2E",
        "accent": "#F2C24F",
        "page": "#EAE4FF",
        "eye": "#F2C24F",
        "line": "#0E0D18",
    },
    "ark": {
        "body": "#42A9A4",
        "light": "#C4EFE6",
        "dark": "#207078",
        "accent": "#C98C4B",
        "page": "#F5F2E7",
        "eye": "#16303A",
        "line": "#123840",
    },
    "ark_mutated": {
        "body": "#E7E1D4",
        "light": "#FFFFFF",
        "dark": "#A79E90",
        "accent": "#C4463D",
        "page": "#7FE3E0",
        "eye": "#C4463D",
        "line": "#4E2B31",
    },
    "nova": {
        "body": "#FFD44F",
        "light": "#FFF6C0",
        "dark": "#F2943B",
        "accent": "#E8552E",
        "page": "#FFFFFF",
        "eye": "#3A2414",
        "line": "#8A4A12",
    },
    "nova_mutated": {
        "body": "#7C50D2",
        "light": "#CDBBFF",
        "dark": "#3F2685",
        "accent": "#5FE3F0",
        "page": "#F4EEFF",
        "eye": "#F4EEFF",
        "line": "#1E1240",
    },
}


class Brush:
    """A 48 x 48 sheet with the few strokes the sprites are built from."""

    def __init__(self, palette: dict[str, str]) -> None:
        self.image = Image.new("RGBA", (GRID, GRID), CLEAR)
        self.draw = ImageDraw.Draw(self.image)
        self.colors = {name: _rgb(value) for name, value in palette.items()}

    def oval(self, box: tuple[int, int, int, int], color: str) -> None:
        self.draw.ellipse(box, fill=self.colors[color])

    def box(self, box: tuple[int, int, int, int], color: str) -> None:
        self.draw.rectangle(box, fill=self.colors[color])

    def shape(self, points: list[tuple[int, int]], color: str) -> None:
        self.draw.polygon(points, fill=self.colors[color])

    def dots(self, points: list[tuple[int, int]], color: str) -> None:
        for x, y in points:
            if 0 <= x < GRID and 0 <= y < GRID:
                self.image.putpixel((x, y), self.colors[color])

    def star(self, cx: int, cy: int, reach: int, color: str) -> None:
        """A four-pointed star: a plus with a filled heart."""
        for step in range(reach + 1):
            self.dots(
                [(cx + step, cy), (cx - step, cy), (cx, cy + step), (cx, cy - step)],
                color,
            )
        if reach >= 2:
            self.box((cx - 1, cy - 1, cx + 1, cy + 1), color)

    def mirror(self) -> None:
        """Copy the left half onto the right, for a creature seen from the front."""
        left = self.image.crop((0, 0, GRID // 2, GRID))
        self.image.paste(
            left.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (GRID // 2, 0)
        )
        self.draw = ImageDraw.Draw(self.image)

    def finish(self) -> Image.Image:
        """Ring the figure with its line colour, one pixel wide."""
        source = self.image.load()
        result = self.image.copy()
        target = result.load()
        line = self.colors["line"]
        for y in range(GRID):
            for x in range(GRID):
                if source[x, y][3]:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID and 0 <= ny < GRID and source[nx, ny][3]:
                        target[x, y] = line
                        break
        return result


# ── Fable: a fox that keeps stories; its tails are quills ─────────
def _fable(stage: int, mutated: bool) -> Image.Image:
    b = Brush(PALETTES["fable_mutated" if mutated else "fable"])
    grow = stage - 1  # 0, 1, 2
    head_top = 17 - 3 * grow
    floor = 43
    # quill tails behind the body, drawn on the left and mirrored
    tails = {1: [(12, 30)], 2: [(9, 26), (13, 32)], 3: [(5, 20), (8, 27), (13, 33)]}
    for tip_x, tip_y in tails[stage]:
        b.shape(
            [(22, floor - 6), (tip_x, tip_y - 6), (tip_x - 2, tip_y), (20, floor - 2)],
            "body",
        )
        b.shape(
            [(tip_x, tip_y - 6), (tip_x - 2, tip_y), (tip_x + 3, tip_y - 1)], "page"
        )
        b.dots([(tip_x - 1, tip_y - 5), (tip_x, tip_y - 3)], "accent")
    # body and chest
    b.oval((16 - grow, floor - 15 - 2 * grow, 31 + grow, floor), "body")
    b.oval((20 - grow, floor - 11 - grow, 27 + grow, floor - 1), "light")
    # front paw
    b.box((18 - grow, floor - 2, 21 - grow, floor), "light")
    # head
    b.oval((12 - grow, head_top, 35 + grow, head_top + 15 + grow), "body")
    # ear: a tall triangle with a lighter inside
    ear_tip = head_top - 6 - 2 * grow
    b.shape(
        [(13 - grow, head_top + 5), (14 - grow, ear_tip), (20, head_top + 2)], "body"
    )
    b.shape(
        [(15 - grow, head_top + 3), (15 - grow, ear_tip + 3), (18, head_top + 2)],
        "light",
    )
    if stage == 3:
        b.dots([(14 - grow, ear_tip - 1), (13 - grow, ear_tip - 2)], "accent")
    # muzzle, cheek, eye, nose
    b.oval((18 - grow, head_top + 8, 29 + grow, head_top + 15 + grow), "light")
    b.box((17 - grow, head_top + 6, 18 - grow, head_top + 8), "eye")
    b.dots([(18 - grow, head_top + 6)], "page")
    b.dots([(23, head_top + 10), (23, head_top + 11)], "eye")
    b.dots([(15 - grow, head_top + 10), (16 - grow, head_top + 10)], "dark")
    b.mirror()
    b.box((23, head_top + 10, 24, head_top + 10), "eye")
    # the mark between the eyes grows into a bookmark
    if stage >= 2:
        b.box((23, head_top + 2, 24, head_top + 3 + grow), "accent")
    # the book: a closed one beside it, then an open one at its feet
    if stage == 2:
        b.box((35, 22, 41, 30), "accent")
        b.box((36, 23, 40, 29), "page")
        b.dots([(37, 25), (38, 25), (39, 25), (37, 27), (38, 27)], "accent")
    if stage == 3:
        b.shape([(15, 45), (23, 43), (23, 47), (15, 47)], "page")
        b.shape([(32, 45), (24, 43), (24, 47), (32, 47)], "page")
        b.dots([(17, 45), (19, 45), (21, 45), (26, 45), (28, 45), (30, 45)], "accent")
        b.star(40, 12, 2, "accent")
        b.star(7, 10, 1, "accent")
    if mutated:
        b.star(24, head_top - 3, 2, "accent")
        b.dots([(9, 38), (38, 36), (41, 26)], "accent")
    return b.finish()


# ── Ark: a turtle that carries a ship on its back ─────────────────
def _ark(stage: int, mutated: bool) -> Image.Image:
    b = Brush(PALETTES["ark_mutated" if mutated else "ark"])
    grow = stage - 1
    floor = 42
    left, right = 12 - 3 * grow, 36 + 3 * grow
    top = 26 - 3 * grow
    # flippers behind
    b.oval((left + 2, floor - 4, left + 9, floor + 2), "dark")
    b.oval((right - 9, floor - 4, right - 2, floor + 2), "dark")
    # body
    b.oval((left, top + 4, right, floor), "body")
    b.oval((left + 4, floor - 7, right - 4, floor), "light")
    # head, looking left
    head = left - 5 + grow
    b.oval((head, top + 6, head + 11, top + 16), "body")
    b.box((head + 3, top + 9, head + 4, top + 11), "eye")
    b.dots([(head + 3, top + 9)], "page")
    b.dots([(head + 1, top + 13), (head + 2, top + 14), (head + 3, top + 14)], "dark")
    # tail
    b.shape(
        [(right - 1, floor - 8), (right + 4, floor - 11), (right + 1, floor - 4)],
        "body",
    )
    # hull: the shell is planked like a boat
    b.shape(
        [
            (left + 6, top + 6),
            (right - 3, top + 6),
            (right - 7, top - 1),
            (left + 9, top - 1),
        ],
        "accent",
    )
    for x in range(left + 9, right - 6, 4):
        b.dots([(x, top + 1), (x, top + 3), (x, top + 5)], "dark")
    b.box((left + 6, top + 6, right - 3, top + 7), "dark")
    # masts and sails
    masts = {1: [24], 2: [22], 3: [18, 30]}[stage]
    for index, mast in enumerate(masts):
        height = (6, 12, 15)[grow] - 3 * index
        b.box((mast, top - 1 - height, mast, top - 1), "dark")
        if stage == 1:
            b.shape(
                [(mast + 1, top - 7), (mast + 5, top - 5), (mast + 1, top - 3)], "page"
            )
        else:
            b.shape(
                [(mast + 1, top - height), (mast + 8, top - 4), (mast + 1, top - 3)],
                "page",
            )
            b.dots([(mast + 3, top - 5), (mast + 5, top - 5)], "accent")
    if stage == 3:
        # a lantern at the bow and spray under the keel
        b.box((left + 9, top - 5, left + 11, top - 2), "page")
        b.dots([(left + 10, top - 6)], "accent")
        b.dots([(6, 45), (10, 46), (38, 46), (42, 45), (24, 46)], "light")
    if mutated:
        b.star(right - 2, top - 14, 2, "page")
        b.dots([(left + 2, top - 4), (right + 3, top + 2), (25, top - 20)], "page")
    return b.finish()


# ── Nova: a bird hatched from a star ──────────────────────────────
def _nova(stage: int, mutated: bool) -> Image.Image:
    b = Brush(PALETTES["nova_mutated" if mutated else "nova"])
    grow = stage - 1
    floor = 43
    top = 20 - 4 * grow
    if stage == 3:
        # the ring behind it, drawn before the bird
        for x, y in [(x, y) for x in range(8, 24) for y in range(2, 30)]:
            distance = ((x - 24) ** 2 + (y - 15) ** 2) ** 0.5
            if 13.2 <= distance <= 14.2:
                b.dots([(x, y)], "light")
    # wing: a stub, then a spread wing, then a raised one
    if stage == 1:
        b.oval((11, 30, 18, 38), "dark")
    elif stage == 2:
        b.shape([(18, 26), (4, 22), (7, 29), (5, 33), (10, 34), (18, 36)], "dark")
        b.dots([(8, 26), (11, 29), (9, 31)], "body")
    else:
        b.shape(
            [(18, 24), (5, 6), (6, 15), (2, 16), (6, 22), (3, 26), (9, 29), (18, 34)],
            "dark",
        )
        b.dots([(7, 12), (8, 17), (7, 22), (10, 25), (11, 19)], "body")
    # tail flame
    if stage >= 2:
        b.shape(
            [(21, floor - 4), (16 - 2 * grow, floor + 1 + grow), (23, floor - 1)],
            "accent",
        )
    # body, belly
    b.oval((14 - grow, top + 6, 33 + grow, floor - 1), "body")
    b.oval((18 - grow, floor - 12 - grow, 29 + grow, floor - 2), "light")
    # foot
    b.box((19, floor - 1, 21, floor), "accent")
    # eye and cheek
    b.box((18 - grow, top + 12, 19 - grow, top + 14), "eye")
    b.dots([(19 - grow, top + 12)], "page")
    b.dots([(16 - grow, top + 16), (17 - grow, top + 16)], "accent")
    b.mirror()
    # beak, in the middle
    b.shape([(22, top + 15), (25, top + 15), (24, top + 18), (23, top + 18)], "accent")
    # the star on its brow grows with each stage
    b.star(24, top + 3 - grow, 2 + grow, "page" if stage == 3 else "light")
    b.dots([(23, top + 3 - grow), (24, top + 3 - grow)], "body")
    if stage == 3:
        b.star(8, 36, 1, "light")
        b.star(40, 38, 1, "light")
    if mutated:
        b.star(41, 9, 2, "accent")
        b.star(6, 40, 1, "accent")
        b.dots([(24, top + 3 - grow)], "accent")
    return b.finish()


PAINTERS = {"fable": _fable, "ark": _ark, "nova": _nova}


@lru_cache(maxsize=None)
def sprite(species: str, stage: int, mutated: bool = False) -> Image.Image:
    """The 48 x 48 sprite; a mutated companion is drawn in its third stage."""
    return PAINTERS[species](3 if mutated else stage, mutated)


def enlarged(
    species: str, stage: int, mutated: bool = False, scale: int = 6
) -> Image.Image:
    small = sprite(species, stage, mutated)
    return small.resize((GRID * scale, GRID * scale), Image.Resampling.NEAREST)
