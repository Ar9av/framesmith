#!/usr/bin/env python3
"""devtool-launch-video: a 34-second, 16:9 launch film for a CLI / dev tool / AI-security product.

Arc: the problem runs wild in a terminal → freeze → logo reveal → the same actions replayed and
caught, each annotated with its verdict → feature beats → dashboard → install → end card.

Design rules: the brand's real logo only; no pills, chips or badges (verdicts are typeset,
coloured words with leader lines); every string has a width budget and `check` fails on overflow.

    python3 launch.py check|assets|still|sheet|render --brief brief.json [times...] [--audio a.mp3]
"""
import argparse, json, math, os, re, sys
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import (Assets, Scene, Theme, Timeline, cover, ease_in_out, ease_out, generate_images, h, hex2rgb,
                        lerp, overflow_report, scramble, text, typed)
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith import ui

SLOTS = ("logo", "threat", "holo")          # logo is supplied (the brand's real mark), the rest can be generated
G = None


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        th = brief.get("theme", {})
        self.th = Theme.from_dict(th)
        col = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.danger = col("danger", (255, 93, 93))
        self.muted = col("muted", (113, 113, 122))
        self.panel = col("panel", (18, 18, 20))
        self.line = col("line", (38, 38, 42))
        self.good = col("good", (113, 221, 140))
        self.holo_pal = [hex2rgb(x) for x in brief.get("holo", ["#FFB6DE", "#AAF0D2", "#BEAAF5", "#A0D2FA", "#FFDCA0"])]
        self.verdicts = {k: hex2rgb(v) for k, v in brief.get("verdicts", {}).items()}
        self.W, self.H = brief.get("size", [1920, 1080])
        self.assets = Assets(os.path.join(base, brief.get("assets_dir", "assets")), os.path.join(HERE, "..", "placeholders"))
        self._c = {}

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]

    def canvas(self, col=None):
        return Image.new("RGB", (self.W, self.H), col or self.th.ink)

    def kind(self, k):
        th = self.th
        return {"agent": (161, 161, 170), "inject": self.danger, "cmd": th.paper, "leak": (255, 181, 91),
                "dim": self.muted, "ok": self.good, "note": (161, 161, 170)}.get(k, th.paper)


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def holo(c, w=None, hgt=None, speed=1.0):
    """Brand light: the holographic texture drifting, mixed with a live interference field."""
    w, hgt = int(w or G.W), int(hgt or G.H)
    base = G.cache(("holo", w, hgt), lambda: np.asarray(cover(G.assets.get("holo").convert("RGB"), int(w * 1.15) + 2, int(hgt * 1.15) + 2), np.float32))
    ox = int((math.sin(c.t * 0.35 * speed) * 0.5 + 0.5) * (base.shape[1] - w))
    oy = int((math.cos(c.t * 0.27 * speed) * 0.5 + 0.5) * (base.shape[0] - hgt))
    img = base[oy:oy + hgt, ox:ox + w]
    small = ui.holo_field(max(8, w // 6), max(8, hgt // 6), c.t * speed, G.holo_pal)
    field = np.asarray(Image.fromarray(small).resize((w, hgt), Image.BILINEAR), np.float32)
    return (img * 0.62 + field * 0.38).astype(np.uint8)


def split_mask(w, hgt, s=1.0, which="upper"):
    """The logo's diagonal: triangle above (upper) / below (lower) the TL→BR diagonal, grown from its corner by s."""
    m = Image.new("L", (w, hgt), 0)
    d = ImageDraw.Draw(m)
    if which == "upper":
        d.polygon([(w, 0), (w - s * w * 1.001, 0), (w, s * hgt * 1.001)], fill=255)
    else:
        d.polygon([(0, hgt), (s * w * 1.001, hgt), (0, hgt - s * hgt * 1.001)], fill=255)
    return m


def logo_at(size):
    size = int(size)
    return G.cache(("logo", size), lambda: G.assets.get("logo").resize((size, size), Image.LANCZOS))


def glow(im, c, cx, cy, radius, strength):
    """Soft holographic bloom behind a mark, so a dark logo still separates from a dark ground."""
    if strength <= 0:
        return im
    R = int(radius)
    pad = Image.new("RGB", (R * 3, R * 3), (0, 0, 0))
    pad.paste(Image.fromarray(holo(c, R, R)), (R, R))
    ga = np.asarray(pad.filter(ImageFilter.GaussianBlur(R * 0.3)), np.float32) * strength
    base = np.asarray(im, np.float32).copy()
    x0, y0 = int(cx - R * 1.5), int(cy - R * 1.5)
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x1, y1 = min(base.shape[1], x0 + R * 3), min(base.shape[0], y0 + R * 3)
    base[max(0, y0):y1, max(0, x0):x1] += ga[sy0:sy0 + y1 - max(0, y0), sx0:sx0 + x1 - max(0, x0)]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def draw_logo(im, c, cx, cy, size, reveal=1.0, sheen=None):
    """Paste the brand logo. reveal < 1 wipes it in along its own diagonal; sheen in [0,1] sweeps a highlight."""
    lg = logo_at(size)
    a = np.asarray(lg.getchannel("A"), np.float32)
    if reveal < 1:
        a *= np.asarray(split_mask(lg.width, lg.height, reveal * 2.0, "lower"), np.float32) / 255
    rgb = np.asarray(lg.convert("RGB"), np.float32)
    if sheen is not None and 0 < sheen < 1:
        yy, xx = np.mgrid[0:lg.height, 0:lg.width]
        band = np.clip(1 - np.abs((xx + yy) / (lg.width + lg.height) - sheen) * 9, 0, 1)[..., None]
        rgb = np.clip(rgb + band * 90, 0, 255)
    tile = Image.fromarray(rgb.astype(np.uint8))
    im.paste(tile, (int(cx - lg.width / 2), int(cy - lg.height / 2)), Image.fromarray(a.astype(np.uint8)))


def glitch_bands(a, fi, amount, seed=0):
    out = a.copy()
    rng = np.random.default_rng(fi * 7 + seed)
    y = 0
    while y < a.shape[0]:
        bh = int(rng.integers(4, 40))
        if rng.random() < 0.35:
            out[y:y + bh] = np.roll(out[y:y + bh], int(rng.integers(-amount, amount + 1)), axis=1)
        y += bh
    return out


def holo_text(im, c, xy, s, font, anchor="mm", track=0):
    """Text filled with the brand light (no box behind it)."""
    m = Image.new("L", im.size, 0)
    text(ImageDraw.Draw(m), xy, s, font, 255, track, anchor, max_w=G.W - 200)
    bb = m.getbbox()
    if not bb:
        return
    patch = Image.fromarray(holo(c, bb[2] - bb[0], bb[3] - bb[1], 1.4))
    im.paste(patch, bb[:2], m.crop(bb))


# ------------------------------------------------------------------ scenes
def s_hook(c):
    th = G.th
    im = G.canvas()
    hk = G.c["hook"]
    f = F("mono", 64)
    size = min(64, int(64 * (c.W - 320) / max(f.getlength(x) for x in hk)))
    lines = [{"spans": [(hk[0], th.paper)], "t": 0.25, "type": 0.7}, {"spans": [(hk[1], th.paper)], "t": 1.05, "type": 0.5}]
    ui.terminal(im, (160, 420), lines, c.lt, size, 1.45, th.paper, c.fi, max_width=c.W - 320)
    a = arr(im)
    if c.lt > c.dur - 0.25:
        a = glitch_bands(a, c.fi, 120)
    return a


def s_names(c):
    th = G.th
    names = G.c["names"]
    end = c.lt > c.dur - 0.45
    i = int(c.lt / 0.1)
    inv = (i % 2 == 1) and not end
    im = G.canvas(th.paper if inv else th.ink)
    d = ImageDraw.Draw(im)
    if end:
        s = G.c["names_end"]
        text(d, (c.W / 2, c.H / 2), scramble(s, ease_out(c.p(-0.45, -0.25)), 3, c.fi, 3), F("sans_medium", 190),
             G.danger, -6, "mm", max_w=c.W - 240, fit_to=s)
    else:
        jx = int((h(5, i) - 0.5) * 240)
        text(d, (c.W / 2 + jx, c.H / 2 + int((h(6, i) - 0.5) * 160)), names[i % len(names)], F("sans_medium", 200),
             th.ink if inv else th.paper, -6, "mm", max_w=c.W - 240 - 2 * abs(jx))
    return arr(im)


ROGUE_BOX = (70, 120, 1180, 960)


def rogue_schedule():
    rl = G.c["rogue_lines"]
    n = len(rl)
    out, t = [], 0.15
    for k, ln in enumerate(rl):
        gap = lerp(0.62, 0.3, k / max(1, n - 1))           # accelerating
        typ = {"cmd": lerp(0.32, 0.18, k / max(1, n - 1))}.get(ln["kind"], 0.12)
        spans = [("$ ", G.good), (ln["text"][2:], G.kind("cmd"))] if ln["kind"] == "cmd" and ln["text"].startswith("$ ") \
            else [(ln["text"], G.kind(ln["kind"]))]
        out.append({"spans": spans, "t": t, "type": typ, "bg": (70, 12, 14) if ln["kind"] == "inject" else None})
        t += gap
    return out


def vignette(w, hgt):
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - hgt / 2) / (hgt / 2)) ** 2)
    return np.clip((r - 0.35) / 0.9, 0, 1)[..., None]


