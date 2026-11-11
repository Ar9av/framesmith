#!/usr/bin/env python3
"""riso-poster-promo: a two-plate risograph street-poster promo (9:16, 120 BPM, ~20 s).

    python3 main.py check  --brief brief.json
    python3 main.py assets --brief brief.json            # gpt-image product photo (halftoned in the film)
    python3 main.py still  --brief brief.json 1 5 9 17 26 34
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

Two inks (default fluorescent pink and riso blue) multiplied onto paper, riso grain re-rolled every
other frame, a ghost plate that misregisters only on impact frames, glyphs that slam in on 1/16-note
staggers, letters that scramble and snap on the beat, and a fly-through the counter of an O.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Assets, Scene, Theme, Timeline, cover, generate_images, h, prog, text, text_width, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith.motion import spring
from framesmith import press
from framesmith.score import Score

G = None
ASSET_SLOTS = ("hero",)


def eo(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


class State:
    def __init__(self, brief, base):
        self.b, self.c, self.base = brief, brief["copy"], base
        self.th = Theme.from_dict(brief.get("theme"))
        self.A, self.B = self.th.extra["plate_a"], self.th.extra["plate_b"]
        self.W, self.H = brief.get("size", [1080, 1920])
        self.fps = brief.get("fps", 30)
        self.bpm = brief.get("bpm", 120)
        self.spb = 60 / self.bpm
        self.seed = brief.get("seed", 11)
        self.assets = Assets(os.path.join(base, brief.get("assets_dir", "assets")), os.path.join(HERE, "..", "placeholders"))
        self._c = {}

    def cached(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


def B(k):
    return k * G.spb


# ------------------------------------------------------------------ type helpers
def fit_size(s, role, width, cap=900):
    f = F(role, 100)
    w = text_width(s, f, -2)
    return max(12, min(cap, int(100 * width / max(w, 1))))


def mask(fn):
    m = Image.new("L", (G.W, G.H), 0)
    fn(ImageDraw.Draw(m), m)
    return np.asarray(m, np.float32) / 255


def slam(d, s, font, x, y, lt, t0, stagger=None, track=-2, anchor="ls", seed=0):
    """Glyphs drop in one by one on 1/16-note staggers with a snappy spring (baseline anchored)."""
    stagger = stagger if stagger is not None else G.spb / 4
    if anchor[0] == "m":
        x -= text_width(s, font, track) / 2
    for i, ch in enumerate(s):
        ti = lt - t0 - i * stagger
        if ti >= 0:
            dy = (1 - spring(ti, 320, 26)) * -font.size * 0.75
            d.text((x, y + dy), ch, font=font, fill=255, anchor="l" + anchor[1])
        x += font.getlength(ch) + track


def shuffled(s, k):
    """Seeded Fisher–Yates shuffle of a word's letters (spaces stay put)."""
    idx = [i for i, ch in enumerate(s) if ch != " "]
    chars = [s[i] for i in idx]
    for i in range(len(chars) - 1, 0, -1):
        j = int(h(G.seed, k, i) * (i + 1))
        chars[i], chars[j] = chars[j], chars[i]
    out = list(s)
    for i, ch in zip(idx, chars):
        out[i] = ch
    return "".join(out)


def snap(s, lt, land, fi):
    """Scrambled until the beat it lands on, re-shuffled every 2 frames, then exact."""
    return s if lt >= land else shuffled(s, fi // 2)


# ------------------------------------------------------------------ halftone photo (cached duotone)
def photo_plates(box):
    """Duotone halftone of the hero photo inside box: plate B carries the shadows (15°), plate A the mids (75°)."""
    def make():
        x0, y0, x1, y1 = box
        im = cover(G.assets.get("hero").convert("L"), x1 - x0, y1 - y0)
        g = np.asarray(im, np.float32) / 255
        lo, hi = np.percentile(g, 3), np.percentile(g, 97)
        g = np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1)
        dark = 1 - g
        b = press.halftone(np.clip(dark * 1.15 - 0.08, 0, 1) ** 1.25, pitch=11, angle=15)
        a = press.halftone(np.clip(1 - np.abs(dark - 0.45) * 2.2, 0, 1) * 0.55, pitch=11, angle=75)
        A = np.zeros((G.H, G.W), np.float32)
        Bm = np.zeros_like(A)
        A[y0:y1, x0:x1] = a
        Bm[y0:y1, x0:x1] = b
        return A, Bm
    return G.cached(("photo", box), make)


