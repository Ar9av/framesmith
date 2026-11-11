#!/usr/bin/env python3
"""pixel-quest-intro: a retro side-scroller attract sequence (320×180 internal, ×6 nearest-neighbour, 20 s).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1 2.6 7 10 13.6 15.5 18.5
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

Everything is drawn into a 320×180 buffer of palette indices (16 colours) and scaled by an integer.
Parallax layers move by whole pixels; sprites are hand-authored and animate on stepped timing (no
smooth easing on sprites). The hero runs, collects coins, bops a slime, the palette shifts from day
to sunset in steps, a chest opens with a light burst, a dialogue box types the facts, and the
chunky logo drops in with a shine sweep. A light scanline pass keeps the pixels square. Chiptune
score (pulse lead, triangle bass, noise drums) and the jump/coin/chest effects are synthesised here.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Scene, Timeline, h, hex2rgb, text, text_width, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.score import Score, SR, hz

G = None
IW, IH = 320, 180
DUR = 20.0
GROUND = 150

# a 16-colour palette (PICO-8's): indices are what every layer draws with
PAL = ["#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
       "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA"]

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16


def spr(rows):
    """Sprite from strings: '.' transparent, hex digit = palette index."""
    return np.array([[-1 if ch == "." else int(ch, 16) for ch in r] for r in rows], np.int16)


BODY = [
    "......8888......",
    ".....888888.....",
    ".....88888888...",
    ".....ffff0f.....",
    ".....fffff......",
    "...44cccc.......",
    "..444cccccf.....",
    "..444ccccc......",
    "..444cccc.......",
    "...44cccc.......",
    ".....1111.......",
]
LEGS = [
    [".....1..11......", "....11...11.....", "....1.....1.....", "...00.....00....", "................"],
    [".....11.1.......", ".....11.1.......", ".....1..1.......", ".....00.00......", "................"],
    ["......11.1......", ".....11...11....", "....11.....1....", "....00.....00...", "................"],
    ["......1.11......", "......1.11......", "......1..1......", "......00.00.....", "................"],
]
JUMP = [".....1111.......", "....11..11......", "....00..00......", "................", "................"]
STAND = [".....1..1.......", ".....1..1.......", ".....1..1.......", "....00..00......", "................"]
HERO_RUN = [spr(BODY + l) for l in LEGS]
HERO_JUMP = spr(BODY + JUMP)
HERO_STAND = spr(BODY + STAND)
SLIME = spr(["....bbbb....", "..bbbbbbbb..", ".bbb7bb7bbb.", ".bbb0bb0bbb.", "bbbbbbbbbbbb", "bbbbbbbbbbbb",
             "3bbbbbbbbbb3", ".3333333333."])


def coin(k):
    """Spinning coin, 4 frames: the width narrows and widens."""
    w = [8, 6, 2, 6][k % 4]
    a = np.full((8, 8), -1, np.int16)
    for y in range(8):
        half = math.sqrt(max(0.0, 16 - (y - 3.5) ** 2)) / 4 * w / 2
        x0, x1 = int(round(4 - half)), int(round(4 + half))
        if x1 > x0:
            a[y, x0:x1] = 10
            a[y, x0] = 9
            a[y, x1 - 1] = 9
    if w >= 6:
        a[2:6, 4] = 7
    return a


def chest(open_):
    a = np.full((14, 18), -1, np.int16)
    a[6:14, 1:17] = 4
    a[6:14, 1] = a[6:14, 16] = 2
    a[13, 1:17] = 2
    a[6:14, 8:10] = 9
    a[9:11, 8:10] = 10
    if open_:
        a[0:3, 1:17] = 2
        a[3:6, 1:17] = 0
        a[3, 2:16] = 9
    else:
        a[2:6, 1:17] = 4
        a[2, 1:17] = 2
        a[2:6, 8:10] = 9
    return a


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.fps = brief.get("fps", 30)
        self.k = brief.get("scale", 6)
        self.W, self.H = IW * self.k, IH * self.k
        self.spb = 60 / brief.get("bpm", 120)
        self.seed = brief.get("seed", 3)
        self.pal = np.array([hex2rgb(c) for c in PAL], np.uint8)
        self.th = None
        rng = np.random.default_rng(self.seed)
        self.mount = rng.integers(0, 28, 64)                       # far ridge heights (period 320 px)
        self.trees = rng.integers(0, 3, 40)                         # mid-layer silhouette kinds


# ------------------------------------------------------------------ cue sheet (seconds)
SPEED = 60                       # near-layer px per second
STOP = 12.0                      # the world stops scrolling here
COINS = [(200, GROUND - 14), (216, GROUND - 14), (232, GROUND - 14), (676, GROUND - 40), (692, GROUND - 46), (708, GROUND - 40)]
SLIME_X = 480
JUMPS = [(6.55, 7.0), (7.0, 7.45), (9.95, 10.65)]                   # (start, end): onto the slime, off it, through the coin arc
CHEST_T = 13.5
DIALOG = (14.2, 17.0)
LOGO = 17.0


def dist(t):
    """World scroll in whole pixels."""
    if t < STOP:
        return int(SPEED * t)
    return int(SPEED * STOP)


def hero_pos(t):
    """Hero (screen x, feet y, sprite)."""
    if t < 1.0:
        x = int(-16 + 76 * t)
    elif t < STOP:
        x = 60
    else:
        x = min(60 + int((t - STOP) * 60), 136)
    y = GROUND
    for a, b in JUMPS:
        if a <= t < b:
            u = (t - a) / (b - a)
            hgt = 34 if (a, b) == JUMPS[2] else 18
            y = GROUND - int(4 * hgt * u * (1 - u))
            if (a, b) == JUMPS[0]:
                y -= int(10 * u)                                     # lands on the slime's head
            if (a, b) == JUMPS[1]:
                y -= int(10 * (1 - u))
            return x, y, HERO_JUMP
    if t >= STOP and x >= 136:
        return x, y, HERO_STAND
    f = int(t * 12) % 4                                             # 12 fps run cycle, stepped
    return x, y, HERO_RUN[f]


def blit(buf, s, x, y):
    hh, ww = s.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(IW, x + ww), min(IH, y + hh)
    if x1 <= x0 or y1 <= y0:
        return
    sub = s[y0 - y:y1 - y, x0 - x:x1 - x]
    m = sub >= 0
    buf[y0:y1, x0:x1][m] = sub[m]


def phase(t):
    """Day → sunset in four palette steps (beats 16–22)."""
    return 0 if t < 8.0 else min(3, int(t - 8.0) + 1)


SKY = [(12, 6), (12, 14), (13, 9), (2, 9)]
RIDGE = [13, 13, 2, 2]
TREES = [3, 3, 1, 0]
SUN = [(10, 70), (10, 84), (9, 98), (8, 112)]


def sky(buf, t):
    ph = phase(t)
    top, bot = SKY[ph]
    g = np.linspace(0, 1, GROUND)[:, None]
    th = np.tile(BAYER, (GROUND // 4 + 1, IW // 4))[:GROUND, :IW]
    buf[:GROUND] = np.where(g > th, bot, top)
    col, sy = SUN[ph]
    yy, xx = np.ogrid[:IH, :IW]
    buf[((xx - 250) ** 2 + (yy - sy) ** 2 <= 14 ** 2) & (yy < GROUND)] = col
    # clouds drift at 6 px/s
    off = int(6 * t)
    for k, (cx, cy) in enumerate(((40, 30), (150, 22), (260, 40))):
        x = (cx - off) % (IW + 60) - 30
        for dx, dy, r in ((0, 0, 6), (7, -3, 7), (14, 0, 5)):
            buf[((xx - x - dx) ** 2 + ((yy - cy - dy) * 1.6) ** 2 <= r * r)] = 7


def ridge(buf, t):
    off = int(SPEED * 0.2 * min(t, STOP))
    col = RIDGE[phase(t)]
    xs = (np.arange(IW) + off) % 320
    k = xs // 5
    hgt = (G.mount[k % 64] * (1 - (xs % 5) / 5) + G.mount[(k + 1) % 64] * ((xs % 5) / 5)).astype(int)
    for x in range(IW):
        top = 96 - hgt[x]
        buf[top:GROUND, x] = col


def trees(buf, t):
    off = int(SPEED * 0.5 * min(t, STOP))
    col = TREES[phase(t)]
    d = ImageDraw.Draw(im := Image.fromarray(buf.astype(np.uint8), "L"))
    for k in range(-1, 14):
        wx = k * 26 - off % 26
        kind = G.trees[(k + off // 26) % len(G.trees)]
        base = GROUND
        if kind == 0:                                               # pine
            d.polygon([(wx, base), (wx + 12, base - 34), (wx + 24, base)], fill=col)
        elif kind == 1:                                             # round tree
            d.ellipse((wx + 2, base - 32, wx + 22, base - 10), fill=col)
            d.rectangle((wx + 11, base - 12, wx + 13, base), fill=col)
        else:                                                       # cottage
            d.rectangle((wx + 2, base - 16, wx + 22, base), fill=col)
            d.polygon([(wx, base - 16), (wx + 12, base - 26), (wx + 24, base - 16)], fill=col)
            d.rectangle((wx + 9, base - 10, wx + 12, base - 6), fill=10 if phase(t) >= 2 else col)
    buf[:] = np.asarray(im, np.int16)


def ground(buf, t):
    off = dist(t)
    xs = (np.arange(IW) + off)
    buf[GROUND:GROUND + 2] = 11
    buf[GROUND + 2] = 3
    buf[GROUND + 3:] = 4
    tile = ((xs // 16) + (np.arange(GROUND + 3, IH)[:, None] // 8)) % 2 == 0
    dots = ((xs[None] * 7 + np.arange(GROUND + 3, IH)[:, None] * 13) % 23 == 0)
    sub = buf[GROUND + 3:]
    sub[tile & ((xs[None] % 16) == 0)] = 2
    sub[dots] = 5


def to_screen(wx, t):
    return wx - dist(t)


def world(buf, t, fi):
    sky(buf, t)
    ridge(buf, t)
    trees(buf, t)
    ground(buf, t)
    hx, hy, hs = hero_pos(t)
    # coins (collected when the hero passes) with a 3-frame sparkle
    got = 0
    for wx, wy in COINS:
        sx = to_screen(wx, t)
        t_hit = None
        for tt in np.arange(0, t, 1 / 30):
            ax, ay, _ = hero_pos(tt)
            if abs(to_screen(wx, tt) - (ax + 6)) < 8 and abs(wy - (ay - 10)) < 12:
                t_hit = tt
                break
        if t_hit is None:
            blit(buf, coin(int(t * 8) + wx // 16), sx, wy - 4)
        else:
            got += 1
            k = int((t - t_hit) * 30)
            if k < 6:
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    for r in range(1, 2 + k // 2):
                        x, y = sx + 4 + dx * (r + k), wy + dy * (r + k)
                        if 0 <= x < IW and 0 <= y < IH:
                            buf[y, x] = 7 if k % 2 == 0 else 10
    # the slime: hops in place until bopped, then squashes and poofs
    sx = to_screen(SLIME_X, t)
    bop = JUMPS[1][0]
    if t < bop:
        hop = 2 if int(t * 4) % 2 else 0
        blit(buf, SLIME, sx, GROUND - 8 - hop)
    elif t < bop + 0.25:
        blit(buf, SLIME[[0, 2, 4, 6, 7]], sx - 1, GROUND - 5)
    elif t < bop + 0.5:
        k = int((t - bop - 0.25) * 24)
        for dx in (-4, 2, 8, 14):
            for r in range(2):
                y, x = GROUND - 4 - k - r, sx + dx + (k if dx > 6 else -k)
                if 0 <= x < IW and 0 <= y < IH:
                    buf[y, x] = 7
    # chest + light burst
    cx = to_screen(int(SPEED * STOP) + 160, t)
    opened = t >= CHEST_T
    blit(buf, chest(opened), cx, GROUND - 14)
    if opened and t < LOGO + 0.5:
        k = int((t - CHEST_T) * 12)                                 # stepped rotation
        d = ImageDraw.Draw(im := Image.fromarray(buf.astype(np.uint8), "L"))
        ox, oy = cx + 9, GROUND - 12
        grow = min(1.0, (t - CHEST_T) * 3)
        for r in range(8):
            a = math.radians(-90 + (r - 3.5) * 22 + (k % 2) * 6)
            L = int(70 * grow)
            d.line((ox, oy, ox + math.cos(a) * L, oy + math.sin(a) * L), fill=10 if r % 2 else 7, width=2 if r % 2 else 1)
        buf[:] = np.asarray(im, np.int16)
        blit(buf, chest(True), cx, GROUND - 14)
    blit(buf, hs, hx, hy - 16)
    if t < DIALOG[0]:                                               # HUD: coin counter (cleared for the dialogue)
        blit(buf, coin(0), 8, 8)
        hud(buf, f"x {got:02d}", 19, 7, 7)


def text_mask(s, size=11, track=0):
    """Departure Mono at its native 11 px grid, thresholded so every pixel is solid."""
    f = F("pixel", size)
    w = int(text_width(s, f, track)) + 4
    m = Image.new("L", (w, size + 6), 0)
    text(ImageDraw.Draw(m), (0, size), s, f, 255, track, "ls")
    return np.asarray(m) > 110


def hud(buf, s, x, y, col):
    m = text_mask(s)
    hh, ww = m.shape
    sub = buf[y:y + hh, x:x + ww]
    sh = m[:sub.shape[0], :sub.shape[1]]
    shadow = np.zeros_like(sh)
    shadow[1:, 1:] = sh[:-1, :-1]
    sub[shadow & ~sh] = 0
    sub[sh] = col


def dialog(buf, t):
    a, b = DIALOG
    if not a <= t < b:
        return
    pages = G.c["dialogue"][:2]
    per = (b - a) / len(pages)
    i = min(len(pages) - 1, int((t - a) / per))
    s = pages[i]
    n = int((t - a - i * per) * 30)                                 # types at 30 characters a second
    x0, y0, x1, y1 = 8, 8, IW - 8, 44
    buf[y0:y1, x0:x1] = 1
    buf[y0, x0:x1] = buf[y1 - 1, x0:x1] = 7
    buf[y0:y1, x0] = buf[y0:y1, x1 - 1] = 7
    buf[y0 + 1, x0 + 1:x1 - 1] = buf[y1 - 2, x0 + 1:x1 - 1] = 13
    lines = wrap(s[:n], s, 40)
    for j, ln in enumerate(lines[:2]):
        hud(buf, ln, x0 + 8, y0 + 5 + j * 13, 7)
    if n >= len(s) and int(t * 4) % 2:                              # blinking continue marker
        buf[y1 - 8:y1 - 5, x1 - 12:x1 - 6] = 10


def wrap(part, full, n):
    """Wrap by the full string's word breaks so typing never reflows."""
    words, rows, cur = full.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > n:
            rows.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    rows.append(cur)
    out, k = [], len(part)
    for r in rows:
        out.append(r[:max(0, k)])
        k -= len(r) + 1
    return [r for r in out if r]