def s_rogue(c, frozen=False):
    th = G.th
    z = lerp(1.0, 1.08, c.p(0, c.dur))
    bg = np.asarray(cover(G.assets.get("threat").convert("RGB"), c.W, c.H, z, 0.62, 0.5), np.float32) * 0.42
    im = Image.fromarray(bg.astype(np.uint8)).convert("RGBA")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = ROGUE_BOX
    ui.window(layer, ROGUE_BOX, G.panel + (238,), G.line + (255,), G.c["rogue_title"], font_size=15)
    im.alpha_composite(layer)
    im = im.convert("RGB")
    ui.terminal(im, (x0 + 40, y0 + 85), rogue_schedule(), c.lt, 30, 1.8, th.paper, 0 if frozen else c.fi,
                max_lines=13, max_width=x1 - x0 - 80)
    d = ImageDraw.Draw(im)
    cx, cw = x1 + 70, c.W - x1 - 70 - 70                    # caption column and its width budget
    for k, (a, b) in enumerate(G.c["rogue_captions"]):
        t0 = 0.75 + k * 1.1
        if c.lt >= t0:
            p = ease_out(c.p(t0, t0 + 0.3))
            y = 300 + k * 230
            text(d, (cx, y), scramble(a, p, 40 + k, c.fi, 3), F("sans_medium", 66), th.paper, -2, max_w=cw, fit_to=a)
            text(d, (cx, y + 78), scramble(b, p, 50 + k, c.fi, 3), F("sans_medium", 66), G.danger, -2, max_w=cw, fit_to=b)
    a = np.asarray(im, np.float32)
    heat = c.p(2.4, c.dur)
    v = G.cache(("vig", c.W, c.H), lambda: vignette(c.W, c.H))
    a = (a * (1 - v * heat * 0.8) + np.array(G.danger, np.float32) * v * heat * 0.8).astype(np.uint8)
    if not frozen and heat > 0:
        amp = int(heat * 16)
        a = np.roll(a, (int((h(8, c.fi) - 0.5) * 2 * amp), int((h(9, c.fi) - 0.5) * 2 * amp)), axis=(0, 1))
        if h(10, c.fi) < heat * 0.5:
            a = glitch_bands(a, c.fi, int(60 * heat))
            a[..., 0] = np.roll(a[..., 0], 6, axis=1)
    return a


