#!/usr/bin/env python3
"""one-line-film: the whole film is one continuous line (16:9, 20 s).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 0.6 2.5 5 8.5 11.5 13.6 15.5 19
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

A single champagne line of constant width, round caps and a pen tip that leads the draw. Each
figure's tail is the next one's start: seed → sapling → a house drawn from the branch → a skyline
→ the horizon, which lifts and loops into a monogram. The monogram fills from its anchor point
(line to fill), the camera, which has followed the tip with older segments dimmed to 35 %, dollies
out to reveal the whole drawing as a poster, and the wordmark sets in letter-spaced serif caps.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Scene, Theme, Timeline, prog, text, overflow_report, mix
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.score import Score

G = None
DUR = 20.0
SS = 2


def io(p):
    """cubic-bezier(0.65, 0, 0.35, 1)-like: the draw eases into and out of each figure's corners."""
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def lerp(a, b, p):
    return a + (b - a) * p


# ------------------------------------------------------------------ path building (world units, y down)
def bez(p0, p1, p2, p3, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array(p, np.float32) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def seg(a, b, n=None):
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    n = n or max(2, int(np.hypot(*(b - a)) / 6))
    t = np.linspace(0, 1, n)[:, None]
    return a + (b - a) * t


def arc(cx, cy, r, a0, a1, n=None):
    n = n or max(16, int(abs(a1 - a0) / 360 * 2 * math.pi * r / 6))
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)


# single-stroke monogram letters in a unit box (0..1, y down) and the fill anchor
LETTERS = {
    "V": ([(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)], (0.5, 1.0)),
    "W": ([(0.0, 0.0), (0.25, 1.0), (0.5, 0.35), (0.75, 1.0), (1.0, 0.0)], (0.5, 0.35)),
    "M": ([(0.0, 1.0), (0.0, 0.0), (0.5, 0.65), (1.0, 0.0), (1.0, 1.0)], (0.5, 0.65)),
    "N": ([(0.0, 1.0), (0.0, 0.0), (1.0, 1.0), (1.0, 0.0)], (0.5, 0.5)),
    "A": ([(0.0, 1.0), (0.5, 0.0), (1.0, 1.0)], (0.5, 0.0)),
    "Z": ([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)], (0.5, 0.5)),
    "L": ([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)], (0.0, 1.0)),
    "U": ([(0.0, 0.0), (0.0, 0.7), (0.5, 1.0), (1.0, 0.7), (1.0, 0.0)], (0.5, 1.0)),
}


def build_path(mono):
    """One continuous polyline and the cue (length marks) where each figure ends."""
    parts, marks = [], []

    def add(p, name=None):
        parts.append(np.asarray(p, np.float32))
        if name:
            marks.append((name, sum(len(x) for x in parts)))

    gy = 900.0
    # seed: a small teardrop loop
    add(arc(200, 860, 20, 10, 370, 36), "seed")
    # sapling: stem with two leaf excursions
    add(bez((215, 866), (190, 800), (250, 760), (232, 702)))
    add(bez((232, 702), (170, 690), (140, 640), (152, 628)))           # leaf 1 out
    add(bez((152, 628), (200, 640), (230, 670), (238, 690)))           # and back
    add(bez((238, 690), (250, 650), (250, 620), (256, 600)))
    add(bez((256, 600), (300, 580), (330, 556), (346, 548)))           # leaf 2 out
    add(bez((346, 548), (320, 580), (285, 596), (262, 590)), "sapling")
    # the branch becomes the house's roof line and frame
    add(bez((262, 590), (300, 520), (360, 480), (420, 470)))
    for a, b in (((420, 470), (660, 330)), ((660, 330), (900, 470)), ((900, 470), (900, gy)), ((900, gy), (680, gy)),
                 ((680, gy), (680, 780)), ((680, 780), (600, 780)), ((600, 780), (600, gy)), ((600, gy), (420, gy)),
                 ((420, gy), (420, 470)), ((420, 470), (900, 470)), ((900, 470), (900, 640)), ((900, 640), (420, 640)),
                 ((420, 640), (420, gy)), ((420, gy), (980, gy))):
        add(seg(a, b))
    marks.append(("house", sum(len(x) for x in parts)))
    # skyline: the ground line climbs over a run of towers
    x, tops = 980, [(80, 520), (120, 640), (80, 460), (140, 720), (80, 560), (140, 680), (80, 500), (160, 600), (80, 450)]
    y = gy
    for w, hgt in tops:
        top = gy - hgt * 0.78
        add(seg((x, y), (x, top)))
        add(seg((x, top), (x + w, top)))
        x, y = x + w, top
    add(seg((x, y), (x, gy)))
    add(seg((x, gy), (2480, gy)), "skyline")
    # the horizon lifts and loops into the monogram ring
    cx, cy, r = 2800, 560, 230
    add(bez((2480, gy), (2540, gy), (2560, 760), (cx - r, cy)))
    # the letter sits in the square inscribed in the ring, so a corner start lies on the ring itself
    pts, anchor = LETTERS.get(mono, LETTERS["V"])
    s = r * math.sqrt(2) * 0.98
    ox, oy = cx - s / 2, cy - s / 2
    first = (ox + pts[0][0] * s, oy + pts[0][1] * s)
    ang = math.degrees(math.atan2(first[1] - cy, first[0] - cx)) % 360
    add(arc(cx, cy, r, 180, 180 + 360 + (ang - 180) % 360, 160), "ring")
    L = [tuple(arc(cx, cy, r, ang, ang, 1)[0])] + [(ox + u * s, oy + v * s) for u, v in pts]
    for a, b in zip(L[:-1], L[1:]):
        add(seg(a, b))
    marks.append(("letter", sum(len(x) for x in parts)))
    P = np.vstack(parts)
    seglen = np.sqrt(((P[1:] - P[:-1]) ** 2).sum(1))
    cum = np.concatenate([[0], np.cumsum(seglen)])
    return P, cum, {n: cum[min(i, len(cum)) - 1] for n, i in marks}, (cx, cy, r), (ox + anchor[0] * s, oy + anchor[1] * s), [(ox + u * s, oy + v * s) for u, v in pts]