def logo(buf, t):
    if t < LOGO:
        return
    title = G.c["title"].upper()
    m = text_mask(title, 22, 1)
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh, ww = m.shape
    if ww > IW - 20:
        m = m[:, :IW - 20]
        hh, ww = m.shape
    x = (IW - ww) // 2
    steps = [-40, -10, 38, 30, 34, 32]                              # stepped drop with a two-step settle
    k = min(len(steps) - 1, int((t - LOGO) * 10))
    y = steps[k] if k < len(steps) - 1 else 32
    big = np.zeros((IH, IW), bool)
    yy0, xx0 = max(0, y), x
    sub = m[yy0 - y:, :]
    big[yy0:yy0 + sub.shape[0], xx0:xx0 + ww] = sub[:IH - yy0]
    outline = np.asarray(Image.fromarray(big.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    shadow = np.zeros_like(big)
    shadow[2:, 2:] = outline[:-2, :-2]
    buf[shadow & ~outline] = 0
    buf[outline & ~big] = 1
    rows = np.arange(IH)[:, None]
    buf[big & (rows < y + hh // 2)] = 10
    buf[big & (rows >= y + hh // 2)] = 9
    sweep = int((t - LOGO - 0.8) * 160)                             # shine: a diagonal band crossing the letters
    if 0 < sweep < IW + 60:
        cols = np.arange(IW)[None, :]
        band = (np.abs((cols + (rows - y)) - (x + sweep - 30)) <= 2)
        buf[big & band] = 7
    if t >= LOGO + 0.9:
        s = G.c["release"]
        mm = text_mask(s)
        hud(buf, s, (IW - mm.shape[1]) // 2, y + hh + 12, 7)
    if t >= LOGO + 1.4 and int(t * 2) % 2 == 0:
        s = G.c["url"]
        mm = text_mask(s)
        hud(buf, s, (IW - mm.shape[1]) // 2, y + hh + 27, 10)


def frame(c):
    t = c.t
    buf = np.zeros((IH, IW), np.int16)
    world(buf, t, c.fi)
    dialog(buf, t)
    logo(buf, t)
    rgb = G.pal[np.clip(buf, 0, 15)]
    big = np.repeat(np.repeat(rgb, G.k, 0), G.k, 1)
    big[G.k - 1::G.k] = (big[G.k - 1::G.k].astype(np.uint16) * 7 // 8).astype(np.uint8)   # light scanlines, pixels stay square
    return big


# ------------------------------------------------------------------ chiptune
def pulse(note, dur, duty=0.25, vol=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = (t * hz(note)) % 1
    env = np.minimum(1, t / 0.004) * np.exp(-t / max(dur, 0.05) * 1.5)
    return np.where(ph < duty, 1.0, -1.0) * env * vol


def tri(note, dur, vol=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = (t * hz(note)) % 1
    env = np.minimum(1, t / 0.004) * np.clip(1 - t / dur, 0, 1) ** 0.3
    return (4 * np.abs(ph - 0.5) - 1) * env * vol


def noise(dur, vol=0.2, seed=1, decay=0.05):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.random.default_rng(seed).choice([-1.0, 1.0], n)
    x = np.repeat(x[::8], 8)[:n]                                    # 8-bit style stepped noise
    return x * np.exp(-t / decay) * vol


def sweep(f0, f1, dur, vol=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    ph = np.cumsum(f) / SR % 1
    return np.where(ph < 0.5, 1.0, -1.0) * np.exp(-t / dur * 1.2) * vol


def score(path):
    sc = Score(120, DUR + 0.3)
    b = sc.spb
    lead = ["E5", "G5", "A5", "G5", "E5", "D5", "C5", "D5", "E5", "G5", "C6", "B5", "A5", "G5", "E5", "G5"]
    bassn = ["C3", "C3", "A2", "A2", "F2", "F2", "G2", "G2"]
    end = int(STOP / b)
    for k in range(0, end):
        if k % 2 == 0:
            sc.add(tri(bassn[(k // 4) % 8], b * 1.8), k * b)
        sc.add(pulse(lead[(k * 2) % 16], b * 0.45), k * b, 0.9, 0.2)
        sc.add(pulse(lead[(k * 2 + 1) % 16], b * 0.45), (k + 0.5) * b, 0.8, 0.2)
        sc.add(noise(0.05, 0.12, k), (k + 0.5) * b)
        if k % 2 == 0:
            sc.add(noise(0.12, 0.25, 99, 0.03), k * b)
    for a, z in JUMPS:
        sc.add(sweep(300, 900, 0.18), a)
    sc.add(sweep(700, 120, 0.2), JUMPS[1][0])                        # bop
    for wx, wy in COINS:
        for tt in np.arange(0, DUR, 1 / 30):
            ax, ay, _ = hero_pos(tt)
            if abs(wx - dist(tt) - (ax + 6)) < 8 and abs(wy - (ay - 10)) < 12:
                sc.add(pulse("B5", 0.06, 0.5, 0.2), tt)
                sc.add(pulse("E6", 0.18, 0.5, 0.2), tt + 0.06)
                break
    for i, n in enumerate(["C5", "E5", "G5", "C6", "E6", "G6", "C7"]):  # chest arpeggio
        sc.add(pulse(n, 0.1, 0.125, 0.2), CHEST_T + i * 0.06)
    for k in range(int((DIALOG[1] - DIALOG[0]) * 12)):              # dialogue blips
        sc.add(pulse("A5", 0.025, 0.5, 0.08), DIALOG[0] + k / 12)
    t0 = LOGO
    for n, d in [("C5", 0.15), ("G4", 0.15), ("C5", 0.15), ("E5", 0.15), ("G5", 0.6), ("C6", 1.2)]:   # logo jingle
        sc.add(pulse(n, d * 1.5, 0.25, 0.25), t0)
        t0 += d
    sc.add(tri("C3", 2.5), LOGO)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("attract", DUR, frame)], G.W, G.H, G.fps, data=G), brief


def check(tl):
    errs = []
    for k in ("title", "dialogue", "release", "url"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    for s in G.c["dialogue"] + [G.c["release"], G.c["url"]]:
        if s.rstrip().endswith("."):
            errs.append(f"trailing period: {s!r}")
    for s in G.c["dialogue"]:
        if len(s) > 80:
            errs.append(f"dialogue page over 80 characters (two 40-character lines): {s!r}")
    tm = text_mask(G.c["title"].upper(), 22, 1)
    if tm.shape[1] > IW - 20:
        errs.append(f"title is {tm.shape[1]} px wide at 22 px pixel type; keep it under {IW - 20} (about 13 characters)")
    for s in (G.c["release"], G.c["url"]):
        if text_mask(s).shape[1] > IW - 16:
            errs.append(f"too wide for the 320 px screen: {s!r}")
    if len(G.c["dialogue"]) > 2:
        errs.append("at most 2 dialogue pages")
    print(f"{DUR:.2f}s, {tl.n_frames} frames at {IW}×{IH} ×{G.k} = {G.W}×{G.H}")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "moss-courier", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("fully procedural: sprites are authored in scripts/main.py.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=6, rows=4, thumb_w=320))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, "pixel-quest-intro.mp4"), audio))


if __name__ == "__main__":
    main()