def s_freeze(c):
    frame = s_rogue(replace(c, lt=G.rogue_dur - 0.01, dur=G.rogue_dur, fi=0), frozen=True).astype(np.float32)
    p = ease_out(c.p(0, 0.3))
    frame = frame * (1 - p) + frame.mean(axis=2, keepdims=True) * p * 0.55
    im = Image.fromarray(frame.astype(np.uint8))
    s = ease_in_out(c.p(0.25, c.dur))
    if s > 0:
        im.paste(Image.fromarray(holo(c)), (0, 0), split_mask(c.W, c.H, s, "upper"))
        im.paste(Image.new("RGB", im.size, G.th.ink), (0, 0), split_mask(c.W, c.H, s, "lower"))
    return arr(im)


def s_reveal(c):
    """The real logo: blooms in on black, scales up gently, a highlight sweeps its diagonal."""
    im = G.canvas()
    size = 380 * lerp(0.88, 1.0, ease_out(c.p(0, c.dur)))
    cy = c.H / 2 - 50
    im = glow(im, c, c.W / 2, cy, 420, 0.55 * ease_out(c.p(0, 0.5)))
    draw_logo(im, c, c.W / 2, cy, size, ease_out(c.p(0, 0.35)), sheen=c.p(0.3, 0.9))
    text(ImageDraw.Draw(im), (c.W / 2, c.H - 190), typed(G.c["meet"], c.p(0.35, 0.6)), F("mono", 36), G.th.paper, 4, "mm")
    a = arr(im)
    if c.lt < 0.07:
        a = (a.astype(np.float32) * 0.3 + 255 * 0.7).astype(np.uint8)
    return a


