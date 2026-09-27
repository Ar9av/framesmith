#!/usr/bin/env python3
"""devtool-launch-video: a 34-second, 16:9 launch film for a CLI / dev tool / AI-security product.

Arc: the problem runs wild in a terminal → freeze → brand reveal → the same actions replayed and
caught with verdict chips → feature beats → dashboard → install → end card.

    python3 launch.py check|assets|still|sheet|render --brief brief.json [times...] [--audio a.mp3]
"""
import argparse, json, math, os, re, sys
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import (Assets, Scene, Theme, Timeline, cover, ease_in_out, ease_out, generate_images, h, hex2rgb,
                        lerp, mix, prog, scramble, text, typed)
from framesmith.typography import F
from framesmith import ui

SLOTS = ("threat", "reveal", "holo")
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
    """Brand light: the holographic foil asset drifting, mixed with a live interference field."""
    w, hgt = w or G.W, hgt or G.H
    base = G.cache(("holo", w, hgt), lambda: np.asarray(cover(G.assets.get("holo").convert("RGB"), int(w * 1.15), int(hgt * 1.15)), np.float32))
    ox = int((math.sin(c.t * 0.35 * speed) * 0.5 + 0.5) * (base.shape[1] - w))
    oy = int((math.cos(c.t * 0.27 * speed) * 0.5 + 0.5) * (base.shape[0] - hgt))
    img = base[oy:oy + hgt, ox:ox + w]
    small = ui.holo_field(max(8, w // 6), max(8, hgt // 6), c.t * speed, G.holo_pal)
    field = np.asarray(Image.fromarray(small).resize((w, hgt), Image.BILINEAR), np.float32)
    return (img * 0.62 + field * 0.38).astype(np.uint8)


def split_mask(w, hgt, s=1.0, which="upper"):
    """Logo motif: triangle above (upper) / below (lower) the TL→BR diagonal, grown from its corner by s."""
    m = Image.new("L", (w, hgt), 0)
    d = ImageDraw.Draw(m)
    if which == "upper":
        d.polygon([(w, 0), (w - s * w * 1.001, 0), (w, s * hgt * 1.001)], fill=255)
    else:
        d.polygon([(0, hgt), (s * w * 1.001, hgt), (0, hgt - s * hgt * 1.001)], fill=255)
    return m


def draw_logo(im, c, cx, cy, size, reveal=1.0):
    """Rounded square split on the diagonal: ink lower-left, holographic upper-right."""
    size = int(size)
    patch = Image.fromarray(holo(c, size, size, 1.6))
    sq = Image.new("L", (size, size), 0)
    ImageDraw.Draw(sq).rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.2, fill=255)
    up = split_mask(size, size, 1.0, "upper")
    tile = Image.new("RGB", (size, size), G.th.ink)
    tile.paste(patch, (0, 0), up)
    wipe = split_mask(size, size, reveal * 2.0, "lower") if reveal < 1 else sq
    m = Image.fromarray(np.minimum(np.asarray(sq), np.asarray(wipe)))
    x, y = int(cx - size / 2), int(cy - size / 2)
    im.paste(tile, (x, y), m)
    ImageDraw.Draw(im).rounded_rectangle((x, y, x + size - 1, y + size - 1), radius=size * 0.2, outline=(52, 52, 58), width=2)


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


# ------------------------------------------------------------------ scenes
def s_hook(c):
    th = G.th
    im = G.canvas()
    lines = [{"spans": [(G.c["hook"][0], th.paper)], "t": 0.25, "type": 0.7},
             {"spans": [(G.c["hook"][1], th.paper)], "t": 1.05, "type": 0.5}]
    ui.terminal(im, (160, 420), lines, c.lt, 64, 1.45, th.paper, c.fi)
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
        text(d, (c.W / 2, c.H / 2), scramble(G.c["names_end"], ease_out(c.p(-0.45, -0.25)), 3, c.fi, 3),
             F("sans_medium", 190), G.danger, -6, "mm")
    else:
        jx = int((h(5, i) - 0.5) * 240)
        text(d, (c.W / 2 + jx, c.H / 2 + int((h(6, i) - 0.5) * 160)), names[i % len(names)], F("sans_medium", 200),
             th.ink if inv else th.paper, -6, "mm")
    return arr(im)


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
    ui.window(layer, (70, 120, 1180, 960), G.panel + (238,), G.line + (255,), G.c["rogue_title"], font_size=15)
    im.alpha_composite(layer)
    im = im.convert("RGB")
    ui.terminal(im, (110, 205), rogue_schedule(), c.lt, 31, 1.8, th.paper, 0 if frozen else c.fi, max_lines=13)
    d = ImageDraw.Draw(im)
    for k, (a, b) in enumerate(G.c["rogue_captions"]):
        t0 = 0.75 + k * 1.1
        if c.lt >= t0:
            p = ease_out(c.p(t0, t0 + 0.3))
            y = 300 + k * 230
            text(d, (1250, y), scramble(a, p, 40 + k, c.fi, 3), F("sans_medium", 66), th.paper, -2)
            text(d, (1250, y + 78), scramble(b, p, 50 + k, c.fi, 3), F("sans_medium", 66), G.danger, -2)
    a = np.asarray(im, np.float32)
    heat = c.p(2.4, c.dur)
    v = G.cache(("vig", c.W, c.H), lambda: vignette(c.W, c.H))
    a = a * (1 - v * heat * 0.8) + np.array(G.danger, np.float32) * v * heat * 0.8
    a = a.astype(np.uint8)
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
    gray = frame.mean(axis=2, keepdims=True)
    frame = frame * (1 - p) + gray * p * 0.55
    im = Image.fromarray(frame.astype(np.uint8))
    s = ease_in_out(c.p(0.25, c.dur))
    if s > 0:
        im.paste(Image.fromarray(holo(c)), (0, 0), split_mask(c.W, c.H, s, "upper"))
        im.paste(Image.new("RGB", im.size, G.th.ink), (0, 0), split_mask(c.W, c.H, s, "lower"))
    return arr(im)


def s_reveal(c):
    z = lerp(1.14, 1.0, ease_out(c.p(0, c.dur)))
    im = cover(G.assets.get("reveal").convert("RGB"), c.W, c.H, z, 0.45, 0.5)
    d = ImageDraw.Draw(im)
    text(d, (c.W / 2, c.H - 120), typed(G.c["meet"], c.p(0.25, 0.5)), F("mono", 36), G.th.paper, 4, "mm")
    a = arr(im)
    if c.lt < 0.08:
        a = (a.astype(np.float32) * 0.3 + 255 * 0.7).astype(np.uint8)
    return a


def s_title(c):
    th = G.th
    im = G.canvas()
    im.paste(Image.fromarray(holo(c)), (0, 0), split_mask(c.W, c.H, 1.0, "upper"))
    d = ImageDraw.Draw(im)
    text(d, (118, 640), G.c["meet"], F("mono", 34), G.muted, 4)
    text(d, (104, 900), scramble(G.c["brand"], ease_out(c.p(0, 0.45)), 61, c.fi, 3), F("sans_medium", 230), th.paper, -9, "ls")
    text(d, (116, 975), typed(G.c["product_sub"], c.p(0.3, 0.8)), F("mono", 34), th.paper, 1)
    return arr(im)


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
            out = it["out"]
            lines.append({"spans": [(out, G.verdicts.get(it["verdict"], G.muted))], "t": v_t, "type": 0})
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
    text(d, (80, 92), scramble(G.c["intercept_caption"], ease_out(c.p(0, 0.45)), 70, c.fi, 4), F("sans_medium", 54), th.paper, -2, "lm")
    ui.window(im, (80, 170, 1180, 1010), G.panel, G.line, G.c["intercept_title"], font_size=15)
    lines, plan = intercept_plan()
    pos = ui.terminal(im, (120, 255), lines, c.lt, 30, 2.05, th.paper, c.fi)
    d = ImageDraw.Draw(im)
    counts = {}
    for li, t0, v_t, it in plan:
        if li not in pos:
            continue
        x0, y, x1 = pos[li]
        col = G.verdicts.get(it["verdict"], G.muted)
        sp = c.p(v_t - 0.2, v_t)                                  # scan line sweeps the command
        if 0 < sp < 1:
            sx = lerp(x0, max(x1, x0 + 200), sp)
            d.line((sx, y - 8, sx, y + 40), fill=G.holo_pal[int(sp * 5) % 5], width=4)
        if c.lt >= v_t:
            counts[it["verdict"]] = counts.get(it["verdict"], 0) + 1
            if it["verdict"] == "BLOCKED":
                d.line((x0, y + 18, x1, y + 18), fill=G.danger, width=3)
            p = ease_out(c.p(v_t, v_t + 0.22))
            x = lerp(1900, 1230, p)
            box = ui.chip(im, (x, y + 18), it["verdict"], th.ink, col, 20, (16, 8))
            text(ImageDraw.Draw(im), (box[2] + 18, y + 18), it["rule"], F("mono", 22), (170, 170, 178), 0, "lm")
    x = c.W - 80
    for k in reversed(list(G.verdicts)):
        box = ui.chip(im, (x, 92), f"{k} {counts.get(k, 0)}", G.verdicts[k], G.panel, 18, (14, 8), "rm", outline=G.line)
        x = box[0] - 12
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
    text(d, (104, 620), scramble(feats[i]["word"], ease_out(min(1, b / 0.2)), 80 + i, c.fi, 3), F("sans_medium", 176), fg, -7, "ls")
    text(d, (112, 700), typed(feats[i]["sub"], min(1, b / 0.3)), F("mono", 32), fg, 1)
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
    P = (249, 249, 250)
    im = Image.new("RGB", (c.W, c.H), P)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 300, c.H), fill=(255, 255, 255))
    d.line((300, 0, 300, c.H), fill=(228, 228, 231))
    draw_logo(im, c, 52, 52, 36)
    text(d, (82, 52), D["app"], F("sans_medium", 24), th.ink, -0.5, "lm")
    for k, nav in enumerate(D["nav"]):
        y = 140 + k * 48
        if k == 0:
            ui.rrect(d, (16, y - 18, 284, y + 18), 8, fill=(240, 240, 242))
        text(d, (36, y), nav, F("sans", 20), th.ink if k == 0 else G.muted, 0, "lm")
    text(d, (340, 52), f"Dashboard  /  {D['title']}", F("sans", 20), G.muted, 0, "lm")
    ui.chip(im, (c.W - 60, 52), "● LIVE", (21, 128, 61), (220, 252, 231), 15, (12, 6), "rm")
    cw = (c.W - 340 - 60 - 3 * 20) / 4
    for k, (lab, val) in enumerate(D["cards"]):
        x = 340 + k * (cw + 20)
        pk = ease_out(c.p(0.15 + k * 0.06, 1.2 + k * 0.06))
        ui.stat_card(im, (x, 100, x + cw, 250), lab, count_str(val, pk), (255, 255, 255), th.ink, G.muted)
    ui.rrect(d, (340, 280, 1180, 740), 12, fill=(255, 255, 255))
    text(d, (366, 312), D["chart_title"], F("sans_medium", 22), th.ink, 0, "lm")
    order = list(G.verdicts)
    for k in range(14):
        x = 380 + k * 56
        y = 700
        gp = ease_out(c.p(0.3 + k * 0.05, 0.9 + k * 0.05))
        for j, vk in enumerate(["ALLOWED", "CLOAKED", "BLOCKED"]):
            if vk not in G.verdicts:
                continue
            hh = ((30 + h(20, k, j) * 170) if j == 0 else (8 + h(20, k, j) * 50)) * gp
            d.rectangle((x, y - hh, x + 36, y), fill=G.verdicts[vk])
            y -= hh + 3
    ui.rrect(d, (1200, 280, c.W - 60, 740), 12, fill=(255, 255, 255))
    text(d, (1226, 312), D["dist_title"], F("sans_medium", 22), th.ink, 0, "lm")
    for j, vk in enumerate(order):
        y = 400 + j * 80
        text(d, (1226, y), vk.lower(), F("mono", 18), G.muted, 1, "lm")
        wmax = (c.W - 60 - 1226 - 40) * (0.35 + h(30, j) * 0.6)
        ui.rrect(d, (1226, y + 18, 1226 + max(12, wmax * ease_out(c.p(0.4 + j * 0.08, 1.2 + j * 0.08))), y + 36), 9, fill=G.verdicts[vk])
    ui.rrect(d, (340, 770, c.W - 60, c.H - 40), 12, fill=(255, 255, 255))
    text(d, (366, 802), D["table_title"], F("sans_medium", 22), th.ink, 0, "lm")
    for k, (call, agent, rule, verdict) in enumerate(D["rows"]):
        p = ease_out(c.p(0.6 + k * 0.1, 0.9 + k * 0.1))
        if p <= 0:
            continue
        y = 860 + k * 46
        dx = int((1 - p) * 60)
        text(d, (366 + dx, y), call, F("sans", 20), th.ink, 0, "lm")
        text(d, (820 + dx, y), agent, F("mono", 18), G.muted, 0, "lm")
        text(d, (1120 + dx, y), rule, F("mono", 18), G.muted, 0, "lm")
        ui.chip(im, (c.W - 90 + dx, y), verdict.lower(), th.ink, G.verdicts.get(verdict, G.muted), 15, (12, 5), "rm")
    z = lerp(1.0, 1.035, ease_in_out(c.p(0, c.dur)))
    if z > 1.001:
        im = cover(im, c.W, c.H, z, 0.5, 0.5)
    if c.lt > 1.1:
        d = ImageDraw.Draw(im)
        f = F("sans_medium", 44)
        cap = G.c["dashboard_caption"]
        w = f.getlength(cap) + 60
        p = ease_out(c.p(1.1, 1.4))
        y = lerp(c.H + 40, c.H - 110, p)
        ui.rrect(d, (c.W / 2 - w / 2, y - 38, c.W / 2 + w / 2, y + 38), 38, fill=th.ink)
        text(d, (c.W / 2, y), cap, f, th.paper, -1, "mm")
    return arr(im)


