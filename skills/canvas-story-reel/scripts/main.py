#!/usr/bin/env python3
"""canvas-story-reel: a 20-second, music-only story reel in the design-canvas style.

Kinetic type that lands word by word (the newest word flashes the accent), every element wearing
design-editor overlays: red selection handles, a hopping yellow anchor cluster, pink diamonds and
code tags in red brackets. Between the type beats: a ring with an arrow, a blue dot-matrix wave, a
photo plate zooming from a card to full bleed, a blue-tinted plate behind a text frame that punches
into its last word, a pixel grid, scattered words converging, a scrolling photo column, tilted photo
flips, a huge stacked headline over full-bleed plates, a glow-lit closing line, and the logo.

    python3 main.py assets|check|still|sheet|render --brief brief.json [times...] [--audio music.m4a]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from framesmith import Assets, Scene, Timeline, bezier, cover, ease_in_out, ease_out, generate_images, h, hex2rgb, lerp, overflow_report, text, typed
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width

G = None
pop = bezier(0.34, 1.56, 0.64, 1)       # small overshoot for the logo


class State:
    def __init__(self, brief, base):
        self.b = brief
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.accent = c("accent", (90, 107, 255))      # flashing word, dot wave, grid
        self.handle = c("handle", (226, 38, 77))       # selection handles, code brackets
        self.anchor = c("anchor", (244, 228, 9))       # hopping dot cluster
        self.lav = c("lavender", (163, 173, 255))      # particles, photo handles
        self.pink = c("pink", (240, 138, 168))         # diamonds
        self.warm = c("warm", (255, 155, 61))          # path line, grid accents
        self.tint = c("tint", (42, 79, 168))           # blue plate tint
        self.green = c("green", (15, 122, 58))         # second colour in scatter words
        self.W, self.H = brief.get("size", [1920, 1080])
        self.assets = Assets(os.path.join(base, brief.get("assets_dir", "assets")), os.path.join(HERE, "..", "placeholders"))
        self._c = {}

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


def photo(name):
    return G.cache(("img", name), lambda: Image.open(G.assets.path(name)).convert("RGB"))


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def ground(kind):
    if kind == "white":
        return Image.new("RGB", (G.W, G.H), (255, 255, 255))
    if kind == "glow":
        return glow_layer().copy()
    return Image.new("RGB", (G.W, G.H), (0, 0, 0))


def glow_layer():
    """Blue horizon glow rising from the bottom edge (one blob, made once)."""
    def build():
        w, hh = G.W // 8, G.H // 8
        g = Image.new("RGB", (w, hh), (0, 0, 0))
        ImageDraw.Draw(g).ellipse((w * 0.22, hh * 0.9, w * 0.78, hh * 1.35), fill=(22, 50, 190))
        return g.filter(ImageFilter.GaussianBlur(w * 0.07)).resize((G.W, G.H), Image.BICUBIC)
    return G.cache("glow", build)


def tinted(name, mode):
    """A plate recoloured: 'blue' maps its luminance onto the tint (like CSS mix-blend 'color'), 'bw' greys it."""
    def build():
        im = photo(name)
        g = ImageOps.grayscale(im)
        if mode == "bw":
            return g.convert("RGB")
        g = ImageOps.autocontrast(g, cutoff=1)
        return ImageOps.colorize(g, (6, 12, 34), tuple(min(255, v + 150) for v in G.tint), mid=G.tint)
    return G.cache(("tint", name, mode), build)


# ------------------------------------------------------------------ editor overlays
def handles(d, box, fi, seed, col=None, cluster=True, frame=False, pad=12):
    """Selection box: 8 square handles, optional hairline frame, and a 3x3 anchor cluster that hops every 4 frames."""
    col = col or G.handle
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    if frame:
        d.rectangle((x0, y0, x1, y1), outline=(160, 170, 255), width=1)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    for x in (x0, mx, x1):
        for y in (y0, my, y1):
            if (x, y) != (mx, my):
                d.rectangle((x - 4, y - 4, x + 3, y + 3), fill=col)
    if cluster:
        k = fi // 4
        cx = lerp(x0, x1, 0.15 + h(seed, "x", k) * 0.7)
        cy = lerp(y0, y1, 0.3 + h(seed, "y", k) * 0.5)
        for i in range(9):
            if h(seed, i) > 0.15:
                gx, gy = cx + (i % 3) * 9, cy + (i // 3) * 9
                d.rectangle((gx, gy, gx + 5, gy + 5), fill=G.anchor)


def diamond(d, xy, col=None, r=8):
    x, y = xy
    d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], outline=col or G.pink, width=2)


def tags(d, c, items):
    """Literal code fragments typing in, wrapped in red bracket bars with a diamond above."""
    f = F("mono", 18)
    for t in items:
        if c.lt < t["at"]:
            continue
        s = t["t"]
        x, y = t["x"] * c.W, t["y"] * c.H
        w = text_width(s, f)
        d.rectangle((x, y - 12, x + 7, y + 12), fill=G.handle)
        text(d, (x + 14, y), s[: int((c.lt - t["at"]) * 75)], f, (154, 154, 166), 0, "lm")
        d.rectangle((x + 20 + w, y - 12, x + 27 + w, y + 12), fill=G.handle)
        diamond(d, (x + 14 + w * 0.55, y - 32))


def particles(d, c, n, col=None, seed=7):
    tab = G.cache(("rng", n, seed), lambda: np.random.default_rng(seed).random((n, 3)))
    for x, y, v in tab:
        py = (y * (c.H + 100) - c.lt * 30 * (0.6 + v)) % (c.H + 100) - 50
        d.rectangle((x * c.W, py, x * c.W + 5, py + 5), fill=col or G.lav)


def draw_words(d, xy, words, lt, every, f, col, flash=None, anchor="mm", max_w=None):
    """Word-by-word reveal; the newest word shows in the flash colour for its first 0.25 s.
    Sized and laid out against the full line, so nothing shifts as words land. Returns the line's box."""
    if lt < 0:
        return None
    full = " ".join(words)
    text(d, (-9999, -9999), "", f, col, 0, "lm", max_w=max_w or G.W - 200, fit_to=full)   # records overflow / shrink
    tw = text_width(full, f)
    if max_w and tw > max_w:
        f = F(f.path, max(int(f.size * 0.55), int(f.size * max_w / tw)))
        tw = text_width(full, f)
    x, y = xy
    x0 = x - tw / 2 if anchor[0] == "m" else x
    n = min(len(words), int(lt / every) + 1)
    age = lt - (n - 1) * every
    sp = f.getlength(" ")
    cx = x0
    for i, wd in enumerate(words[:n]):
        fl = i == n - 1 and age < 0.25
        d.text((cx, y), wd, font=f, fill=(flash or G.accent) if fl else col, anchor="l" + anchor[1])
        cx += f.getlength(wd) + sp
    return (x0, y - f.size * 0.45, x0 + tw, y + f.size * 0.4)


