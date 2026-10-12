"""BOT. logo, redrawn as clean vector art (same shapes and colours as the old logo).

Coordinates are in the old logo's own 840-unit frame (traced from public/bot-logo.png)
so the shapes can be compared directly with the original.
"""
import os
import sys

# ── the mark ──────────────────────────────────────────────────────
GRADIENTS = """
  <linearGradient id="gSun" x1="138" y1="0" x2="532" y2="0" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#F9AB2C"/><stop offset="1" stop-color="#FA8640"/>
  </linearGradient>
  <linearGradient id="gLeft" x1="0" y1="160" x2="0" y2="690" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#FB8B3D"/><stop offset="0.55" stop-color="#FB5A4A"/><stop offset="1" stop-color="#F7335C"/>
  </linearGradient>
  <linearGradient id="gBlue" x1="0" y1="38" x2="0" y2="485" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#5D89F0"/><stop offset="1" stop-color="#3D78EE"/>
  </linearGradient>
  <linearGradient id="gCrimson" x1="330" y1="640" x2="560" y2="770" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#F4346F"/><stop offset="1" stop-color="#EA2468"/>
  </linearGradient>
  <linearGradient id="gTeal" x1="450" y1="520" x2="700" y2="700" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#2FD3CD"/><stop offset="1" stop-color="#27C3C6"/>
  </linearGradient>
  <linearGradient id="gMagenta" x1="352" y1="350" x2="522" y2="545" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#E55BD8"/><stop offset="1" stop-color="#C348D8"/>
  </linearGradient>
  <linearGradient id="gSheen" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity="0.22"/><stop offset="0.45" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
"""

SHAPES = """
  <rect x="138" y="38" width="394" height="114" rx="16" fill="url(#gSun)"/>
  <path d="M138 176 Q138 160 150 166 L258 231 Q268 238 268 250 L268 478
           C268 532 306 572 344 597 Q354 604 345 611 L252 676
           C192 692 138 642 138 574 Z" fill="url(#gLeft)"/>
  <path d="M619 38 H726 Q742 38 742 54 V483 Q742 490 735 486 L611 402 Q603 397 603 388 V54 Q603 38 619 38 Z" fill="url(#gBlue)"/>
  <path d="M443 625 L565 716 C540 758 482 786 420 781 C370 776 330 746 312 718 C340 682 392 650 443 625 Z" fill="url(#gCrimson)"/>
  <path d="M441 628 C510 612 574 574 611 497 Q614 490 621 494 L729 560 Q741 568 734 580 L565 716 Z" fill="url(#gTeal)"/>
  <circle cx="437" cy="447" r="100" fill="url(#gMagenta)"/>
"""

# a soft light edge on the top of each piece, for a flat-glass look
SHEEN = """
  <rect x="138" y="38" width="394" height="52" rx="16" fill="url(#gSheen)"/>
  <path d="M619 38 H726 Q742 38 742 54 V120 H603 V54 Q603 38 619 38 Z" fill="url(#gSheen)"/>
"""

MARK_BOX = (138, 38, 742, 786)  # x0, y0, x1, y1 of the artwork


def mark_group(extra=""):
    return "<g>%s%s%s</g>" % (SHAPES, SHEEN, extra)


def mark_svg(size=1024, pad=70, background=None):
    x0, y0, x1, y1 = MARK_BOX
    w, h = x1 - x0, y1 - y0
    side = max(w, h) + 2 * pad
    ox = x0 - (side - w) / 2
    oy = y0 - (side - h) / 2
    bg = '<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % (ox, oy, side, side, background) if background else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" width="%d" height="%d">'
        "<defs>%s</defs>%s%s</svg>" % (ox, oy, side, side, size, size, GRADIENTS, bg, mark_group())
    )


# ── the wordmark: B O T and a round full stop, drawn from strokes ─
STROKE = 62
CAP = 330  # cap height of the letters


