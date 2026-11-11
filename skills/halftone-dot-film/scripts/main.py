#!/usr/bin/env python3
"""halftone-dot-film: one dot carries the whole film (1:1, 120 BPM, 20 s, ink + paper + one accent).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 0.8 2.6 5.5 8.6 13 15.5 18.5
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

The dot drops and draws its own spring curve, lands as the tittle of the brand's i, becomes day one
of a month of habit dots, floods the frame, turns into a halftone year whose dot sizes follow it,
grows past the frame until the page flips to ink, and lands on the i again. No gradients, glows or
particles: every mark is a solid dot, a line or type.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Scene, Theme, Timeline, h, prog, text, text_width, overflow_report, mix
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.motion import spring
from framesmith import press
from framesmith.score import Score

G = None
SS = 2                                     # supersampling for crisp dots


def io(p):
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def lerp(a, b, p):
    return a + (b - a) * p


# act boundaries in beats
DROP, WORD, MONTH, FLOOD, YEAR, FLIP, END, TOTAL = 0, 4, 8, 16, 24, 29, 32, 40


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        self.paper, self.ink, self.acc = self.th.paper, self.th.ink, self.th.accent
        self.W, self.H = brief.get("size", [1080, 1080])
        self.fps = brief.get("fps", 30)
        self.spb = 60 / brief.get("bpm", 120)
        self.seed = brief.get("seed", 4)
        self.S = self.W / 1080
        self.word = self.word_layout()

    def word_layout(self):
        """The brand set huge with dotless i's; returns the font, origin and each tittle's centre and radius."""
        brand = self.c["brand"]
        set_as = brand.replace("i", "ı")
        f = F("sans_black", int(330 * self.S))
        track = -8 * self.S
        w = min(text_width(set_as, f, track), self.W * 0.8)
        x0 = (self.W - w) / 2
        base = self.H * 0.56
        tittles = []
        x = x0
        bi, bd = f.getbbox("i"), f.getbbox("ı")
        for ch in brand:
            if ch == "i":
                r = (bd[2] - bd[0]) * 0.47
                gap = (bd[1] - bi[1]) - 2 * r
                cy = base - f.getmetrics()[0] + bd[1] - gap * 0.5 - r
                tittles.append((x + (bd[0] + bd[2]) / 2, cy, r))
            x += f.getlength("ı" if ch == "i" else ch) + track
        return dict(s=set_as, font=f, track=track, x=x0, base=base, tittles=tittles)


def B(k):
    return k * G.spb


def canvas(col):
    im = Image.new("RGB", (G.W * SS, G.H * SS), col)
    d = ImageDraw.Draw(im)
    d.im_ref = im
    return im, d


def dot(d, x, y, r, col):
    if r > 0.2:
        d.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=col)


def ring(d, x, y, r, col, w=2):
    d.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), outline=col, width=int(w * SS))


def T(d, xy, s, role, size, col, track=0, anchor="la", max_w=None, fit_to=None):
    text(d, (xy[0] * SS, xy[1] * SS), s, F(role, int(size * G.S * SS)), col, track * SS, anchor,
         max_w=max_w * SS if max_w else None, fit_to=fit_to)


def finish(im):
    return np.asarray(im.reduce(SS))


def word(d, col, p=1.0):
    """The brand rising out of its baseline mask (p 0→1)."""
    wl = G.word
    m = Image.new("L", (G.W * SS, G.H * SS), 0)
    text(ImageDraw.Draw(m), (wl["x"] * SS, wl["base"] * SS), wl["s"], F("sans_black", wl["font"].size * SS), 255,
         wl["track"] * SS, "ls", max_w=G.W * 0.86 * SS)
    if p < 1:
        shift = int((1 - p) * wl["font"].size * 0.9 * SS)
        top = int((wl["base"] - wl["font"].size) * SS)
        moved = Image.new("L", m.size, 0)
        moved.paste(m.crop((0, top, m.width, int(wl["base"] * SS) + 4)), (0, top + shift))
        mm = Image.new("L", m.size, 0)
        mm.paste(moved.crop((0, top, m.width, int(wl["base"] * SS) + 4)), (0, top))
        m = mm
    d.im_ref.paste(Image.new("RGB", m.size, col), (0, 0), m)


# ------------------------------------------------------------------ the spring the dot falls on
K, D = 140, 7.5                         # underdamped: a few visible bounces


def drop_xy(b):
    """The dot's fall: x sweeps at a constant speed, y is the spring step response (rest line at y_rest)."""
    tt = max(0.0, B(b - DROP) - 0.05)
    x0, x1 = 150 * G.S, 930 * G.S
    y_top, y_rest = 150 * G.S, 700 * G.S
    x = lerp(x0, x1, min(1.0, tt / B(3.6)))
    y = lerp(y_top, y_rest, spring(tt, K, D))
    return x, y