def arrow(d, xy, size, rot=0, col=None, width=4):
    """Right arrow rotated by rot degrees (−90 points up)."""
    col = col or G.lav
    a = math.radians(rot)
    R = lambda px, py: (xy[0] + px * math.cos(a) - py * math.sin(a), xy[1] + px * math.sin(a) + py * math.cos(a))
    s = size / 2
    d.line([R(-s, 0), R(s, 0)], fill=col, width=width)
    d.line([R(s * 0.35, -s * 0.55), R(s, 0), R(s * 0.35, s * 0.55)], fill=col, width=width, joint="curve")


# ------------------------------------------------------------------ shots
def shot_words(c, s):
    """Centred line(s) landing word by word with handles; each line replaces the last at its `at` time.

    keys: bg (black|white|glow), lines [str | {text, at, chars}], every, size, lead_arrow, tags [{t, x, y, at}], particles
    """
    bg = s.get("bg", "black")
    im = ground(bg)
    d = ImageDraw.Draw(im)
    if s.get("particles"):
        particles(d, c, s["particles"], G.accent, 11)
    tags(d, c, s.get("tags", []))
    lines = [ln if isinstance(ln, dict) else {"text": ln, "at": 0} for ln in s["lines"]]
    cur = [ln for ln in lines if c.lt >= ln.get("at", 0)]
    if not cur:
        return arr(im)
    ln = cur[-1]
    lt = c.lt - ln.get("at", 0)
    f = F("sans", s.get("size", 64))
    col = (17, 17, 17) if bg == "white" else (255, 255, 255)
    y = c.H * s.get("y", 0.47)
    tw = text_width(ln["text"], f)
    if s.get("lead_arrow"):
        arrow(d, (lerp(-200, c.W / 2 - tw / 2 - 60, ease_out(min(1, c.lt / 0.35))), y), 46)
        lt -= 0.25
    if ln.get("chars"):                                   # letter by letter, for one-word beats
        shown = typed(ln["text"], lt / max(0.2, len(ln["text"]) * 0.08))
        text(d, (c.W / 2 - tw / 2, y), shown, f, col, 0, "lm", max_w=c.W - 200, fit_to=ln["text"])
        box = (c.W / 2 - tw / 2, y - f.size * 0.45, c.W / 2 + tw / 2, y + f.size * 0.4)
    else:
        box = draw_words(d, (c.W / 2, y), ln["text"].split(), lt, s.get("every", 0.3), f, col,
                         None if bg == "white" else G.lav, max_w=c.W - 200)
    if box:
        handles(d, box, c.fi, ln["text"])
        if bg == "glow":
            diamond(d, (box[0] - 50, y), (120, 120, 120))
    return arr(im)


