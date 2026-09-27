#!/usr/bin/env python3
"""brutalist-product-promo: a 22-second, 21-scene hardware/product spec-sheet promo.

    python3 promo.py render  --brief brief.json [--out out/promo.mp4] [--audio track.mp3]
    python3 promo.py still   --brief brief.json 3.4 11.2        # review single frames
    python3 promo.py sheet   --brief brief.json                 # contact sheet of the whole cut
    python3 promo.py assets  --brief brief.json [names...]      # generate images with gpt-image-2
    python3 promo.py check   --brief brief.json                 # validate brief + list missing assets

Assets resolve from <brief dir>/assets, then the bundled placeholders.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from framesmith import (Assets, Ctx, Mosaic, Scene, Theme, Timeline, cover, cover_point, decay, ease_in_out,
                        ease_out, generate_images, h, lerp, pingpong, rot_text, scramble, sprite_masks, spread,
                        text, typed, wordmark_mask, fit_unit)
from framesmith.typography import F
from framesmith import blueprint as bp
from framesmith import fx

ASSET_SLOTS = ("hero", "closeup", "cutout", "environment", "lineart", "sprite")


class P:
    """Everything a scene needs: brief copy, theme, assets, helpers."""

    def __init__(self, brief, brief_dir):
        self.b = brief
        self.c = brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        self.W, self.H = brief.get("size", [720, 1280])
        self.assets = Assets(os.path.join(brief_dir, brief.get("assets_dir", "assets")),
                             os.path.join(HERE, "..", "placeholders"))
        self.meta = brief.get("meta", {})
        self._cache = {}

    def img(self, name):
        return self.assets.get(name)

    def cached(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def sprite(self, t, rate=8.0):
        grid = self.b.get("assets", {}).get("sprite", {}).get("grid", [2, 2])
        frames = self.cached("sprite", lambda: sprite_masks(self.img("sprite"), *grid))
        order = pingpong(len(frames))
        return frames[order[int(t * rate) % len(order)]]

    def canvas(self, col):
        return Image.new("RGB", (self.W, self.H), col)


G = None   # set by build(); scene functions read it (fork-safe global)


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def sprite_on(im, t, box, col, rate=8.0):
    m = G.sprite(t, rate)
    x, y, w, hh = box
    s = min(w / m.width, hh / m.height)
    m = m.resize((max(1, int(m.width * s)), max(1, int(m.height * s))), Image.LANCZOS)
    im.paste(Image.new("RGB", m.size, col), (int(x + (w - m.width) / 2), int(y + (hh - m.height) / 2)), m)


def U(unit, frac=0.5):
    """Wordmark cell height: `unit` for short names, shrunk so long names fit frac of the width."""
    return fit_unit(G.c["brand"], G.W * frac, unit)


def logo(im, col, unit, y, frac=0.5, **kw):
    unit = U(unit, frac)
    m, boxes = wordmark_mask(G.c["brand"], (G.W, int(unit * 9)), unit, **kw)
    im.paste(Image.new("RGB", m.size, col), (0, int(y - m.height / 2)), m)
    return boxes


def footer(d, p, col, y0=735):
    for i, s in enumerate(G.c["footer"]):
        text(d, (G.W / 2, y0 + i * 14), typed(s, min(1, max(0, p * 3 - i))), F("mono", 9), col, 0, "mm")


def bracket(s):
    return f"[ {s} ]"


# ---------------------------------------------------------------- scenes
def s_intro(c: Ctx):
    im = G.canvas(G.th.ink)
    if c.lt > 0.2:
        text(ImageDraw.Draw(im), (c.W / 2, c.H / 2), "[   ]", F("mono", 16), G.th.paper, anchor="mm")
    return arr(im)


def s_tagline_bar(c):
    th = G.th
    im = G.canvas(th.accent)
    d = ImageDraw.Draw(im)
    d.rectangle((0, c.H / 2 - 30, c.W, c.H / 2 + 30), fill=th.ink)
    text(d, (c.W / 2, c.H / 2), scramble(bracket(G.c["tagline"]), ease_out(c.p(0, 0.25)), 1, c.fi), F("mono", 25), th.paper, 1, "mm")
    return arr(im)


def s_word_field(c):
    th = G.th
    light = c.lt < 0.23
    n = fx.noise_tex()
    ox, oy = int(c.lt * 260) % 300, int(c.lt * 120) % 300
    fg, bg = (th.ink, th.paper) if light else (th.paper, th.ink)
    im = Image.fromarray(fx.word_field(n[oy:oy + 600, ox:ox + 600], c.fi, c.W, c.H, G.c["field_word"], fg, bg))
    d = ImageDraw.Draw(im)
    cap = bracket(G.c["tagline"])
    kw = G.c.get("tagline_keyword")
    if c.lt > 0.73 and kw:                              # caption decays down to its keyword
        p = c.p(0.73, 1.0)
        i0 = cap.find(kw)
        cap = bracket(kw) if p > 0.85 else decay(cap, p, set(range(i0, i0 + len(kw))))
    d.rectangle((c.W / 2 - 350, c.H / 2 - 22, c.W / 2 + 350, c.H / 2 + 22), fill=bg)
    text(d, (c.W / 2, c.H / 2), cap, F("mono", 25), fg, 1, "mm")
    return arr(im)


def s_model_black(c):
    th = G.th
    im = G.canvas(th.ink)
    sprite_on(im, c.t, (-40, 30, c.W + 80, 300), th.paper)
    s = lerp(1.05, 1.18, ease_in_out(c.p(0, 1)))
    bp.top_view(im, 250, 900, s, th.paper, th.ink, c.lt, ease_out(c.p(0, 0.45)), 2, int(c.lt * 8), label=G.c["dim_label"])
    text(ImageDraw.Draw(im), (c.W - 30, 690), f"[{G.c['model']}]", F("sans_medium", 104), th.paper, -4, "rm")
    return arr(im)


def s_accent_zoom(c):
    th = G.th
    im = G.canvas(th.accent)
    p = ease_out(c.p(0, c.dur))
    bp.top_view(im, lerp(520, 640, p), lerp(560, 620, p), lerp(2.8, 3.6, p), th.on_accent, th.accent, c.t, 1, 4, label=G.c["dim_label"])
    return arr(im)


def s_spec_sheet(c):
    th = G.th
    lt = c.lt
    im = G.canvas(th.paper)
    d = ImageDraw.Draw(im)
    for x in range(0, c.W, 24):
        d.line((x, 0, x, c.H), fill=th.paper_grid)
    for y in range(0, c.H, 24):
        d.line((0, y, c.W, y), fill=th.paper_grid)
    layer = G.canvas(th.paper)
    L = G.c["dim_label"]
    if lt < 0.25:
        p = ease_out(c.p(0, 0.25))
        bp.top_view(layer, lerp(560, 460, p), 720, lerp(3.0, 2.2, p), th.accent, th.on_accent, c.t, 1, 3, 2, label=L)
    elif lt < 0.8:
        bp.front_view(layer, 360, 230, lerp(1.08, 1.12, c.p(0.25, 0.8)), th.accent, th.on_accent, lt, ease_out(c.p(0.25, 0.5)), 2, label=L)
    elif lt < 1.05:
        bp.top_view(layer, 360, 760, lerp(1.25, 1.35, c.p(0.8, 1.05)), th.accent, th.on_accent, lt, 1, 2, 3, label=L)
    else:
        p = ease_in_out(c.p(1.05, c.dur))
        bp.top_view(layer, lerp(860, 900, p), 780, lerp(2.0, 2.3, p), th.accent, th.on_accent, lt * 2, 1, 3, 4, label=L)
    d.rectangle((0, 0, c.W, 150), fill=th.paper)
    text(d, (16, 17), G.c["company"], F("sans", 14), th.ink, anchor="lm")
    text(d, (c.W - 16, 17), G.c["origin"], F("sans", 14), th.ink, anchor="rm")
    text(d, (14, 92), scramble(G.c["sheet_title"], ease_out(c.p(0, 0.3)), 5, c.fi, 4), F("sans", 88), th.ink, -4, "lm")
    lay = np.asarray(layer, np.float32)
    lay[:150] = 255
    return (np.asarray(im, np.float32) * lay / 255).astype(np.uint8)      # multiply: grid shows through


def env_strips(c):
    g = G.cached("env_gray", lambda: ImageOps.autocontrast(G.img("environment").convert("L"), cutoff=2))
    a = np.asarray(cover(ImageOps.invert(g).convert("RGB"), c.W, 1180, 1.25)).copy()
    out = np.zeros_like(a)
    sw = 120
    for i in range(0, c.W, sw):
        k = i // sw
        off = int(math.sin(k * 1.7) * 60 + c.lt * (40 + 30 * (k % 3)) * (1 if k % 2 else -1))
        col = np.roll(a[:, i:i + sw], off, axis=0)
        out[:, i:i + sw] = 255 - col if k % 3 == 1 else col
    lum = out.mean(axis=2, keepdims=True)
    return np.clip((lum - 128) * 1.6 + 128, 0, 255).repeat(3, axis=2).astype(np.uint8)


def s_environment(c):
    th = G.th
    im = G.canvas(th.paper)
    im.paste(Image.fromarray(env_strips(c)), (0, 0))
    d = ImageDraw.Draw(im)
    for i, s in enumerate(G.c["terminal"]):
        text(d, (18, 1200 + i * 16), typed(s, c.p(0.1 + i * 0.12, 0.5 + i * 0.12)), F("mono", 11), th.ink, 1)
    return arr(im)


def s_env_ascii(c):
    g = G.cached("env_gray", lambda: ImageOps.autocontrast(G.img("environment").convert("L"), cutoff=2))
    im = cover(g.convert("RGB"), c.W, c.H, 1.3, 0.5, 0.3 + c.lt * 0.04).convert("L")
    return fx.ascii_render(ImageOps.autocontrast(im, cutoff=5), c.W, c.H, 6, 10, 9, G.th.paper, G.th.ink)


def s_hero(c):
    th = G.th
    lt = c.lt
    im = G.canvas(th.paper)
    src = G.img("hero").convert("RGB")
    zoom = lerp(1.0, 1.06, c.p(0, 1))
    im.paste(cover(src, c.W, 820, zoom), (0, 0))
    d = ImageDraw.Draw(im)
    if lt > 0.1:
        x, y = cover_point(src, c.W, 820, G.meta.get("hero_target", [0.8, 0.3]), zoom)
        s = lerp(70, 46, ease_out(c.p(0.1, 0.35)))
        d.rectangle((x - s, y - s, x + s, y + s), outline=th.paper, width=1)
        d.line((x + s, y, c.W, y), fill=th.paper)
        d.line((0, y + s * 0.3, x - s, y + s * 0.3), fill=th.mid)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=th.paper)
    text(d, (c.W - 14, 862), scramble(G.c["product_name"], ease_out(c.p(0, 0.35)), 9, c.fi, 4), F("sans", 52), th.ink, -2, "rm")
    blk = fx.random_text_block(c.W, 380, c.fi, 21, 6, 9, 8, th.ink, th.paper)
    rows = int(lerp(4, 42, ease_out(c.p(0, 0.6))))
    im.paste(Image.fromarray(blk[: rows * 9]), (0, 900))
    return arr(im)


def arrow_poly(cx, cy, s):
    k = s / 100
    pts = [(-50, -40), (-40, -50), (30, 20), (30, -20), (45, -20), (45, 45), (-20, 45), (-20, 30), (20, 30)]
    return [(cx + x * k, cy + y * k) for x, y in pts]


def s_arrow(c):
    im = G.canvas(G.th.ink)
    p = ease_out(c.p(0, c.dur))
    ImageDraw.Draw(im).polygon(arrow_poly(lerp(360, 32, p), lerp(640, 35, p), lerp(1500, 60, p)), fill=G.th.accent)
    return arr(im)


def overview_page(c):
    """Landscape page, rotated clockwise into the portrait frame."""
    th, C = G.th, G.c
    pg = Image.new("RGB", (c.H - 70, c.W - 70), th.paper)
    d = ImageDraw.Draw(pg)
    sp = lambda i: ease_out(c.p(0.05 + i * 0.06, 0.45 + i * 0.06))    # 60 ms stagger
    d.line((600, 0, 600, pg.height), fill=th.paper_grid)
    for i, line in enumerate(C["overview_title"]):
        text(d, (18, 12 + i * 60), scramble(line, sp(i), 31 + i, c.fi), F("sans", 58), th.ink, -3)
    w1, w2 = C["overview_words"]
    text(d, (18, 200), scramble(w1, sp(2), 33, c.fi), F("sans", 30), th.ink, -1)
    text(d, (250, 290), scramble(w2, sp(3), 34, c.fi), F("sans", 30), th.ink, -1)
    if sp(3) > 0:
        d.rectangle((18, 420, 18 + int(260 * sp(4)), 436), fill=th.ink)
    for i, s in enumerate(C["overview_specs"]):
        text(d, (400, 170 + i * 16), typed(s, sp(4 + i * 0.3)), F("mono", 10), th.ink)
    fine = C["overview_fineprint"]
    for j in range(3):
        for i in range(5):
            text(d, (18 + j * 190, 480 + i * 14), typed(fine[: 18 + j * 4], sp(6 + j)), F("mono", 9), th.mid)
    la = ImageOps.invert(G.img("lineart").convert("L")).convert("RGB")
    la = cover(la, 600, pg.height, 1.0, 0.5, 0.55)
    wp = int(pg.height * ease_out(c.p(0.1, 0.7)))
    pg.paste(la.crop((0, 0, 600, wp)), (610, 0))
    (a1, a2), (b1, b2) = C["overview_side"]
    d.rectangle((620, 6, 900, 70), fill=th.paper)
    d.rectangle((620, pg.height - 70, 900, pg.height - 6), fill=th.paper)
    text(d, (630, 14), scramble(a1, sp(2), 35, c.fi), F("sans", 22), th.ink)
    text(d, (630, 40), scramble(a2, sp(3), 36, c.fi), F("sans", 22), th.ink)
    text(d, (630, pg.height - 62), scramble(b1, sp(5), 37, c.fi), F("sans", 22), th.ink)
    text(d, (630, pg.height - 36), scramble(b2, sp(6), 38, c.fi), F("sans", 22), th.ink)
    return pg.rotate(-90, expand=True)


def s_overview(c):
    th = G.th
    im = G.canvas(th.paper)
    im.paste(overview_page(c), (0, 70))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, c.W, 70), fill=th.accent)
    d.polygon(arrow_poly(32, 35, 60), fill=th.ink)
    text(d, (70, 36), G.c["overview_header"], F("sans_medium", 26), th.ink, -1, "lm")
    m, _ = wordmark_mask(G.c["brand"], (400, 40), fit_unit(G.c["brand"], 56, 4))
    m = m.crop(m.getbbox() or (0, 0, 1, 1)).rotate(-90, expand=True)
    im.paste(Image.new("RGB", m.size, th.ink), (c.W - 14 - m.width, 8), m)
    return arr(im)


def glitch_words():
    return G.c.get("glitch_words") or [G.c["field_word"], G.c["field_word"][::-1], G.c["brand"]]


def s_closeup(c):
    th = G.th
    lt = c.lt
    if lt < 0.17:                                            # paper flash with a grey wordmark
        im = G.canvas(th.paper)
        a = cover(G.img("closeup").convert("L"), c.W, 520, 1.3, 0.3, 0.5)
        a = ImageOps.autocontrast(a).point(lambda v: 255 if v > 60 else 255 - v)
        im.paste(a.convert("RGB"), (0, 330))
        logo(im, (150, 150, 150), 22, 560)
        im.paste(fx.glitch_rows(c.W, 480, c.fi, 41, 0.35, glitch_words(), th.paper, th.paper), (0, 800))
        return arr(im)
    im = G.canvas(th.ink)
    im.paste(cover(G.img("closeup").convert("RGB"), c.W, 560, lerp(1.0, 1.12, c.p(0.17, 1.8)), 0.55, 0.5), (0, 300))
    g = fx.glitch_rows(c.W, 520, c.fi, 42, lerp(0.35, 0.6, c.p(0.2, 1.6)), glitch_words(), th.ink, th.paper)
    gm = Image.fromarray((np.asarray(g.convert("L")) > np.mean(th.ink) + 1).astype(np.uint8) * 255)
    im.paste(g, (0, 760), gm)
    im.paste(g.crop((0, 80, c.W, 520)), (0, 860))
    return arr(im)


def s_specs(c):
    th = G.th
    lt = c.lt - 0.25                                         # choreography keyed to the end of the wipe
    im = G.canvas(th.accent)
    d = ImageDraw.Draw(im)
    for x in range(0, c.W, 40):
        d.line((x, 0, x, c.H), fill=th.accent_grid)
    for y in range(0, c.H, 40):
        d.line((0, y, c.W, y), fill=th.accent_grid)
    sprite_on(im, c.t, (-30, 60, c.W + 60, 470), th.ink, 6)
    sl = G.c["spec_side_labels"]
    rot_text(im, (8, 20), sl[0], F("mono", 11), th.ink)
    for i, s in enumerate(sl[1:3]):
        rot_text(im, (c.W - 40 + i * 16, 20), s, F("mono", 11), th.ink)
    pg = Image.new("RGB", (c.W, c.W), th.accent)
    pd = ImageDraw.Draw(pg)
    text(pd, (10, 0), scramble(G.c["specs_title"], ease_out(c.p(0, 0.35)), 51, c.fi, 3), F("sans_medium", 76), th.ink, -3)
    y = 110
    for bi, blk in enumerate(G.c["spec_blocks"]):
        p0 = -0.2 + bi * 0.08
        pr = lambda a, b: min(max((lt - a) / (b - a), 0), 1)
        pd.rectangle((10, y, 10 + int(700 * ease_out(pr(p0, p0 + 0.3))), y + 22), fill=th.ink)
        text(pd, (16, y + 3), typed(blk["head"], pr(p0, p0 + 0.2)), F("mono_bold", 15), th.accent, 1)
        y += 34
        for li, s in enumerate(blk["lines"]):
            text(pd, (16, y), typed(s, pr(p0 + 0.05 + li * 0.05, p0 + 0.35 + li * 0.05)), F("mono", 15), th.ink, 1)
            y += 21
        y += 22
    im.paste(pg.rotate(-90, expand=True), (0, 560))
    fx.barcode(ImageDraw.Draw(im), c.W - 130, c.H - 60, 120, 44, th.ink, 77)
    return arr(im)


def s_lineart(c):
    th = G.th
    lt = c.lt - 0.55
    la = cover(G.img("lineart").convert("RGB"), c.W, c.H - 90, lerp(1.1, 1.18, min(max(lt / 1.5, 0), 1)), 0.5, 0.55)
    base = np.zeros((c.H, c.W, 3), np.uint8)
    base[90:] = np.asarray(la)
    cw, ch = 120, 128
    on = lambda r, cc: h(88, r, cc) < min(max((lt - 0.3) / 1.1, 0), 1) * 0.55
    tint = np.zeros_like(base)
    for r in range(c.H // ch):
        for cc in range(c.W // cw):
            if on(r, cc):
                tint[r * ch:(r + 1) * ch, cc * cw:(cc + 1) * cw] = th.tint
    im = Image.fromarray(np.maximum(tint, base))             # line art stays on top of the tint
    d = ImageDraw.Draw(im)
    edge = tuple(min(255, int(v * 1.3)) for v in th.tint)
    for r in range(c.H // ch):
        for cc in range(c.W // cw):
            if on(r, cc):
                d.rectangle((cc * cw, r * ch, (cc + 1) * cw, (r + 1) * ch), outline=edge)
                fx.crosshair(d, cc * cw + 60, r * ch + 64, edge)
    im.paste(Image.fromarray(fx.random_text_block(c.W, 90, c.fi, 61, 6, 9, 8, th.ink, th.paper)), (0, 0))
    words = glitch_words()
    for i in range(4):
        x = int(h(62, i, c.fi // 3) * (c.W - 160))
        d.rectangle((x, c.H - 44, x + 140, c.H - 24), fill=th.paper)
        d.text((x + 4, c.H - 40), words[(i + c.fi // 3) % len(words)][:18], font=F("mono", 12), fill=th.ink)
    return arr(im)


def s_checker(c):
    th = G.th
    im = G.canvas(th.paper)
    d = ImageDraw.Draw(im)
    cs, k = 180, int(c.lt / 0.25)
    for r in range(6):
        for cc in range(4):
            y = 300 + r * cs
            dark = h(95, r, cc, k) < 0.45
            d.rectangle((cc * cs, y, (cc + 1) * cs, y + cs), fill=th.ink if dark else th.paper)
            if not dark:
                for px, py in ((45, 45), (135, 45), (45, 135), (135, 135)):
                    fx.crosshair(d, cc * cs + px, y + py, th.paper_grid, 8)
    g = G.img("cutout")
    g = g.resize((980, int(g.height * 980 / g.width)), Image.LANCZOS)
    rgb = np.asarray(g.convert("RGB")).astype(np.float32)
    alpha = g.getchannel("A")
    lum = rgb.mean(axis=2, keepdims=True)
    tinted = np.clip(np.array(th.accent, np.float32) * (0.55 + lum / 255 * 0.7), 0, 255)
    mask = np.zeros(rgb.shape[:2], bool)
    for i in range(3):                                       # flashing accent bands
        x0 = int(h(96, i, c.fi // 3) * 900)
        mask[:, x0:x0 + int(80 + h(97, i, c.fi // 3) * 200)] = True
    im.paste(Image.fromarray(np.where(mask[..., None], tinted, rgb).astype(np.uint8)), (-180, 720 - g.height // 2), alpha)
    d.rectangle((0, 0, c.W, 300), fill=th.paper)
    l1, l2 = G.c["labels"]
    lab, p = (l1, c.p(0, 0.3)) if c.lt < 0.5 else (l2, c.p(0.5, 0.85))
    f = F("mono", 12)
    bw = f.getlength(lab) + 40
    d.rectangle((c.W / 2 - bw / 2, 160, c.W / 2 + bw / 2, 190), outline=th.ink)
    text(d, (c.W / 2 - bw / 2 + 20, 175), typed(lab, p), f, th.ink, 1, "lm")
    return arr(im)


def s_connecting(c):
    th = G.th
    im = G.canvas(th.ink)
    d = ImageDraw.Draw(im)
    for r in range(7):
        for cc in range(2):
            if (r + cc) % 2 == 0 or cc == 1:
                x, y = 560 + cc * 80, 460 + r * 90
                d.rectangle((x, y, x + 80, y + 90), outline=th.tint)
                fx.crosshair(d, x + 40, y + 45, th.tint)
    text(d, (100, c.H / 2), scramble(f"[{G.c['connecting']}]", c.p(0, 0.15), 71, c.fi, 3), F("mono", 17), th.paper, 1, "lm")
    return arr(im)


def s_connected(c):
    th = G.th
    lt = c.lt
    im = G.canvas(th.ink)
    a = G.cached("closeup_th", lambda: ImageOps.autocontrast(G.img("closeup").convert("L"), cutoff=2).point(lambda v: 255 if v > 95 else 0))
    s = lerp(1.25, 1.35, c.p(0, 1)) * 0.62
    a = a.resize((int(a.width * s), int(a.height * s)), Image.LANCZOS).rotate(28 + lt * 3, expand=True, fillcolor=0)
    im.paste(Image.new("RGB", a.size, th.paper), (int(-260 - lt * 30), int(260 - lt * 20)), a)
    d = ImageDraw.Draw(im)
    jx = int((h(72, c.fi) - 0.5) * 10) if h(73, c.fi) > 0.7 else 0
    text(d, (c.W / 2 + jx, c.H / 2), scramble(bracket(G.c["connected"]), c.p(0, 0.3), 74, c.fi), F("mono", 22), th.accent, 1, "mm")
    if lt > 0.75:
        p = ease_out(c.p(0.75, 1.0))
        d.rectangle((0, 470, int(lerp(0, 440, p)), 700), fill=th.paper)
        d.rectangle((0, 470, int(lerp(0, 330, p)), 740), fill=th.paper)
    return arr(im)


def s_smear(c):
    out = fx.smear(s_connected(c.at(0.98)), c.fi, G.th.tint)
    out[520:760, 280:460] = G.th.accent
    return out


def s_cross(c):
    th = G.th
    im = G.canvas(th.ink)
    d = ImageDraw.Draw(im)
    d.rectangle((160, 0, 560, c.H), fill=th.accent)
    d.rectangle((120, 440, 600, 860), fill=th.accent)
    bp.front_view(im, 360, 60, 1.25, th.on_accent, th.accent, c.lt + 1.5, 1, 2, label=G.c["dim_label"])
    ImageDraw.Draw(im).rectangle((190, 590, 530, 690), fill=th.accent)
    logo(im, th.on_accent, 9, 640, 0.42)
    footer(ImageDraw.Draw(im), 1.0, th.on_accent, 720)
    return arr(im)


def s_logo(c):
    im = G.canvas(G.th.ink)
    logo(im, G.th.accent, 9.5, 640)
    footer(ImageDraw.Draw(im), c.p(0, 1.2), G.th.paper)
    return arr(im)


def s_outro(c):
    th = G.th
    lt = c.lt
    im = G.canvas(th.ink)
    d = ImageDraw.Draw(im)
    n = len(G.c["brand"])
    if lt < 0.25:                                            # oversized ghost outline
        logo(im, (60, 60, 60), 15, 640, 0.8, outline=1)
        logo(im, th.accent, 9.5, 640)
    elif lt < 0.55:                                          # barcode interrupt
        logo(im, (40, 40, 40), 15, 640, 0.8, outline=1)
        logo(im, th.accent, 9.5, 640, letters_dx=spread(n, 40))
        fx.barcode(d, c.W / 2 - 55, 540, 110, 170, th.paper, c.fi // 2)
    else:                                                    # letters drift apart, then drop out
        p = ease_out(c.p(0.55, 0.9))
        m, boxes = wordmark_mask(G.c["brand"], (c.W, 160), lerp(U(9.5), U(6, 0.3), p), letters_dx=spread(n, lerp(40, 140, p)))
        if lt > 0.95:
            a = np.asarray(m).copy()
            for i, (x0, _, x1, _) in enumerate(boxes):
                if h(99, i) < c.p(0.95, 1.15):
                    a[:, max(0, int(x0) - 2):int(x1) + 2] = 0
            m = Image.fromarray(a)
        im.paste(Image.new("RGB", m.size, th.accent), (0, 560), m)
    if lt < 0.85:
        footer(d, 1.0, th.paper)
    return arr(im)


SCENES = [  # (name, seconds, fn, transition)
    ("intro", 0.45, s_intro, None),
    ("tagline_bar", 0.27, s_tagline_bar, None),
    ("word_field", 1.00, s_word_field, None),
    ("model_black", 1.00, s_model_black, None),
    ("accent_zoom", 0.25, s_accent_zoom, None),
    ("spec_sheet", 1.78, s_spec_sheet, None),
    ("environment", 1.25, s_environment, None),
    ("env_ascii", 1.45, s_env_ascii, Mosaic(0.85, 6, 10, 11)),
    ("hero", 1.00, s_hero, None),
    ("arrow", 0.27, s_arrow, None),
    ("overview", 1.73, s_overview, None),
    ("closeup", 1.80, s_closeup, None),
    ("specs", 2.20, s_specs, Mosaic(0.30, 6, 10, 55)),
    ("lineart", 2.00, s_lineart, Mosaic(0.55, 8, 14, 66)),
    ("checker", 1.00, s_checker, None),
    ("connecting", 0.27, s_connecting, None),
    ("connected", 1.00, s_connected, None),
    ("smear", 0.25, s_smear, None),
    ("cross", 0.25, s_cross, None),
    ("logo", 2.23, s_logo, None),
    ("outro", 1.19, s_outro, None),
]


def build(brief_path):
    global G
    with open(brief_path) as f:
        brief = json.load(f)
    G = P(brief, os.path.dirname(os.path.abspath(brief_path)))
    over = brief.get("scenes", {})          # {"name": seconds | 0 to drop}
    scenes = []
    for name, dur, fn, tr in SCENES:
        dur = over.get(name, dur)
        if dur:
            scenes.append(Scene(name, dur * brief.get("speed", 1.0) ** -1, fn, tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 25), data=G, theme=G.th), brief


REQUIRED_COPY = ["brand", "company", "origin", "tagline", "field_word", "model", "dim_label", "sheet_title", "terminal",
                 "product_name", "overview_header", "overview_title", "overview_words", "overview_specs",
                 "overview_fineprint", "overview_side", "specs_title", "spec_blocks", "spec_side_labels",
                 "labels", "connecting", "connected", "footer"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["render", "still", "sheet", "assets", "check"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "arc", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--force", action="store_true", help="assets: regenerate even if present")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    base = os.path.dirname(os.path.abspath(a.brief))
    outdir = os.path.join(base, "out")
    if a.cmd == "check":
        miss = [k for k in REQUIRED_COPY if k not in brief["copy"]]
        print("copy keys missing:", miss or "none")
        own = Assets(G.assets.dirs[0])
        print("assets missing (placeholders will be used):", [n for n in ASSET_SLOTS if not own.path(n)] or "none")
        from framesmith.theme import luminance
        l1, l2 = sorted((luminance(G.th.accent), luminance(G.th.paper)))
        ratio = (l2 + 0.05) / (l1 + 0.05)
        if ratio < 1.6:
            print(f"warning: accent vs paper contrast {ratio:.2f}:1, accent line art on the spec sheet will be faint")
        print(f"duration {tl.duration:.2f}s, {tl.n_frames} frames, {len(tl.scenes)} scenes")
    elif a.cmd == "assets":
        specs = {k: v for k, v in brief.get("assets", {}).items() if k in ASSET_SLOTS}
        fmtd = lambda s: s.format(**{k: v for k, v in brief["copy"].items() if isinstance(v, str)})
        for m in generate_images(specs, G.assets.dirs[0], names=a.args or None, force=a.force, fmt=fmtd):
            print(m)
    elif a.cmd == "still":
        os.makedirs(outdir, exist_ok=True)
        for s in a.args or ["3.4"]:
            print(tl.still(float(s), os.path.join(outdir, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        os.makedirs(outdir, exist_ok=True)
        print(tl.contact_sheet(a.out or os.path.join(outdir, "contact_sheet.png")))
    else:
        print(tl.render(a.out or os.path.join(outdir, "promo.mp4"), a.audio))


if __name__ == "__main__":
    main()
