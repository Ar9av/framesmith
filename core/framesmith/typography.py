"""Type: bundled fonts, tracking, text-scramble and typewriter reveals, rotated text."""
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .easing import h

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
ROLES = {
    "sans": "InterDisplay-Regular.otf",
    "sans_medium": "InterDisplay-Medium.otf",
    "mono": "GeistMono-Regular.otf",
    "mono_medium": "GeistMono-Medium.otf",
    "mono_bold": "GeistMono-SemiBold.otf",
    "serif": "Fraunces-Regular.ttf",              # Latin subset: letters, digits, basic punctuation
    "serif_italic": "Fraunces-Italic.ttf",
    "serif_italic_bold": "Fraunces-SemiBoldItalic.ttf",
}
GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&@$*+=<>/\\|"


@lru_cache(None)
def F(role, size):
    """Font by role name (sans, sans_medium, mono, mono_bold) or file path."""
    path = os.path.join(FONT_DIR, ROLES[role]) if role in ROLES else role
    return ImageFont.truetype(path, int(size))


def text_width(s, font, track=0):
    return sum(font.getlength(c) + track for c in s) - (track if s else 0)


OVERFLOWS = []          # (text, needed_px, max_px) for text that could not be fitted; check with overflow_report()
SHRINKS = []            # (text, scale) for text shrunk below WARN_SCALE to fit its budget
WARN_SCALE = 0.8
MIN_SCALE = 0.55        # never shrink below 55% of the requested size


def fit(s, font, max_w, track=0):
    """Largest version of `font` (down to MIN_SCALE) whose rendering of `s` fits max_w px."""
    w = text_width(s, font, track)
    if max_w is None or w <= max_w:
        return font
    size = max(int(font.size * MIN_SCALE), int(font.size * max_w / max(w, 1)))
    f = ImageFont.truetype(font.path, size)
    while size > font.size * MIN_SCALE and text_width(s, f, track * size / font.size) > max_w:
        size -= 1
        f = ImageFont.truetype(font.path, size)
    return f


def text(d, xy, s, font, fill, track=0, anchor="la", max_w=None, fit_to=None):
    """Draw text with tracking (letter-spacing, px). Anchors as in PIL, e.g. 'mm', 'rm'.

    max_w: hard width budget. The font shrinks to fit (down to MIN_SCALE); anything still too wide
    is recorded in OVERFLOWS so templates can fail `check` instead of shipping clipped text.
    fit_to: size against this string instead (pass the final copy when `s` is mid-scramble/typing,
    so the size doesn't flicker frame to frame).
    """
    if max_w is not None:
        ref = fit_to if fit_to is not None else s
        f2 = fit(ref, font, max_w, track)
        if f2 is not font:
            if f2.size < font.size * WARN_SCALE:
                SHRINKS.append((ref, f2.size / font.size))
            track = track * f2.size / font.size
            font = f2
        if text_width(ref, font, track) > max_w + 1:
            OVERFLOWS.append((ref, int(text_width(ref, font, track)), int(max_w)))
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


def overflow_report(warn=False):
    """Overflow errors, or with warn=True the strings shrunk below WARN_SCALE (copy too long for its slot)."""
    seen, out = set(), []
    if warn:
        for s, k in SHRINKS:
            if s.strip() and s not in seen:
                seen.add(s)
                out.append(f"'{s}' shrunk to {k:.0%} of its designed size; shorten it")
        return out
    for s, need, mx in OVERFLOWS:
        if s.strip() and s not in seen:
            seen.add(s)
            out.append(f"'{s}' needs {need}px, budget {mx}px")
    return out


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
