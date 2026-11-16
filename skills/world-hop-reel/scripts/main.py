#!/usr/bin/env python3
"""world-hop-reel: one rigged character runs through a chain of art-style worlds, cut on the beat.

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1 2 5.1 9 13 16.5
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--format reel|wide] [--audio track.m4a]

The rule this template is built on: ONE character, the SAME rules, EVERY world. The figure is a
single skeleton (joints from a beat-locked run cycle). A world is only a renderer: a plate, a brush
for the bones, a typeface rule for its keyword and a post pass. Swapping worlds never touches the
rig, so the character stays on-model with zero re-drawing. A whip-pan lands on every downbeat and
the seam crosses the figure, which renders half in the old world and half in the new one.

`--format reel` wraps the 16:9 film in a 9:16 frame: blurred cover of the same film behind, the
film in the middle band, a fixed hook line on top (the format the reference reel used).
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Scene, Timeline, ease_out, ease_in_out, prog, hex2rgb, text_width
from framesmith.typography import F
from framesmith.score import Score, riser, blip

G = None
W, H = 1280, 720                 # the film; the reel wrapper is 1080×1920
RW, RH = 1080, 1920
L = W + 160                      # world length in camera pixels (room for the hold drift)
DRIFT = 40                       # px/s camera drift while a world holds
WHIP = 0.16                      # half-width of the whip-pan around each downbeat (s)
STYLES = ("cave", "egypt", "greek", "glass", "crt", "holo")


# ------------------------------------------------------------------ helpers
def rgb(c):
    return tuple(hex2rgb(c))


def vnoise(h, w, cell, rng, octaves=3):
    """Smooth value noise in [0, 1]."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2, cell >> o)
        g = rng.random((h // c + 2, w // c + 2)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w + 2 * c, h + 2 * c), Image.BICUBIC)
        out += np.asarray(im, np.float32)[c:c + h, c:c + w] / 255 * amp
        tot += amp
        amp *= 0.5
    return out / tot


def capsule(d, a, b, w, fill):
    w = max(1, int(round(w)))
    d.line([a, b], fill=fill, width=w)
    r = w / 2
    for p in (a, b):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=fill)


def rise_mask(s, font, p, track=0, pad=6):
    """Text as an L mask with a masked rise-in (p: 0 → 1); returns (mask, width, height)."""
    tw = int(text_width(s, font, track)) + 2 * pad
    asc, desc = font.getmetrics()
    th = asc + desc + 2 * pad
    m = Image.new("L", (tw, th), 0)
    d = ImageDraw.Draw(m)
    dy = (1 - ease_out(p)) * th
    x = pad
    for ch in s:
        d.text((x, pad + dy), ch, font=font, fill=255)
        x += font.getlength(ch) + track
    return m, tw, th


def paste_mask(img, mask, xy, color, mode="normal", alpha=1.0):
    """Composite a solid colour through mask onto an RGB PIL image (normal or multiply)."""
    x, y = int(xy[0]), int(xy[1])
    m = np.asarray(mask, np.float32) / 255 * alpha
    a = np.asarray(img).copy()
    h, w = m.shape
    x0, y0, x1, y1 = max(0, x), max(0, y), min(a.shape[1], x + w), min(a.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return img
    m = m[y0 - y:y1 - y, x0 - x:x1 - x, None]
    reg = a[y0:y1, x0:x1].astype(np.float32)
    col = np.array(color, np.float32)
    tgt = reg * col / 255 if mode == "multiply" else col
    a[y0:y1, x0:x1] = (reg * (1 - m) + tgt * m).astype(np.uint8)
    return Image.fromarray(a)


# ------------------------------------------------------------------ the rig (shared by every world)
def rig(t, x, yg, fh, spb, phase=0.0):
    """Joints of a run cycle locked to the beat: one stride pair per beat (feet land on the 8ths)."""
    ph = 2 * math.pi * t / spb + phase
    lean = 0.17
    th, sh, tor, ua, fa = 0.25 * fh, 0.25 * fh, 0.30 * fh, 0.16 * fh, 0.15 * fh
    legs = {}
    for side, off in (("near", 0.0), ("far", math.pi)):
        p = ph + off
        a_th = 0.62 * math.sin(p)
        bend = 0.2 + 1.25 * max(0.0, math.cos(p)) ** 1.4
        a_sh = a_th - bend
        knee = (th * math.sin(a_th), th * math.cos(a_th))
        foot = (knee[0] + sh * math.sin(a_sh), knee[1] + sh * math.cos(a_sh))
        legs[side] = (knee, foot)
    low = max(legs["near"][1][1], legs["far"][1][1])
    hip = (x, yg - low)
    J = {"hip": hip}
    for side, (k, f) in legs.items():
        J[side + "_knee"] = (hip[0] + k[0], hip[1] + k[1])
        J[side + "_foot"] = (hip[0] + f[0], hip[1] + f[1])
        J[side + "_toe"] = (J[side + "_foot"][0] + 0.06 * fh, J[side + "_foot"][1])
    neck = (hip[0] + tor * math.sin(lean), hip[1] - tor * math.cos(lean))
    J["neck"] = neck
    J["head"] = (neck[0] + 0.11 * fh * math.sin(lean * 1.4), neck[1] - 0.11 * fh * math.cos(lean * 1.4))
    sho = (neck[0] - 0.01 * fh, neck[1] + 0.03 * fh)
    J["sho"] = sho
    for side, off in (("near", math.pi), ("far", 0.0)):        # arms swing against the same-side leg
        a_up = 0.8 * math.sin(ph + off)
        el = (sho[0] + ua * math.sin(a_up), sho[1] + ua * math.cos(a_up))
        a_fo = a_up + 1.45
        J[side + "_elbow"] = el
        J[side + "_hand"] = (el[0] + fa * math.sin(a_fo), el[1] + fa * math.cos(a_fo))
    J["fh"] = fh
    return J


def bones(J, side):
    return [("thigh", J["hip"], J[side + "_knee"]), ("shin", J[side + "_knee"], J[side + "_foot"]),
            ("foot", J[side + "_foot"], J[side + "_toe"]),
            ("upper", J["sho"], J[side + "_elbow"]), ("fore", J[side + "_elbow"], J[side + "_hand"])]


WIDTH = {"thigh": 0.09, "shin": 0.072, "foot": 0.05, "upper": 0.068, "fore": 0.058, "torso": 0.13}
HEAD_R = 0.085


def draw_rig(d, J, brush):
    """Far side, torso, head, near side, through brush(d, part, a, b, width, depth)."""
    fh = J["fh"]
    for part, a, b in bones(J, "far"):
        brush(d, part, a, b, WIDTH[part] * fh, "far")
    brush(d, "torso", J["hip"], J["neck"], WIDTH["torso"] * fh, "mid")
    brush(d, "head", J["head"], J["head"], HEAD_R * fh * 2, "mid")
    for part, a, b in bones(J, "near"):
        brush(d, part, a, b, WIDTH[part] * fh, "near")


# ------------------------------------------------------------------ plates (built once per world)
def plate_cave(rng):
    n = vnoise(H, L, 96, rng, 4)
    fine = vnoise(H, L, 6, rng, 2)
    base = np.array(rgb("#b39a7c"), np.float32)
    a = base[None, None] * (0.72 + 0.42 * n[..., None]) * (0.9 + 0.12 * fine[..., None])
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for _ in range(14):                                           # cracks: random walks
        x, y = rng.uniform(0, L), rng.uniform(0, H)
        pts = [(x, y)]
        ang = rng.uniform(0, math.pi)
        for _ in range(int(rng.integers(8, 20))):
            ang += rng.normal(0, 0.5)
            x += 14 * math.cos(ang)
            y += 14 * math.sin(ang)
            pts.append((x, y))
        d.line(pts, fill=rgb("#5e4c3b"), width=int(rng.integers(1, 3)))
    spots = [(L * 0.08, H * 0.24), (L * 0.40, H * 0.16), (L * 0.88, H * 0.62)]
    sp = Image.new("L", (L, H), 0)                                # hand stencils: a spray halo around a hand
    sd = ImageDraw.Draw(sp)
    hands = Image.new("L", (L, H), 0)
    hd = ImageDraw.Draw(hands)
    for hx, hy in spots:
        sd.ellipse([hx - 70, hy - 60, hx + 70, hy + 80], fill=150)
        hd.ellipse([hx - 24, hy - 6, hx + 24, hy + 40], fill=255)
        for k, (ang, ln) in enumerate([(-0.9, 46), (-0.35, 62), (0.0, 66), (0.32, 60), (0.7, 46)]):
            ex, ey = hx + ln * math.sin(ang), hy + 6 - ln * math.cos(ang)
            capsule(hd, (hx + (k - 2) * 9, hy + 4), (ex, ey), 14, 255)
    sp = np.asarray(sp.filter(ImageFilter.GaussianBlur(22)), np.float32) / 255
    sp *= 1 - np.asarray(hands.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    sp *= 0.6 + 0.4 * vnoise(H, L, 4, rng, 1)
    ochre = np.array(rgb("#8f3a22"), np.float32)
    a = np.asarray(im, np.float32)
    a = a * (1 - sp[..., None] * 0.7) + a * ochre / 255 * sp[..., None] * 0.7
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for row in range(2):                                          # rows of ochre finger dots
        y = H * (0.08 + 0.05 * row)
        for k in range(18):
            x = L * 0.52 + k * 26 + rng.normal(0, 3)
            r = 7 + rng.normal(0, 1)
            d.ellipse([x - r, y - r, x + r, y + r], fill=rgb("#963f24"))
    return np.asarray(im)


GLYPHS = ("sun", "water", "reed", "loaf", "seat", "ankh", "bird", "rope")


def glyph(d, kind, x, y, s, col):
    w = max(2, int(s * 0.12))
    if kind == "sun":
        d.ellipse([x - s * .35, y - s * .35, x + s * .35, y + s * .35], outline=col, width=w)
        d.ellipse([x - s * .07, y - s * .07, x + s * .07, y + s * .07], fill=col)
    elif kind == "water":
        pts = [(x - s * .45 + i * s * .15, y + (s * .1 if i % 2 else -s * .1)) for i in range(7)]
        d.line(pts, fill=col, width=w)
    elif kind == "reed":
        d.line([(x, y + s * .45), (x, y - s * .4)], fill=col, width=w)
        d.polygon([(x, y - s * .4), (x + s * .22, y - s * .1), (x, y)], fill=col)
    elif kind == "loaf":
        d.pieslice([x - s * .4, y - s * .2, x + s * .4, y + s * .5], 180, 360, fill=col)
    elif kind == "seat":
        d.rectangle([x - s * .3, y - s * .3, x + s * .3, y + s * .3], outline=col, width=w)
        d.line([(x - s * .3, y), (x + s * .3, y)], fill=col, width=w)
    elif kind == "ankh":
        d.ellipse([x - s * .17, y - s * .45, x + s * .17, y - s * .1], outline=col, width=w)
        d.line([(x, y - s * .1), (x, y + s * .45)], fill=col, width=w)
        d.line([(x - s * .3, y + s * .02), (x + s * .3, y + s * .02)], fill=col, width=w)
    elif kind == "bird":
        d.ellipse([x - s * .25, y - s * .1, x + s * .2, y + s * .25], fill=col)
        d.ellipse([x + s * .08, y - s * .32, x + s * .3, y - s * .1], fill=col)
        d.polygon([(x - s * .25, y + s * .05), (x - s * .45, y + s * .3), (x - s * .15, y + s * .2)], fill=col)
        d.line([(x, y + s * .25), (x - s * .05, y + s * .45)], fill=col, width=w)
    else:
        d.arc([x - s * .3, y - s * .4, x + s * .3, y + s * .2], 0, 360, fill=col, width=w)
        d.line([(x - s * .1, y + s * .2), (x - s * .2, y + s * .45)], fill=col, width=w)
        d.line([(x + s * .1, y + s * .2), (x + s * .2, y + s * .45)], fill=col, width=w)


def plate_egypt(rng):
    n = vnoise(H, L, 64, rng, 3)
    base = np.array(rgb("#dcc391"), np.float32)
    a = base[None, None] * (0.88 + 0.16 * n[..., None])
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    bands = [("#1f3f8f", 14), ("#c9962b", 8), ("#2a9d8f", 10), ("#a33a2a", 6)]
    y = 0
    for c, hh in bands:
        d.rectangle([0, y, L, y + hh], fill=rgb(c))
        y += hh
    y = H
    for c, hh in bands:
        d.rectangle([0, y - hh, L, y], fill=rgb(c))
        y -= hh
    gy = int(H * 0.845)
    d.rectangle([0, gy, L, gy + 5], fill=rgb("#6b4a2a"))           # ground register line
    cols = ["#1f3f8f", "#a33a2a", "#1b1b1b", "#2a9d8f"]
    for ci, cx in enumerate(range(40, L, 74)):                      # ruled hieroglyph columns
        d.line([(cx - 37, 60), (cx - 37, gy)], fill=rgb("#8a6a40"), width=2)
        rows = range(100, 190, 66) if cx > 0.15 * L else range(100, gy - 40, 66)   # keep the runner's register clear
        for k, gy_ in enumerate(rows):
            glyph(d, GLYPHS[int(rng.integers(len(GLYPHS)))], cx, gy_, 44, rgb(cols[(k + ci) % 4]))
    return np.asarray(im)


def meander(d, y0, hh, col, L_):
    """Greek key band between y0 and y0+hh."""
    u = hh // 5
    for x in range(0, L_ + 5 * u, 5 * u):
        pts = [(x, y0 + 4 * u), (x, y0 + u), (x + 3 * u, y0 + u), (x + 3 * u, y0 + 3 * u),
               (x + 2 * u, y0 + 3 * u), (x + 2 * u, y0 + 2 * u), (x + u, y0 + 2 * u), (x + u, y0 + 4 * u),
               (x + 5 * u, y0 + 4 * u)]
        d.line(pts, fill=col, width=max(2, u // 2 + 1), joint="curve")


def plate_greek(rng):
    n = vnoise(H, L, 80, rng, 3)
    base = np.array(rgb("#c9652f"), np.float32)
    yy = np.linspace(-1, 1, H)[:, None]
    shade = 1.0 - 0.22 * yy ** 2                                  # the vase's curvature, top and bottom darker
    a = base[None, None] * (shade * (0.92 + 0.12 * n))[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    ink = rgb("#1b120d")
    d.rectangle([0, 0, L, 70], fill=ink)
    d.rectangle([0, H - 64, L, H], fill=ink)
    meander(d, 12, 50, rgb("#c9652f"), L)
    gy = int(H * 0.84)
    d.rectangle([0, gy, L, gy + 6], fill=ink)
    for x in range(0, L, 30):                                    # tongue pattern under the ground line
        d.pieslice([x, gy + 6, x + 26, gy + 46], 0, 180, fill=ink)
    return np.asarray(im)


def plate_glass(rng):
    q = 4
    hh, ww = H // q, L // q
    n = 150
    sx, sy = rng.uniform(0, ww, n), rng.uniform(0, hh, n)
    ys, xs = np.mgrid[0:hh, 0:ww]
    dist = (xs[..., None] - sx) ** 2 + (ys[..., None] - sy) ** 2
    cell = dist.argmin(-1).astype(np.int16)
    jewels = np.array([rgb(c) for c in ("#1d3f9e", "#2453c2", "#173071", "#a3182c", "#1f7a4a",
                                         "#d39a1c", "#5b2a86", "#2453c2", "#1d3f9e")], np.float32)
    pal = jewels[rng.integers(0, len(jewels), n)] * rng.uniform(0.8, 1.15, (n, 1))
    cellbig = np.asarray(Image.fromarray(cell).resize((L, H), Image.NEAREST)).astype(np.int16)
    a = pal[cellbig]
    grain = vnoise(H, L, 5, rng, 2)
    yy, xx = np.mgrid[0:H, 0:L]
    light = 1.05 - 0.45 * np.hypot((xx - L * 0.3) / L, (yy - H * 0.2) / H)  # light from upper left
    a = a * (light * (0.85 + 0.25 * grain))[..., None]
    edge = np.zeros((H, L), bool)
    edge[:, 1:] |= cellbig[:, 1:] != cellbig[:, :-1]
    edge[1:, :] |= cellbig[1:, :] != cellbig[:-1, :]
    lead = Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    lm = np.asarray(lead, np.float32)[..., None] / 255
    a = a * (1 - lm) + np.array(rgb("#14120f"), np.float32) * lm
    return np.clip(a, 0, 255).astype(np.uint8), cellbig


def plate_crt(rng):
    q = 4
    im = Image.new("RGB", (L // q, H // q), rgb("#020d05"))
    d = ImageDraw.Draw(im)
    g, gd = rgb("#39ff7a"), rgb("#147a3a")
    for _ in range(70):
        x, y = rng.integers(0, L // q), rng.integers(12, int(H / q * 0.55))
        d.point((int(x), int(y)), fill=gd)
    pts, x = [], 0                                                # vector-arcade mountain outline
    while x < L // q + 20:
        pts.append((x, int(H / q * 0.62 - rng.integers(0, 26))))
        x += int(rng.integers(10, 24))
    d.line(pts, fill=gd, width=1)
    gy = int(H / q * 0.84)
    d.line([(0, gy), (L // q, gy)], fill=g, width=1)
    for x in range(0, L // q, 6):
        d.point((x, gy + 4), fill=gd)
    return np.asarray(im.resize((L, H), Image.NEAREST))


def plate_holo(rng):
    yy = np.linspace(0, 1, H)[:, None, None]
    a = np.array(rgb("#030914"), np.float32) * (1 - yy) + np.array(rgb("#071a33"), np.float32) * yy
    a = np.broadcast_to(a, (H, L, 3))
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    hz_, cyan = int(H * 0.56), rgb("#1c6f8f")
    for k in range(1, 18):                                       # perspective floor
        y = hz_ + (H - hz_) * (k / 17) ** 2
        d.line([(0, y), (L, y)], fill=cyan, width=1)
    for x in range(-L, 2 * L, 90):
        d.line([(L / 2 + (x - L / 2) * 0.12, hz_), (x, H)], fill=cyan, width=1)
    d.line([(0, hz_), (L, hz_)], fill=rgb("#3fd0ff"), width=2)
    glow = im.filter(ImageFilter.GaussianBlur(6))
    return np.clip(np.asarray(im, np.float32) + np.asarray(glow, np.float32) * 0.8, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ brushes (how each world draws the same bones)
def brush_cave(fi):
    rng = np.random.default_rng(fi // 3)                         # boil on 3s
    col = rgb("#8f2f1c")

    def b(d, part, a, c, w, depth):
        if part == "head":
            r = w / 2
            d.ellipse([a[0] - r, a[1] - r * 1.1, a[0] + r, a[1] + r * 0.9], fill=col)
            return
        for k in range(2):
            j = rng.normal(0, w * 0.12, 4)
            capsule(d, (a[0] + j[0], a[1] + j[1]), (c[0] + j[2], c[1] + j[3]), w * (0.8 - 0.25 * k), col)
    return b


def brush_egypt():
    skin, far, kilt, wig = rgb("#a4532c"), rgb("#7f3f22"), rgb("#f4efe2"), rgb("#141414")

    def b(d, part, a, c, w, depth):
        if part == "head":
            r = w / 2
            d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=skin)
            d.pieslice([a[0] - r * 1.15, a[1] - r * 1.2, a[0] + r * 0.9, a[1] + r * 1.4], 160, 330, fill=wig)
            d.rectangle([a[0] - r * 1.15, a[1] - r * 0.2, a[0] - r * 0.15, a[1] + r * 1.2], fill=wig)
            return
        capsule(d, a, c, w, far if depth == "far" else skin)
        if part == "torso":
            nx, ny = c
            for k, col in enumerate(("#1f3f8f", "#c9962b", "#2a9d8f")):  # broad collar
                rr = w * (0.75 - 0.12 * k)
                d.arc([nx - rr, ny - rr * 0.6, nx + rr, ny + rr * 1.1], 20, 160, fill=rgb(col), width=int(w * 0.14))
            hx, hy = a
            d.polygon([(hx - w * 0.75, hy - w * 0.35), (hx + w * 0.85, hy - w * 0.35),
                       (hx + w * 1.6, hy + w * 2.2), (hx - w * 0.5, hy + w * 2.0)], fill=kilt)
    return b


def brush_greek():
    ink, inc = rgb("#1b120d"), rgb("#c9652f")

    def b(d, part, a, c, w, depth):
        if part == "head":
            r = w / 2
            d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=ink)
            d.arc([a[0] - r * 0.7, a[1] - r * 0.8, a[0] + r * 0.3, a[1] + r * 0.2], 180, 320, fill=inc, width=2)
            d.arc([a[0] - r * 0.9, a[1] - r * 0.3, a[0] - r * 0.1, a[1] + r * 0.5], 140, 300, fill=inc, width=2)
            return
        capsule(d, a, c, w, ink)
        if part in ("thigh", "upper", "torso") and depth != "far":   # incised muscle line
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            dx, dy = c[0] - a[0], c[1] - a[1]
            ln = math.hypot(dx, dy) or 1
            ox, oy = -dy / ln * w * 0.18, dx / ln * w * 0.18
            d.line([(a[0] + dx * 0.25 + ox, a[1] + dy * 0.25 + oy), (mx + ox * 1.4, my + oy * 1.4),
                    (a[0] + dx * 0.75 + ox, a[1] + dy * 0.75 + oy)], fill=inc, width=2, joint="curve")
        if part == "shin" and depth != "far":
            d.arc([a[0] - w * 0.3, a[1] - w * 0.3, a[0] + w * 0.3, a[1] + w * 0.3], 0, 300, fill=inc, width=2)
    return b


def brush_glass():
    lead = rgb("#14120f")
    fills = {"head": "#e3a923", "torso": "#b01e33", "thigh": "#1f7a4a", "shin": "#1f7a4a", "foot": "#5b2a86",
             "upper": "#b01e33", "fore": "#e3a923"}

    def b(d, part, a, c, w, depth):
        col = tuple(int(v * (0.72 if depth == "far" else 1.0)) for v in rgb(fills[part]))
        if part == "head":
            r = w / 2
            hr = r * 1.8                                            # halo
            d.ellipse([a[0] - hr - 5, a[1] - hr - 5, a[0] + hr + 5, a[1] + hr + 5], fill=lead)
            d.ellipse([a[0] - hr, a[1] - hr, a[0] + hr, a[1] + hr], fill=rgb("#d9a52a"))
            d.ellipse([a[0] - r - 5, a[1] - r - 5, a[0] + r + 5, a[1] + r + 5], fill=lead)
            d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=col)
            return
        capsule(d, a, c, w + 10, lead)
        capsule(d, a, c, w, col)
        if part == "torso":                                         # a lead line across the tunic
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            d.line([(mx - w * 0.5, my), (mx + w * 0.5, my - 4)], fill=lead, width=5)
    return b


def brush_line(col, width):
    dim = tuple(int(v * 0.55) for v in col)

    def b(d, part, a, c, w, depth):
        if part == "head":
            r = w / 2
            d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], outline=col, width=width)
            return
        d.line([a, c], fill=col if depth != "far" else dim, width=width)
        for p in (a, c):
            d.ellipse([p[0] - width, p[1] - width, p[0] + width, p[1] + width], fill=col)
    return b


# ------------------------------------------------------------------ worlds
TYPE = {   # each world's keyword rule: (font role, size, colour, year role, tracking)
    "cave": ("condensed", 128, "#2a1a12", "condensed", 2),
    "egypt": ("sans_black", 104, "#1f3f8f", "mono_bold", 6),
    "greek": ("serif", 132, "#1b120d", "serif", 14),
    "glass": ("serif", 124, "#f1d48a", "serif", 4),
    "crt": ("pixel", 88, "#39ff7a", "pixel", 0),
    "holo": ("mono_medium", 96, "#8fe9ff", "mono", 2),
}
YEAR_COL = {"cave": "#4a2214", "egypt": "#a33a2a", "greek": "#1b120d", "glass": "#e3a923", "crt": "#39ff7a",
            "holo": "#3fd0ff"}
UPPER = ("cave", "egypt", "greek", "crt")


def label_of(w):
    return w["label"].upper() if w["style"] in UPPER else w["label"]


def keyword(img, style, label, year, p1, p2, x, y):
    role, size, col, yrole, track = TYPE[style]
    f = F(role, size)
    fy = F(yrole, int(size * 0.42) if role != "pixel" else 44)
    mode = "multiply" if style == "cave" else "normal"
    if p1 > 0:
        m, tw, th = rise_mask(label, f, p1, track)
        if style == "cave":                                         # dry brush: noise bites the strokes
            nz = vnoise(m.size[1], m.size[0], 5, np.random.default_rng(len(label)), 2)
            m = Image.fromarray((np.asarray(m, np.float32) * (nz > 0.32)).astype(np.uint8))
        if style == "glass":                                        # a lead band carries the line
            a = np.asarray(img).copy()
            wb = int((tw + 60) * ease_out(p1))
            a[max(0, y - 10):y + th + 90, max(0, x - 30):max(0, min(W, x - 30 + wb))] = rgb("#14120f")
            img = Image.fromarray(a)
        if style == "holo":
            glow = m.filter(ImageFilter.GaussianBlur(10))
            img = paste_mask(img, glow, (x, y), rgb(col), alpha=0.8 * ease_out(p1))
        img = paste_mask(img, m, (x, y), rgb(col), mode, 0.92 if style == "cave" else 1.0)
        if style == "egypt":
            a = np.asarray(img).copy()
            w_ = int(tw * ease_out(p1))
            x0 = max(0, x)
            a[y - 14:y - 8, x0:max(x0, x + w_)] = rgb("#c9962b")
            a[y + th + 4:y + th + 10, x0:max(x0, x + w_)] = rgb("#c9962b")
            img = Image.fromarray(a)
    if p2 > 0:
        m2, _, _ = rise_mask(year, fy, p2, track * 0.5)
        img = paste_mask(img, m2, (x, y + int(size * 1.12) + (22 if style == "egypt" else 0)), rgb(YEAR_COL[style]), mode)
    return img


def crt_post(a, t, fi):
    a = a.astype(np.float32)
    glow = np.asarray(Image.fromarray(a.astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
                      .filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR), np.float32)
    a = a + glow * 0.9
    a[::3] *= 0.55                                                  # scanlines
    roll = (t * 180) % (H + 200) - 100                              # rolling bright bar
    yy = np.arange(H)[:, None, None]
    a *= 1 + 0.12 * np.exp(-((yy - roll) / 40) ** 2)
    a *= 0.96 + 0.04 * ((fi * 7919) % 13) / 13                     # flicker
    a *= G.crt_vig
    a += G.crt_bezel
    return np.clip(a, 0, 255).astype(np.uint8)


def world_frame(k, t, ok, fig_x=None, show_kw=True, blur=0):
    """World k rendered with camera offset ok (world-local px); the figure stays fixed on screen."""
    style = G.worlds[k]["style"]
    fi = int(round(t * G.fps))
    cols = np.clip(np.arange(W) + int(round(ok)), 0, L - 1)
    base = G.plates[k][:, cols]
    if style == "glass":                                            # cells breathe with the light
        cid = G.cells[k][:, cols]
        gain = (0.9 + 0.12 * np.sin(t * 2.2 + G.cellph[k])).astype(np.float32)
        base = np.clip(base * gain[cid][..., None], 0, 255).astype(np.uint8)
    if style == "cave":                                             # torch flicker
        base = (base * (0.93 + 0.05 * math.sin(t * 13) + 0.02 * math.sin(t * 31))).astype(np.uint8)
    img = Image.fromarray(np.ascontiguousarray(base))
    if show_kw:
        w = G.worlds[k]
        lt = t - G.B[k]
        x = int(G.kx - ok)                                          # the keyword belongs to the world: it scrolls with it
        img = keyword(img, style, label_of(w), w["year"], prog(lt, 0.25, 0.7), prog(lt, 0.5, 0.95), x, G.ky)
        if style == "holo" and lt > 0.2:                             # HUD arcs beside the keyword
            d = ImageDraw.Draw(img)
            cx, cy, r = x + 40, G.ky + 300, 54
            a0 = (t * 90) % 360
            for k2, rr in enumerate((r, r * 0.7)):
                d.arc([cx - rr, cy - rr, cx + rr, cy + rr], a0 * (1 - 2 * k2) + k2 * 140,
                      a0 * (1 - 2 * k2) + k2 * 140 + 250 * ease_out(prog(lt, 0.2, 0.8)), fill=rgb("#3fd0ff"), width=2)
            d.text((cx + 80, cy), G.worlds[k].get("note", ""), font=F("mono", 22), fill=rgb("#3fd0ff"), anchor="lm")
    if blur > 2:                                                    # whip blur on the world layer only; the runner stays sharp
        img = Image.fromarray(hblur(np.asarray(img), blur))
    fh = G.fh
    J = rig(t, fig_x if fig_x is not None else G.fx, G.yg, fh, G.spb)
    if style == "cave":
        lay = Image.new("RGB", (W, H), (255, 255, 255))
        draw_rig(ImageDraw.Draw(lay), J, brush_cave(fi))
        img = Image.fromarray((np.asarray(img, np.float32) * np.asarray(lay, np.float32) / 255).astype(np.uint8))
    elif style == "crt":
        q = 6
        m = Image.new("L", (W // q, H // q), 0)
        Js = {kk: ((v[0] / q, v[1] / q) if isinstance(v, tuple) else v / q) for kk, v in J.items()}

        def pix(d, part, a, c, w, dep):
            if part == "head":
                d.ellipse([a[0] - w / 2, a[1] - w / 2, a[0] + w / 2, a[1] + w / 2], fill=255)
            else:
                capsule(d, a, c, max(1.0, w * 0.8), 255 if dep != "far" else 120)
        draw_rig(ImageDraw.Draw(m), Js, pix)
        img = paste_mask(img, m.resize((W, H), Image.NEAREST), (0, 0), rgb("#39ff7a"))
    elif style == "holo":
        lay = Image.new("RGB", (W, H), (0, 0, 0))
        ld = ImageDraw.Draw(lay)
        fx_, yg = J["hip"][0], G.yg
        ld.ellipse([fx_ - fh * 0.32, yg - 12, fx_ + fh * 0.32, yg + 12], outline=rgb("#3fd0ff"), width=3)
        draw_rig(ld, J, brush_line(rgb("#8fe9ff"), 3))
        la = np.asarray(lay, np.float32)
        band = 0.75 + 0.25 * np.sin(np.arange(H) * 0.35 + t * 20)[:, None, None]   # interlace shimmer
        glow = np.asarray(lay.filter(ImageFilter.GaussianBlur(9)), np.float32)
        cone = Image.new("L", (W, H), 0)
        ImageDraw.Draw(cone).polygon([(fx_ - fh * 0.32, yg), (fx_ + fh * 0.32, yg), (fx_ + fh * 0.5, yg - fh * 1.15),
                                      (fx_ - fh * 0.5, yg - fh * 1.15)], fill=40)
        cn = np.asarray(cone.filter(ImageFilter.GaussianBlur(20)), np.float32)[..., None] / 255
        a = np.asarray(img, np.float32) + la * band + glow * 1.6 + cn * np.array(rgb("#3fd0ff"), np.float32)
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    else:
        brush = {"egypt": brush_egypt, "greek": brush_greek, "glass": brush_glass}[style]()
        draw_rig(ImageDraw.Draw(img), J, brush)
    a = np.asarray(img)
    if style == "crt":
        a = crt_post(a, t, fi)
    return a


# ------------------------------------------------------------------ camera and end card
def cam(t):
    """Camera position along the strip of worlds: drift while a world holds, whip on each downbeat."""
    N = len(G.worlds)
    for k in range(1, N + 1):
        b = G.B[k]
        if t < b - WHIP:
            return (k - 1) * L + DRIFT * (t - G.B[k - 1])
        if t < b + WHIP:
            u0 = (k - 1) * L + DRIFT * (b - WHIP - G.B[k - 1])
            u1 = k * L + (DRIFT * WHIP if k < N else 0)
            return u0 + (u1 - u0) * ease_in_out(prog(t, b - WHIP, b + WHIP))
    return N * L


PAPER, INK, SIGNAL = "#f1eee6", "#141414", "#c8442a"


def hblur(a, n):
    """Horizontal box blur of n px (the whip's motion blur)."""
    cs = np.cumsum(np.pad(a.astype(np.float32), ((0, 0), (n + 1, n), (0, 0)), mode="edge"), axis=1)
    return ((cs[:, 2 * n + 1:] - cs[:, :-2 * n - 1]) / (2 * n + 1)).astype(np.uint8)


def end_frame(t, ok, blur=0):
    """Gallery world: the same figure in every world, side by side, then the title block."""
    lt = t - G.B[len(G.worlds)]
    a = np.empty((H, W, 3), np.uint8)
    a[:] = rgb(PAPER)
    n = len(G.worlds)
    gap = 16
    tw = min(172, (W - 120 - (n - 1) * gap) // n)
    th = int(tw * 1.4)
    x0 = (W - (n * tw + (n - 1) * gap)) // 2 - int(ok)
    y0 = 64
    cw, ch = 300, 420                                               # crop around the figure in its own world
    cx, cy = W // 2 + 20, G.yg - ch // 2 + 40
    for i in range(n):
        p = ease_out(prog(lt, 0.25 + i * 0.25, 0.6 + i * 0.25))
        if p <= 0:
            continue
        fr = world_frame(i, t, L * 0.1, fig_x=W // 2, show_kw=False)
        crop = Image.fromarray(fr[cy - ch // 2:cy + ch // 2, cx - cw // 2:cx + cw // 2]).resize((tw, th), Image.LANCZOS)
        hh = max(1, int(th * p))                                    # the tile wipes up from its base
        x = x0 + i * (tw + gap)
        xa, xb = max(0, x), min(W, x + tw)
        if xb > xa:
            a[y0 + th - hh:y0 + th, xa:xb] = np.asarray(crop)[th - hh:, xa - x:xb - x]
    img = Image.fromarray(a)
    for i in range(n):
        p = prog(lt, 0.45 + i * 0.25, 0.8 + i * 0.25)
        if p > 0:
            m, _, _ = rise_mask(G.worlds[i]["year"], F("mono", 20), p)
            img = paste_mask(img, m, (x0 + i * (tw + gap), y0 + th + 8), rgb(INK))
    c = G.c
    m, mw, _ = rise_mask(c["title"], F("serif", 112), prog(lt, 3.0, 3.5))
    img = paste_mask(img, m, ((W - mw) // 2 - int(ok), 372), rgb(INK))
    m, mw, _ = rise_mask(c["details"], F("sans_medium", 34), prog(lt, 3.5, 3.9))
    img = paste_mask(img, m, ((W - mw) // 2 - int(ok), 520), rgb(INK))
    m, mw, _ = rise_mask(c["url"], F("mono_medium", 30), prog(lt, 4.0, 4.4))
    img = paste_mask(img, m, ((W - mw) // 2 - int(ok), 580), rgb(SIGNAL))
    return hblur(np.asarray(img), blur) if blur > 2 else np.asarray(img)


def film(t):
    u = cam(t)
    N = len(G.worlds)
    n = int(abs(cam(t + 0.5 / G.fps) - cam(t - 0.5 / G.fps)) * 0.4)   # whip blur length (px), part shutter
    out = np.empty((H, W, 3), np.uint8)
    for k in range(N + 1):
        x0 = k * L - u
        x1 = x0 + L if k < N else 10 ** 6
        a, b = int(max(0, math.floor(x0))), int(min(W, math.ceil(x1)))
        if b <= a:
            continue
        fr = world_frame(k, t, u - k * L, blur=n) if k < N else end_frame(t, u - k * L, n)
        out[:, a:b] = fr[:, a:b]
    return out


def wrap(s, font, max_w):
    lines, cur = [], ""
    for w in s.split():
        if cur and text_width(cur + " " + w, font) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def reel(fr):
    """9:16 wrapper: blurred cover of the film, the film in the middle band, a fixed hook line on top."""
    cw = int(H * RW / RH)
    small = Image.fromarray(fr[:, (W - cw) // 2:(W + cw) // 2]).resize((RW // 12, RH // 12), Image.BILINEAR)
    bg = small.filter(ImageFilter.GaussianBlur(3)).resize((RW, RH), Image.BILINEAR)
    a = (np.asarray(bg, np.float32) * 0.5).astype(np.uint8)
    fh = int(H * RW / W)
    fy = (RH - fh) // 2 + 40
    a[fy:fy + fh] = np.asarray(Image.fromarray(fr).resize((RW, fh), Image.LANCZOS))
    img = Image.fromarray(a)
    f = F("sans_bold", 76)
    lines = wrap(G.c["hook"], f, RW - 140)
    sh = Image.new("L", (RW, RH), 0)
    sd = ImageDraw.Draw(sh)
    y = fy - 90 - (len(lines) - 1) * 92
    for ln in lines:
        sd.text((RW // 2, y), ln, font=f, anchor="ms", fill=255)
        y += 92
    img = paste_mask(img, sh.filter(ImageFilter.GaussianBlur(10)), (0, 6), (0, 0, 0), alpha=0.85)
    img = paste_mask(img, sh, (0, 0), rgb(G.b.get("hook_color", "#ffe14d")))
    if G.c.get("footer"):
        ImageDraw.Draw(img).text((RW // 2, fy + fh + 120), G.c["footer"], font=F("sans_medium", 44), anchor="ms",
                                 fill=(238, 236, 230))
    return np.asarray(img)


def frame(c):
    fr = film(c.t)
    return reel(fr) if G.fmt == "reel" else fr


# ------------------------------------------------------------------ score
def score(path):
    N = len(G.worlds)
    sc = Score(G.bpm, G.dur + 0.3)
    end = G.B[N] / sc.spb
    sc.pattern("kick", 1, 0, end)
    sc.pattern("hat", 0.5, 0.5, end, 0.5)
    sc.pattern("snare", 2, 1, end, 0.7)
    roots = ["A1", "F1", "C2", "G1", "D2", "E2", "A1", "F1"]
    per = G.beats
    for k in range(N):
        r = roots[k % len(roots)]
        sc.bass([(r, 0, 0.5), (r, 0.75, 0.25), (r, 1.5, 0.5), (r, per - 1.5, 0.5), (r, per - 0.75, 0.5)], G.B[k], 0.9)
        if k:
            sc.add(riser(0.32, k), G.B[k] - 0.32, 0.8)
            sc.hit("thud", G.B[k], 1.0)
    b = G.B[N]
    sc.add(riser(0.32, 99), b - 0.32, 0.8)
    sc.hit("thud", b, 1.0)
    notes = ["A4", "C5", "E5", "G5", "A5", "C6", "E6", "G6"]
    for i in range(N):
        sc.add(blip(notes[i % 8], 0.12), b + 0.25 + i * 0.25, 0.6)
    sc.chord(["A2", "E3", "A3", "C4", "E4"], b, G.dur - b + 0.3, 1.0)
    sc.hit("thud", b + 3.0, 0.8)
    sc.hit("slap", b + 3.5, 0.6)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
class State:
    def __init__(self, brief, fmt):
        self.b, self.c = brief, brief["copy"]
        self.fps = brief.get("fps", 30)
        self.bpm = brief.get("bpm", 120)
        self.spb = 60 / self.bpm
        self.worlds = brief["worlds"]
        self.beats = brief.get("beats_per_world", 4)
        self.B = [k * self.beats * self.spb for k in range(len(self.worlds) + 1)]
        self.dur = self.B[-1] + brief.get("end_hold", 6.5)
        self.fmt = fmt or brief.get("format", "reel")
        self.fh, self.fx, self.yg = int(H * 0.47), int(W * 0.27), int(H * 0.84)
        self.kx, self.ky = int(W * 0.50), int(H * 0.22)
        rng = np.random.default_rng(brief.get("seed", 7))
        self.plates, self.cells, self.cellph = [], {}, {}
        makers = {"cave": plate_cave, "egypt": plate_egypt, "greek": plate_greek, "crt": plate_crt, "holo": plate_holo}
        for k, w in enumerate(self.worlds):
            if w.get("style") == "glass":
                p, cid = plate_glass(rng)
                self.cells[k], self.cellph[k] = cid, rng.uniform(0, 6.28, int(cid.max()) + 1).astype(np.float32)
            elif w.get("style") in makers:
                p = makers[w["style"]](rng)
            else:
                p = np.zeros((H, L, 3), np.uint8)
            self.plates.append(p)
        yy, xx = np.mgrid[0:H, 0:W]                                 # CRT tube: vignette + bezel, built once
        v = 1 - 0.55 * (((xx - W / 2) / (W / 2)) ** 4 + ((yy - H / 2) / (H / 2)) ** 4)
        bez = Image.new("L", (W, H), 0)
        ImageDraw.Draw(bez).rounded_rectangle([18, 14, W - 18, H - 14], radius=60, fill=255)
        bz = np.asarray(bez.filter(ImageFilter.GaussianBlur(3)), np.float32)[..., None] / 255
        self.crt_vig = (np.clip(v, 0, 1)[..., None] * bz).astype(np.float32)
        self.crt_bezel = ((1 - bz) * np.array(rgb("#1a1a17"), np.float32)).astype(np.float32)


def build(path, fmt=None):
    global G
    brief = json.load(open(path))
    G = State(brief, fmt)
    size = (RW, RH) if G.fmt == "reel" else (W, H)
    return Timeline([Scene("hop", G.dur, frame)], size[0], size[1], G.fps, data=G), brief


def check(tl):
    errs = []
    for k in ("hook", "title", "details", "url"):
        if not G.c.get(k):
            errs.append(f"copy.{k} missing")
    if not 3 <= len(G.worlds) <= 8:
        errs.append("use 3 to 8 worlds")
    for w in G.worlds:
        if w.get("style") not in STYLES:
            errs.append(f"unknown style {w.get('style')!r}; pick from {', '.join(STYLES)}")
            continue
        role, size, _, _, track = TYPE[w["style"]]
        need = text_width(label_of(w), F(role, size), track)
        if need > W - G.kx - 30:
            errs.append(f"{w['style']} label {w['label']!r} needs {need:.0f}px, the right half has {W - G.kx - 30}")
    for s in [G.c.get(k, "") for k in ("hook", "title", "details", "url", "footer")] + [w["label"] for w in G.worlds]:
        if s.rstrip().endswith("."):
            errs.append(f"trailing period: {s!r}")
    if len(wrap(G.c.get("hook", ""), F("sans_bold", 76), RW - 140)) > 2:
        errs.append("hook wraps past two lines; keep it under about 26 characters")
    for k, f in (("title", F("serif", 112)), ("details", F("sans_medium", 34)), ("url", F("mono_medium", 30))):
        if text_width(G.c.get(k, ""), f) > W - 80:
            errs.append(f"copy.{k} is wider than the frame")
    print(f"{G.dur:.2f}s, {len(G.worlds)} worlds × {G.beats} beats at {G.bpm} BPM, {tl.n_frames} frames, "
          f"{'1080×1920 reel' if G.fmt == 'reel' else '1280×720'}")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "walk-cycle", "brief.json"))
    ap.add_argument("--format", choices=["reel", "wide"])
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief, a.format)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("fully procedural: every world is drawn in scripts/main.py.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{G.fmt}_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, f"contact_sheet_{G.fmt}.png"), cols=6, rows=4, thumb_w=240))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, f"world-hop-reel-{G.fmt}.mp4"), audio))


if __name__ == "__main__":
    main()