# ------------------------------------------------------------------ scenes → (plate A mask, plate B mask, impacts)
# impacts: global times of slams; the ghost plate misregisters for a few frames after each.
def s_slam(c):
    C = G.c
    word = C["slam"].upper()
    f = F("condensed", fit_size(word, "condensed", G.W - 90, 760))

    def a(d, m):
        slam(d, word, f, 45, G.H * 0.62, c.lt, 0.0)
    def b(d, m):
        if c.lt > B(1):
            text(d, (48, 70), C["brand"].upper(), F("condensed", 64), 255, 1, max_w=G.W - 96)
        if c.lt > B(2):
            text(d, (48, G.H * 0.62 + 70), C["kicker"].upper(), F("condensed", 92), 255, 0, max_w=G.W - 96)
        if c.lt > B(3):
            text(d, (G.W - 48, 72), C["product"], F("pixel", 44), 255, 0, "ra", max_w=G.W * 0.4)
            text(d, (G.W - 48, 132), C["ships"], F("pixel", 22), 255, 0, "ra", max_w=G.W * 0.55)
    Bm = mask(b)
    top = G.H * (1 - 0.34 * eo(prog(c.lt, 0, B(2))))              # a halftone ramp rises from the foot of the page
    y0 = int(G.H * 0.64)
    yy = np.arange(y0, G.H, dtype=np.float32)[:, None]
    field = np.clip((yy - top) / (G.H - top + 1) * 1.3, 0, 1) * np.ones((1, G.W), np.float32)
    field *= 1 + 0.08 * np.sin(np.arange(G.W) / 60 + c.t * 3)[None]
    ramp = press.halftone(np.clip(field, 0, 1), pitch=14, angle=15)
    Bm[y0:] = np.maximum(Bm[y0:], ramp)
    return mask(a), Bm, [B(k / 4) for k in range(len(word))] + [B(1), B(2), B(3)]


ECHO_ROWS = 5


def echo_layout():
    word = G.c["echo"].upper()
    rh = G.H / ECHO_ROWS
    f = F("condensed", fit_size(word, "condensed", G.W - 150, int(rh * 0.98)))
    return word, f, rh


def s_echo(c):
    """The word repeats down the page like delay taps: eighth-note apart, alternating plates, decaying ink."""
    word, f, rh = echo_layout()
    A = np.zeros((G.H, G.W), np.float32)
    Bm = np.zeros_like(A)
    for i in range(ECHO_ROWS):
        t0 = B(i * 0.5)
        if c.lt < t0:
            continue
        wow = math.sin(c.t * 5 + i) * i * 3                    # tape wow: later taps wander a little
        m = mask(lambda d, _: slam(d, word, f, 45 + i * 14 + wow, rh * (i + 1) - 22, c.lt, t0, G.spb / 8))
        k = 1.0 - i * 0.16
        if i % 2 == 0:
            A = np.maximum(A, m * k)
        else:
            Bm = np.maximum(Bm, m * k)
    return A, Bm, [B(i * 0.5) for i in range(ECHO_ROWS)]


def echo_counter():
    """Centre and counter mask of the first O in the middle echo row (for the fly-through)."""
    def make():
        word, f, rh = echo_layout()
        i = ECHO_ROWS // 2
        k = word.find("O") if "O" in word else len(word) - 1
        x = 45 + i * 14 + text_width(word[:k], f, -2) + (-2 if k else 0)
        y = rh * (i + 1) - 22
        m = Image.new("L", (G.W, G.H), 0)
        ImageDraw.Draw(m).text((x, y), word[k], font=f, fill=255, anchor="ls")
        bb = m.getbbox()
        fill = m.copy()
        ImageDraw.floodfill(fill, (bb[0] - 2, bb[1] - 2), 128)
        a = np.asarray(fill)
        hole = (a == 0).astype(np.float32)
        hole[: bb[1]] = 0
        hole[bb[3]:] = 0
        hole[:, : bb[0]] = 0
        hole[:, bb[2]:] = 0
        ys, xs = np.nonzero(hole)
        if len(xs) == 0:                                      # no counter (e.g. letter without a hole): use the glyph
            hole = np.asarray(m, np.float32) / 255
            ys, xs = np.nonzero(hole)
        return (float(xs.mean()), float(ys.mean())), hole
    return G.cached("counter", make)


