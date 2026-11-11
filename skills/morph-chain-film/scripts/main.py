#!/usr/bin/env python3
"""morph-chain-film: one hero shape becomes a chain of icons on the beat (1:1, 120 BPM, 20 s).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 0.5 1.6 2.6 3.4 7 11 13.5 17
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

Every A → B goes through a circle with a turn and 10–15 % squash and stretch. Outlines are resampled
by arc length from the top, clockwise, so no morph knots. The ground changes with a clean colour-block
wipe on each morph, and a caption with one concrete fact lands with each icon. The last shape is the
app icon: the first shape is cut back into it and the wordmark rises beside it.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Scene, Theme, Timeline, hex2rgb, prog, text, text_width, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.score import Score

G = None
N = 360
SS = 2


def ease(p):
    """cubic-bezier(0.7, 0, 0.3, 1)-like."""
    p = min(1.0, max(0.0, p))
    return 8 * p ** 4 if p < 0.5 else 1 - 8 * (1 - p) ** 4


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def lerp(a, b, p):
    return a + (b - a) * p


# ------------------------------------------------------------------ shapes (unit size, y down, centred)
def polar(fn, n=720):
    th = np.linspace(-math.pi / 2, 3 * math.pi / 2, n, endpoint=False)
    r = np.array([fn(a) for a in th])
    return np.stack([r * np.cos(th), r * np.sin(th)], 1)


def s_drop():
    t = np.linspace(0, 2 * math.pi, 720, endpoint=False)
    x = 0.78 * np.sin(t) * np.abs(np.sin(t / 2)) ** 1.25
    y = -np.cos(t) * 0.95
    return np.stack([x, y + 0.08], 1)


def s_pin():
    t = np.linspace(0, 2 * math.pi, 720, endpoint=False)
    x = 0.82 * np.sin(t) * np.abs(np.sin(t / 2)) ** 0.75
    y = np.cos(t) * 0.98
    return np.stack([x, y - 0.06], 1)


def s_cloud():
    circles = [(-0.5, 0.1, 0.4), (-0.05, -0.2, 0.55), (0.5, 0.06, 0.44), (-0.22, 0.18, 0.4), (0.24, 0.18, 0.4)]

    def r(a):
        d = np.array([math.cos(a), math.sin(a)])
        best = 0.0
        for cx, cy, R in circles:
            c = np.array([cx, cy])
            b = d @ c
            disc = b * b - c @ c + R * R
            if disc >= 0:
                best = max(best, b + math.sqrt(disc))
        if d[1] > 1e-6:                                              # a flat base
            best = min(best, 0.46 / d[1])
        return best
    return polar(r)


def s_sun():
    return polar(lambda a: 0.6 + 0.36 * (0.5 + 0.5 * math.cos(12 * (a + math.pi / 2))) ** 5)


def s_leaf():
    """A vesica (two circular arcs meeting in points), tipped 35°."""
    R, dd = 1.0, 0.8
    hh = math.sqrt(R * R - dd * dd)
    y = np.linspace(-hh, hh, 360)
    xr = np.sqrt(R * R - y * y) - dd
    pts = np.vstack([np.stack([xr, y], 1), np.stack([-xr[::-1], y[::-1]], 1)[1:-1]]) * 1.55
    a = math.radians(35)
    x, y = pts[:, 0], pts[:, 1]
    return np.stack([x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)], 1)


def s_bell():
    def bz(p0, p1, p2, p3, n=60):
        t = np.linspace(0, 1, n)[:, None]
        return (1 - t) ** 3 * np.array(p0) + 3 * (1 - t) ** 2 * t * np.array(p1) + 3 * (1 - t) * t ** 2 * np.array(p2) + t ** 3 * np.array(p3)
    right = np.vstack([bz((0, -0.92), (0.12, -0.92), (0.13, -0.78), (0.1, -0.72), 20),
                       bz((0.1, -0.72), (0.5, -0.66), (0.52, -0.2), (0.56, 0.2)),
                       bz((0.56, 0.2), (0.6, 0.45), (0.86, 0.5), (0.86, 0.6), 30),
                       bz((0.86, 0.6), (0.6, 0.6), (0.3, 0.6), (0.2, 0.6), 20),
                       bz((0.2, 0.6), (0.18, 0.86), (0.02, 0.9), (0, 0.9), 20)])
    left = right[::-1] * np.array([-1, 1])
    return np.vstack([right, left[1:]]) + np.array([0, 0.02])


def s_squircle():
    return polar(lambda a: 0.86 / (abs(math.cos(a)) ** 5 + abs(math.sin(a)) ** 5) ** (1 / 5))


def s_circle():
    return polar(lambda a: 0.8)


SHAPES = {"drop": s_drop, "pin": s_pin, "cloud": s_cloud, "sun": s_sun, "leaf": s_leaf, "bell": s_bell,
          "squircle": s_squircle, "circle": s_circle}


def resample(poly, n=N):
    """Arc-length resample, clockwise (y down), starting at the point nearest straight up from the centroid."""
    poly = np.asarray(poly, np.float64)
    area = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
    if area < 0:
        poly = poly[::-1]
    closed = np.vstack([poly, poly[:1]])
    seg = np.sqrt((np.diff(closed, axis=0) ** 2).sum(1))
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n, endpoint=False)
    pts = np.stack([np.interp(s, cum, closed[:, 0]), np.interp(s, cum, closed[:, 1])], 1)
    c = pts.mean(0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    k = int(np.argmin(np.abs((ang + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi)))
    return np.roll(pts, -k, 0)


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        self.W, self.H = brief.get("size", [1080, 1080])
        self.fps = brief.get("fps", 30)
        self.spb = 60 / brief.get("bpm", 120)
        self.S = self.W / 1080
        self.chain = brief["chain"]
        self.pal = [(hex2rgb(a), hex2rgb(b)) for a, b in brief["palette"]]
        self.shapes = [resample(SHAPES[x["shape"]]()) for x in self.chain]
        self.circle = resample(s_circle())


def B(k):
    return k * G.spb


def land(i):
    """Beat on which shape i lands."""
    return 2 + 4 * i


MORPH = 1.6          # beats per morph, ending on the landing beat
CUSHION = 3          # frames of hold at both ends


def morph_state(b):
    """(index of current shape, morph progress 0..1 toward the next, or None while holding)."""
    n = len(G.shapes)
    for i in range(1, n):
        a, z = land(i) - MORPH, land(i)
        if b < a:
            return i - 1, None
        if b < z:
            cus = CUSHION / G.fps / G.spb
            return i - 1, prog(b, a + cus, z - cus)
    return n - 1, None


def outline_at(b):
    i, p = morph_state(b)
    if p is None:
        return G.shapes[i], 0.0, 1.0, 1.0
    q = ease(p)
    A, Bp = G.shapes[i], G.shapes[i + 1]
    mid = G.circle
    pts = lerp(A, mid, q * 2) if q < 0.5 else lerp(mid, Bp, (q - 0.5) * 2)
    rot = 70 * math.sin(math.pi * q)                                 # a turn through the circle
    sq = 0.13 * math.sin(2 * math.pi * q)                            # stretch on the way in, squash on the way out
    return pts, rot, 1 + sq, 1 - sq


def colours(b):
    """(old ground, old ink, new ground, new ink, wipe 0..1). Colour blocks wipe up during each morph."""
    i, p = morph_state(b)
    pal = G.pal
    if p is None:
        g, f = pal[i % len(pal)]
        return g, f, g, f, 0.0
    g0, f0 = pal[i % len(pal)]
    g1, f1 = pal[(i + 1) % len(pal)]
    return g0, f0, g1, f1, ease(prog(p, 0.25, 0.8))


def shape_mask(pts, cx, cy, scale, rot, sx, sy, extra=None):
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    q = pts * np.array([sx, sy])
    q = np.stack([q[:, 0] * c - q[:, 1] * s, q[:, 0] * s + q[:, 1] * c], 1) * scale + np.array([cx, cy])
    m = Image.new("L", (G.W * SS, G.H * SS), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(x * SS, y * SS) for x, y in q], fill=255)
    if extra is not None:
        e = extra * np.array([1, 1]) * scale + np.array([cx, cy])
        d.polygon([(x * SS, y * SS) for x, y in e], fill=0)
    return np.asarray(m.reduce(SS), np.float32) / 255


def frame(ctx):
    b = ctx.t / G.spb
    W, H, S = G.W, G.H, G.S
    g0, f0, g1, f1, wipe = colours(b)
    pts, rot, sx, sy = outline_at(b)
    cx, cy, scale = W / 2, H * 0.44, 300 * S
    # intro: the first shape drops in and squashes on its landing beat
    if b < land(0):
        fall = prog(b, 0, land(0))
        cy = lerp(-H * 0.4, H * 0.44, fall ** 2)
        sy *= 1 + 0.18 * fall ** 6
        sx *= 1 - 0.1 * fall ** 6
    k = b - land(0)
    if 0 <= k < 0.6:                                                 # landing squash, settling
        e = math.exp(-k * 8) * math.cos(k * 14)
        sx *= 1 + 0.14 * e
        sy *= 1 - 0.14 * e
    # outro: the icon slides left and the first shape is cut back into it; the wordmark rises
    last = land(len(G.shapes) - 1)
    out = eo(prog(b, last + 2, last + 3))
    cx = lerp(cx, W * 0.27, out)
    cy = lerp(cy, H * 0.47, out)
    scale *= lerp(1.0, 0.56, out)
    cut = None
    cp = eo(prog(b, last + 0.5, last + 1.5))
    if cp > 0 and morph_state(b)[1] is None and morph_state(b)[0] == len(G.shapes) - 1:
        cut = G.shapes[0] * 0.5 * cp
    sm = shape_mask(pts, cx, cy, scale, rot, sx, sy, cut)
    # colour-block wipe from the bottom; the shape and captions change ink where the new block is
    edge = H * (1 - wipe)
    rows = (np.arange(H)[:, None] >= edge).astype(np.float32)
    g = np.array(g0, np.float32) * (1 - rows[..., None]) + np.array(g1, np.float32) * rows[..., None]
    f = np.array(f0, np.float32) * (1 - rows[..., None]) + np.array(f1, np.float32) * rows[..., None]
    img = g * np.ones((H, W, 1), np.float32)
    tm = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(tm)
    i, p = morph_state(b)
    cap = G.chain[i].get("caption", "")
    if cap:
        t_in = eo(prog(b, land(i) + 0.15, land(i) + 0.7))
        t_out = 1.0 if p is None else 1 - eo(prog(p, 0.0, 0.3))
        q = min(t_in, t_out)
        if q > 0:
            f_c = F("sans_black", int(54 * S))
            lines = balance(cap, f_c, W - 140 * S)
            for j, ln in enumerate(lines):
                y = H - 110 * S - (len(lines) - 1 - j) * 62 * S + (1 - q) * 40 * S
                text(d, (70 * S, y), ln, f_c, int(255 * q), -0.5, "ls", max_w=W - 140 * S)
    if out > 0:
        wq = eo(prog(b, last + 2.5, last + 3.5))
        f_w = F("sans_black", int(150 * S))
        text(d, (W * 0.47, H * 0.5 + 30 * S + (1 - wq) * 60 * S), G.c["brand"], f_w, int(255 * wq), -5, "ls", max_w=W * 0.5)
        lq = eo(prog(b, last + 3.5, last + 4.3))
        text(d, (W * 0.475, H * 0.5 + 100 * S), G.c["line"], F("sans_medium", int(34 * S)), int(255 * lq), 0, "ls", max_w=W * 0.5)
        text(d, (W * 0.475, H * 0.5 + 150 * S), G.c["url"], F("sans_black", int(34 * S)), int(255 * lq), 0, "ls", max_w=W * 0.5)
    a = np.maximum(sm, np.asarray(tm, np.float32) / 255)[..., None]
    img = img * (1 - a) + f * a
    return img.astype(np.uint8)


def balance(s, f, w):
    """One line if it fits, else the two-line split with the shortest longest line (no orphans)."""
    words = s.split()
    if text_width(s, f, -0.5) <= w or len(words) < 2:
        return [s]
    best = min(range(1, len(words)), key=lambda k: max(text_width(" ".join(words[:k]), f, -0.5), text_width(" ".join(words[k:]), f, -0.5)))
    return [" ".join(words[:best]), " ".join(words[best:])]


def wrap(s, f, w):
    out, cur = [], ""
    for tok in s.split():
        t = (cur + " " + tok).strip()
        if cur and text_width(t, f, -0.5) > w:
            out.append(cur)
            cur = tok
        else:
            cur = t
    return out + ([cur] if cur else [])


def octave(note, k):
    return note[:-1] + str(int(note[-1]) + k)


# ------------------------------------------------------------------ sound: plucky arpeggio, a pitched whoosh per morph
def score(path, dur):
    sc = Score(120, dur + 0.3)
    n = len(G.shapes)
    arp = [["A3", "C4", "E4", "A4"], ["F3", "A3", "C4", "F4"], ["C4", "E4", "G4", "C5"], ["G3", "B3", "D4", "G4"]]
    for bar in range(int(dur / B(4)) + 1):
        ch = arp[bar % len(arp)]
        root = ch[0][:-1] + "2"
        sc.bass([(root, 0, 2), (root, 2.5, 1)], start=B(bar * 4), gain=0.5)
        for k in range(8):
            sc.hit("blip", B(bar * 4 + k * 0.5), 0.32, pan=(k % 2 - 0.5) * 0.6, note=octave(ch[k % 4], 2))
    sc.hit("thud", B(land(0)), 1.0)
    for i in range(1, n):
        sc.hit("riser", B(land(i) - MORPH), 0.5, dur=B(MORPH))
        sc.hit("clack", B(land(i)), 0.9, pitch=0.9 + 0.08 * i)
        sc.hit("kick", B(land(i)), 0.8)
    sc.pattern("hat", every=0.5, start=land(0), end=land(n - 1) + 2, gain=0.35)
    last = land(n - 1)
    sc.chord(["A3", "C4", "E4", "G4"], B(last + 2), dur - B(last + 2), 0.8)
    sc.hit("clack", B(last + 2.5), 0.8, pitch=1.6)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    dur = B(land(len(G.shapes) - 1) + 8)
    return Timeline([Scene("chain", dur, frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    for k in ("brand", "line", "url"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
    for x in G.chain:
        if x["shape"] not in SHAPES:
            errs.append(f"unknown shape {x['shape']!r}; use one of {', '.join(SHAPES)}")
        if x.get("caption", "").rstrip().endswith("."):
            errs.append(f"trailing period: {x['caption']!r}")
    if not 4 <= len(G.chain) <= 9:
        errs.append("use 4–9 shapes")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    # knot check: every morph midpoint must stay a simple outline (no self-crossing)
    for i in range(len(G.shapes) - 1):
        for q in (0.25, 0.75):
            pts = lerp(G.shapes[i], G.circle, q * 2) if q < 0.5 else lerp(G.circle, G.shapes[i + 1], (q - 0.5) * 2)
            if self_cross(pts):
                errs.append(f"morph {G.chain[i]['shape']} → {G.chain[i + 1]['shape']} knots at {q}")
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.1, tl.duration - 0.05, 20):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{tl.duration:.2f}s, {tl.n_frames} frames, {len(G.shapes)} shapes: {' → '.join(x['shape'] for x in G.chain)}")
    for e in errs:
        print("✗", e)
    return not errs


def self_cross(pts, step=6):
    """Coarse self-intersection test on a subsampled outline."""
    p = pts[::step]
    n = len(p)
    segs = [(p[i], p[(i + 1) % n]) for i in range(n)]

    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            a, b = segs[i]
            c, d = segs[j]
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "kestrel", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("fully procedural: no image slots.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=8, rows=3, thumb_w=200))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a"), tl.duration))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"), tl.duration)
        print(tl.render(a.out or os.path.join(out, "morph-chain-film.mp4"), audio))


if __name__ == "__main__":
    main()