def wordmark_paths(ink, x0, y0):
    """The letters B, O, T (strokes) and the dot (the logo's magenta circle)."""
    t, h = STROKE, CAP
    parts, x = [], x0
    gap = 44
    # B
    stem = x + t / 2
    w_top, w_bot = 146, 168
    top_y, mid_y, bot_y = y0 + t / 2, y0 + h / 2, y0 + h - t / 2
    r_top, r_bot = (mid_y - top_y) / 2, (bot_y - mid_y) / 2
    path = (
        "M%g %g V%g M%g %g H%g A%g %g 0 0 1 %g %g H%g M%g %g H%g A%g %g 0 0 1 %g %g H%g"
        % (
            stem, y0, y0 + h,
            stem, top_y, stem + w_top - r_top, r_top, r_top, stem + w_top - r_top, mid_y, stem,
            stem, mid_y, stem + w_bot - r_bot, r_bot, r_bot, stem + w_bot - r_bot, bot_y, stem,
        )
    )
    parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%d" stroke-linejoin="round"/>' % (path, ink, t))
    x += t / 2 + max(w_top, w_bot) + t / 2 + gap
    # O
    r = (h - t) / 2
    parts.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="%s" stroke-width="%d"/>' % (x + r + t / 2, y0 + h / 2, r, ink, t))
    x += h + gap
    # T
    width = 236
    path = "M%g %g H%g M%g %g V%g" % (x, y0 + t / 2, x + width, x + width / 2, y0, y0 + h)
    parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%d" stroke-linejoin="round"/>' % (path, ink, t))
    x += width + gap
    # the full stop is the logo's own circle
    rr = t * 0.62
    parts.append('<circle cx="%g" cy="%g" r="%g" fill="url(#gMagenta2)"/>' % (x + rr, y0 + h - rr, rr))
    x += 2 * rr
    return "".join(parts), x


def wordmark_svg(ink, background=None, pad=90):
    x0, y0, x1, y1 = MARK_BOX
    mark_h = y1 - y0
    text_y = 447 - CAP / 2  # the wordmark is centred on the logo's round centre
    text_x = x1 + 104
    letters, end = wordmark_paths(ink, text_x, text_y)
    # the dot reuses the circle's gradient, scaled to its own box
    dot_grad = (
        '<linearGradient id="gMagenta2" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#E55BD8"/><stop offset="1" stop-color="#C348D8"/></linearGradient>'
    )
    vx0, vy0 = x0 - pad, y0 - pad
    vw, vh = end - x0 + 2 * pad, mark_h + 2 * pad
    bg = '<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % (vx0, vy0, vw, vh, background) if background else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" width="%d" height="%d">'
        "<defs>%s%s</defs>%s%s%s</svg>" % (vx0, vy0, vw, vh, vw * 1.25, vh * 1.25, GRADIENTS, dot_grad, bg, mark_group(), letters)
    )


# ── the avatar: the mark on a dark rounded square ─────────────────
def avatar_svg(size=1024, rounded=True, fill=0.60):
    """The mark on a warm dark tile. ``fill`` is the mark's height as a share of the tile.

    Discord shows avatars as circles, so the mark sits well inside the inscribed circle.
    """
    x0, y0, x1, y1 = MARK_BOX
    scale = fill * size / (y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    radius = size * 0.2237 if rounded else 0
    tile = (
        "<defs>%s"
        '<linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#2A221E"/><stop offset="1" stop-color="#14100E"/></linearGradient>'
        '<radialGradient id="glowSun" cx="0.15" cy="0.1" r="0.7">'
        '<stop offset="0" stop-color="#F9AB2C" stop-opacity="0.20"/><stop offset="1" stop-color="#F9AB2C" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="glowBlue" cx="0.9" cy="0.95" r="0.7">'
        '<stop offset="0" stop-color="#3D78EE" stop-opacity="0.20"/><stop offset="1" stop-color="#3D78EE" stop-opacity="0"/></radialGradient>'
        '<clipPath id="clip"><rect width="%d" height="%d" rx="%g"/></clipPath>'
        "</defs>" % (GRADIENTS, size, size, radius)
    )
    body = (
        '<g clip-path="url(#clip)">'
        '<rect width="%d" height="%d" fill="url(#tile)"/>'
        '<rect width="%d" height="%d" fill="url(#glowSun)"/>'
        '<rect width="%d" height="%d" fill="url(#glowBlue)"/>'
        '<g transform="translate(%g %g) scale(%g)">%s</g>'
        "</g>"
        '<rect x="2" y="2" width="%d" height="%d" rx="%g" fill="none" stroke="#fff" stroke-opacity="0.07" stroke-width="4"/>'
        % (size, size, size, size, size, size, size / 2 - cx * scale, size / 2 - cy * scale, scale, mark_group(), size - 4, size - 4, max(radius - 2, 0))
    )
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">%s%s</svg>' % (size, size, size, size, tile, body)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    open(out + "/mark.svg", "w", encoding="utf-8").write(mark_svg())
    open(out + "/wordmark-dark-text.svg", "w", encoding="utf-8").write(wordmark_svg("#1B1714"))
    open(out + "/wordmark-light-text.svg", "w", encoding="utf-8").write(wordmark_svg("#F6F1EC"))
    open(out + "/avatar.svg", "w", encoding="utf-8").write(avatar_svg())
    open(out + "/avatar-square.svg", "w", encoding="utf-8").write(avatar_svg(rounded=False))
    print("ok")