def s_product(c):
    C = G.c
    box = (40, 300, G.W - 40, 1460)
    A, Bm = (x.copy() for x in photo_plates(box))

    def b(d, m):
        text(d, (48, 70), C["product"], F("condensed", 150), 255, -1, max_w=G.W * 0.45)
        text(d, (G.W - 48, 92), C["kicker"].upper(), F("pixel", 33), 255, 0, "ra", max_w=G.W * 0.5)
        text(d, (G.W - 48, 150), C["brand"].upper(), F("pixel", 22), 255, 0, "ra", max_w=G.W * 0.5)
    Bm = np.maximum(Bm, mask(b))
    specs = C["specs"][:3]
    cw = (G.W - 96) / len(specs)
    fs = F("condensed", min(fit_size(big, "condensed", cw - 30, 150) for big, _ in specs))
    for i, (big, small) in enumerate(specs):
        land = B(1 + 2 * i)
        if c.lt < land - B(0.25):
            continue
        x = 48 + i * cw
        A = np.maximum(A, mask(lambda d, _: slam(d, big, fs, x, 1700, c.lt, land - B(0.25), G.spb / 8)))
        if c.lt >= land:
            Bm = np.maximum(Bm, mask(lambda d, _: text(d, (x, 1745), small.upper(), F("pixel", 22), 255, 0, max_w=cw - 20)))
    return A, Bm, [B(0)] + [B(1 + 2 * i) for i in range(len(specs))]


def s_facts(c):
    """Inverse-video bands: each fact is paper knocked out of a solid plate, scrambled until its beat."""
    facts = G.c["facts"][:4]
    A = np.zeros((G.H, G.W), np.float32)
    Bm = np.zeros_like(A)
    band, gap = 210, 46
    y0 = (G.H - len(facts) * band - (len(facts) - 1) * gap) / 2
    for i, s in enumerate(facts):
        land = B(2 * i)
        if c.lt < land - B(0.5):
            continue
        y = y0 + i * (band + gap)
        p = eo(prog(c.lt, land - B(0.5), land))
        left = i % 2 == 0
        x0, x1 = (0, G.W * p) if left else (G.W * (1 - p), G.W)
        word = snap(s.upper(), c.lt, land, c.fi)
        f = F("condensed", fit_size(s.upper(), "condensed", G.W - 120, 150))

        def draw(d, m):
            d.rectangle((x0, y, x1, y + band), fill=255)
            text(d, (60, y + band / 2 + f.size * 0.36), word, f, 0, -2, "ls", max_w=G.W - 120, fit_to=s.upper())
        m = mask(draw)
        if left:
            A = np.maximum(A, m)
        else:
            Bm = np.maximum(Bm, m)
    return A, Bm, [B(2 * i) for i in range(len(facts))]


def s_hero(c):
    """The product name, rotated to run the full height, its glyphs filled with the halftone photo."""
    name = G.c["product"].upper()
    f = F("condensed", fit_size(name, "condensed", G.H - 140, 1000))
    pan = (1 - eo(prog(c.lt, 0, B(0.5)))) * G.W * 1.1                 # smash pan in from the right
    def glyphs():
        tw = int(text_width(name, f, -4)) + 40
        L = Image.new("L", (tw, int(f.size * 1.05)), 0)
        text(ImageDraw.Draw(L), (20, f.size * 0.9), name, f, 255, -4, "ls")
        L = L.crop(L.getbbox()).rotate(90, expand=True)
        return L
    L = G.cached(("hero_glyphs", name), glyphs)
    m = Image.new("L", (G.W, G.H), 0)
    x = int((G.W - L.width) / 2 + pan)
    m.paste(L, (x, int((G.H - L.height) / 2)))
    gm = np.asarray(m, np.float32) / 255
    A_ph, B_ph = photo_plates((0, 0, G.W, G.H))
    Bm = B_ph * gm
    A = press.shift(gm, 10, 8) * 0.85                                   # flat pink ghost under the halftone
    def crumbs(d, _):
        if c.lt > B(2):
            text(d, (48, G.H - 70), G.c["brand"].upper(), F("pixel", 22), 255, 0, max_w=G.W * 0.5)
        if c.lt > B(3):
            text(d, (G.W - 48, 70), G.c["kicker"].upper(), F("pixel", 22), 255, 0, "ra", max_w=G.W * 0.5)
    Bm = np.maximum(Bm, mask(crumbs))
    return A, Bm, [B(0.5), B(4)]