def s_title(c):
    th = G.th
    im = G.canvas()
    im.paste(Image.fromarray(holo(c)), (0, 0), split_mask(c.W, c.H, 1.0, "upper"))
    d = ImageDraw.Draw(im)
    base_y, x = 900, 104
    cap_top = base_y - 0.73 * 230
    budget = cap_top * c.W / c.H - x - 60                     # stay inside the ink triangle
    text(d, (118, 640), G.c["meet"], F("mono", 34), G.muted, 4)
    b = G.c["brand"]
    text(d, (x, base_y), scramble(b, ease_out(c.p(0, 0.45)), 61, c.fi, 3), F("sans_medium", 230), th.paper, -9, "ls",
         max_w=budget, fit_to=b)
    sub = G.c["product_sub"]
    text(d, (116, 975), typed(sub, c.p(0.3, 0.8)), F("mono", 34), th.paper, 1, max_w=(975 * c.W / c.H) - 116 - 60, fit_to=sub)
    return arr(im)


TERM_BOX = (80, 170, 1180, 1010)
ANN_X = 1240                                                   # verdict annotation column


def intercept_plan():
    items = G.c["intercept"]
    lines, plan, t = [], [], 0.55
    step = (G.intercept_dur - 1.3) / len(items)
    for it in items:
        spans = [("$ ", G.good), (it["cmd"][2:], G.th.paper)] if it["cmd"].startswith("$ ") else [(it["cmd"], G.kind("agent"))]
        li = len(lines)
        lines.append({"spans": spans, "t": t, "type": 0.28 if it["cmd"].startswith("$ ") else 0.1})
        v_t = t + 0.5
        if it.get("out"):
            lines.append({"spans": [(it["out"], G.verdicts.get(it["verdict"], G.muted))], "t": v_t, "type": 0})
        plan.append((li, t, v_t, it))
        t += step
    return lines, plan


def s_intercept(c):
    th = G.th
    im = G.canvas()
    d = ImageDraw.Draw(im)
    for x in range(0, c.W, 60):
        d.line((x, 0, x, c.H), fill=(17, 17, 19))
    for y in range(0, c.H, 60):
        d.line((0, y, c.W, y), fill=(17, 17, 19))
    cap = G.c["intercept_caption"]
    text(d, (80, 92), scramble(cap, ease_out(c.p(0, 0.45)), 70, c.fi, 4), F("sans_medium", 54), th.paper, -2, "lm",
         max_w=1100, fit_to=cap)
    x0, y0, x1, y1 = TERM_BOX
    ui.window(im, TERM_BOX, G.panel, G.line, G.c["intercept_title"], font_size=15)
    lines, plan = intercept_plan()
    pos = ui.terminal(im, (x0 + 40, y0 + 85), lines, c.lt, 30, 2.05, th.paper, c.fi, max_width=x1 - x0 - 80)
    d = ImageDraw.Draw(im)
    counts = {}
    fv, fr = F("mono_bold", 24), F("mono", 19)
    for li, t0, v_t, it in plan:
        if li not in pos:
            continue
        rows = pos[li]
        rx0, ry, rx1 = rows[0]
        col = G.verdicts.get(it["verdict"], G.muted)
        sp = c.p(v_t - 0.2, v_t)                                  # scan line sweeps the command
        if 0 < sp < 1:
            sx = lerp(rx0, max(rows[-1][2], rx0 + 200), sp)
            d.line((sx, ry - 8, sx, rows[-1][1] + 40), fill=G.holo_pal[int(sp * 5) % 5], width=4)
        if c.lt >= v_t:
            counts[it["verdict"]] = counts.get(it["verdict"], 0) + 1
            if it["verdict"] == "BLOCKED":
                for a0, ay, a1 in rows:
                    d.line((a0, ay + 18, a1, ay + 18), fill=G.danger, width=3)
            # leader line from the command out to the margin, then the verdict typeset as words
            lp = ease_out(c.p(v_t, v_t + 0.18))
            ly = ry + 18
            lx0 = rows[0][2] + 18 if len(rows) == 1 else x1 - 30
            lx1 = lerp(lx0, ANN_X - 18, lp)
            d.line((lx0, ly, lx1, ly), fill=col, width=1)
            if lp >= 1:
                d.rectangle((ANN_X - 22, ly - 3, ANN_X - 16, ly + 3), fill=col)
                word = it["verdict"]
                text(d, (ANN_X, ly), typed(word, c.p(v_t + 0.18, v_t + 0.3)), fv, col, 2, "lm", max_w=c.W - ANN_X - 80, fit_to=word)
                text(d, (ANN_X, ly + 30), typed(it["rule"], c.p(v_t + 0.22, v_t + 0.45)), fr, (150, 150, 158), 0, "lm",
                     max_w=c.W - ANN_X - 80, fit_to=it["rule"])
    # running tally, typeset (number in the verdict colour, label muted)
    x = c.W - 80
    f_n, f_l = F("mono_bold", 20), F("mono", 20)
    for k in reversed(list(G.verdicts)):
        lab = f" {k.lower()}"
        n = str(counts.get(k, 0))
        text(d, (x, 92), lab, f_l, G.muted, 0, "rm")
        x -= f_l.getlength(lab)
        text(d, (x, 92), n, f_n, G.verdicts[k], 0, "rm")
        x -= f_n.getlength(n) + 34
    return arr(im)