def s_drop(b, fi):
    im, d = canvas(G.paper)
    y_rest = 700 * G.S
    d.line((60 * G.S * SS, y_rest * SS, (G.W - 60 * G.S) * SS, y_rest * SS), fill=mix(G.paper, G.ink, 0.25), width=SS)
    # the curve the dot has drawn so far (sampled from the same spring that moves it)
    erase = io(prog(b, WORD - 0.6, WORD + 0.6))
    n = 160
    bs = np.linspace(DROP, min(b, WORD - 0.4), n)
    pts = [drop_xy(k) for k in bs]
    pts = pts[int(len(pts) * erase):]
    if len(pts) > 1:
        press.stroke(d, pts, 3.2 * G.S, SS, G.ink)
    x, y = drop_xy(min(b, WORD - 0.4))
    return im, d, (x, y)


def s_word(b, fi, im=None, d=None):
    """The word rises; the dot hops from the rest line to the first tittle; the others pop in on the beat."""
    if im is None:
        im, d = canvas(G.paper)
    wl = G.word
    word(d, G.ink, eo(prog(b, WORD - 0.2, WORD + 0.8)))
    sx, sy = drop_xy(WORD - 0.4)
    for i, (tx, ty, r) in enumerate(wl["tittles"]):
        if i == 0:
            p = io(prog(b, WORD, WORD + 1))
            x = lerp(sx, tx, p)
            y = lerp(sy, ty, p) - math.sin(math.pi * p) * 160 * G.S
            rr = lerp(26 * G.S, r, p)
            dot(d, x, y, rr, G.acc)
        else:
            land = WORD + 1 + i
            dot(d, tx, ty, r * spring(B(b - land + 0.25), 320, 22), G.acc)
    if b >= WORD + 2:
        T(d, (G.W / 2, wl["base"] + 120 * G.S), G.c["kind"], "sans_medium", 40, G.ink, 0, "mm", G.W * 0.84)
    return im, d