def s_end(c):
    C = G.c
    fb = F("condensed", fit_size(C["brand"].upper(), "condensed", G.W - 96, 180))
    fp = F("condensed", fit_size(C["product"], "condensed", G.W - 96, 620))
    fpr = F("condensed", fit_size(C["price"], "condensed", G.W - 96, 560))

    def a(d, m):
        slam(d, C["product"], fp, 48, 880, c.lt, B(0.5))
        if c.lt > B(4):
            slam(d, C["price"], fpr, 40, 1600, c.lt, B(4))
    def b(d, m):
        slam(d, C["brand"].upper(), fb, 48, 60 + fb.size * 0.85, c.lt, 0)
        if c.lt > B(2.5):
            text(d, (52, 950), C["kicker"].upper(), F("pixel", 44), 255, 0, max_w=G.W - 104)
        if c.lt > B(5):
            text(d, (52, 1660), C["ships"], F("pixel", 33), 255, 0, max_w=G.W - 104)
        if c.lt > B(6):
            text(d, (52, G.H - 110), C["url"], F("condensed", 84), 255, 0, max_w=G.W - 104)
    return mask(a), mask(b), [0, B(0.5), B(2.5), B(4), B(5), B(6)]


SCENES = [("slam", 4, s_slam), ("echo", 4, s_echo), ("product", 8, s_product), ("facts", 8, s_facts),
          ("hero", 8, s_hero), ("end", 8, s_end)]


# ------------------------------------------------------------------ compositor
def composite(c, fn):
    A, Bm, impacts = fn(c)
    t0 = c.t - c.lt
    since = min([c.lt - k for k in impacts if c.lt >= k] or [9])
    kick = math.exp(-since * 14)                                      # ~4 frames of misregistration per impact
    k = int((c.t - since) * 1000)
    ghost = (round(4 * kick * (1 if h(G.seed, k) > 0.5 else -1)), round(3 * kick * (1 if h(G.seed, k, 1) > 0.5 else -1)))
    gA = press.grain((G.W, G.H), c.fi, 0.2, 2, G.seed, 2)
    gB = press.grain((G.W, G.H), c.fi, 0.2, 2, G.seed + 1, 2)
    layers = [(Bm * gB, G.B, ghost), (A * gA, G.A, (0, 0))]
    if kick > 0.08:                                                  # ghost plate: a 40 % duplicate on impact frames only
        layers.append((A * 0.4 * kick, G.B, (ghost[0] * 2, ghost[1] * 2)))
    out = press.plates(press.paper((G.W, G.H), G.th.paper, G.seed, 0.05), layers, press.tooth((G.W, G.H), G.seed), 0.25)
    z = 1 + 0.045 * math.exp(-since * 7) * (since < 9)               # punch-in on every impact, decaying
    if z > 1.002:
        im = Image.fromarray(out)
        cw, ch = G.W / z, G.H / z
        out = np.asarray(im.resize((G.W, G.H), Image.BILINEAR, box=((G.W - cw) / 2, (G.H - ch) / 2, (G.W + cw) / 2, (G.H + ch) / 2)))
    return out


class ThroughO:
    """Fly through the counter of an O: the outgoing frame zooms into the hole, which reveals the next scene."""
    def __init__(self, dur):
        self.dur = dur

    def blend(self, a, b, p, theme=None):
        (cx, cy), hole = echo_counter()
        z = math.exp(math.log(28) * (p ** 2.2))
        im = Image.fromarray(a)
        cw, ch = G.W / z, G.H / z
        box = (cx - cw * cx / G.W, cy - ch * cy / G.H)
        box = (box[0], box[1], box[0] + cw, box[1] + ch)
        az = np.asarray(im.resize((G.W, G.H), Image.BILINEAR, box=box), np.float32)
        hm = Image.fromarray((hole * 255).astype(np.uint8)).resize((G.W, G.H), Image.BILINEAR, box=box)
        hm = np.asarray(hm, np.float32)[..., None] / 255
        return (az * (1 - hm) + b.astype(np.float32) * hm).astype(np.uint8)