def s_features(c):
    th = G.th
    feats = G.c["features"]
    beat = c.dur / len(feats)
    i = min(int(c.lt / beat), len(feats) - 1)
    b = c.lt - i * beat
    light = i % 2 == 1
    im = Image.fromarray(holo(c, speed=2.0)) if light else G.canvas()
    fg = th.ink if light else th.paper
    d = ImageDraw.Draw(im)
    text(d, (112, 150), f"{i + 1:02d}/{len(feats):02d}", F("mono", 26), fg, 2)
    text(d, (c.W - 112, 150), G.c["brand"], F("mono_bold", 26), fg, 4, "ra")
    w, s = feats[i]["word"], feats[i]["sub"]
    text(d, (104, 620), scramble(w, ease_out(min(1, b / 0.2)), 80 + i, c.fi, 3), F("sans_medium", 176), fg, -7, "ls",
         max_w=c.W - 216, fit_to=w)
    text(d, (112, 700), typed(s, min(1, b / 0.3)), F("mono", 32), fg, 1, max_w=c.W - 224, fit_to=s)
    return arr(im)


def parse_num(s):
    m = re.search(r"[\d,.]+", s)
    return (float(m.group().replace(",", "")), m.start(), m.end()) if m else (None, 0, 0)


def count_str(s, p):
    v, a, b = parse_num(s)
    if v is None:
        return s
    n = v * p
    body = f"{n:,.0f}" if "," in s or v >= 1000 else (f"{n:.1f}" if "." in s[a:b] else f"{n:.0f}")
    return s[:a] + body + s[b:]


