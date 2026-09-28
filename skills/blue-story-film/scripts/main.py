#!/usr/bin/env python3
"""blue-story-film: a music-driven SaaS story film in the blue-light style.

Typewriter captions with a caret and selection highlight over ghosted UI, a huge "Meet" word that
collapses into the brand line, product UI in perspective over gpt-image-2 blue light backdrops, a split
screen where a UI row wires into a dark terminal, bracket words, a wide streaking word, a camera
flying over oversized form fields, and a black typewriter CTA.

    python3 main.py assets|check|still|sheet|render --brief brief.json [times...] [--audio music.m4a]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Dissolve, Scene, Timeline, cover, ease_in_out, ease_out, generate_images, hex2rgb, lerp, overflow_report, text, typed
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width
from framesmith import ui

G = None


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.ink = c("ink", (14, 16, 24))
        self.blue = c("blue", (24, 110, 255))
        self.sky = c("sky", (120, 200, 255))
        self.muted = c("muted", (150, 156, 175))
        self.bg = (255, 255, 255)
        self.W, self.H = brief.get("size", [1920, 1080])
        self.assets = os.path.join(base, brief.get("assets_dir", "assets"))
        self._c = {}

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def png(name):
    return G.cache(("png", name), lambda: Image.open(os.path.join(G.assets, name if "." in os.path.basename(name) else name + ".png")).convert("RGBA"))


def fade(im, p):
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * max(0.0, min(1.0, p))).astype(np.uint8)
    return Image.fromarray(a)


def backdrop(kind, lt=0.0, drift=True):
    """white | black | a gpt-image-2 backdrop (bg_sky, bg_navy, bg_wash, bg_glow) with a slow drift."""
    if kind == "white":
        return Image.new("RGBA", (G.W, G.H), (255, 255, 255, 255))
    if kind == "black":
        return Image.new("RGBA", (G.W, G.H), (0, 0, 0, 255))
    src = png(kind).convert("RGB")
    z = 1.08 + (0.04 * math.sin(lt * 0.4) if drift else 0)
    return cover(src, G.W, G.H, z, 0.5 + 0.03 * math.sin(lt * 0.3), 0.5).convert("RGBA")


def is_dark(kind):
    return kind in ("black", "bg_navy", "bg_glow")


# ------------------------------------------------------------------ perspective (shared with glass-saas-promo)
def project(w, hgt, rx, ry, rz, scale, cx, cy, fov=1400):
    rx, ry, rz = [math.radians(v) for v in (rx, ry, rz)]
    pts = []
    for x, y in ((-w / 2, -hgt / 2), (w / 2, -hgt / 2), (w / 2, hgt / 2), (-w / 2, hgt / 2)):
        x, y, z = x * scale, y * scale, 0.0
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
        k = fov / (fov + z)
        pts.append((cx + x * k, cy + y * k))
    return pts


def warp(img, quad, size, shadow=0.35):
    w, hgt = img.size
    A, B = [], []
    for (x, y), (u, v) in zip(quad, [(0, 0), (w, 0), (w, hgt), (0, hgt)]):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    c = np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()
    out = img.transform(size, Image.PERSPECTIVE, c, Image.BICUBIC)
    if shadow:
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).polygon([(x, y + 30) for x, y in quad], fill=int(255 * shadow))
        base = Image.new("RGBA", size, (10, 30, 90, 0))
        base.putalpha(m.filter(ImageFilter.GaussianBlur(40)))
        base.alpha_composite(out)
        out = base
    return out


def panel(name, radius=16):
    def build():
        im = png(name).convert("RGBA")
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
        im.putalpha(m)
        return im
    return G.cache(("panel", name), build)


# ------------------------------------------------------------------ text
def line_layer(line, f, color, blue, lt, stagger=0.07, max_w=None):
    """Transparent layer with a centred line; *words in the accent colour; words blur in one by one."""
    max_w = max_w or G.W - 220
    toks = line.split(" ")
    sp = f.getlength(" ")
    total = sum(text_width(t.lstrip("*"), f) for t in toks) + sp * (len(toks) - 1)
    if total > max_w:
        SHRINKS.append((line, max_w / total))
        f = F("sans_medium", int(f.size * max_w / total))
        sp = f.getlength(" ")
        total = sum(text_width(t.lstrip("*"), f) for t in toks) + sp * (len(toks) - 1)
    lay = Image.new("RGBA", (G.W, G.H), (0, 0, 0, 0))
    x = G.W / 2 - total / 2
    for k, tk in enumerate(toks):
        word = tk.lstrip("*")
        p = ease_out(min(1, max(0, (lt - k * stagger) / 0.35)))
        w = text_width(word, f)
        if p > 0:
            m = Image.new("L", (int(w) + 40, int(f.size * 1.6)), 0)
            ImageDraw.Draw(m).text((20, f.size * 1.15), word, font=f, fill=255, anchor="ls")
            if p < 1:
                m = m.filter(ImageFilter.GaussianBlur((1 - p) * 10)).point(lambda v: int(v * p))
            col = blue if tk.startswith("*") else color
            lay.paste(Image.new("RGBA", m.size, col + (255,)), (int(x - 20), int(G.H / 2 - f.size * 0.8 + (1 - p) * 16)), m)
        x += w + sp
    return lay


def place(im, lay, cy):
    im.alpha_composite(lay, (0, int(cy - G.H / 2)))


def shot_type(c, s):
    """Typewriter caption with a caret; an optional word gets a selection highlight; ghost UI drifts around."""
    im = backdrop(s.get("bg", "white"), c.lt)
    for k, g in enumerate(s.get("ghosts", [])):             # faint UI fragments, like the reference's wireframes
        img = panel(g["media"])
        k2 = g.get("w", 420) / img.width
        q = project(img.width * k2, img.height * k2, g.get("rx", 8), g.get("ry", 0), g.get("rz", 0), 1.0,
                    g["x"] * c.W + math.sin(c.lt * 0.6 + k) * 8, g["y"] * c.H + math.cos(c.lt * 0.5 + k) * 6)
        im.alpha_composite(fade(warp(img, q, im.size, shadow=0.15), g.get("alpha", 0.55)))
    f = F("sans_medium", s.get("size", 58))
    full = s["text"]
    shown = typed(full, (c.lt - 0.15) / max(0.2, s.get("type_s", len(full) * 0.045)))
    dark = is_dark(s.get("bg", "white"))
    col = (255, 255, 255) if dark else G.ink
    y = c.H * s.get("y", 0.5)
    x0 = c.W / 2 - text_width(full, f) / 2
    d = ImageDraw.Draw(im)
    sel = s.get("select")
    sel_on = sel and c.lt >= s.get("select_at", 99) and sel in shown
    if sel_on:                                             # text-selection highlight (square, like an editor)
        i = full.index(sel)
        sx = x0 + text_width(full[:i], f)
        sw = text_width(sel, f)
        pp = ease_out(min(1, (c.lt - s["select_at"]) / 0.25))
        d.rectangle((sx - 4, y - f.size * 0.72, sx - 4 + (sw + 8) * pp, y + f.size * 0.3), fill=G.blue)
    text(d, (x0, y), shown, f, col, 0, "ls", max_w=c.W - 200, fit_to=full)
    if sel_on:
        i = full.index(sel)
        text(d, (x0 + text_width(full[:i], f), y), sel, f, (255, 255, 255), 0, "ls")
    if (c.fi // 12) % 2 == 0 or len(shown) < len(full):
        cx = x0 + text_width(shown, f) + 4
        d.rectangle((cx, y - f.size * 0.75, cx + 3, y + f.size * 0.2), fill=col)
    if s.get("url"):
        text(d, (c.W / 2, c.H - 60), s["url"], F("sans", 22), (170, 176, 200), 0, "mm")
    return arr(im)


def shot_line(c, s):
    """One or two centred lines on a backdrop, words blurring in."""
    bg = s.get("bg", "bg_wash")
    im = backdrop(bg, c.lt)
    dark = is_dark(bg)
    col = (255, 255, 255) if dark else G.ink
    acc = G.sky if dark else G.blue
    lines = s["lines"]
    f = F("sans_medium", s.get("size", 64))
    for i, ln in enumerate(lines):
        place(im, line_layer(ln, f, col, acc, c.lt - 0.1 - i * 0.35), c.H * s.get("y", 0.5) + (i - (len(lines) - 1) / 2) * f.size * 1.25)
    if s.get("blur_out") and c.lt > c.dur - 0.35:
        return np.asarray(im.filter(ImageFilter.GaussianBlur((c.lt - (c.dur - 0.35)) / 0.35 * 14)).convert("RGB")).copy()
    return arr(im)


def shot_meet(c, s):
    """A huge word filling the frame, pulling back with motion blur, then collapsing into 'word [logo] Name'."""
    im = backdrop(s.get("bg", "bg_sky"), c.lt)
    big, small = s.get("word", "Meet"), s.get("name", "")
    t_col = s.get("collapse_at", 1.1)
    p_in = ease_out(min(1, c.lt / 0.6))
    col = s.get("color", "ink")
    rgb = G.ink if col == "ink" else (255, 255, 255)
    if c.lt < t_col:
        size = int(lerp(620, 440, p_in))
        f = F("sans_medium", size)
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((c.W / 2, c.H / 2 + size * 0.3), big, font=f, fill=rgb + (255,), anchor="ms")
        blur = (1 - p_in) * 26
        if blur > 0.5:
            lay = lay.filter(ImageFilter.GaussianBlur(blur))
        im.alpha_composite(lay)
    else:
        p = ease_in_out(min(1, (c.lt - t_col) / 0.5))
        f = F("sans_medium", int(lerp(440, 96, p)))
        fl = F("sans_medium", 96)
        lg_s = 96
        total = fl.getlength(big + " ") + lg_s + 24 + fl.getlength(small)
        x0 = c.W / 2 - total / 2
        d = ImageDraw.Draw(im)
        bx = lerp(c.W / 2 - f.getlength(big) / 2, x0, p)
        d.text((bx, c.H / 2 + f.size * 0.33), big, font=f, fill=rgb, anchor="ls")
        if p > 0.4:
            q = ease_out(min(1, (p - 0.4) / 0.6))
            lx = x0 + fl.getlength(big + " ")
            tile = Image.new("RGBA", (lg_s, lg_s), (0, 0, 0, 0))
            ImageDraw.Draw(tile).rounded_rectangle((0, 0, lg_s - 1, lg_s - 1), 22, fill=(255, 255, 255, 255))
            lg = png("logo").resize((int(lg_s * 0.72),) * 2, Image.LANCZOS)
            tile.alpha_composite(lg, ((lg_s - lg.width) // 2, (lg_s - lg.height) // 2))
            im.alpha_composite(fade(tile, q), (int(lx), int(c.H / 2 - lg_s / 2 + (1 - q) * 20)))
            lay = line_layer(small, fl, rgb, rgb, c.lt - t_col - 0.35, max_w=c.W)
            bb = lay.getbbox()
            if bb:
                im.alpha_composite(lay, (int(lx + lg_s + 24 - bb[0]), 0))
    return arr(im)


def console_img(c, s):
    """Live enterprise-console component (framesmith.console) animated by the shot's local time."""
    from framesmith import console as _console
    data = s.get("data")
    if isinstance(data, str) or data is None:
        pool = G.cache("console_data", lambda: json.load(open(os.path.join(G.base, G.b.get("console_data", "console.json")))))
        data = pool[data or s["component"]]
    return _console.render(s["component"], data, c.lt - s.get("delay", 0.3))


