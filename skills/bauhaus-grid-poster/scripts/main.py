#!/usr/bin/env python3
"""bauhaus-grid-poster: a kinetic Bauhaus / Swiss poster that assembles itself on a module grid at 120 BPM.

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 2 9.5 14.8
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json            # synthesise the soundtrack only
    python3 main.py render --brief brief.json [--audio track.m4a]

Every move is a whole number of modules and lands on a grid line on the beat; easing is in-out quad
with no overshoot. Four ink plates (red, yellow, blue, black) are multiplied onto paper with drifting
misregistration until the "press lock" beat snaps them into register.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Scene, Theme, Timeline, h, prog, text, text_width, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith import press
from framesmith.score import Score

G = None


def quad(p):
    p = min(1.0, max(0.0, p))
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


class State:
    def __init__(self, brief, base):
        self.b, self.c, self.base = brief, brief["copy"], base
        self.th = Theme.from_dict(brief.get("theme"))
        x = self.th.extra
        self.red, self.yellow, self.blue = x["red"], x["yellow"], x["blue"]
        self.W, self.H = brief.get("size", [1080, 1350])
        self.cols, self.rows = brief.get("grid", [8, 10])
        self.M = self.W / self.cols
        self.bpm = brief.get("bpm", 120)
        self.spb = 60 / self.bpm
        self.fps = brief.get("fps", 30)
        self.beats = brief.get("beats", 40)
        self.lock = brief.get("press_lock_beat", 30)
        self.seed = brief.get("seed", 7)
        self.logo = None
        lp = brief.get("meta", {}).get("logo")
        if lp:
            im = Image.open(os.path.join(base, lp)).convert("RGBA")
            self.logo = im.crop(im.getbbox())


# ------------------------------------------------------------------ geometry (module units, y down)
def arc(cx, cy, r, a0, a1, n=48):
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)


def circle(cx, cy, r):
    return arc(cx, cy, r, 0, 360, 96)


def quarter(px, py, r, a0):
    """Quarter disc with its right-angle corner at (px, py), opening from angle a0 (deg, clockwise)."""
    return np.vstack([[[px, py]], arc(px, py, r, a0, a0 + 90, 40)])


def semi(cx, cy, r, a0):
    return arc(cx, cy, r, a0, a0 + 180, 64)


def rect(x, y, w, hh):
    return np.array([[x, y], [x + w, y], [x + w, y + hh], [x, y + hh]], np.float32)


def tri(*pts):
    return np.array(pts, np.float32)


def rot(pts, pivot, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    q = pts - pivot
    return np.stack([q[:, 0] * c - q[:, 1] * s, q[:, 0] * s + q[:, 1] * c], 1) + pivot


def scl(pts, pivot, sx, sy):
    return (pts - pivot) * np.array([sx, sy]) + pivot


def detent(p, teeth):
    """Escapement: the turn advances in `teeth` quick steps with a hold between each."""
    u = p * teeth
    n = math.floor(u)
    if n >= teeth:
        return 1.0
    return (n + quad(min(1.0, (u - n) * 2.5))) / teeth


# ------------------------------------------------------------------ the cue sheet
# Each element: ink, base polygon, and actions [(land_beat, kind, params, dur_beats)].
# kinds: "in" (grow from pivot), "rot" (deg about pivot), "slide" (dx, dy modules), "flip" (x or y about pivot).
# One element acts per beat during the assembly, and every action lands on its beat.
# Rotation pivots alternate between an element's own centre, a corner, and the frame-centre group turn.
def elements():
    C = G.cols
    return [
        dict(name="sun", ink="red", pts=circle(2, 3, 2), start=dict(dy=-5),
             acts=[(2, "slide", dict(dx=0, dy=5), 2.2), (7, "slide", dict(dx=1, dy=0), 1)]),
        dict(name="fan", ink="yellow", pts=quarter(C, 0, 3, 90), start=dict(rot=((C, 0), -90)),
             acts=[(4, "rot", dict(pivot=(C, 0), deg=90), 1)]),
        dict(name="dome", ink="blue", pts=semi(5, 7, 2, 180), start=dict(dx=3),
             acts=[(5, "slide", dict(dx=-3, dy=0), 1)]),
        dict(name="beam", ink="black", pts=rect(0, 7, 6, 0.25),
             acts=[(6, "in", dict(pivot=(0, 7.125), axis="x"), 1)]),
        dict(name="wedge", ink="yellow", pts=tri((0, 10), (3, 10), (0, 7.25)),
             acts=[(8, "flip", dict(pivot=(1.5, 10), axis="x"), 1)]),
        dict(name="slab_l", ink="blue", pts=rect(5, 5, 1, 2), acts=[(9, "in", dict(pivot=(5, 7), axis="y"), 1)]),
        dict(name="slab_r", ink="blue", pts=rect(5, 5, 1, 2),
             acts=[(9, "in", dict(pivot=(5, 7), axis="y"), 1), (10, "slide", dict(dx=1, dy=0), 1)]),
        dict(name="dot", ink="black", pts=circle(6.5, 2.5, 0.5),
             acts=[(11, "in", dict(pivot=(6.5, 2.5), axis="xy"), 0.5), (14, "slide", dict(dx=0, dy=1), 1)]),
        dict(name="key", ink="red", pts=quarter(1, 7, 1, 180),
             acts=[(12, "in", dict(pivot=(1, 7), axis="xy"), 1), (15, "rot", dict(pivot=(1, 7), deg=90), 1)]
             + [(G.lock + 4 + 4 * i, "rot", dict(pivot=(1, 7), deg=90), 1) for i in range(3)]),
        dict(name="eye", ink="black", pts=quarter(3, 3, 1, 270),
             acts=[(19, "in", dict(pivot=(3, 3), axis="xy"), 1), (21, "rot", dict(pivot=(3.5, 2.5), deg=180), 1)]),
    ]


GROUP_TURN = (16, 18.5)           # beats: the top 8×8 block turns 90° about its centre, in 12 teeth of 7.5°
TURN_TEETH = 12
WAVE = (24, 30)                   # beats: the cascade (the hero, ~60–75 % in)
FIXED = ("fan", "beam", "wedge", "slab_l", "slab_r", "key")


def place(el, b):
    """Polygon of an element at beat b (module units), or None before it enters."""
    pts = el["pts"].copy()
    st = el.get("start", {})
    if "dx" in st or "dy" in st:
        pts = pts + np.array([st.get("dx", 0), st.get("dy", 0)])
    if "rot" in st:
        pts = rot(pts, np.array(st["rot"][0], np.float32), st["rot"][1])
    land0, kind0, _, dur0 = el["acts"][0]
    if b < land0 - dur0 and kind0 in ("in", "flip"):
        return None
    for land, kind, kw, dur in el["acts"]:
        p = quad(prog(b, land - dur, land))
        if kind == "slide":
            pts = pts + np.array([kw["dx"], kw["dy"]]) * p
        elif kind == "rot":
            pts = rot(pts, np.array(kw["pivot"], np.float32), kw["deg"] * p)
        else:
            k = (-1 + 2 * p) if kind == "flip" else p
            k = k if abs(k) > 0.02 else 0.02
            sx = k if "x" in kw["axis"] else 1
            sy = k if "y" in kw["axis"] else 1
            pts = scl(pts, np.array(kw["pivot"], np.float32), sx, sy)
    turn = detent(prog(b, *GROUP_TURN), TURN_TEETH)
    if turn > 0 and el["name"] not in FIXED:
        pts = rot(pts, np.array([G.cols / 2, G.cols / 2], np.float32), 90 * turn)
    return pts


# ------------------------------------------------------------------ drawing
def poly_mask(polys):
    M = G.M

    def draw(d, s):
        for p in polys:
            d.polygon([(float(x) * M * s, float(y) * M * s) for x, y in p], fill=255)
    return press.mask_from(draw, (G.W, G.H), 2)


def grid_mask(b):
    """Grid lines draw on over the first two bars: verticals top→down, horizontals left→right, staggered."""
    M, W, H = G.M, G.W, G.H

    def draw(d, s):
        lw = 2
        for i in range(1, G.cols):
            p = quad(prog(b, 0.15 * i - 0.6, 0.15 * i + 2.2))
            if p > 0:
                d.line((i * M * s, 0, i * M * s, H * p * s), fill=255, width=lw)
        for j in range(1, G.rows):
            p = quad(prog(b, 0.12 * j, 0.12 * j + 2.4))
            if p > 0:
                d.line((0, j * M * s, W * p * s, j * M * s), fill=255, width=lw)
    return press.mask_from(draw, (W, H), 1) * 0.22


def wave_mask(b):
    """The drop: a quarter disc grows in every cell and turns 90° a beat, phase-delayed along the diagonal."""
    a, z = WAVE
    if b < a - 1 or b > z + 4:
        return None
    polys = []
    for r in range(G.rows):
        for c in range(G.cols):
            ph = (c + r) * 0.125
            k = quad(prog(b, a - 1 + ph, a + ph)) * (1 - quad(prog(b, z - 0.5 + ph, z + 0.5 + ph)))
            if k <= 0.01:
                continue
            turns = min(z - a - 1.0, max(0.0, b - a - ph))
            ang = 90 * (math.floor(turns) + quad(turns - math.floor(turns)))
            q = quarter(c, r, k, 0)
            polys.append(rot(q, np.array([c + 0.5, r + 0.5], np.float32), ang))
    return poly_mask(polys) if polys else None


def type_mask(b):
    """Black-plate typography set flush-left on grid lines."""
    c, M = G.c, G.M
    m = Image.new("L", (G.W, G.H), 0)
    d = ImageDraw.Draw(m)
    if b >= 12:                                               # masthead, top-left, on beat 12
        text(d, (0.18 * M, 0.2 * M), c["brand"].upper(), F("sans_black", 24), 255, 2.5, max_w=3.5 * M)
        text(d, (0.18 * M, 0.2 * M + 32), c["edition"], F("sans_medium", 22), 255, 0.3, max_w=3.5 * M)
    if b >= 6.5:                                              # small caps riding the beam
        text(d, (0.18 * M, 6.7 * M), c["sub"].upper(), F("sans_bold", 19), 255, 4, max_w=5.6 * M)
    p = prog(b, 20, 22)                                       # vertical title, wiped up the last column
    if p > 0:
        title = c["title"].upper()
        f = F("sans_black", int(M * 1.38))
        budget = (G.rows - 0.4) * M
        tw = min(text_width(title, f, -4), budget)
        L = Image.new("L", (int(tw + 40), int(M * 1.3)), 0)
        text(ImageDraw.Draw(L), (0, M * 1.3 - 6), title, f, 255, -4, "ls", max_w=budget)
        L = L.rotate(90, expand=True)
        cut = int(L.height * (1 - quad(p)))
        crop = L.crop((0, cut, L.width, L.height))
        m.paste(crop, (int(G.W - L.width + 6), int(G.H - 0.15 * M - crop.height)), crop)
    for i, s in enumerate(c["facts"]):                        # facts type in one per beat after the lock
        bi = G.lock + 1 + i
        if b < bi - 0.5:
            break
        k = quad(prog(b, bi - 0.5, bi))
        part = s[:max(1, int(round(len(s) * k)))]
        role, size, tr = ("sans_black", 34, -0.3) if i == 0 else ("sans_medium", 25, 0.2)
        y = 7.45 * M + (0 if i == 0 else 20 + i * 34)
        text(d, (3.15 * M, y), part, F(role, size), 255, tr, max_w=3.55 * M, fit_to=s)
    if b >= G.lock + 2 + len(c["facts"]):
        text(d, (3.15 * M, 9.68 * M), c["url"], F("sans_bold", 22), 255, 1, "ls", max_w=3.55 * M)
    return np.asarray(m, np.float32) / 255


def logo_on(out, b):
    if G.logo is None or b < G.lock + 2 + len(G.c["facts"]):
        return out
    im = Image.fromarray(out)
    hh = int(G.M * 0.32)
    lg = G.logo.resize((max(1, int(G.logo.width * hh / G.logo.height)), hh), Image.LANCZOS)
    im.paste(lg, (int(G.M * 6.95 - lg.width), int(G.M * 9.75 - hh)), lg)
    return np.asarray(im)


def frame(c):
    b = c.t / G.spb
    inks = {"red": [], "yellow": [], "blue": [], "black": []}
    for el in elements():
        p = place(el, b)
        if p is not None:
            inks[el["ink"]].append(p)
    masks = {k: (poly_mask(v) if v else None) for k, v in inks.items()}
    # misregistration: plates drift 1–4 px on slow seeded sines, then lock into register on the press beat
    lock = quad(prog(b, G.lock - 0.35, G.lock))

    def off(i):
        a = 1 - lock
        ph = h(G.seed, i) * 6.28
        return (round((1.5 + 2.5 * h(G.seed, i, 1)) * math.sin(c.t * 0.9 + ph) * a),
                round((1 + 2 * h(G.seed, i, 2)) * math.cos(c.t * 0.7 + ph) * a))
    layers = [(grid_mask(b), G.th.ink, None)]
    for i, k in enumerate(("yellow", "red", "blue")):
        if masks[k] is not None:
            layers.append((masks[k], getattr(G, k), off(i)))
    wm = wave_mask(b)
    if wm is not None:
        layers.append((wm, G.th.ink, off(5)))
    black = type_mask(b)
    if masks["black"] is not None:
        black = np.maximum(black, masks["black"])
    layers.append((black, G.th.ink, off(4)))
    dens = 1.0 + 0.12 * (1 - prog(b, G.lock, G.lock + 2)) * (b >= G.lock)       # +ink on the lock, settling
    ground = press.paper((G.W, G.H), G.th.paper, G.seed, 0.07)
    out = logo_on(press.plates(ground, layers, press.tooth((G.W, G.H), G.seed), 0.2, dens), b)
    if G.lock <= b < G.lock + 0.12:                                                # the paper jolts 2 px
        out = np.roll(out, 2, 0)
    return out


# ------------------------------------------------------------------ sound: the same cue sheet as the picture
def score(path):
    sc = Score(G.bpm, G.beats * G.spb + 0.6)
    lands = sorted({a[0] for el in elements() for a in el["acts"]})
    pitches = [1.0, 1.12, 1.26, 1.33, 1.5, 1.68, 1.89, 2.0]
    for i, k in enumerate(lands):
        sc.hit("clack", sc.beat(k), 0.9, pan=(i % 3 - 1) * 0.35, pitch=pitches[i % len(pitches)])
    sc.pattern("tick", every=0.5, start=0, end=4, gain=0.5)
    sc.pattern("kick", every=1, start=4, end=G.beats - 2, gain=0.9, skip=(G.lock,))
    sc.pattern("hat", every=0.5, start=8.5, end=G.beats - 2, gain=0.5)
    a, z = GROUP_TURN
    for k in range(TURN_TEETH):                                                   # escapement teeth
        sc.hit("tick", sc.beat(a + (k + 0.4) * (z - a) / TURN_TEETH), 0.7, pitch=0.6)
    notes = ["A5", "C6", "D6", "E6", "G6", "A6", "C7", "D7"]
    for r in range(4):
        for k in range(WAVE[0], WAVE[1]):
            sc.hit("blip", sc.beat(k + r * 0.25), 0.5, pan=(r - 1.5) * 0.3, note=notes[(k + r) % len(notes)])
    sc.hit("riser", sc.beat(G.lock - 2), 0.8)
    sc.hit("thud", sc.beat(G.lock), 1.4)
    sc.hit("kick", sc.beat(G.lock), 1.2)
    bass = [("A1", 0, 2), ("A1", 2, 1), ("C2", 3, 1), ("D2", 4, 2), ("E2", 6, 1), ("G1", 7, 1)]
    for bar in range(1, G.beats // 8):
        sc.bass(bass, start=sc.beat(bar * 8), gain=0.55)
    sc.chord(["A3", "C4", "E4", "G4"], sc.beat(G.lock), (G.beats - G.lock) * G.spb, 0.8)
    for i in range(len(G.c["facts"]) + 1):
        sc.hit("clack", sc.beat(G.lock + 1 + i), 0.6, pitch=2.2)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("poster", G.beats * G.spb, frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    for k in ("brand", "edition", "title", "sub", "facts", "url"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
    for s in [G.c.get("title", ""), G.c.get("sub", ""), G.c.get("url", "")] + G.c.get("facts", []):
        if s.rstrip().endswith("."):
            errs.append(f"trailing period: {s!r}")
    if len(G.c.get("title", "")) > 7:
        errs.append("title longer than 7 letters loses its one-module cap height; shorten it")
    if len(G.c.get("facts", [])) > 4:
        errs.append("at most 4 facts fit the block")
    if errs:
        for e in errs:
            print("✗", e)
        return False
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.2, tl.duration - 0.05, 24):
        tl.frame(int(t * tl.fps))
    rep = overflow_report(warn=True)
    if OVERFLOWS:
        errs.append(rep)
    elif SHRINKS:
        print("warn:", rep)
    print(f"{tl.duration:.2f}s, {tl.n_frames} frames at {tl.fps} fps, {G.beats} beats at {G.bpm} BPM, press lock on beat {G.lock}")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "vesna", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("fully procedural: no image slots. Set meta.logo to the brand's real logo file if it has one.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=8, rows=3, thumb_w=200))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, "bauhaus-grid-poster.mp4"), audio))


if __name__ == "__main__":
    main()