def s_dashboard(c):
    th, D = G.th, G.c["dashboard"]
    im = Image.new("RGB", (c.W, c.H), (249, 249, 250))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 300, c.H), fill=(255, 255, 255))
    d.line((300, 0, 300, c.H), fill=(228, 228, 231))
    draw_logo(im, c, 70, 52, 36)
    text(d, (100, 52), D["app"], F("sans_medium", 24), th.ink, -0.5, "lm", max_w=180)
    for k, nav in enumerate(D["nav"]):
        y = 140 + k * 48
        if k == 0:
            d.rectangle((30, y - 18, 33, y + 18), fill=th.ink)          # active marker: a rule, not a pill
        text(d, (52, y), nav, F("sans", 20), th.ink if k == 0 else G.muted, 0, "lm", max_w=230)
    text(d, (340, 52), f"Dashboard  /  {D['title']}", F("sans", 20), G.muted, 0, "lm", max_w=900)
    text(d, (c.W - 60, 52), "● live", F("mono", 16), (21, 128, 61), 1, "rm")
    cw = (c.W - 340 - 60 - 3 * 20) / 4
    for k, (lab, val) in enumerate(D["cards"]):
        x = 340 + k * (cw + 20)
        pk = ease_out(c.p(0.15 + k * 0.06, 1.2 + k * 0.06))
        ui.stat_card(im, (x, 100, x + cw, 250), lab, count_str(val, pk), (255, 255, 255), th.ink, G.muted)
    ui.rrect(d, (340, 280, 1180, 740), 12, fill=(255, 255, 255))
    text(d, (366, 312), D["chart_title"], F("sans_medium", 22), th.ink, 0, "lm", max_w=780)
    for k in range(14):
        x, y = 380 + k * 56, 700
        gp = ease_out(c.p(0.3 + k * 0.05, 0.9 + k * 0.05))
        for j, vk in enumerate(["ALLOWED", "CLOAKED", "BLOCKED"]):
            if vk not in G.verdicts:
                continue
            hh = ((30 + h(20, k, j) * 170) if j == 0 else (8 + h(20, k, j) * 50)) * gp
            d.rectangle((x, y - hh, x + 36, y), fill=G.verdicts[vk])
            y -= hh + 3
    ui.rrect(d, (1200, 280, c.W - 60, 740), 12, fill=(255, 255, 255))
    text(d, (1226, 312), D["dist_title"], F("sans_medium", 22), th.ink, 0, "lm", max_w=600)
    for j, vk in enumerate(G.verdicts):
        y = 400 + j * 80
        text(d, (1226, y), vk.lower(), F("mono", 18), G.muted, 1, "lm")
        wmax = (c.W - 60 - 1226 - 40) * (0.35 + h(30, j) * 0.6)
        d.rectangle((1226, y + 20, 1226 + max(6, wmax * ease_out(c.p(0.4 + j * 0.08, 1.2 + j * 0.08))), y + 32), fill=G.verdicts[vk])
    ui.rrect(d, (340, 770, c.W - 60, c.H - 40), 12, fill=(255, 255, 255))
    text(d, (366, 802), D["table_title"], F("sans_medium", 22), th.ink, 0, "lm", max_w=900)
    for k, (call, agent, rule, verdict) in enumerate(D["rows"]):
        p = ease_out(c.p(0.6 + k * 0.1, 0.9 + k * 0.1))
        if p <= 0:
            continue
        y = 860 + k * 46
        dx = int((1 - p) * 60)
        text(d, (366 + dx, y), call, F("sans", 20), th.ink, 0, "lm", max_w=430)
        text(d, (820 + dx, y), agent, F("mono", 18), G.muted, 0, "lm", max_w=280)
        text(d, (1120 + dx, y), rule, F("mono", 18), G.muted, 0, "lm", max_w=420)
        text(d, (c.W - 90 + dx, y), verdict.lower(), F("mono_bold", 18), G.verdicts.get(verdict, G.muted), 1, "rm", max_w=200)
    z = lerp(1.0, 1.02, ease_in_out(c.p(0, c.dur)))
    if z > 1.001:
        im = cover(im, c.W, c.H, z, 0.5, 0.5)
    if c.lt > 1.1:                                            # lower-third caption over a scrim, no box
        p = ease_out(c.p(1.1, 1.5))
        a = np.asarray(im, np.float32)
        ramp = np.clip((np.arange(c.H) - (c.H - 380)) / 230, 0, 1)[:, None, None] * p   # opaque over the bottom 150 px
        a = a * (1 - ramp) + np.array(th.ink, np.float32) * ramp
        im = Image.fromarray(a.astype(np.uint8))
        cap = G.c["dashboard_caption"]
        text(ImageDraw.Draw(im), (c.W / 2, lerp(c.H - 30, c.H - 78, p)), cap, F("sans_medium", 54), th.paper, -1.5, "mm",
             max_w=c.W - 240)
    return arr(im)