def shot_tilt(c, s):
    """UI panel in perspective over a backdrop, swinging between two poses; optional line above."""
    im = backdrop(s.get("bg", "bg_sky"), c.lt)
    img = console_img(c, s) if s.get("component") else panel(s["media"])
    p = ease_in_out(c.p(0, c.dur))
    a = dict(rx=18, ry=-22, rz=4, scale=0.9, cx=0.52, cy=0.56)
    a.update(s.get("from", {}))
    b = dict(rx=10, ry=-8, rz=0, scale=1.06, cx=0.5, cy=0.54)
    b.update(s.get("to", {}))
    q = {k: lerp(a[k], b.get(k, a[k]), p) for k in a}
    base = min(c.W * s.get("width", 0.74) / img.width, c.H * 0.7 / img.height)
    quad = project(img.width * base, img.height * base, q["rx"], q["ry"], q["rz"], q["scale"], q["cx"] * c.W, q["cy"] * c.H)
    im.alpha_composite(warp(img, quad, im.size))
    if s.get("leak", True):                                # a soft diagonal light leak sweeping across
        lk = Image.new("L", im.size, 0)
        x = lerp(-c.W * 0.3, c.W * 1.1, c.lt / c.dur)
        ImageDraw.Draw(lk).polygon([(x, 0), (x + 220, 0), (x - 380, c.H), (x - 600, c.H)], fill=70)
        im.paste(Image.new("RGB", im.size, (255, 255, 255)), (0, 0), lk.filter(ImageFilter.GaussianBlur(60)))
    if s.get("line"):
        dark = is_dark(s.get("bg", "bg_sky"))
        place(im, line_layer(s["line"], F("sans_medium", 52), (255, 255, 255) if dark else G.ink, G.sky if dark else G.blue, c.lt - 0.2),
              c.H * 0.12)
    return arr(im)