# ------------------------------------------------------------------ a month of dots
def month_grid():
    n = G.c["days"]
    cols = 7
    pitch = 104 * G.S
    x0 = (G.W - (cols - 1) * pitch) / 2
    y0 = 330 * G.S
    cells = [(x0 + (k % cols) * pitch, y0 + (k // cols) * pitch) for k in range(n)]
    return cells, pitch * 0.34


def s_month(b, fi):
    im, d = canvas(G.paper)
    cells, r = month_grid()
    kept = set(G.c["kept"])
    tx, ty, tr = G.word["tittles"][0] if G.word["tittles"] else (G.W / 2, G.H / 2, r)
    out = io(prog(b, MONTH - 0.2, MONTH + 0.6))
    if out < 1:                                                      # the word sinks away, its tittle stays
        word(d, G.ink, 1 - out)
        for i, (x, y, rr) in enumerate(G.word["tittles"][1:]):
            dot(d, x, y, rr * (1 - out), G.acc)
    p = io(prog(b, MONTH, MONTH + 1))                                # day one: the tittle moves to its cell
    dot(d, lerp(tx, cells[0][0], p), lerp(ty, cells[0][1], p), lerp(tr, r, p), G.acc)
    for k in range(1, len(cells)):
        land = MONTH + 1 + k * 0.125
        q = spring(B(b - land), 320, 24)
        if b < land:
            continue
        x, y = cells[k]
        if (k + 1) in kept:
            dot(d, x, y, r * q, G.acc)
        else:
            ring(d, x, y, r * 0.55 * min(1, q), G.ink, 2.2 * G.S)
    if b >= MONTH + 0.5:
        T(d, (cells[0][0] - r, 200 * G.S), G.c["habit"], "sans_black", 54, G.ink, -0.5, "la", G.W * 0.62)
        T(d, (cells[6][0] + r, 214 * G.S), G.c["month"], "sans_medium", 36, mix(G.paper, G.ink, 0.6), 0, "ra", G.W * 0.3)
    if b >= MONTH + 6:
        s = G.c["count"]
        n = max(1, int(len(s) * eo(prog(b, MONTH + 6, MONTH + 6.6)) + 0.999))
        T(d, (cells[0][0] - r, cells[-1][1] + r + 70 * G.S), s[:n], "sans_black", 54, G.ink, -0.5, "la", G.W * 0.8, s)
    return im, d


# ------------------------------------------------------------------ flood + features
def last_kept():
    cells, r = month_grid()
    k = max(G.c["kept"]) - 1
    return cells[min(k, len(cells) - 1)], r


def s_flood(b, fi):
    (x, y), r = last_kept()
    p = eo(prog(b, FLOOD - 0.15, FLOOD + 0.55))                      # clears the farthest corner in ~0.35 s
    R = math.hypot(max(x, G.W - x), max(y, G.H - y)) * 1.05
    if p < 1:
        im, d = s_month(b, fi)
        dot(d, x, y, lerp(r, R, p), G.acc)
        return im, d
    im, d = canvas(G.acc)
    feats = G.c["features"][:3]
    for i, s in enumerate(feats):
        land = FLOOD + 1 + 2 * i
        q = eo(prog(b, land - 0.5, land))
        if q <= 0:
            continue
        y0 = (300 + i * 200) * G.S + (1 - q) * 40 * G.S
        dot(d, 120 * G.S, y0 + 28 * G.S, 16 * G.S * spring(B(b - land + 0.5), 320, 22), G.ink)
        lines = wrap(s, F("sans_black", int(56 * G.S)), G.W - 300 * G.S)
        for j, ln in enumerate(lines[:2]):
            T(d, (170 * G.S, y0 + j * 66 * G.S), ln, "sans_black", 56, G.ink, -0.5, "la", G.W - 260 * G.S)
    return im, d


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


# ------------------------------------------------------------------ the year as a halftone that follows the dot
def year_values():
    def make():
        vals = []
        for k in range(26 * 14):
            v = h(G.seed, k)
            season = 0.55 + 0.45 * math.sin(k / 364 * 2 * math.pi - 1.2)
            vals.append(0.0 if v > 0.82 else min(1.0, 0.25 + v * season))
        return np.array(vals, np.float32)
    if not hasattr(G, "_yv"):
        G._yv = make()
    return G._yv


def s_year(b, fi):
    cols, rows = 26, 14
    pitch = (G.W - 120 * G.S) / cols
    x0, y0 = 60 * G.S + pitch / 2, (G.H - (rows - 1) * pitch) / 2 + 50 * G.S
    vals = year_values()
    # the focal dot orbits the field; nearby dots swell (the halftone follows it)
    a = B(b - YEAR) * 1.4
    fx, fy = G.W / 2 + math.cos(a) * 300 * G.S, y0 + rows * pitch / 2 + math.sin(a * 1.3) * 180 * G.S
    grow = io(prog(b, FLIP, END))                                     # dots swell past the frame until it flips to ink
    ground = G.acc
    im, d = canvas(ground)
    if grow >= 1:
        return canvas(G.ink)
    for k in range(cols * rows):
        c, r = k % cols, k // cols
        x, y = x0 + c * pitch, y0 + r * pitch
        z = 1 + 3.5 * grow                                            # the field grows past the frame around the dot
        x, y = fx + (x - fx) * z, fy + (y - fy) * z
        appear = spring(B(b - YEAR - (c + r) * 0.06), 320, 26)
        if appear <= 0:
            continue
        dist = math.hypot(x - fx, y - fy) / (360 * G.S)
        swell = 1 + 0.6 * max(0.0, 1 - dist) ** 2
        base = (0.12 + 0.36 * vals[k]) * pitch * swell
        rr = lerp(base, pitch * 0.75, min(1.0, grow * 1.6)) * z * appear
        if vals[k] == 0 and grow < 0.05:
            ring(d, x, y, pitch * 0.12 * appear, G.ink, 1.6 * G.S)
        else:
            dot(d, x, y, rr, G.ink)
    dot(d, fx, fy, 15 * G.S * (1 - grow), G.paper)
    if b >= YEAR + 1 and grow < 0.3:
        T(d, (60 * G.S, y0 - pitch - 70 * G.S), G.c["year"], "sans_black", 54, G.ink, -0.5, "la", G.W - 120 * G.S)
    if grow > 0:                                                     # the gaps close: fill to ink as the dots merge
        cover = Image.new("RGB", im.size, G.ink)
        im = Image.blend(im, cover, max(0.0, (grow - 0.7) / 0.3))
        d = ImageDraw.Draw(im)
        d.im_ref = im
    return im, d


# ------------------------------------------------------------------ end: ink ground, the word, the dot lands again
def s_end(b, fi):
    im, d = canvas(G.ink)
    wl = G.word
    word(d, G.paper, eo(prog(b, END, END + 1)))
    for i, (tx, ty, r) in enumerate(wl["tittles"]):
        land = END + 1.5 + i
        fall = spring(B(b - land + 0.4), K, D)
        y = lerp(-60 * G.S, ty, fall)
        if b >= land - 0.4:
            dot(d, tx, y, r, G.acc)
    if b >= END + 3.5:
        T(d, (G.W / 2, wl["base"] + 120 * G.S), G.c["offer"], "sans_medium", 42, G.paper, 0, "mm", G.W * 0.84)
    if b >= END + 4.5:
        T(d, (G.W / 2, wl["base"] + 190 * G.S), G.c["url"], "sans_black", 42, G.acc, 0, "mm", G.W * 0.84)
    return im, d


def frame(c):
    b = c.t / G.spb + 0.1
    if b < WORD:
        im, d, xy = s_drop(b, c.fi)
        dot(d, xy[0], xy[1], 26 * G.S, G.acc)
        return finish(im)
    if b < MONTH - 0.2:
        if b < WORD + 0.7:                                          # the curve finishes erasing under the rising word
            im, d, _ = s_drop(b, c.fi)
            im, d = s_word(b, c.fi, im, d)
        else:
            im, d = s_word(b, c.fi)
        return finish(im)
    if b < FLOOD - 0.15:
        return finish(s_month(b, c.fi)[0])
    if b < YEAR:
        return finish(s_flood(b, c.fi)[0])
    if b < END:
        return finish(s_year(b, c.fi)[0])
    return finish(s_end(b, c.fi)[0])


# ------------------------------------------------------------------ sound
def score(path, dur):
    sc = Score(120, dur)
    # the drop: a blip on every bounce peak of the spring (where velocity flips)
    bs = np.linspace(0, WORD - 0.4, 400)
    ys = [drop_xy(k)[1] for k in bs]
    for i in range(1, len(ys) - 1):
        if (ys[i] - ys[i - 1]) * (ys[i + 1] - ys[i]) < 0:
            sc.hit("blip", B(bs[i]), 0.7 * math.exp(-i / 200), note="A5")
    sc.hit("tick", B(0.3), 0.6)
    sc.hit("clack", B(WORD + 1), 1.0, pitch=1.5)
    for i in range(1, len(G.word["tittles"])):
        sc.hit("clack", B(WORD + 1 + i), 0.9, pitch=1.68)
    sc.keys([("A4", WORD, 2), ("E5", WORD + 2, 2)], gain=0.5)
    kept = set(G.c["kept"])
    for k in range(1, G.c["days"]):
        if (k + 1) in kept:
            sc.hit("blip", B(MONTH + 1 + k * 0.125), 0.45, pan=((k % 7) - 3) / 5, note=["A5", "C6", "D6", "E6", "G6", "A6", "C7"][k % 7])
        else:
            sc.hit("tick", B(MONTH + 1 + k * 0.125), 0.4, pitch=0.7)
    sc.pattern("kick", every=1, start=MONTH, end=END + 6, gain=0.8)
    sc.pattern("hat", every=0.5, start=FLOOD, end=FLIP, gain=0.45)
    sc.hit("thud", B(FLOOD), 1.2)
    for i in range(3):
        sc.hit("clack", B(FLOOD + 1 + 2 * i), 0.9, pitch=1.26)
    bass = [("A1", 0, 2), ("A1", 2, 1), ("C2", 3, 1), ("F1", 4, 2), ("G1", 6, 2)]
    for k in range(MONTH, END + 8, 8):
        sc.bass(bass, start=B(k), gain=0.55)
    sc.hit("riser", B(FLIP), 1.0, dur=B(END - FLIP))
    sc.hit("thud", B(END), 1.3)
    for i in range(len(G.word["tittles"])):
        sc.hit("clack", B(END + 1.5 + i), 1.0, pitch=1.5 + 0.18 * i)
    sc.chord(["A3", "C4", "E4", "G4"], B(END), dur - B(END), 0.8)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("dot", B(TOTAL), frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    need = ("brand", "kind", "habit", "month", "kept", "days", "count", "features", "year", "offer", "url")
    errs += [f"copy.{k} missing" for k in need if k not in G.c]
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    if "i" not in G.c["brand"]:
        errs.append("the brand needs a lowercase i: the dot lands as its tittle (set the brand in lowercase)")
    lines = [G.c[k] for k in ("kind", "habit", "count", "year", "offer", "url")] + G.c["features"]
    errs += [f"trailing period: {s!r}" for s in lines if s.rstrip().endswith(".")]
    if not 28 <= G.c["days"] <= 31 or any(not 1 <= k <= G.c["days"] for k in G.c["kept"]):
        errs.append("days must be 28–31 and kept days within it")
    if len(G.c["features"]) > 3:
        errs.append("at most 3 features")
    from framesmith.score import INSTRUMENTS  # noqa: F401  (score deps import cleanly)
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.3, tl.duration - 0.05, 20):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{tl.duration:.2f}s, {tl.n_frames} frames, {len(G.word['tittles'])} tittle(s) in '{G.c['brand']}'")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "tiri", "brief.json"))
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
        print(tl.render(a.out or os.path.join(out, "halftone-dot-film.mp4"), audio))


if __name__ == "__main__":
    main()
