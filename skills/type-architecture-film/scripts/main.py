#!/usr/bin/env python3
"""type-architecture-film: a spoken-word statement staged as architecture (1:1, 20 s, loops).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1 4.8 7.9 9.4 11.8 15 19.6
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

Five lines, each with a word that takes a structural role, built from the letterforms themselves:
a heavy LINTEL presses on a narrow opening; a LOAD hangs on two fine cables and bends the baseline;
a vertical SUPPORT lifts one end; the counter of an APERTURE word opens onto the next composition;
a second SUPPORT levels the floor (the film's first perfect horizontal, then 400 ms of stillness);
the floor becomes a platform and the last line settles on it. The end tracks beneath the platform
and its underside wipes back to the opening frame, so render(0) == render(20).
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from framesmith import Scene, Theme, Timeline, prog, text, text_width, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.score import Score

G = None
DUR = 20.0
# cue sheet (seconds): phrase-led, not beat-led
A1, A2, A3, APT, A4, STILL, A5, HOLD, LOOP = 0.0, 3.0, 6.5, 8.6, 10.0, (11.6, 12.05), 12.4, 16.0, 18.0


def io(p):
    p = min(1.0, max(0.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def settle(t, w=6.0):
    """Critically damped step (no overshoot): how loads come to rest."""
    if t <= 0:
        return 0.0
    return 1 - (1 + w * t) * math.exp(-w * t)


def lerp(a, b, p):
    return a + (b - a) * p


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        x = self.th.extra
        self.ground, self.accent = x["ground"], self.th.accent
        self.paper = self.th.paper
        self.W, self.H = brief.get("size", [1080, 1080])
        self.fps = brief.get("fps", 30)
        self.S = self.W / 1080
        self._c = {}

    def cached(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


def P(v):
    return v * G.S


# ------------------------------------------------------------------ glyph images
def heavy(word, width, max_size=420):
    """A structural word: Inter Display Black, tight-cropped L image fitted to `width` px."""
    def make():
        f0 = F("sans_black", 200)
        size = min(max_size, int(200 * width / max(1, text_width(word, f0, -6))))
        f = F("sans_black", size)
        im = Image.new("L", (int(text_width(word, f, -6 * size / 200) + 40), int(size * 1.3)), 0)
        text(ImageDraw.Draw(im), (20, size * 1.05), word, f, 255, -6 * size / 200, "ls")
        return im.crop(im.getbbox())
    return G.cached(("heavy", word, int(width), max_size), make)


def put(m, glyph, x, y, rot=0):
    """Paste a glyph image into mask m with its top-left at (x, y), optionally rotated 90° (reads bottom → top)."""
    g = glyph.rotate(rot, expand=True) if rot else glyph
    layer = Image.new("L", m.size, 0)
    layer.paste(g, (int(round(x)), int(round(y))))
    m.paste(ImageChops.lighter(m, layer))
    return g.size


def groups(s, n=3):
    w = s.split()
    k = max(1, math.ceil(len(w) / n))
    return [" ".join(w[i:i + n]) for i in range(0, len(w), n)] if len(w) > n else [s]


def phrase(m, s, x, y, size, t0, t1, out=None, anchor="ls", max_w=None, lines=1):
    """The line in serif, revealed in reading order by phrase groups that rise out of their baseline.
    out=(a, b) sinks it back under the baseline. Wraps to `lines` lines inside max_w."""
    max_w = max_w or G.W - P(180)
    f = F("serif", int(P(size)))
    rows = wrap(s, f, max_w) if lines > 1 else [s]
    sink = io(prog(TT, *out)) if out else 0.0
    if sink >= 1:
        return
    items = []                                                      # (text, x, baseline y)
    for ri, row in enumerate(rows):
        rx = x - text_width(row, f) / 2 if anchor[0] == "m" else x
        off = 0.0
        for g in groups(row, 3):
            items.append((g, rx + off, y + ri * f.size * 1.08))
            off += text_width(g + " ", f)
    n = len(items)
    for i, (g, gx, gy) in enumerate(items):
        p = eo(prog(TT, t0 + (t1 - t0) * i / n, t0 + (t1 - t0) * (i + 1) / n))
        p = min(p, 1 - sink)
        if p <= 0:
            continue
        L = Image.new("L", (int(text_width(g, f) + 20), int(f.size * 1.4)), 0)
        text(ImageDraw.Draw(L), (10, f.size * 1.05), g, f, 255, 0, "ls", max_w=max_w, fit_to=g)
        shift = int((1 - p) * f.size * 1.1)                          # masked at the line box: rises from below
        layer = Image.new("L", m.size, 0)
        layer.paste(L.crop((0, 0, L.width, L.height - shift)), (int(gx - 10), int(gy - f.size * 1.05) + shift))
        m.paste(ImageChops.lighter(m, layer))


def wrap(s, f, w):
    out, cur = [], ""
    for tok in s.split():
        t = (cur + " " + tok).strip()
        if cur and text_width(t, f) > w:
            out.append(cur)
            cur = tok
        else:
            cur = t
    return out + ([cur] if cur else [])


TT = 0.0          # current time, read by phrase()


# ------------------------------------------------------------------ the structure as a function of time
def rule_state(t):
    """Baseline: x span, left/right heights and sag (controlled elastic deformation, the only one in the film)."""
    x0 = lerp(P(90), P(140), io(prog(t, A2, A2 + 0.6)))
    x1 = lerp(P(990), P(940), io(prog(t, A2, A2 + 0.6)))
    comp = io(prog(t, 0.3, 2.8))                                   # the opening compresses
    y = lerp(P(780), P(700), comp)
    y = lerp(y, P(560), io(prog(t, A2, A2 + 0.6)))
    yl = yr = y
    load = settle(t - (A2 + 0.9), 4.5)
    sag = P(44) * load
    lift_r = settle(t - (A3 + 0.7), 5)                             # support A lifts the right end
    yr -= P(40) * lift_r
    sag *= 1 - 0.5 * lift_r
    lift_l = settle(t - (A4 + 0.4), 5)                             # support B levels it
    yl -= P(40) * lift_l
    sag *= 1 - lift_l
    if t >= HOLD:                                                   # tension release in the hold
        sag += P(3) * math.sin((t - HOLD) * 9) * math.exp(-(t - HOLD) * 2.2)
    return x0, x1, yl, yr, sag


def rule_y(x, st):
    x0, x1, yl, yr, sag = st
    u = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
    return yl + (yr - yl) * u + sag * math.sin(math.pi * u)


def structure(t, m_paper, m_acc, act):
    """Draw the floor, load, supports and platform for the given time. act ≥ 4 means the load has gone."""
    c = G.c
    st = rule_state(t)
    x0, x1 = st[0], st[1]
    d = ImageDraw.Draw(m_paper)
    pts = [(x, rule_y(x, st)) for x in np.linspace(x0, x1, 60)]
    d.line(pts, fill=255, width=max(2, int(P(4))))
    # the load, on two cables, until the aperture
    if act < 4 and t >= A2 + 0.3:
        g = heavy(c["load"]["word"], P(700))
        k = settle(t - (A2 + 0.3), 4.5)
        cx = G.W / 2
        bottom = lerp(P(-40), rule_y(cx, st) - P(52) - (st[4] * 0.6), k)
        bottom -= P(700) * io(prog(t, APT - 0.35, APT + 0.25))       # released: the load lifts away before the aperture
        top = bottom - g.height
        ImageDraw.Draw(m_acc).line((cx - g.width / 2 + P(70), 0, cx - g.width / 2 + P(70), top), fill=255, width=max(1, int(P(2))))
        ImageDraw.Draw(m_acc).line((cx + g.width / 2 - P(70), 0, cx + g.width / 2 - P(70), top), fill=255, width=max(1, int(P(2))))
        put(m_acc, g, cx - g.width / 2, top)
    # supports: vertical words standing under the rule ends
    for key, t0, xc in (("support_a", A3 + 0.2, P(860)), ("support_b", A4 - 0.1, P(220))):
        if t < t0:
            continue
        g = heavy(c[key]["word"], P(470), 190)
        k = settle(t - t0, 4.2)
        gw, gh = g.height, g.width                                   # rotated 90°
        slab = P(30) * eo(prog(t, A5 + 0.2, A5 + 0.8))
        top_target = rule_y(xc, st) + slab + P(8)
        top = lerp(G.H + P(20), top_target, k)
        put(m_paper, g, xc - gw / 2, top, rot=90)
    # the platform: the floor thickens into an accent slab
    if t >= A5 + 0.2:
        th = P(30) * eo(prog(t, A5 + 0.2, A5 + 0.8))
        y = rule_y(G.W / 2, st)
        ImageDraw.Draw(m_acc).rectangle((x0, y - 1, x1, y + th), fill=255)


def frame_at(t, act=None):
    """Render the composition at time t (act forces the structure state for the aperture handoff)."""
    global TT
    TT = t
    c = G.c
    act = act or (1 if t < A2 else 2 if t < A3 else 3 if t < A4 else 4 if t < A5 else 5)
    mp = Image.new("L", (G.W, G.H), 0)
    ma = Image.new("L", (G.W, G.H), 0)
    st = rule_state(t)
    # act 1: the lintel presses on a narrow opening holding the first line
    if t < A2 + 0.7:
        g = heavy(c["lintel"]["word"], P(900))
        comp = io(prog(t, 0.3, 2.8))
        bottom = lerp(P(500), P(590), comp) - P(800) * eo(prog(t, A2, A2 + 0.6))
        put(mp, g, (G.W - g.width) / 2, bottom - g.height)
        mid = (bottom + rule_y(G.W / 2, st)) / 2
        phrase(mp, c["lintel"]["line"], G.W / 2, mid + P(22), 66, -1, -0.5, out=(A2 - 0.1, A2 + 0.3), anchor="ms", max_w=P(860))
        if act == 1:
            d = ImageDraw.Draw(mp)
            d.line([(x, rule_y(x, st)) for x in (st[0], st[1])], fill=255, width=max(2, int(P(4))))
    if act >= 2:
        phrase(mp, c["load"]["line"], G.W / 2, P(680), 66, A2 + 0.3, A2 + 2.4, out=(A3 - 0.2, A3 + 0.2), anchor="ms", lines=3, max_w=P(520))
    if act == 3:
        phrase(mp, c["support_a"]["line"], G.W / 2, P(680), 66, A3 + 0.2, A3 + 1.7, anchor="ms", lines=3, max_w=P(500))
    if act >= 4:
        phrase(mp, c["support_b"]["line"], G.W / 2, P(680), 66, A4 + 0.1, A4 + 1.3, out=(A5 - 0.1, A5 + 0.3), anchor="ms", lines=3, max_w=P(500))
    if act >= 2:
        structure(t, mp, ma, act)
    if act >= 5:                                                    # the last line settles onto the platform
        y = rule_y(G.W / 2, st)
        k = settle(t - (A5 + 0.5), 5)
        f_e = F("serif", int(P(250)))
        drop = (1 - k) * P(-260)
        phrase(mp, c["platform"]["line"], P(146), y - P(250) + drop * 0.6, 70, A5 + 0.5, A5 + 1.6, max_w=P(800))
        if t >= A5 + 1.4:
            k2 = settle(t - (A5 + 1.4), 5)
            text(ImageDraw.Draw(ma), (P(136), y - P(18) + (1 - k2) * P(-220)), c["platform"]["emphasis"], f_e, 255, -3, "ls", max_w=P(800))
        if t >= HOLD + 0.2:
            q = int(255 * eo(prog(t, HOLD + 0.2, HOLD + 0.8)))
            line = c["credit"].upper() + "   " + c["url"]
            text(ImageDraw.Draw(mp), (G.W / 2, P(1030)), line, F("sans_bold", int(P(20))), q, P(3), "ms", max_w=P(560))
    out = np.empty((G.H, G.W, 3), np.float32)
    out[:] = G.ground
    for m, col in ((mp, G.paper), (ma, G.accent)):
        a = np.asarray(m, np.float32)[..., None] / 255
        out = out * (1 - a) + np.array(col, np.float32) * a
    return out.astype(np.uint8)


# ------------------------------------------------------------------ the aperture: fly through the counter of a word's O
def aperture():
    def make():
        word = G.c["support_a"].get("aperture", "O").upper()
        g = heavy(word, P(720), 520)
        x, y = (G.W - g.width) / 2, (G.H - g.height) / 2 + P(40)
        m = Image.new("L", (G.W, G.H), 0)
        m.paste(g, (int(x), int(y)))
        k = word.find("O")
        hole = np.zeros((G.H, G.W), np.float32)
        if k >= 0:
            f = Image.new("L", (G.W, G.H), 0)
            f.paste(g, (int(x), int(y)))
            ImageDraw.floodfill(f, (2, 2), 128)
            a = np.asarray(f)
            hole = (a == 0).astype(np.float32)
            gx = int(x + g.width * (k + 0.5) / len(word))
            ys, xs = np.nonzero(hole)
            if len(xs):
                near = np.abs(xs - gx) < g.width / len(word) * 0.6
                hole[:] = 0
                hole[ys[near], xs[near]] = 1
        ys, xs = np.nonzero(hole)
        cx, cy = (float(xs.mean()), float(ys.mean())) if len(xs) else (G.W / 2, G.H / 2)
        return np.asarray(m, np.float32) / 255, hole, (cx, cy)
    return G.cached("aperture", make)


def frame(c):
    t = c.t
    if t >= LOOP:                                                   # track beneath the platform; its underside wipes back to frame 0
        st = rule_state(t)
        cam = P(700) * io(prog(t, LOOP, LOOP + 1.2))
        base = frame_at(LOOP - 0.01)
        out = np.roll(base, -int(cam), 0)
        y = int(rule_y(G.W / 2, st) - cam)
        out[max(0, y + int(P(30))):] = G.ground
        fill = io(prog(t, LOOP + 0.6, LOOP + 1.3))                  # the slab's underside fills the frame
        y_bottom = int(lerp(y + P(30), G.H, fill))
        out[max(0, y):max(0, y_bottom)] = G.accent
        wipe = io(prog(t, LOOP + 1.35, DUR - 0.05))
        if wipe > 0:
            first = frame_at(0.0)
            edge = int(G.H * (1 - wipe))
            out[edge:] = first[edge:]
        return out
    if APT <= t < A4:
        a = frame_at(t, 3)
        word_m, hole, (cx, cy) = aperture()
        rise = eo(prog(t, APT, APT + 0.5))
        shift = int((1 - rise) * P(300))
        wm = np.roll(word_m, shift, 0) if shift else word_m
        if shift:
            wm[:shift] = 0
        occ = io(prog(t, APT, APT + 0.45))                          # the word occludes everything behind it
        a = a.astype(np.float32) * (1 - occ) + np.array(G.ground, np.float32) * occ
        a = (a * (1 - wm[..., None]) + np.array(G.paper, np.float32) * wm[..., None]).astype(np.uint8)
        z = math.exp(math.log(30) * io(prog(t, APT + 0.6, A4)))
        if z <= 1.001:
            return a
        b = frame_at(t, 4)
        cw, ch = G.W / z, G.H / z
        box = (cx - cw * cx / G.W, cy - ch * cy / G.H)
        box = (box[0], box[1], box[0] + cw, box[1] + ch)
        az = np.asarray(Image.fromarray(a).resize((G.W, G.H), Image.BILINEAR, box=box), np.float32)
        hm = np.asarray(Image.fromarray((hole * 255).astype(np.uint8)).resize((G.W, G.H), Image.BILINEAR, box=box), np.float32)[..., None] / 255
        return (az * (1 - hm) + b.astype(np.float32) * hm).astype(np.uint8)
    return frame_at(t)


# ------------------------------------------------------------------ sound: phrase cues, not a dance beat
def score(path):
    sc = Score(60, DUR + 0.3)
    sc.chord(["D3", "A3", "E4"], 0.0, 3.2, 0.7)
    sc.keys([("D4", 0, 1.2)], start=0.2, gain=0.55)
    sc.hit("thud", A2 + 0.05, 0.5)
    sc.keys([("F4", 0, 1.2), ("A4", 1.4, 1.4)], start=A2 + 0.3, gain=0.5)
    sc.hit("thud", A2 + 1.1, 0.9)                                    # the load comes to rest
    sc.hit("clack", A3 + 0.75, 0.9, pitch=0.7)                       # support A seats
    sc.keys([("G4", 0, 1.2), ("D5", 1.3, 1.6)], start=A3 + 0.3, gain=0.5)
    sc.hit("riser", APT + 0.2, 0.6, dur=1.2)
    sc.hit("clack", A4 + 0.45, 1.0, pitch=0.8)                       # support B seats; then silence for the stillness
    sc.chord(["D3", "A3", "F#4"], STILL[1], 4.0, 0.75)
    sc.hit("thud", A5 + 0.7, 1.1)
    sc.keys([("A4", 0, 1.2), ("F#5", 1.0, 2.5)], start=A5 + 0.6, gain=0.55)
    sc.hit("clack", A5 + 1.55, 0.9, pitch=1.2)
    sc.chord(["D3", "A3", "E4"], LOOP, DUR - LOOP + 0.3, 0.7)
    sc.hit("slap", LOOP + 1.3, 0.8)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    return Timeline([Scene("speech", DUR, frame)], G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    c = G.c
    for k in ("lintel", "load", "support_a", "support_b", "platform", "credit", "url"):
        if k not in c:
            errs.append(f"copy.{k} missing")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    for k in ("lintel", "load", "support_a", "support_b", "platform"):
        s = c[k]["line"]
        if s.rstrip().endswith("."):
            errs.append(f"trailing period: {s!r}")
    for k in ("lintel", "load", "support_a", "support_b"):
        w = c[k]["word"]
        if w.upper() not in c[k]["line"].upper():
            print(f"warn: {k} word {w!r} is not in its line; the role should come from a spoken word")
    ap = c["support_a"].get("aperture", "")
    if "O" not in ap.upper():
        errs.append("support_a.aperture needs an O: its counter is the window into the next composition")
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.1, DUR - 0.05, 22):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    a, b = tl.frame(0), tl.frame(tl.n_frames - 1)
    diff = np.abs(a.astype(int) - b.astype(int)).mean()
    print(f"{DUR:.2f}s, {tl.n_frames} frames; loop seam mean diff {diff:.1f}/255")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "halden", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("fully typographic: no image slots.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=8, rows=3, thumb_w=200))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, "type-architecture-film.mp4"), audio))


if __name__ == "__main__":
    main()