def shot_split(c, s):
    """Left: a UI panel with one row lit; a wire runs to a dark terminal on the right that types its steps."""
    im = backdrop(s.get("bg", "bg_wash"), c.lt)
    W, H = c.W, c.H
    img = panel(s["media"])
    k = W * 0.46 / img.width
    quad = project(img.width * k, img.height * k, 6, 16, 0, 1.0, W * 0.27, H * 0.52)
    im.alpha_composite(warp(img, quad, im.size))
    rf = s.get("row", 0.5)                                  # lit row, as a fraction of panel height
    L = np.array(quad[0]) * (1 - rf) + np.array(quad[3]) * rf
    R = np.array(quad[1]) * (1 - rf) + np.array(quad[2]) * rf
    d = ImageDraw.Draw(im)
    lp = ease_out(min(1, c.lt / 0.4))
    d.line([tuple(L), tuple(R)], fill=G.blue, width=3)
    tx0, ty0, tx1, ty1 = W * 0.56, H * 0.2, W * 0.94, H * 0.8
    term = Image.new("RGBA", im.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(term)
    td.rectangle((tx0, ty0, tx1, ty1), fill=(6, 8, 14, int(235 * lp)))
    im.alpha_composite(term)
    d = ImageDraw.Draw(im)
    wp = ease_out(min(1, max(0, (c.lt - 0.3) / 0.4)))
    ex = lerp(R[0], tx0, wp)
    d.line([tuple(R), (ex, R[1])], fill=G.blue, width=3)
    if wp > 0.95:
        cx, cy = tx0, R[1]
        d.polygon([(cx, cy - 12), (cx + 12, cy), (cx, cy + 12), (cx - 12, cy)], fill=G.blue)
    fm = F("mono", 30)
    y = ty0 + 70
    for i, ln in enumerate(s["lines"]):
        t0 = 0.8 + i * s.get("step", 0.7)
        if c.lt < t0:
            break
        part = typed(ln["t"], (c.lt - t0) / 0.4)
        bx = tx0 + 50
        if ln.get("check"):
            d.rectangle((bx, y - 14, bx + 26, y + 12), outline=(230, 236, 250), width=2)
            if len(part) == len(ln["t"]):
                d.line((bx + 5, y, bx + 11, y + 6, bx + 21, y - 8), fill=(230, 236, 250), width=3)
            bx += 44
        text(d, (bx, y), part, fm, (230, 236, 250) if not ln.get("dim") else (130, 140, 165), 0, "lm", max_w=tx1 - bx - 40)
        if ln.get("bar"):
            bp = ease_in_out(min(1, max(0, (c.lt - t0 - 0.2) / 1.2)))
            d.rectangle((tx0 + 50, y + 34, tx1 - 50, y + 40), fill=(40, 46, 66))
            d.rectangle((tx0 + 50, y + 34, lerp(tx0 + 50, tx1 - 50, bp), y + 40), fill=G.blue)
            y += 40
        y += 74
    return arr(im)


def shot_brackets(c, s):
    """A word inside corner brackets: the brackets close in, hold, then collapse to an empty [ ]."""
    bg = s.get("bg", "bg_navy")
    im = backdrop(bg, c.lt)
    f = F("sans_medium", s.get("size", 110))
    word = s["word"]
    w = text_width(word, f)
    open_p = ease_out(min(1, c.lt / 0.45))
    t_col = c.dur - 0.7
    col_p = ease_in_out(min(1, max(0, (c.lt - t_col) / 0.45)))
    half = lerp(lerp(c.W / 2, w / 2 + 70, open_p), 34, col_p)
    hgt = lerp(f.size * 0.9, 60, col_p)
    d = ImageDraw.Draw(im)
    acc = G.sky if is_dark(bg) else G.blue
    for sgn in (-1, 1):
        x = c.W / 2 + sgn * half
        d.line((x, c.H / 2 - hgt, x, c.H / 2 + hgt), fill=acc, width=6)
        d.line((x, c.H / 2 - hgt, x - sgn * 26, c.H / 2 - hgt), fill=acc, width=6)
        d.line((x, c.H / 2 + hgt, x - sgn * 26, c.H / 2 + hgt), fill=acc, width=6)
    if col_p < 1:
        lay = line_layer("*" + " *".join(word.split(" ")), f, acc, acc, c.lt - 0.2)
        if col_p > 0:
            lay = fade(lay.filter(ImageFilter.GaussianBlur(col_p * 12)), 1 - col_p)
        place(im, lay, c.H / 2)
    if s.get("above") and col_p < 1:
        place(im, line_layer(s["above"], F("sans_medium", 44), (255, 255, 255) if is_dark(bg) else G.ink, acc, c.lt), c.H * 0.3)
    return arr(im)


def shot_wide(c, s):
    """An extra-wide word streaking in horizontally with motion blur, then settling."""
    bg = s.get("bg", "bg_navy")
    im = backdrop(bg, c.lt)
    f = F("sans_medium", s.get("size", 150))
    word = s["word"]
    p = ease_out(min(1, c.lt / 0.55))
    stretch = lerp(2.4, s.get("stretch", 1.35), p)
    w = int(text_width(word, f) + 40)
    hgt = int(f.size * 1.4)
    m = Image.new("L", (w, hgt), 0)
    ImageDraw.Draw(m).text((20, f.size * 1.08), word, font=f, fill=255, anchor="ls")
    m = m.resize((int(w * stretch), hgt), Image.LANCZOS)
    blur = (1 - p) * 60
    if blur > 1:                                           # horizontal motion blur (box filter along x)
        mb = np.asarray(m, np.float32)
        kx = int(blur)
        mb = np.cumsum(np.pad(mb, ((0, 0), (kx, kx))), axis=1)
        mb = (mb[:, 2 * kx:] - mb[:, :-2 * kx]) / (2 * kx)
        m = Image.fromarray(np.clip(mb, 0, 255).astype(np.uint8))
    x = c.W / 2 - m.width / 2 + (1 - p) * 500
    col = (255, 255, 255) if is_dark(bg) else G.ink
    im.paste(Image.new("RGB", m.size, col), (int(x), int(c.H / 2 - hgt * 0.55)), m)
    if c.lt > c.dur - 0.4:
        q = (c.lt - (c.dur - 0.4)) / 0.4
        return np.asarray(im.filter(ImageFilter.GaussianBlur(q * 16)).convert("RGB")).copy()
    return arr(im)


def shot_form(c, s):
    """Camera flying low over oversized form fields: labels, soft white fields, values typing in."""
    im = backdrop(s.get("bg", "bg_wash"), c.lt)
    fields = s["fields"]
    page = Image.new("RGBA", (1600, 240 * len(fields) + 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(page)
    fl, fv = F("sans_medium", 64), F("sans", 60)
    for i, fd in enumerate(fields):
        y = 60 + i * 240
        d.text((40, y + 50), fd["label"], font=fl, fill=G.ink + (255,), anchor="ls")
        d.rounded_rectangle((30, y + 80, 1560, y + 200), 30, fill=(255, 255, 255, 235), outline=(214, 224, 245, 255), width=3)
        t0 = fd.get("t", 0.4 + i * 0.9)
        val = typed(fd["value"], (c.lt - t0) / 0.6) if c.lt > t0 else ""
        text(d, (80, y + 142), val, F("mono", 54) if fd.get("mono") else fv, (70, 74, 90, 255), 0, "lm", max_w=1440, fit_to=fd["value"])
        if 0 < len(val) < len(fd["value"]) or (c.lt > t0 and (c.fi // 10) % 2 == 0 and len(val) == len(fd["value"]) and i == len(fields) - 1):
            cx = 80 + text_width(val, F("mono", 54) if fd.get("mono") else fv) + 4
            d.rectangle((cx, y + 112, cx + 3, y + 170), fill=G.blue + (255,))
    p = ease_in_out(c.p(0, c.dur))
    k = lerp(1.25, 0.95, p)
    quad = project(page.width * k, page.height * k, lerp(28, 14, p), lerp(-10, -4, p), 0, 1.0, lerp(c.W * 0.62, c.W * 0.55, p),
                   lerp(c.H * 0.72, c.H * 0.5, p))
    im.alpha_composite(warp(page, quad, im.size, shadow=0.0))
    return arr(im)


def shot_logo(c, s):
    im = backdrop(s.get("bg", "bg_wash"), c.lt)
    p = ease_out(min(1, c.lt / 0.5))
    lg_s = 130
    f = F("sans_medium", 100)
    name = s["name"]
    total = lg_s + 30 + f.getlength(name)
    x0 = c.W / 2 - total / 2
    tile = Image.new("RGBA", (lg_s, lg_s), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, lg_s - 1, lg_s - 1), 30, fill=(255, 255, 255, 255))
    lg = png("logo").resize((int(lg_s * 0.72),) * 2, Image.LANCZOS)
    tile.alpha_composite(lg, ((lg_s - lg.width) // 2, (lg_s - lg.height) // 2))
    im.alpha_composite(fade(tile, p), (int(x0), int(c.H / 2 - lg_s / 2)))
    lay = line_layer(name, f, G.ink, G.ink, c.lt - 0.25, max_w=c.W)
    bb = lay.getbbox()
    if bb:
        im.alpha_composite(lay, (int(x0 + lg_s + 30 - bb[0]), 0))
    return arr(im)


# ---- icon shots (shared with glass-saas-promo), adapted to this template's backdrops
from framesmith.media import fetch_icons, icon, is_light_mark, rasterize_svg
import urllib.request


def canvas():
    return backdrop(getattr(G, "_icon_bg", "bg_wash"), 0)


def draw_line(im, line, lt, f, cy, stagger=0.07):
    dark = is_dark(getattr(G, "_icon_bg", "bg_wash"))
    place(im, line_layer(line, f, (255, 255, 255) if dark else G.ink, G.sky if dark else G.blue, lt, stagger), cy)


def with_bg(fn):
    def run(c, s):
        G._icon_bg = s.get("bg", "bg_wash")
        return fn(c, s)
    return run


def icon_ref(ref, size, color=None):
    """'lucide:name' (tinted line icon) or 'brand:slug' (thesvg mark, real colours)."""
    kind, name = ref.split(":", 1)
    if kind == "lucide":
        return icon(os.path.join(G.assets, "lucide", name + ".svg"), int(size), tuple(color or G.ink))
    im = icon(os.path.join(G.assets, "icons", name + ".svg"), int(size))
    return icon(os.path.join(G.assets, "icons", name + ".svg"), int(size), G.ink) if is_light_mark(im) else im


def glass_tile(size, inner, lift=0.0):
    """A white rounded tile with a soft blue shadow holding an icon (app-icon style, not a pill)."""
    pad = int(size * 0.3)
    t = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    sh = Image.new("L", t.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + size * 0.08, pad + size, pad + size * 1.08), int(size * 0.26), fill=90)
    t.paste(G.blue + (255,), (0, 0), sh.filter(ImageFilter.GaussianBlur(size * 0.12)))
    ImageDraw.Draw(t).rounded_rectangle((pad, pad, pad + size, pad + size), int(size * 0.26), fill=(255, 255, 255, 255),
                                        outline=(222, 226, 246, 255), width=2)
    t.alpha_composite(inner, (pad + (size - inner.width) // 2, pad + (size - inner.height) // 2))
    return t


def shot_pillars(c, s):
    """Governance pillars: a row of icon tiles rising in with labels and a one-line detail each."""
    im = canvas()
    if s.get("words"):
        draw_line(im, s["words"], c.lt - 0.1, F("sans_medium", s.get("size", 60)), c.H * 0.2)
    items = s["items"]
    n = len(items)
    cell = min(280, (c.W - 200) / n)
    x0 = c.W / 2 - cell * n / 2
    d = ImageDraw.Draw(im)
    for k, it in enumerate(items):
        p = ease_out(min(1, max(0, (c.lt - 0.4 - k * 0.12) / 0.4)))
        if p <= 0:
            continue
        ts = 118
        ic = icon_ref(it["icon"], ts * 0.46, G.blue)
        tile = glass_tile(ts, ic)
        cx = x0 + cell * (k + 0.5)
        y = c.H * 0.5 + (1 - p) * 40 + math.sin(c.lt * 1.6 + k) * 4
        im.alpha_composite(fade(tile, p), (int(cx - tile.width / 2), int(y - tile.height / 2)))
        d = ImageDraw.Draw(im)
        text(d, (cx, y + 110), it["label"], F("sans_medium", 32), tuple(int(lerp(bg, v, p)) for bg, v in zip(G.bg, G.ink)), 0, "mm",
             max_w=cell - 16)
        if it.get("sub"):
            text(d, (cx, y + 150), it["sub"], F("sans", 22), tuple(int(lerp(bg, v, p)) for bg, v in zip(G.bg, G.muted)), 0, "mm",
                 max_w=cell - 16)
    return arr(im)


def shot_flow(c, s):
    """A pipeline of icon tiles on a line; a glowing pulse travels through, lighting each step in turn."""
    im = canvas()
    if s.get("words"):
        draw_line(im, s["words"], c.lt - 0.1, F("sans_medium", s.get("size", 60)), c.H * 0.2)
    steps = s["steps"]
    n = len(steps)
    x0, x1, y = c.W * 0.14, c.W * 0.86, c.H * 0.52
    d = ImageDraw.Draw(im)
    lp = ease_out(min(1, c.lt / 0.6))
    d.line((x0, y, lerp(x0, x1, lp), y), fill=(206, 212, 240), width=4)
    head = (c.lt - 0.6) / max(0.1, c.dur - 1.2)
    hx = lerp(x0, x1, max(0, min(1, head)))
    if 0 < head < 1:
        g = Image.new("L", im.size, 0)
        ImageDraw.Draw(g).ellipse((hx - 40, y - 40, hx + 40, y + 40), fill=255)
        im.paste(Image.new("RGB", im.size, G.blue), (0, 0), g.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(im)
        d.line((x0, y, hx, y), fill=G.blue, width=4)
    elif head >= 1:
        d.line((x0, y, x1, y), fill=G.blue, width=4)
    for k, st in enumerate(steps):
        cx = lerp(x0, x1, k / max(1, n - 1))
        p = ease_out(min(1, max(0, (c.lt - 0.2 - k * 0.1) / 0.4)))
        lit = hx >= cx - 1 and head > 0
        ic = icon_ref(st["icon"], 50, G.blue if lit else G.muted)
        tile = glass_tile(104, ic)
        im.alpha_composite(fade(tile, p), (int(cx - tile.width / 2), int(y - tile.height / 2)))
        d = ImageDraw.Draw(im)
        text(d, (cx, y + 100), st["label"], F("sans_medium", 32), G.ink if lit else G.muted, 0, "mm", max_w=260)
        if st.get("sub"):
            text(d, (cx, y + 140), st["sub"], F("sans", 22), G.muted, 0, "mm", max_w=260)
    return arr(im)


def shot_orbit(c, s):
    """The logo on a white tile at the centre, brand icons popping onto two slowly counter-rotating rings."""
    im = canvas()
    cx, cy = c.W / 2, c.H * 0.5
    d = ImageDraw.Draw(im)
    rings = s["rings"]
    radii = s.get("radii", [250, 400])
    for r in radii:
        rp = ease_out(min(1, c.lt / 0.6))
        rr = r * lerp(0.8, 1, rp)
        d.ellipse((cx - rr * 1.35, cy - rr * 0.78, cx + rr * 1.35, cy + rr * 0.78), outline=(214, 220, 245), width=2)
    for ri, ring in enumerate(rings):
        r = radii[ri]
        spin = c.lt * (0.18 if ri % 2 == 0 else -0.13)
        for k, slug in enumerate(ring):
            t0 = 0.3 + ri * 0.4 + k * 0.06
            p = ease_out(min(1, max(0, (c.lt - t0) / 0.35)))
            if p <= 0:
                continue
            a = k / len(ring) * math.tau + spin + ri * 0.4
            x, y = cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 0.78
            ts = int(lerp(40, 84, p))
            tile = glass_tile(ts, icon_ref("brand:" + slug, ts * 0.58))
            im.alpha_composite(fade(tile, p), (int(x - tile.width / 2), int(y - tile.height / 2)))
    lp = ease_out(min(1, c.lt / 0.5))
    ls = int(150 * lerp(0.7, 1, lp))
    lg = png("logo").resize((int(ls * 0.66),) * 2, Image.LANCZOS)
    im.alpha_composite(fade(glass_tile(ls, lg), lp), (int(cx - ls * 0.8), int(cy - ls * 0.8)))
    if s.get("words"):
        draw_line(im, s["words"], c.lt - 0.6, F("sans_medium", s.get("size", 56)), c.H * 0.9)
    return arr(im)


SHOTS = {"type": shot_type, "line": shot_line, "meet": shot_meet, "tilt": shot_tilt, "split": shot_split,
         "brackets": shot_brackets, "wide": shot_wide, "form": shot_form, "logo": shot_logo,
         "pillars": with_bg(shot_pillars), "flow": with_bg(shot_flow), "orbit": with_bg(shot_orbit)}


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    scenes = []
    for k, s in enumerate(brief["shots"]):
        tr = Dissolve(s.get("tr_dur", 0.35), 16) if s.get("tr") == "blur" else None
        scenes.append(Scene(f"{k:02d}-{s['type']}", s["dur"], (lambda f, sh: lambda c: f(c, sh))(SHOTS[s["type"]], s), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["assets", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor-enterprise", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    if a.cmd == "assets":
        brief = json.load(open(a.brief))
        for m in generate_images(brief.get("assets", {}), os.path.join(base, brief.get("assets_dir", "assets")), names=a.args or None):
            print(m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep:
            print("  ✗", r)
        for r in overflow_report(warn=True):
            print("  ! warning:", r)
        blob = json.dumps(brief["shots"])
        trailing = re.findall(r'"(?:text|word|name|line|above|value|label)": "([^"]*[^.]\.)"', blob)
        trailing += [x for x in re.findall(r'"lines": \[([^\]]*)\]', blob) for x in re.findall(r'"([^"]+\.)"', x)]
        if trailing:
            print(f"  ! {len(trailing)} on-screen lines end with a period, e.g. {trailing[0]!r}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} shots")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 5, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "film.mp4"), a.audio))


if __name__ == "__main__":
    main()