def shot_ring(c, s):
    """A faint ring scaling up around an up arrow, a row of accent dots streaming in from the right."""
    im = ground("black")
    d = ImageDraw.Draw(im)
    k = lerp(0.6, 1.15, ease_out(c.p(0, c.dur)))
    r, cx, cy = 150 * k, c.W / 2, c.H * 0.45
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(48, 58, 140), width=2)
    arrow(d, (cx, cy), 120 * k, -90, width=6)
    for i in range(int(min(12, c.lt * 60))):
        x = c.W - 12 - i * 22
        d.ellipse((x - 7, c.H * 0.6 - 7, x + 7, c.H * 0.6 + 7), fill=G.accent)
    return arr(im)


def shot_wave(c, s):
    """A dot-matrix wave in accent blues rolling under a glowing up arrow."""
    im = ground("black")
    d = ImageDraw.Draw(im)
    step = 30
    rows = c.H // step + 1
    for x in range(c.W // step + 1):
        crest = rows * 0.35 + math.sin(x * 0.18 + c.lt * 7.5) * 5
        for y in range(int(max(0, crest)), rows):
            r = min(13, 4 + (y - crest) * 0.9)
            l = 0.8 + 0.4 * math.sin(x * 0.4 + y * 0.3 + c.lt * 9)
            col = tuple(min(255, int(v * l)) for v in (30, 70, 255))
            px, py = x * step + step / 2, y * step + step / 2
            d.ellipse((px - r, py - r, px + r, py + r), fill=col)
    g = Image.new("L", im.size, 0)
    arrow(ImageDraw.Draw(g), (c.W / 2, c.H * 0.4), 180, -90, 255, 12)
    im.paste((255, 255, 255), (0, 0), g.filter(ImageFilter.GaussianBlur(14)))
    arrow(d, (c.W / 2, c.H * 0.4), 180, -90, (230, 236, 255), 8)
    return arr(im)


def shot_plate(c, s):
    """A photo plate zooming from a framed card on an accent field to past full bleed; its blue tint drains out."""
    im = Image.new("RGB", (c.W, c.H), tuple(s.get("field", (29, 79, 216))))
    k = lerp(s.get("from", 0.62), s.get("to", 1.25), ease_in_out(c.p(0, c.dur)))
    w, hh = int(c.W * k), int(c.H * k)
    src = cover(photo(s["media"]), w, hh)
    tint = max(0.0, 1 - c.lt / 0.45)
    if tint > 0:
        src = Image.blend(src, cover(tinted(s["media"], "blue"), w, hh), tint)
    x, y = (c.W - w) // 2, (c.H - hh) // 2
    im.paste(src, (x, y))
    d = ImageDraw.Draw(im)
    handles(d, (x, y, x + w, y + hh), c.fi, s["media"], G.accent, frame=True, pad=0)
    diamond(d, (c.W / 2, c.H / 2))
    return arr(im)


def shot_frame(c, s):
    """Blue-tinted plate; a white text frame slides in typing a line, then punches into its last word with rings.
    The shot can close into a rounded card on white.

    keys: media, text, every, size, punch_at, close (seconds before the end; omit for none)
    """
    words = s["text"].split()
    t_p = s.get("punch_at", 1.4)
    punch = ease_out(c.p(t_p, t_p + 0.5))
    bg = cover(tinted(s["media"], "blue"), c.W, c.H, 1.05 + punch * 0.25)
    if punch > 0.05:
        bg = bg.filter(ImageFilter.GaussianBlur(punch * 3))
    im = bg.copy()
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle((0, 0, c.W, c.H), fill=(10, 20, 50, 60))
    if punch < 0.95:                                     # a motion path, drawn as if selected
        d.line([(0, c.H * 0.9), (c.W * 0.22, c.H * 0.83), (c.W * 0.36, c.H * 0.81), (c.W * 0.43, c.H * 0.87)],
               fill=G.warm + (int(255 * (1 - punch)),), width=5)
    cx, cy = c.W / 2, c.H / 2
    for k in (0, 1):
        rp = ease_out(c.p(t_p + k * 0.1, t_p + 0.6))
        if rp > 0:
            sc = 0.7 + rp * 0.3
            rw, rh = (380 + k * 190) * sc, (115 + k * 140) * sc
            d.rounded_rectangle((cx - rw, cy - rh, cx + rw, cy + rh), int(rh), outline=(255, 255, 255, int(115 * rp)), width=2,
                                fill=(255, 255, 255, int(30 * rp)) if k == 0 else None)
    f = F("sans", int(s.get("size", 60) * (1 + punch * 0.5)))
    punched = c.lt >= t_p
    line = words[-1] if punched else s["text"]
    slide = (1 - ease_out(c.p(0, 1.3))) * 260
    tw = min(text_width(line, f), c.W - 300)
    px, py = 40 * f.size / 60, 16 * f.size / 60
    bx0, bx1 = cx + slide - tw / 2 - px, cx + slide + tw / 2 + px
    by0, by1 = cy - f.size * 0.62 - py, cy + f.size * 0.5 + py
    d.rounded_rectangle((bx0 - 6, by0 - 6, bx1 + 6, by1 + 6), int((by1 - by0) / 2 + 6), fill=(130, 145, 255, 150))
    d.rounded_rectangle((bx0, by0, bx1, by1), int((by1 - by0) / 2), fill=(255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    if punched:
        text(d, (cx + slide, cy), line, f, (17, 17, 17), 0, "mm", max_w=c.W - 300)
    else:
        draw_words(d, (bx0 + px, cy), words, c.lt, s.get("every", 0.27), f, (17, 17, 17), anchor="lm", max_w=c.W - 300)
    handles(d, (bx0, by0, bx1, by1), c.fi, "frame", pad=-4)
    if s.get("close"):
        q = ease_in_out(c.p(-s["close"], c.dur))
        if q > 0:
            out = Image.new("RGB", im.size, (255, 255, 255))
            m = Image.new("L", im.size, 0)
            ix, iy = c.W * 0.26 * q, c.H * 0.34 * q
            ImageDraw.Draw(m).rounded_rectangle((ix, iy, c.W - ix, c.H - iy), int(lerp(1, 220, q)), fill=255)
            out.paste(im, (0, 0), m)
            return arr(out)
    return arr(im)


def shot_grid(c, s):
    """A pixel-grid icon filling in cell by cell on white, warm squares on a 4-cell lattice, a dark core."""
    im = ground("white")
    d = ImageDraw.Draw(im)
    n, cell, gap = 13, 22, 4
    size = n * (cell + gap) - gap
    x0, y0 = (c.W - size) / 2, (c.H - size) / 2
    for i in range(min(n * n, int(c.lt * 400))):
        x, y = i % n, i // n
        if 5 <= x <= 7 and 4 <= y <= 8:
            continue
        col = G.warm if x % 4 == 2 and y % 4 == 2 else G.accent
        qx, qy = x0 + x * (cell + gap), y0 + y * (cell + gap)
        d.rectangle((qx, qy, qx + cell, qy + cell), fill=tuple(int(lerp(255, v, 0.85)) for v in col))
    d.rectangle((c.W / 2 - 13, c.H / 2 - 13, c.W / 2 + 13, c.H / 2 + 13), fill=(34, 34, 34))
    handles(d, (x0, y0, x0 + size, y0 + size), c.fi, "grid", G.lav, cluster=False)
    return arr(im)


def shot_scatter(c, s):
    """Uppercase words scattered across white, converging into a tight stack.

    keys: words [{t, from [x, y], to [x, y], green}] (px offsets from centre), converge [a, b] seconds, size
    """
    im = ground("white")
    d = ImageDraw.Draw(im)
    a, b = s.get("converge", [0.2, 0.55])
    p = ease_in_out(c.p(a, b))
    f = F("sans_medium", s.get("size", 64))
    for w in s["words"]:
        x = c.W / 2 + lerp(w["from"][0], w["to"][0], p)
        y = c.H / 2 + lerp(w["from"][1], w["to"][1], p)
        tw = text_width(w["t"], f, -1)
        text(d, (x, y), w["t"], f, G.green if w.get("green") else (17, 17, 17), -1, "mm", max_w=c.W - 200)
        handles(d, (x - tw / 2, y - f.size * 0.4, x + tw / 2, y + f.size * 0.4), c.fi, w["t"], cluster=False, pad=8)
    return arr(im)


def shot_column(c, s):
    """Words left and right of a column of photos scrolling upward on white.

    keys: left, right (revealed word by word), right_at, media [names], every, size
    """
    im = ground("white")
    d = ImageDraw.Draw(im)
    cw, gap = 380, 18
    y = lerp(c.H * 0.65, -c.H * 0.83, ease_in_out(c.p(0, c.dur)))
    x = c.W / 2 - cw / 2
    for k, m in enumerate(s["media"]):
        src = photo(m)
        ph = int(cw * src.height / src.width)
        if -ph < y < c.H:
            im.paste(G.cache(("thumb", m, cw), lambda: src.resize((cw, ph), Image.LANCZOS)), (int(x), int(y)))
            handles(d, (x, y, x + cw, y + ph), c.fi, ("col", k), G.lav, cluster=k % 2 == 0, pad=0)
        y += ph + gap
    f = F("sans", s.get("size", 56))
    for key, x0, t0 in (("left", c.W * 0.06, 0), ("right", c.W * 0.68, s.get("right_at", 0.33))):
        bx = draw_words(d, (x0, c.H / 2), s[key].split(), c.lt - t0, s.get("every", 0.27), f, (17, 17, 17), anchor="lm", max_w=c.W * 0.28)
        if bx:
            handles(d, bx, c.fi, key, cluster=False)
    return arr(im)


def shot_flip(c, s):
    """Photos flipping one after another on white, each tilted a few degrees over a soft shadow.

    keys: media [names], tilts [deg]
    """
    im = ground("white")
    n = len(s["media"])
    k = min(n - 1, int(c.lt / (c.dur / n)))
    w = 980

    def card():
        src = photo(s["media"][k])
        cd = src.resize((w, int(w * src.height / src.width)), Image.LANCZOS).convert("RGBA")
        return cd.rotate(s.get("tilts", [-2, -6, 5])[k % 3], Image.BICUBIC, expand=True)
    cd = G.cache(("flip", s["media"][k], k), card)
    ph = int(w * photo(s["media"][k]).height / photo(s["media"][k]).width)
    x, y = (c.W - cd.width) // 2, (c.H - cd.height) // 2
    sh = Image.new("L", im.size, 0)
    sh.paste(cd.getchannel("A").point(lambda v: v * 0.25), (x, y + 18))
    im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(18)))
    im.paste(cd, (x, y), cd)
    bx, by = (c.W - w) / 2, (c.H - ph) / 2
    handles(ImageDraw.Draw(im), (bx, by, bx + w, by + ph), c.fi, ("flip", k), G.lav, frame=True, pad=0)
    return arr(im)


def shot_stack(c, s):
    """A huge stacked headline over full-bleed plates; each beat swaps the plate and lights the next word.

    keys: words, plates [{media, look: color|bw}], size
    """
    words, plates = s["words"], s["plates"]
    per = c.dur / len(words)
    k = min(len(words) - 1, int(c.lt / per))
    pl = plates[k % len(plates)]
    src = tinted(pl["media"], "bw") if pl.get("look") == "bw" else photo(pl["media"])
    im = Image.eval(cover(src, c.W, c.H, 1.08 + (c.lt % per) * 0.03), lambda v: int(v * 0.72))
    d = ImageDraw.Draw(im, "RGBA")
    particles(d, c, 60)
    f = F("sans_medium", s.get("size", 150))
    lh = f.size * 0.98
    cx = c.W / 2 - (c.W * 0.2 if k % 2 else 0)
    top = c.H / 2 - lh * (len(words) - 1) / 2
    wmax = max(text_width(w, f, -6) for w in words)
    m = Image.new("L", im.size, 0)                       # PIL text ignores fill alpha, so fade through a mask
    for i, w in enumerate(words):
        text(ImageDraw.Draw(m), (cx, top + i * lh), w, f, 255 if i == k else 107, -6, "mm", max_w=c.W - 200)
    im.paste((255, 255, 255), (0, 0), m)
    d = ImageDraw.Draw(im)
    handles(d, (cx - wmax / 2, top - lh / 2, cx + wmax / 2, top + lh * (len(words) - 0.5)), c.fi, "stack")
    diamond(d, (cx, top + lh * 0.5))
    diamond(d, (cx, top + lh * 2.5))
    return arr(im)


def shot_logo(c, s):
    """The real logo pops in under handles, then the name slides out beside it."""
    im = ground("black")
    p = pop(c.p(0, 0.5))
    wp = ease_out(c.p(1.0, 1.4))
    ls = 150
    f = F("sans_medium", s.get("size", 112))
    nw = text_width(s["name"], f, -4)
    x0 = c.W / 2 - (ls + (34 + nw) * wp) / 2
    sz = max(2, int(ls * p))
    lg = G.cache(("logo", sz), lambda: Image.open(G.assets.path("logo")).convert("RGBA").resize((sz, sz), Image.LANCZOS))
    lx, ly = int(x0 + (ls - sz) / 2), int(c.H / 2 - sz / 2)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((lx - 2, ly - 2, lx + sz + 2, ly + sz + 2), int(sz * 0.23), outline=(90, 90, 96), width=2)
    im.paste(lg, (lx, ly), lg)
    handles(d, (lx, ly, lx + sz, ly + sz), c.fi, "logo", (255, 255, 255), cluster=c.lt < 1.0, pad=10)
    if wp > 0:
        lay = Image.new("L", im.size, 0)
        text(ImageDraw.Draw(lay), (x0 + ls + 34, c.H / 2), s["name"], f, int(255 * wp), -4, "lm", max_w=c.W * 0.5)
        clip = Image.new("L", im.size, 0)
        ImageDraw.Draw(clip).rectangle((x0 + ls, 0, x0 + ls + 42 + nw * wp, c.H), fill=255)
        im.paste((255, 255, 255), (0, 0), Image.fromarray(np.minimum(np.asarray(lay), np.asarray(clip))))
    return arr(im)


SHOTS = {"words": shot_words, "ring": shot_ring, "wave": shot_wave, "plate": shot_plate, "frame": shot_frame,
         "grid": shot_grid, "scatter": shot_scatter, "column": shot_column, "flip": shot_flip, "stack": shot_stack,
         "logo": shot_logo}


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    scenes = [Scene(f"{k:02d}-{s['type']}", s["dur"], (lambda f, sh: lambda c: f(c, sh))(SHOTS[s["type"]], s))
              for k, s in enumerate(brief["shots"])]
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["assets", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    if a.cmd == "assets":
        brief = json.load(open(a.brief))
        for m in generate_images(brief.get("assets", {}), os.path.join(base, brief.get("assets_dir", "assets")), names=a.args or None, force=a.force):
            print(m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep:
            print("  ✗", r)
        for r in overflow_report(warn=True):
            print("  ! warning:", r)
        trailing = re.findall(r'"(?:text|t|left|right|name)": "([^"]*[^.]\.)"', json.dumps(brief["shots"]))
        if trailing:
            print(f"  ! {len(trailing)} on-screen lines end with a period, e.g. {trailing[0]!r}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} shots")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 5, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "canvas-story-reel.mp4"), a.audio))


if __name__ == "__main__":
    main()