def s_install(c):
    th = G.th
    im = G.canvas()
    box = (360, 170, 1560, 780)
    ui.window(im, box, G.panel, G.line, G.c["install_title"], font_size=15)
    lines, t = [], 0.2
    for ln in G.c["install"]:
        k = ln["kind"]
        spans = [("$ ", G.good), (ln["text"][2:], th.paper)] if k == "cmd" else [(ln["text"], G.kind(k))]
        lines.append({"spans": spans, "t": t, "type": 0.4 if k == "cmd" else 0})
        t += 0.62 if k == "cmd" else 0.28
    agents = "   ".join(G.c["install_agents"])
    lines.append({"spans": [(agents, G.good)], "t": t + 0.05, "type": 0.35})
    ui.terminal(im, (box[0] + 50, box[1] + 80), lines, c.lt, 28, 1.75, th.paper, c.fi, max_width=box[2] - box[0] - 100)
    if c.lt > t + 0.5:
        cap = G.c["install_caption"]
        text(ImageDraw.Draw(im), (c.W / 2, 880), scramble(cap, ease_out(c.p(t + 0.5, t + 0.9)), 90, c.fi, 4),
             F("sans_medium", 62), th.paper, -2, "mm", max_w=c.W - 240, fit_to=cap)
    return arr(im)


def s_end(c):
    th = G.th
    im = G.canvas()
    im = glow(im, c, c.W / 2, 330, 300, 0.5 * ease_out(c.p(0.1, 0.8)))
    draw_logo(im, c, c.W / 2, 330, 220, ease_out(c.p(0, 0.45)), sheen=c.p(0.5, 1.2))
    d = ImageDraw.Draw(im)
    tg = G.c["tagline"]
    text(d, (c.W / 2, 590), scramble(tg, ease_out(c.p(0.35, 0.85)), 95, c.fi, 4), F("sans_medium", 84), th.paper, -3, "mm",
         max_w=c.W - 240, fit_to=tg)
    if c.lt > 0.8:
        holo_text(im, c, (c.W / 2, 715), typed(G.c["cta"], c.p(0.8, 1.15)), F("mono_bold", 44), "mm", 1)
    d = ImageDraw.Draw(im)
    text(d, (c.W / 2, 830), typed(G.c["links"], c.p(1.0, 1.5)), F("mono", 30), (190, 190, 196), 1, "mm", max_w=c.W - 240, fit_to=G.c["links"])
    text(d, (c.W / 2, 885), typed(G.c["license"], c.p(1.3, 1.6)), F("mono", 22), G.muted, 2, "mm", max_w=c.W - 240, fit_to=G.c["license"])
    return arr(im)


SCENES = [
    ("hook", 2.4, s_hook), ("names", 1.2, s_names), ("rogue", 4.8, s_rogue), ("freeze", 0.6, s_freeze),
    ("reveal", 1.0, s_reveal), ("title", 1.4, s_title), ("intercept", 7.0, s_intercept), ("features", 4.4, s_features),
    ("dashboard", 4.0, s_dashboard), ("install", 3.5, s_install), ("end", 3.5, s_end),
]
REQUIRED = ["brand", "hook", "names", "names_end", "rogue_title", "rogue_lines", "rogue_captions", "meet", "product_sub",
            "intercept_title", "intercept_caption", "intercept", "features", "dashboard", "dashboard_caption",
            "install_title", "install", "install_agents", "install_caption", "tagline", "cta", "links", "license"]


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    over, sp = brief.get("scenes", {}), brief.get("speed", 1.0)
    sc = [Scene(n, over.get(n, d) / sp, f) for n, d, f in SCENES if over.get(n, d)]
    durs = {s.name: s.dur for s in sc}
    G.rogue_dur, G.intercept_dur = durs.get("rogue", 4.8), durs.get("intercept", 7.0)
    return Timeline(sc, G.W, G.H, brief.get("fps", 30), data=G, theme=G.th), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        miss = [k for k in REQUIRED if k not in brief["copy"]]
        print("copy keys missing:", miss or "none")
        own = Assets(G.assets.dirs[0])
        print("assets missing (placeholders used):", [s for s in SLOTS if not own.path(s)] or "none")
        OVERFLOWS.clear()
        SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):  # sample 4 frames/s through the whole cut
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep:
            print("  ✗", r)
        for r in overflow_report(warn=True):
            print("  ! warning:", r)
        print(f"duration {tl.duration:.2f}s, {tl.n_frames} frames, {len(tl.scenes)} scenes")
        sys.exit(1 if (miss or rep) else 0)
    elif a.cmd == "assets":
        specs = {k: v for k, v in brief.get("assets", {}).items() if k in SLOTS and "prompt" in v}
        for m in generate_images(specs, G.assets.dirs[0], names=a.args or None, force=a.force):
            print(m)
    elif a.cmd == "still":
        for s in a.args or ["10"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 4, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "launch.mp4"), a.audio))


if __name__ == "__main__":
    main()