# when each figure finishes (seconds); the draw eases within each window
CUES = [("seed", 0.0, 1.1), ("sapling", 1.1, 3.3), ("house", 3.3, 7.4), ("skyline", 7.4, 10.4), ("ring", 10.4, 12.2), ("letter", 12.2, 13.0)]
FILL = (13.1, 14.2)
DOLLY = (13.8, 16.4)
WORD = (15.4, 16.6)


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        x = self.th.extra
        self.ground, self.line = x["ground"], x["line"]
        self.W, self.H = brief.get("size", [1920, 1080])
        self.fps = brief.get("fps", 30)
        self.mono = brief.get("monogram", "V").upper()
        self.P, self.cum, self.marks, self.ring, self.anchor, self.letter = build_path(self.mono)
        self.bbox = (self.P[:, 0].min(), self.P[:, 1].min(), self.P[:, 0].max(), self.P[:, 1].max())


def drawn(t):
    """Length of line drawn at time t."""
    prev = 0.0
    for name, a, b in CUES:
        end = G.marks[name]
        if t < b:
            return lerp(prev, end, io(prog(t, a, b)))
        prev = end
    return prev


def point_at(L):
    i = int(np.searchsorted(G.cum, L))
    if i <= 0:
        return G.P[0]
    if i >= len(G.P):
        return G.P[-1]
    q = (L - G.cum[i - 1]) / max(G.cum[i] - G.cum[i - 1], 1e-6)
    return G.P[i - 1] + (G.P[i] - G.P[i - 1]) * q


def camera(t):
    """Centre + zoom: follow the tip with a lag (mean of the last 0.6 s), then dolly out to the poster."""
    follow = np.mean([point_at(drawn(max(0.0, t - k * 0.12))) for k in range(6)], 0)
    zf = lerp(3.2, 1.3, io(prog(t, 0.4, 4.5))) * G.W / 1920
    x0, y0, x1, y1 = G.bbox
    zp = min(G.W * 0.86 / (x1 - x0), G.H * 0.62 / (y1 - y0))
    cp = np.array([(x0 + x1) / 2, (y0 + y1) / 2 + (y1 - y0) * 0.16])
    p = io(prog(t, *DOLLY))
    z = math.exp(lerp(math.log(zf), math.log(zp), p))                # zoom interpolated in log space
    c = follow * (1 - p) + cp * p
    if t > DOLLY[1]:                                                 # living hold: a slow drift
        c = c + np.array([math.sin((t - DOLLY[1]) * 0.6) * 6, 0]) / z
    return c, z


def to_screen(pts, c, z):
    return (np.asarray(pts) - c) * z + np.array([G.W / 2, G.H / 2])