# ------------------------------------------------------------------ sound
def score(path, tl):
    sc = Score(G.bpm, tl.duration + 0.5)
    starts = {s.name: st for s, st in zip(tl.scenes, tl.starts)}
    sc.pattern("kick", every=1, start=4, end=len(tl.scenes) * 8 - 6, gain=0.95)
    sc.pattern("hat", every=0.5, start=4.5, end=len(tl.scenes) * 8 - 6, gain=0.45)
    sc.pattern("snare", every=2, start=9, end=31, gain=0.6)
    for k in range(len(G.c["slam"])):
        sc.hit("clack", B(k / 4), 0.9, pitch=0.7 + 0.1 * k)
    sc.hit("thud", 0, 1.2)
    for i in range(ECHO_ROWS):                                        # the delay taps, decaying
        sc.hit("blip", starts["echo"] + B(i * 0.5), 0.8 * (1 - i * 0.16), pan=(-1) ** i * 0.4, note="E5")
    sc.hit("riser", starts["product"] - B(2), 0.9)
    for i in range(3):
        sc.hit("clack", starts["product"] + B(1 + 2 * i), 1.0, pitch=1.5)
    for i in range(4):
        for j in range(4):
            sc.hit("tick", starts["facts"] + B(2 * i - 0.5 + j * 0.125), 0.5, pitch=1 + j * 0.1)
        sc.hit("clack", starts["facts"] + B(2 * i), 1.0, pitch=1.2)
    sc.hit("thud", starts["hero"] + B(0.5), 1.4)
    sc.hit("slap", starts["hero"] + B(0.5), 1.0)
    bass = [("E1", 0, 1.5), ("E1", 1.5, 0.5), ("G1", 2, 1), ("A1", 3, 1), ("E1", 4, 1.5), ("E2", 5.5, 0.5), ("D2", 6, 1), ("B1", 7, 1)]
    for bar in range(1, len(tl.scenes) - 1):
        sc.bass(bass, start=B(4 + (bar - 1) * 8), gain=0.6)
    for k in (0.5, 4, 5, 6):
        sc.hit("clack", starts["end"] + B(k), 0.9, pitch=1.8)
    sc.hit("slap", starts["end"] + B(4), 1.0)
    sc.chord(["E3", "G3", "B3", "D4"], starts["end"], tl.duration - starts["end"], 0.7)
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    sc = []
    for name, beats, fn in SCENES:
        tr = ThroughO(B(1)) if name == "product" else None
        sc.append(Scene(name, B(beats), (lambda f: lambda c: composite(c, f))(fn), tr))
    return Timeline(sc, G.W, G.H, G.fps, data=G, theme=G.th), brief


def check(tl):
    errs = []
    need = ("brand", "product", "kicker", "slam", "echo", "specs", "facts", "price", "ships", "url")
    errs += [f"copy.{k} missing" for k in need if k not in G.c]
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    lines = [G.c[k] for k in ("brand", "kicker", "ships", "url")] + G.c["facts"] + [s for p in G.c["specs"] for s in p]
    errs += [f"trailing period: {s!r}" for s in lines if s.rstrip().endswith(".")]
    if "O" not in G.c["echo"].upper():
        print("warn: copy.echo has no O, so the fly-through uses the glyph itself instead of a counter")
    if len(G.c["facts"]) > 4 or len(G.c["specs"]) > 3:
        errs.append("at most 4 facts and 3 specs")
    if G.assets.missing(ASSET_SLOTS):
        print("warn: using placeholder for", G.assets.missing(ASSET_SLOTS))
    del OVERFLOWS[:], SHRINKS[:]
    for t in np.linspace(0.3, tl.duration - 0.05, 20):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append(overflow_report())
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{tl.duration:.2f}s, {tl.n_frames} frames, {len(tl.scenes)} scenes at {G.bpm} BPM")
    for e in errs:
        print("✗", e)
    return not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "ferrum", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        specs = {k: dict(v, prompt=v["prompt"].format(**G.c)) for k, v in brief.get("assets", {}).items()}
        for m in generate_images(specs, G.assets.dirs[0], names=a.args or None, force=a.force):
            print(m)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=8, rows=3, thumb_w=150))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a"), tl))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"), tl)
        print(tl.render(a.out or os.path.join(out, "riso-poster-promo.mp4"), audio))


if __name__ == "__main__":
    main()