def s_install(c):
    th = G.th
    im = G.canvas()
    ui.window(im, (360, 170, 1560, 780), G.panel, G.line, G.c["install_title"], font_size=15)
    lines, t = [], 0.2
    for ln in G.c["install"]:
        k = ln["kind"]
        spans = [("$ ", G.good), (ln["text"][2:], th.paper)] if k == "cmd" else [(ln["text"], G.kind(k))]
        lines.append({"spans": spans, "t": t, "type": 0.4 if k == "cmd" else 0})
        t += 0.62 if k == "cmd" else 0.28
    ui.terminal(im, (410, 250), lines, c.lt, 28, 1.75, th.paper, c.fi)
    d = ImageDraw.Draw(im)
    x = 410
    for k, a in enumerate(G.c["install_agents"]):
        if c.lt >= t + k * 0.07:
            box = ui.chip(im, (x, 640), a, G.good, G.panel, 18, (14, 7), outline=G.good)
            x = box[2] + 12
    if c.lt > t + 0.3:
        text(d, (c.W / 2, 880), scramble(G.c["install_caption"], ease_out(c.p(t + 0.3, t + 0.7)), 90, c.fi, 4),
             F("sans_medium", 62), th.paper, -2, "mm")
    return arr(im)


def s_end(c):
    th = G.th
    im = G.canvas()
    pad = Image.new("RGB", (900, 900), (0, 0, 0))
    pad.paste(Image.fromarray(holo(c, 300, 300)), (300, 300))
    ga = np.asarray(pad.filter(ImageFilter.GaussianBlur(90)), np.float32) * 0.55 * ease_out(c.p(0.1, 0.8))
    base = np.asarray(im, np.float32)
    y0 = 330 - 450                                   # glow runs off the top edge: clip it
    base[max(0, y0):y0 + 900, c.W // 2 - 450:c.W // 2 + 450] += ga[max(0, -y0):]
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    draw_logo(im, c, c.W / 2, 330, 210, ease_out(c.p(0, 0.45)))
    d = ImageDraw.Draw(im)
    text(d, (c.W / 2, 590), scramble(G.c["tagline"], ease_out(c.p(0.35, 0.85)), 95, c.fi, 4), F("sans_medium", 84), th.paper, -3, "mm")
    if c.lt > 0.8:
        f = F("mono_bold", 34)
        w = f.getlength(G.c["cta"]) + 64
        p = ease_out(c.p(0.8, 1.1))
        box = (c.W / 2 - w / 2, 690, c.W / 2 + w / 2, 760)
        patch = Image.fromarray(holo(c, int(w), 70))
        m = Image.new("L", patch.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, patch.width - 1, 69), radius=35, fill=int(255 * p))
        im.paste(patch, (int(box[0]), 690), m)
        text(ImageDraw.Draw(im), (c.W / 2, 725), G.c["cta"], f, th.ink, 0, "mm")
    d = ImageDraw.Draw(im)
    text(d, (c.W / 2, 830), typed(G.c["links"], c.p(1.0, 1.5)), F("mono", 30), (190, 190, 196), 1, "mm")
    text(d, (c.W / 2, 885), typed(G.c["license"], c.p(1.3, 1.6)), F("mono", 22), G.muted, 2, "mm")
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
        print("copy keys missing:", [k for k in REQUIRED if k not in brief["copy"]] or "none")
        own = Assets(G.assets.dirs[0])
        print("assets missing (placeholders used):", [s for s in SLOTS if not own.path(s)] or "none")
        print(f"duration {tl.duration:.2f}s, {tl.n_frames} frames, {len(tl.scenes)} scenes")
    elif a.cmd == "assets":
        specs = {k: v for k, v in brief.get("assets", {}).items() if k in SLOTS}
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
