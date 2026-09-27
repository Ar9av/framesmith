"""Type: bundled fonts, tracking, text-scramble and typewriter reveals, rotated text."""
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .easing import h

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
ROLES = {
    "sans": "InterDisplay-Regular.otf",
    "sans_medium": "InterDisplay-Medium.otf",
    "mono": "Go-Mono.ttf",
    "mono_bold": "Go-Mono-Bold.ttf",
}
GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&@$*+=<>/\\|"


@lru_cache(None)
def F(role, size):
    """Font by role name (sans, sans_medium, mono, mono_bold) or file path."""
    path = os.path.join(FONT_DIR, ROLES[role]) if role in ROLES else role
    return ImageFont.truetype(path, int(size))


def text_width(s, font, track=0):
    return sum(font.getlength(c) + track for c in s) - (track if s else 0)


def text(d, xy, s, font, fill, track=0, anchor="la"):
    """Draw text with tracking (letter-spacing, px). Anchors as in PIL, e.g. 'mm', 'rm'."""
    if not track:
        d.text(xy, s, font=font, fill=fill, anchor=anchor)
        return
    x, y = xy
    w = text_width(s, font, track)
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    for c in s:
        d.text((x, y), c, font=font, fill=fill, anchor="l" + anchor[1])
        x += font.getlength(c) + track


def scramble(s, p, seed, fi, tail=5):
    """Left-to-right decode reveal with a tail of random glyphs. p in [0,1], fi = frame index."""
    if p >= 1:
        return s
    rev = int(p * (len(s) + tail)) - tail
    out = []
    for i, c in enumerate(s):
        if c == " " or i < rev:
            out.append(c)
        elif i < rev + tail and p > 0:
            out.append(GLYPHS[int(h(seed, i, fi // 2) * len(GLYPHS))])
        else:
            out.append(" ")
    return "".join(out)


def typed(s, p):
    """Typewriter reveal."""
    return s[: int(round(len(s) * max(0.0, min(1.0, p))))]


def decay(s, p, keep, seed=3):
    """Characters drop out at random as p→1, except indices in `keep` and brackets."""
    return "".join(c if (i in keep or c in "[]" or h(seed, i) > p) else " " for i, c in enumerate(s))


def rot_text(img, xy, s, font, fill, angle=-90, track=0):
    """Paste rotated text at xy. angle=-90 reads top-to-bottom."""
    w = int(text_width(s, font, track)) + 4
    t = Image.new("L", (max(1, w), int(font.size * 1.3)), 0)
    text(ImageDraw.Draw(t), (0, 0), s, font, 255, track)
    t = t.rotate(angle, expand=True)
    img.paste(Image.new("RGB", t.size, fill), (int(xy[0]), int(xy[1])), t)
