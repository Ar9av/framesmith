#!/usr/bin/env python3
"""drafting-table-film: one mechanism drawn in three inks: pencil → blueprint → hologram (16:9, 120 BPM, 24 s).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1 6 12 17 25 33 37 45
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

The camera is locked like a drafting table. Act 1: graphite on cream paper with boiling, double-
stroked pencil lines and hatching drawn one line at a time. Act 2: a hard-edged blueprint flood
from the pencil tip; white lines, dashed hidden edges, and the gear train runs with true ratios
while callouts draw their leaders. Act 3: one horizontal scan line turns it into a hologram (cyan
lines with a white core, scan-line fills, no glow) and the stack explodes along its axis.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Scene, Theme, Timeline, h, prog, text, text_width, overflow_report, mix
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith import press
from framesmith.score import Score

G = None


def io(p):
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


# beat cues (120 BPM → 0.5 s a beat); moves start 0.05 s early so they land on the beat
FLOOD, SCAN, EXPLODE, END, TOTAL = 16, 32, (33, 36), 40, 48


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        x = self.th.extra
        self.paper = self.th.paper
        self.graphite, self.bp, self.line, self.void, self.holo = (x["graphite"], x["blueprint"], x["line"], x["void"], x["holo"])
        self.W, self.H = brief.get("size", [1920, 1080])
        self.fps = brief.get("fps", 30)
        self.spb = 60 / brief.get("bpm", 120)
        self.seed = brief.get("seed", 5)
        g = brief.get("gear", {})
        self.zs, self.zp, self.m = g.get("sun", 12), g.get("planet", 24), g.get("module", 10.5)
        self.zr = self.zs + 2 * self.zp
        self.cx, self.cy = self.W * 0.33, self.H * 0.5
        self.S = self.H / 1080
        self.m *= self.S


def B(k):
    return k * G.spb


# ------------------------------------------------------------------ geometry
def gear(cx, cy, z, m, ang, internal=False, pts_per=7):
    """Gear outline: trapezoid teeth on the pitch circle; internal=True points the teeth inwards."""
    r = m * z / 2
    tip, root = (r - m, r + 1.25 * m) if internal else (r + m, r - 1.25 * m)
    out = []
    step = 2 * math.pi / z
    for k in range(z):
        a = ang + k * step
        # root → flank → tip land → flank → root (fractions of the tooth pitch)
        for f, rr in ((-0.5, root), (-0.3, root), (-0.17, tip), (0.17, tip), (0.3, root)):
            out.append((cx + rr * math.cos(a + f * step), cy + rr * math.sin(a + f * step)))
    out.append(out[0])
    return np.array(out, np.float32)


def circ(cx, cy, r, n=None):
    return press.circle_pts(cx, cy, r, 0, 360, n or max(48, int(r * 0.8)))


def kinematics(b):
    """Sun input angle → carrier and planet angles, ring fixed (true planetary ratios)."""
    ramp = max(0.0, b - FLOOD - 1)
    spin = 0.0 if ramp <= 0 else (ramp ** 2 / 8 if ramp < 4 else 2 + (ramp - 4))       # ease up to speed
    th_s = spin * 0.9                                           # sun turns (rad)
    th_c = th_s * G.zs / (G.zs + G.zr)                          # carrier
    th_p = -th_c * (G.zr / G.zp - 1)                            # planet, absolute
    return th_s, th_c, th_p


def parts(b, cx=None, cy=None):
    """Every part as closed outlines in the drawing plane, plus its explode height for act 3."""
    cx = G.cx if cx is None else cx
    cy = G.cy if cy is None else cy
    m = G.m
    th_s, th_c, th_p = kinematics(b)
    rs, rp, rr = m * G.zs / 2, m * G.zp / 2, m * G.zr / 2
    out = {}
    out["housing"] = [circ(cx, cy, rr + 3.6 * m), circ(cx, cy, rr + 1.25 * m + 1)]
    out["ring"] = [gear(cx, cy, G.zr, m, 0.0, internal=True)]
    out["sun"] = [gear(cx, cy, G.zs, m, th_s), circ(cx, cy, rs * 0.38)]
    pl = []
    for i in range(3):
        a = th_c + i * 2 * math.pi / 3
        px, py = cx + (rs + rp) * math.cos(a), cy + (rs + rp) * math.sin(a)
        ph0 = i * 2 * math.pi / 3 + math.pi + math.pi / G.zp     # a gap faces the sun at rest
        pl += [gear(px, py, G.zp, m, ph0 + th_p), circ(px, py, rp * 0.3)]
    out["planet"] = pl
    holes = [circ(cx + (rr + 2.45 * m) * math.cos(k * math.pi / 4 + math.pi / 8),
                  cy + (rr + 2.45 * m) * math.sin(k * math.pi / 4 + math.pi / 8), 0.55 * m, 24) for k in range(8)]
    out["bolts"] = holes
    return out


def construction(cx, cy):
    m = G.m
    rr = m * G.zr / 2
    L = rr + 5 * m
    lines = [np.array([[cx - L, cy], [cx + L, cy]], np.float32), np.array([[cx, cy - L], [cx, cy + L]], np.float32)]
    circles = [circ(cx, cy, m * G.zs / 2 + m * G.zp / 2), circ(cx, cy, rr), circ(cx, cy, m * G.zs / 2)]
    return lines, circles


# drawing order for the pencil act: (part, start beat, end beat)
PENCIL = [("housing", 0.2, 2.0), ("bolts", 2.0, 3.0), ("ring", 3.0, 6.0), ("sun", 6.0, 7.0), ("planet", 7.0, 10.0)]


def pencil_progress(name, b):
    for n, a, z in PENCIL:
        if n == name:
            return prog(b, a - 0.1, z - 0.1)
    return 1.0


def staged(polys, p):
    """Draw a list of outlines one after another as p goes 0 → 1."""
    n = len(polys)
    out = []
    for i, pts in enumerate(polys):
        q = min(1.0, max(0.0, p * n - i))
        if q > 0:
            out.append(press.partial(pts, q))
    return out


# ------------------------------------------------------------------ inks
def grid(d, col, alpha_base, s=1):
    """60 px drafting grid at 13 %, every fifth line at 26 %."""
    st = int(60 * G.S)
    for k, x in enumerate(range(0, G.W, st)):
        d.line((x * s, 0, x * s, G.H * s), fill=int(255 * (0.26 if k % 5 == 0 else 0.13) * alpha_base), width=s)
    for k, y in enumerate(range(0, G.H, st)):
        d.line((0, y * s, G.W * s, y * s), fill=int(255 * (0.26 if k % 5 == 0 else 0.13) * alpha_base), width=s)


def to_mask(fn, ss=1):
    return press.mask_from(fn, (G.W, G.H), ss)


def title_hatch(b, x, y, size, p):
    """Big type as hatching cut to the letter shapes, drawn on one line at a time."""
    def make():
        m = Image.new("L", (G.W, G.H), 0)
        text(ImageDraw.Draw(m), (x, y), G.c["product"], F("sans_black", size), 255, -6, "ls", max_w=G.W * 0.36)
        return np.asarray(m, np.float32) / 255
    if not hasattr(G, "_title"):
        G._title = make()
    tm = G._title
    return press.hatch(tm, pitch=7 * G.S, angle=50, width=2.0, p=p), press.outline(tm, 3)


def ink_pencil(b, fi):
    """Act 1: graphite on cream, double-stroked boiling lines (full width at 90 %, half width at 40 %)."""
    lines, circles = construction(G.cx, G.cy)
    P = parts(0.0)                                                # static until the flood
    strokes = []                                                  # (pts, width, alpha)
    pc = prog(b, -0.6, 0.6)
    for i, ln in enumerate(lines):
        strokes.append((press.partial(ln, io(pc)), 1.4, 0.5))
    for i, cc in enumerate(circles):
        q = prog(b, -0.2 + i * 0.25, 0.9 + i * 0.25)
        strokes.append((press.partial(cc, io(q)), 1.2, 0.4))
    tip = None
    for name, a, z in PENCIL:
        p = pencil_progress(name, b)
        for pts in staged(P[name], p):
            strokes.append((pts, 2.4, 0.9))
            if 0 < p < 1:
                tip = pts[-1]
    # dimension: Ø with leader, drawn after the parts
    rr = G.m * G.zr / 2 + 3.6 * G.m
    dimp = prog(b, 10.5, 12)
    dim_line = np.array([[G.cx - rr, G.cy + rr + 40 * G.S], [G.cx + rr, G.cy + rr + 40 * G.S]], np.float32)
    if dimp > 0:
        strokes.append((press.partial(dim_line, io(dimp)), 1.4, 0.8))
        for sx in (-1, 1):
            strokes.append((np.array([[G.cx + sx * rr, G.cy + rr + 10 * G.S], [G.cx + sx * rr, G.cy + rr + 52 * G.S]], np.float32), 1.2, 0.6 * dimp))

    def draw(d, s):
        grid(d, None, 1.0, s)
        for k, (pts, w, a) in enumerate(strokes):
            if len(pts) < 2:
                continue
            wp = press.wobble(pts, fi, 1.1 * G.S, G.seed + k, 8, G.fps, 7)
            press.stroke(d, wp, w * G.S, s, int(255 * a))
            wp2 = press.wobble(pts, fi, 2.0 * G.S, G.seed + k + 99, 8, G.fps, 9)
            press.stroke(d, wp2, w * 0.5 * G.S, s, int(255 * a * 0.4))
    m = to_mask(draw, 2)
    # hatch the housing section (between outer wall and ring root), one line at a time
    hp = prog(b, 11, 13.5)
    if hp > 0:
        ring_mask = to_mask(lambda d, s: (d.polygon([(x * s, y * s) for x, y in P["housing"][0]], fill=255),
                                          d.polygon([(x * s, y * s) for x, y in P["housing"][1]], fill=0),
                                          [d.ellipse(((x.min()) * s, y.min() * s, x.max() * s, y.max() * s), fill=0)
                                           for x, y in [(bb[:, 0], bb[:, 1]) for bb in P["bolts"]]]), 1)
        m = np.maximum(m, press.hatch(ring_mask, 9 * G.S, 45, 1.3, hp) * 0.55)
    # title in hatching + its pencil outline; the kind, lettered under it
    tp = prog(b, 8.5, 13)
    tx, ty, ts = G.W * 0.62, G.H * 0.5, int(330 * G.S)
    if tp > 0:
        hm, om = title_hatch(b, tx, ty, ts, tp)
        m = np.maximum(m, hm * 0.85)
        m = np.maximum(m, om * 0.5 * prog(b, 12.5, 13.5))
    lab = Image.new("L", (G.W, G.H), 0)
    d = ImageDraw.Draw(lab)
    if b >= 13:
        s = G.c["kind"].upper()
        n = int(len(s) * prog(b, 13, 14.5) + 0.999)
        text(d, (tx + 6, ty + 64 * G.S), s[:n], F("sans_bold", int(34 * G.S)), 230, 6, max_w=G.W * 0.34, fit_to=s)
    if dimp > 0:
        text(d, (G.cx, G.cy + rr + 32 * G.S), G.c["dimension"], F("sans_bold", int(26 * G.S)), int(220 * dimp), 2, "mb", max_w=200)
    if b >= 2:
        text(d, (G.W * 0.62 + 6, G.H * 0.5 - ts * 0.78), G.c["brand"].upper(), F("sans_bold", int(22 * G.S)), int(200 * prog(b, 2, 3)), 5, max_w=G.W * 0.34)
    m = np.maximum(m, np.asarray(lab, np.float32) / 255)
    m *= 1 - 0.35 * np.clip(0.5 - press.tooth((G.W, G.H), G.seed), 0, 1) * 2                     # paper tooth knocks graphite out
    ground = press.paper((G.W, G.H), G.paper, G.seed, 0.08)
    out = press.plates(ground, [(m, G.graphite, None)])
    if tip is not None:                                                                          # the pencil point
        im = Image.fromarray(out)
        ImageDraw.Draw(im).ellipse((tip[0] - 4, tip[1] - 4, tip[0] + 4, tip[1] + 4), fill=G.graphite)
        out = np.asarray(im)
    return out, tip


def callouts(b, layout, col, d, size_k=1.0):
    """Leader lines from part anchors to labels in the right column, one per two beats."""
    names = list(G.c["parts"].keys())
    m = G.m
    P = parts(b)
    anchors = {
        "sun": (G.cx, G.cy - m * G.zs / 2 * 0.7),
        "planet": tuple(P["planet"][0][len(P["planet"][0]) // 3]),
        "ring": (G.cx + m * G.zr / 2 * 0.72, G.cy - m * G.zr / 2 * 0.7),
        "housing": (G.cx + (m * G.zr / 2 + 3.2 * m) * 0.7, G.cy + (m * G.zr / 2 + 3.2 * m) * 0.7),
    }
    x_lab = G.W * 0.6
    for i, n in enumerate(names):
        land = layout + 2 * i
        p = io(prog(b, land - 1, land))
        if p <= 0:
            continue
        ax, ay = anchors.get(n, (G.cx, G.cy))
        ly = G.H * (0.22 + 0.17 * i)
        knee = (x_lab - 40 * G.S, ly)
        path = np.array([[ax, ay], [ax + (knee[0] - ax) * 0.55, ly], [knee[0], ly], [x_lab - 10, ly]], np.float32)
        press.stroke(d, press.partial(path, p), 2 * G.S, 1, col)
        d.ellipse((ax - 5, ay - 5, ax + 5, ay + 5), fill=col)
        if p >= 1:
            a, sub = G.c["parts"][n]
            text(d, (x_lab, ly - 6), a.upper(), F("sans_bold", int(30 * G.S * size_k)), col, 4, "ls", max_w=G.W * 0.36)
            text(d, (x_lab, ly + 34 * G.S), sub, F("sans_medium", int(26 * G.S * size_k)), col, 0.5, "ls", max_w=G.W * 0.36)


def ink_blueprint(b, fi):
    """Act 2: white lines on blueprint blue; hidden edges dashed; the gear train runs."""
    P = parts(b)
    lines, circles = construction(G.cx, G.cy)
    im = Image.new("L", (G.W * 2, G.H * 2), 0)
    d = ImageDraw.Draw(im)
    grid(d, None, 1.0, 2)
    for ln in lines:
        press.stroke(d, ln, 1.2 * G.S, 2, 120)
    for cc in circles:                                            # pitch circles: dashed, thinner
        for k in range(0, len(cc) - 1, 4):
            press.stroke(d, cc[k:k + 3], 1.4 * G.S, 2, 150)
    for name in ("housing", "bolts", "ring", "sun", "planet"):
        for pts in P[name]:
            press.stroke(d, pts, 3.4 * G.S, 2, 255)
    rr = G.m * G.zr / 2 + 3.6 * G.m
    y = G.cy + rr + 40 * G.S
    press.stroke(d, [(G.cx - rr, y), (G.cx + rr, y)], 1.6 * G.S, 2, 230)
    m = np.asarray(im.reduce(2), np.float32) / 255
    lab = Image.new("L", (G.W, G.H), 0)
    dl = ImageDraw.Draw(lab)
    text(dl, (G.cx, y - 8 * G.S), G.c["dimension"], F("sans_bold", int(26 * G.S)), 230, 2, "mb", max_w=200)
    callouts(b, FLOOD + 2.5, 255, dl)
    text(dl, (G.W * 0.6, G.H * 0.1), G.c["brand"].upper() + "  /  " + G.c["product"], F("sans_bold", int(24 * G.S)), 200, 5, "ls", max_w=G.W * 0.36)
    m = np.maximum(m, np.asarray(lab, np.float32) / 255)
    ground = press.paper((G.W, G.H), G.bp, G.seed + 1, 0.05)
    out = ground * (1 - m[..., None]) + np.array(G.line, np.float32) * m[..., None]
    return out.astype(np.uint8)


def project(pts, z, k=0.42, cx=None, cy=None):
    """Oblique exploded view: squash the drawing plane and lift by z."""
    cx = G.cx if cx is None else cx
    cy = G.cy if cy is None else cy
    q = np.asarray(pts, np.float32).copy()
    q[:, 1] = cy + (q[:, 1] - cy) * k - z
    return q


def ink_hologram(b, fi):
    """Act 3: cyan line with a white core at 30 % of its width, scan-line fills, no glow; the stack explodes."""
    e = io(prog(b, *EXPLODE))
    k = 1.0 - 0.52 * e
    cy = G.cy - 10 * G.S * e
    P = parts(b, G.cx, cy)
    gap = 128 * G.S * e
    order = [("housing", -1.5), ("ring", -0.5), ("planet", 0.5), ("sun", 1.5)]
    order = [(n, z * gap) for n, z in order]
    W2, H2 = G.W * 2, G.H * 2
    lines_m = Image.new("L", (W2, H2), 0)
    core_m = Image.new("L", (W2, H2), 0)
    fill_m = Image.new("L", (G.W, G.H), 0)
    dl, dc, df = ImageDraw.Draw(lines_m), ImageDraw.Draw(core_m), ImageDraw.Draw(fill_m)
    grid(dl, None, 0.55, 2)
    lw = 3.4 * G.S
    for name, z in order:
        polys = P[name] + (P["bolts"] if name == "housing" else [])
        lit = {"housing": 0.25, "ring": 0.45, "planet": 0.7, "sun": 1.0}[name]
        outer = project(polys[0], z, k, cy=cy)
        # scan-line fill: 8 px pitch, thickness follows how lit the face is
        pitch = 8
        fm = Image.new("L", (G.W, G.H), 0)
        ImageDraw.Draw(fm).polygon([tuple(p) for p in outer], fill=255)
        if name == "housing":
            ImageDraw.Draw(fm).polygon([tuple(p) for p in project(polys[1], z, k, cy=cy)], fill=0)
        fa = np.asarray(fm, np.float32) / 255
        rows = (np.arange(G.H) % pitch) < max(1, round(lit * 3.2))
        fa = fa * rows[:, None]
        fill_m.paste(255, (0, 0), Image.fromarray((fa * 255 * 0.55).astype(np.uint8)))
        for pts in polys:
            q = project(pts, z, k, cy=cy)
            press.stroke(dl, q, lw, 2, 255)
            press.stroke(dc, q, lw * 0.3, 2, 255)
    # the axis through the stack
    top, bot = cy - 2.2 * gap - 60 * G.S * e, cy + 2.2 * gap + 60 * G.S * e
    if e > 0:
        for yy in np.arange(top, bot, 18 * G.S):
            press.stroke(dl, [(G.cx, yy), (G.cx, yy + 9 * G.S)], 1.6 * G.S, 2, 200)
    lm = np.asarray(lines_m.reduce(2), np.float32) / 255
    cm = np.asarray(core_m.reduce(2), np.float32) / 255
    fm = np.asarray(fill_m, np.float32) / 255
    lab = Image.new("L", (G.W, G.H), 0)
    d = ImageDraw.Draw(lab)
    specs = G.c["specs"][:4]
    x = G.W * 0.6
    for i, (big, small) in enumerate(specs):
        land = EXPLODE[1] + i
        p = eo(prog(b, land - 0.5, land))
        if p <= 0:
            continue
        y = G.H * (0.24 + 0.16 * i)
        n = max(1, int(len(big) * p + 0.999))
        fb = F("sans_black", int(76 * G.S))
        text(d, (x, y), big[:n], fb, 255, -1, "ls", max_w=G.W * 0.16, fit_to=big)
        if p >= 1:
            bw = min(text_width(big, fb, -1), G.W * 0.16)
            text(d, (x + bw + 26 * G.S, y - 6 * G.S), small, F("sans_medium", int(30 * G.S)), 255, 0.5, "ls", max_w=G.W * 0.36 - bw - 26 * G.S)
    if b >= END:
        q = eo(prog(b, END, END + 1))
        text(d, (x, G.H * 0.88), G.c["brand"].upper() + "  /  " + G.c["product"], F("sans_bold", int(26 * G.S)), int(255 * q), 5, "ls", max_w=G.W * 0.36)
        text(d, (x, G.H * 0.88 + 44 * G.S), G.c["url"], F("sans_medium", int(28 * G.S)), int(255 * q), 0.5, "ls", max_w=G.W * 0.36)
    tm = np.asarray(lab, np.float32) / 255
    out = np.empty((G.H, G.W, 3), np.float32)
    out[:] = G.void
    holo = np.array(G.holo, np.float32)
    white = np.array((246, 255, 253), np.float32)
    for a, col in ((fm * 0.6, holo), (lm, holo), (tm, holo), (cm, white)):
        out = out * (1 - a[..., None]) + col * a[..., None]
    return out.astype(np.uint8)


# ------------------------------------------------------------------ the film: one shot, three inks
def frame(c):
    b = c.t / G.spb + 0.1                                         # land 0.05 s early on the beat
    if b < FLOOD:
        out, _ = ink_pencil(b, c.fi)
        return out
    if b < FLOOD + 1.2:                                           # hard-edged flood from the pencil's last point
        pen, tip = ink_pencil(FLOOD - 0.01, c.fi)
        tx, ty = (tip if tip is not None else (G.cx + 200, G.cy))
        r = math.hypot(max(tx, G.W - tx), max(ty, G.H - ty)) * 1.05 * eo(prog(b, FLOOD, FLOOD + 0.7))
        bp = ink_blueprint(b, c.fi)
        yy, xx = np.ogrid[:G.H, :G.W]
        inside = ((xx - tx) ** 2 + (yy - ty) ** 2 <= r * r)[..., None]
        return np.where(inside, bp, pen)
    if b < SCAN:
        return ink_blueprint(b, c.fi)
    if b < SCAN + 1:                                              # a single horizontal scan line
        y = int(G.H * io(prog(b, SCAN, SCAN + 1)))
        out = ink_blueprint(b, c.fi).copy()
        hol = ink_hologram(b, c.fi)
        out[:y] = hol[:y]
        out[max(0, y - 2):y + 1] = (246, 255, 253)
        return out
    return ink_hologram(b, c.fi)


# ------------------------------------------------------------------ sound
def score(path, dur):
    sc = Score(120, dur)
    for name, a, z in PENCIL:                                      # pencil on paper while each part is drawn
        sc.hit("scratch", B(a), 0.9, dur=B(z - a))
    sc.hit("scratch", B(11), 0.7, dur=B(2.5))
    sc.hit("scratch", B(8.5), 0.5, dur=B(4))
    sc.keys([("E4", 0, 4), ("B3", 4, 4), ("C4", 8, 4), ("G3", 12, 4)], start=0, gain=0.7)
    sc.hit("slap", B(FLOOD), 1.2)
    sc.hit("thud", B(FLOOD), 1.0)
    sc.pattern("kick", every=1, start=FLOOD, end=TOTAL - 2, gain=0.85)
    sc.pattern("tick", every=0.5, start=FLOOD + 1, end=SCAN, gain=0.45, pitch=0.8)
    for i in range(4):
        sc.hit("clack", B(FLOOD + 2.5 + 2 * i), 0.9, pitch=1.3)
    bass = [("E1", 0, 2), ("E1", 2, 1), ("G1", 3, 1), ("A1", 4, 2), ("B1", 6, 2)]
    for k in range(FLOOD, TOTAL - 4, 8):
        sc.bass(bass, start=B(k), gain=0.55)
    sc.hit("riser", B(SCAN - 2), 0.9)
    sc.hit("snare", B(SCAN), 0.9)
    sc.pattern("hat", every=0.5, start=SCAN, end=TOTAL - 2, gain=0.5)
    for i in range(4):
        sc.hit("blip", B(EXPLODE[1] + i), 0.7, note=["E6", "G6", "B6", "D7"][i])
    sc.chord(["E3", "G3", "B3", "D4"], B(SCAN), dur - B(SCAN), 0.75)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("table", B(TOTAL), frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    for k in ("brand", "product", "kind", "parts", "dimension", "specs", "url"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    lines = [G.c["kind"], G.c["url"]] + [s for v in G.c["parts"].values() for s in v] + [s for p in G.c["specs"] for s in p]
    errs += [f"trailing period: {s!r}" for s in lines if s.rstrip().endswith(".")]
    if len(G.c["parts"]) > 4 or len(G.c["specs"]) > 4:
        errs.append("at most 4 parts and 4 specs")
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.3, tl.duration - 0.05, 18):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{tl.duration:.2f}s, {tl.n_frames} frames; flood on beat {FLOOD}, scan on beat {SCAN}, gear {G.zs}/{G.zp}/{G.zr} ({1 + G.zr / G.zs:g}:1)")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "brannock", "brief.json"))
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
        print(score(os.path.join(out, "score.m4a"), tl.duration))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"), tl.duration)
        print(tl.render(a.out or os.path.join(out, "drafting-table-film.mp4"), audio))


if __name__ == "__main__":
    main()