def frame(ctx):
    t = ctx.t
    L = drawn(t)
    c, z = camera(t)
    W2, H2 = G.W * SS, G.H * SS
    m = Image.new("L", (W2, H2), 0)
    d = ImageDraw.Draw(m)
    lw = max(2, int(3 * G.W / 1920 * SS))
    i = int(np.searchsorted(G.cum, L))
    pts = np.vstack([G.P[:i], point_at(L)[None]]) if i > 0 else G.P[:1]
    S = to_screen(pts, c, z) * SS
    # older segments dim to 35 % as the camera moves on (restored when the poster is revealed)
    keep = L - 900
    restore = io(prog(t, DOLLY[0], DOLLY[1]))
    old_a = int(255 * lerp(0.35, 0.82, restore))
    k = int(np.searchsorted(G.cum, max(0, keep)))
    for seg_pts, a in ((S[:k + 1], old_a), (S[k:], 255)):
        if len(seg_pts) > 1:
            d.line([tuple(p) for p in seg_pts], fill=a, width=lw, joint="curve")
    r = lw / 2
    if len(S):
        x, y = S[0]
        d.ellipse((x - r, y - r, x + r, y + r), fill=old_a if k > 0 else 255)
    # line to fill: the ring fills from the letter's anchor point; the letter stays as a cut line
    fp = io(prog(t, *FILL))
    fill = Image.new("L", (W2, H2), 0)
    if fp > 0:
        cx, cy, rr = G.ring
        (sx, sy), = to_screen([(cx, cy)], c, z) * SS
        ax, ay = (to_screen([G.anchor], c, z) * SS)[0]
        R = rr * z * SS
        df = ImageDraw.Draw(fill)
        rad = 2.2 * R * fp
        df.ellipse((ax - rad, ay - rad, ax + rad, ay + rad), fill=255)
        clip = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(clip).ellipse((sx - R, sy - R, sx + R, sy + R), fill=255)
        fill = Image.fromarray(np.minimum(np.asarray(fill), np.asarray(clip)))
        cut = to_screen(G.letter, c, z) * SS
        ImageDraw.Draw(fill).line([tuple(p) for p in cut], fill=0, width=int(lw * 3.2), joint="curve")
    # the pen tip: a solid point and a thin ring, while drawing
    tip_a = 1 - prog(t, CUES[-1][2], CUES[-1][2] + 0.4)
    if tip_a > 0 and len(S):
        x, y = S[-1]
        rr = 5 * SS * G.W / 1920
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=int(255 * tip_a))
        r2 = rr * 2.4
        d.ellipse((x - r2, y - r2, x + r2, y + r2), outline=int(110 * tip_a), width=max(1, SS))
    # wordmark: letter-spaced serif caps, then the line and URL
    wp = eo(prog(t, *WORD))
    if wp > 0:
        y0 = G.H * 0.85 * SS
        text(d, (G.W / 2 * SS, y0), G.c["brand"].upper(), F("serif", int(60 * G.W / 1920 * SS)), int(255 * wp),
             14 * SS, "ms", max_w=G.W * 0.7 * SS)
        q = eo(prog(t, WORD[0] + 0.5, WORD[1] + 0.5))
        sub = G.c["line"] + "   ·   " + G.c["url"]
        text(d, (G.W / 2 * SS, y0 + 62 * SS * G.W / 1920), sub, F("sans_medium", int(24 * G.W / 1920 * SS)), int(200 * q),
             2 * SS, "ms", max_w=G.W * 0.7 * SS)
    lm = np.asarray(m.reduce(SS), np.float32) / 255
    fm = np.asarray(fill.reduce(SS), np.float32) / 255
    a = np.maximum(lm, fm)[..., None]
    out = np.empty((G.H, G.W, 3), np.float32)
    out[:] = G.ground
    out = out * (1 - a) + np.array(G.line, np.float32) * a
    return out.astype(np.uint8)


# ------------------------------------------------------------------ sound: felt piano, a pen whisper that follows tip speed
def score(path):
    sc = Score(72, DUR + 0.3)
    for name, a, b in CUES:
        sc.hit("scratch", a, 0.8, dur=b - a)
    notes = [("E4", 0.0), ("B4", 1.1), ("G#4", 3.3), ("E5", 5.4), ("C#5", 7.4), ("A4", 9.0), ("B4", 10.4), ("E5", 12.2)]
    for n, t0 in notes:
        sc.keys([(n, 0, 3)], start=t0, gain=0.6, pan=0.15)
    sc.keys([("E3", 0, 6)], start=0.0, gain=0.4)
    sc.keys([("C#3", 0, 6)], start=7.4, gain=0.4)
    sc.chord(["E3", "B3", "G#4"], 10.4, 4.5, 0.7)
    sc.hit("blip", FILL[0] + 0.1, 0.7, note="E7")                  # the chime on the fill
    sc.hit("blip", FILL[0] + 0.35, 0.45, note="B6")
    sc.chord(["A3", "E4", "C#5"], DOLLY[0], DUR - DOLLY[0], 0.85)
    sc.keys([("E5", 0, 4), ("G#5", 1.6, 4)], start=WORD[0], gain=0.5)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("line", DUR, frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    for k in ("brand", "line", "url"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
        elif G.c[k].rstrip().endswith("."):
            errs.append(f"trailing period: {G.c[k]!r}")
    if G.mono not in LETTERS:
        errs.append(f"monogram {G.mono!r} has no single-stroke form; use one of {''.join(LETTERS)} or add it to LETTERS")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.1, DUR - 0.05, 16):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{DUR:.2f}s, {tl.n_frames} frames, one line of {G.cum[-1]:.0f} units, monogram {G.mono}")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "vrana", "brief.json"))
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
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=6, rows=4, thumb_w=320))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, "one-line-film.mp4"), audio))


if __name__ == "__main__":
    main()
