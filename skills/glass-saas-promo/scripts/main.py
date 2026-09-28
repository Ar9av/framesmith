#!/usr/bin/env python3
"""glass-saas-promo: a bright, music-driven SaaS promo in the frosted-glass style.

Lavender-white field, blue-to-violet gradients, gpt-image-2 glass objects, real product UI shown in
3D perspective (tilts, a tunnel of screens, scattered cards, a carousel), and a gradient stream that
sweeps a screen away and settles into a progress bar.

    python3 main.py assets|check|still|sheet|render --brief brief.json [times...] [--audio music.m4a]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith.media import fetch_icons, icon, is_light_mark, rasterize_svg
import urllib.request
from framesmith import Dissolve, Scene, Timeline, ease_in_out, ease_out, generate_images, h, hex2rgb, lerp, overflow_report, text
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width
from framesmith import ui

G = None


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.bg = c("bg", (248, 247, 254))
        self.ink = c("ink", (17, 17, 24))
        self.blue = c("blue", (47, 107, 255))
        self.violet = c("violet", (124, 108, 255))
        self.muted = c("muted", (150, 150, 168))
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
    return G.cache(("png", name), lambda: Image.open(os.path.join(G.assets, name if name.endswith((".png", ".jpg")) else name + ".png")).convert("RGBA"))


def canvas():
    """Lavender field with a soft white bloom in the middle."""
    def build():
        w, hh = G.W // 8, G.H // 8
        yy, xx = np.mgrid[0:hh, 0:w].astype(np.float32)
        d = np.sqrt(((xx / w - 0.5) / 0.6) ** 2 + ((yy / hh - 0.5) / 0.6) ** 2)
        a = np.clip(1 - d, 0, 1)[..., None] ** 2
        base = np.array(G.bg, np.float32) * (1 - a) + np.array((255, 255, 255), np.float32) * a
        return Image.fromarray(base.astype(np.uint8)).resize((G.W, G.H), Image.BICUBIC).convert("RGBA")
    return G.cache("canvas", build).copy()


def gradient(w, hgt, a=None, b=None, vertical=False):
    a, b = a or G.violet, b or G.blue
    t = np.linspace(0, 1, hgt if vertical else w, dtype=np.float32)
    row = np.array(a, np.float32)[None] * (1 - t[:, None]) + np.array(b, np.float32)[None] * t[:, None]
    g = np.repeat(row[:, None], w, 1) if vertical else np.repeat(row[None], hgt, 0)
    return g.astype(np.uint8)


def fade(im, p):
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * max(0.0, min(1.0, p))).astype(np.uint8)
    return Image.fromarray(a)


# ------------------------------------------------------------------ perspective
def project(w, hgt, rx, ry, rz, scale, cx, cy, fov=1400):
    """Corners of a w×h plane rotated in 3D (degrees) and projected; returns 4 (x, y) screen points."""
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


def _coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def warp(img, quad, size, glow=0.0):
    """Paste img (RGBA) onto a transparent canvas of `size` mapped to quad (TL, TR, BR, BL)."""
    w, hgt = img.size
    c = _coeffs(quad, [(0, 0), (w, 0), (w, hgt), (0, hgt)])
    out = img.transform(size, Image.PERSPECTIVE, c, Image.BICUBIC)
    if glow > 0:                                           # soft blue glow + rim, like the reference's lit screens
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).polygon(quad, fill=255)
        halo = Image.new("RGBA", size, G.blue + (0,))
        halo.putalpha(m.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.45 * glow)))
        base = Image.new("RGBA", size, (0, 0, 0, 0))
        base.alpha_composite(halo)
        base.alpha_composite(out)
        ImageDraw.Draw(base).line(quad + [quad[0]], fill=(120, 150, 255, int(200 * glow)), width=3)
        out = base
    return out


def panel(name, radius=18):
    """A UI image with rounded corners and a thin border."""
    def build():
        im = png(name).convert("RGBA")
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
        im.putalpha(m)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, outline=(214, 218, 240, 255), width=3)
        return im
    return G.cache(("panel", name, radius), build)


def soft_veil(im, box, strength=0.92, blur=60):
    """Clear a soft area of the field for a caption: blur the mask, not the colour (no grey halo)."""
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse(box, fill=int(255 * strength))
    im.paste(Image.new("RGB", im.size, G.bg), (0, 0), m.filter(ImageFilter.GaussianBlur(blur)))


def interp(a, b, p):
    return {k: lerp(a[k], b.get(k, a[k]), p) for k in a}


# ------------------------------------------------------------------ kinetic words
def token_w(tok, f):
    if tok.startswith("{obj:"):
        return f.size * 1.9
    return text_width(tok.lstrip("*"), f)


def draw_line(im, line, lt, f, cy, stagger=0.08):
    """One centred line: plain words ink, *words blue gradient, {obj:name} glass object inline. Blur-in per token."""
    toks = line.split(" ")
    sp = f.getlength(" ")
    total = sum(token_w(t, f) for t in toks) + sp * (len(toks) - 1)
    if total > G.W - 200:
        SHRINKS.append((line, (G.W - 200) / total))
        f = F("sans_medium", int(f.size * (G.W - 200) / total))
        total = sum(token_w(t, f) for t in toks) + sp * (len(toks) - 1)
    x = G.W / 2 - total / 2
    for k, tk in enumerate(toks):
        p = ease_out(min(1, max(0, (lt - k * stagger) / 0.35)))
        w = token_w(tk, f)
        if p > 0:
            if tk.startswith("{obj:"):
                ob = png(tk[5:-1])
                s = int(f.size * 1.9 * lerp(0.6, 1, p))
                o = ob.resize((s, s), Image.LANCZOS)
                wob = math.sin(lt * 2.2 + k) * 4
                im.alpha_composite(fade(o, p), (int(x + (w - s) / 2), int(cy - s / 2 + wob)))
            else:
                word = tk.lstrip("*")
                m = Image.new("L", (int(w) + 40, int(f.size * 1.6)), 0)
                ImageDraw.Draw(m).text((20, f.size * 1.15), word, font=f, fill=255, anchor="ls")
                if p < 1:
                    m = m.filter(ImageFilter.GaussianBlur((1 - p) * 10)).point(lambda v: int(v * p))
                fill = Image.fromarray(gradient(m.width, m.height)) if tk.startswith("*") else Image.new("RGB", m.size, G.ink)
                im.paste(fill, (int(x - 20), int(cy - f.size * 1.15 + f.size * 0.35 + (1 - p) * 18)), m)
        x += w + sp


def shot_words(c, s):
    """A sequence of lines that swap on the beat (old line blurs out as the next rises in)."""
    im = canvas()
    f = F("sans_medium", s.get("size", 72))
    seq = s["seq"]
    for k, item in enumerate(seq):
        t0 = item.get("t", k * c.dur / len(seq))
        t1 = seq[k + 1].get("t", (k + 1) * c.dur / len(seq)) if k + 1 < len(seq) else c.dur + 1
        if t0 <= c.lt < t1:
            lt = c.lt - t0
            layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
            draw_line(layer, item["line"], lt, f, c.H * s.get("y", 0.5))
            out_p = min(1, max(0, (c.lt - (t1 - 0.18)) / 0.18)) if k + 1 < len(seq) else 0
            if out_p > 0:
                layer = fade(layer.filter(ImageFilter.GaussianBlur(out_p * 10)), 1 - out_p)
            im.alpha_composite(layer)
    return arr(im)


# ------------------------------------------------------------------ UI in 3D
def cursor(im, x, y, click=0.0, s=2.2):
    d = ImageDraw.Draw(im)
    if 0 < click < 1:
        r = 12 + 26 * click
        d.ellipse((x - r, y - r, x + r, y + r), outline=G.blue, width=max(1, int(4 * (1 - click))))
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.6), (9.6, 18.6), (6.8, 12.2), (12.4, 12.2)]
    P = [(x + px * s, y + py * s) for px, py in pts]
    d.polygon(P, fill=(255, 255, 255))
    d.line(P + [P[0]], fill=(20, 20, 30), width=2)


def console_img(c, s):
    """Live enterprise-console component (framesmith.console) animated by the shot's local time."""
    from framesmith import console as _console
    data = s.get("data")
    if isinstance(data, str) or data is None:
        pool = G.cache("console_data", lambda: json.load(open(os.path.join(G.base, G.b.get("console_data", "console.json")))))
        data = pool[data or s["component"]]
    return _console.render(s["component"], data, c.lt - s.get("delay", 0.3))


def shot_tilt(c, s):
    """A UI panel swinging from a steep 3D tilt to its resting pose; optional caption and cursor click."""
    im = canvas()
    img = console_img(c, s) if s.get("component") else panel(s["media"])
    p = ease_in_out(c.p(0, s.get("move", c.dur * 0.8)))
    a = dict(rx=30, ry=-24, rz=6, scale=0.7, cx=0.5, cy=0.6)
    a.update(s.get("from", {}))
    b = dict(rx=8, ry=-6, rz=0, scale=1.0, cx=0.5, cy=0.52)
    b.update(s.get("to", {}))
    q = interp(a, b, p)
    base = min(c.W * s.get("width", 0.72) / img.width, c.H * s.get("max_h", 0.72) / img.height)
    quad = project(img.width * base, img.height * base, q["rx"], q["ry"], q["rz"], q["scale"], q["cx"] * c.W, q["cy"] * c.H)
    im.alpha_composite(warp(img, quad, im.size, glow=s.get("glow", 0.0 if s.get("component") else 1.0)))
    if s.get("words"):
        draw_line(im, s["words"], c.lt - s.get("words_at", 0.3), F("sans_medium", s.get("size", 56)), c.H * 0.12)
    if s.get("click"):                                     # cursor lands on a point given in panel fractions
        cx_, cy_ = s["click"]["at"]
        u = (1 - cy_) * ((1 - cx_) * np.array(quad[0]) + cx_ * np.array(quad[1])) + cy_ * ((1 - cx_) * np.array(quad[3]) + cx_ * np.array(quad[2]))
        t0 = s["click"].get("t", c.dur * 0.6)
        mv = ease_in_out(min(1, max(0, (c.lt - (t0 - 0.7)) / 0.7)))
        x, y = lerp(c.W * 0.8, u[0], mv), lerp(c.H * 0.95, u[1], mv)
        if c.lt > t0 - 0.9:
            cursor(im, x, y, (c.lt - t0) / 0.4 if c.lt > t0 else 0)
    return arr(im)


def shot_tunnel(c, s):
    """Four UI panels facing inward around the centre, the camera pushing through; words in the middle."""
    im = canvas()
    push = lerp(0.8, 1.35, ease_in_out(c.p(0, c.dur)))
    spots = [  # (panel index, rx, ry, cx, cy)
        (0, 62, 0, 0.5, 0.12), (1, -62, 0, 0.5, 0.88), (2, 0, -62, 0.14, 0.5), (3, 0, 62, 0.86, 0.5)]
    for k, rx, ry, cx, cy in spots:
        img = panel(s["media"][k % len(s["media"])])
        base = c.W * 0.46 / img.width
        dx, dy = (cx - 0.5) * push, (cy - 0.5) * push
        quad = project(img.width * base, img.height * base, rx, ry, 0, push, c.W * (0.5 + dx), c.H * (0.5 + dy))
        im.alpha_composite(warp(img, quad, im.size, glow=0.6))
    soft_veil(im, (c.W * 0.3, c.H * 0.38, c.W * 0.7, c.H * 0.62))
    words_shot = dict(seq=s["seq"], size=s.get("size", 56))
    layer = arr_words(c, words_shot)
    im.alpha_composite(layer)
    return arr(im)


def arr_words(c, s):
    """Words layer on transparency (reuses shot_words' timing)."""
    layer = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
    f = F("sans_medium", s.get("size", 56))
    seq = s["seq"]
    for k, item in enumerate(seq):
        t0 = item.get("t", k * c.dur / len(seq))
        t1 = seq[k + 1].get("t", c.dur + 1) if k + 1 < len(seq) else c.dur + 1
        if t0 <= c.lt < t1:
            draw_line(layer, item["line"], c.lt - t0, f, c.H * 0.5)
    return layer


def shot_stream(c, s):
    """Signature transition: a blue gradient stream sweeps in from the left and settles into a progress bar
    that counts up (v0 → v1)."""
    im = canvas()
    W, H = c.W, c.H
    morph = ease_in_out(c.p(0, s.get("morph", 1.3)))
    if s.get("under"):                                     # the previous screen gets swept off to the left
        img = panel(s["under"])
        k = min(W * 0.6 / img.width, H * 0.66 / img.height)
        q = project(img.width * k, img.height * k, 10, lerp(-8, -55, morph), lerp(0, -8, morph), lerp(1, 1.2, morph),
                    lerp(W * 0.5, -W * 0.25, morph), H * 0.52)
        lay = warp(img, q, im.size, glow=1 - morph)
        if morph > 0:
            lay = lay.filter(ImageFilter.GaussianBlur(morph * 12))
        im.alpha_composite(fade(lay, 1 - morph * 0.9))
    bar_h, y = 70, H * 0.55
    bx0, bx1 = W * 0.22, W * 0.78
    v0, v1 = s.get("from", 82), s.get("to", 99)
    count = ease_out(c.p(s.get("morph", 1.3), c.dur - 0.3))
    v = lerp(v0, v1, count)
    fill_x = lerp(bx0, bx1, v / 100)
    # stream: thickness shrinks from full-screen flare to bar height as it travels
    xs = np.arange(W, dtype=np.float32)
    head = lerp(-W * 0.2, fill_x, morph)
    flare = lerp(H * 1.4, bar_h, morph)
    thick = np.where(xs <= head, bar_h + (flare - bar_h) * np.clip((head - xs) / (W * 0.45), 0, 1) ** 1.6 * (1 - morph) + 0, 0)
    thick = np.where((xs >= bx0 * morph) | (morph < 1), thick, 0)
    mask = np.zeros((H, W), np.uint8)
    yy = np.arange(H, dtype=np.float32)[:, None]
    mask[(np.abs(yy - y) <= thick[None] / 2) & (xs[None] <= head)] = 255
    if morph >= 1:
        mask[:, :int(bx0)] = 0
    m = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(lerp(24, 1.5, morph)))
    track = Image.new("RGBA", im.size, (0, 0, 0, 0))
    if morph > 0.7:                                        # the empty track the bar sits in
        ImageDraw.Draw(track).rounded_rectangle((bx0, y - bar_h / 2, bx1, y + bar_h / 2), bar_h / 2,
                                                fill=(255, 255, 255, int(255 * (morph - 0.7) / 0.3)))
        im.alpha_composite(track.filter(ImageFilter.GaussianBlur(0.5)))
    grad = Image.fromarray(gradient(W, H))
    if morph >= 1:                                         # final bar: rounded, clipped to the filled length
        mb = Image.new("L", im.size, 0)
        ImageDraw.Draw(mb).rounded_rectangle((bx0, y - bar_h / 2, fill_x, y + bar_h / 2), bar_h / 2, fill=255)
        m = mb
        glow = Image.new("RGBA", im.size, G.blue + (0,))
        glow.putalpha(mb.filter(ImageFilter.GaussianBlur(30)).point(lambda q: int(q * 0.35)))
        im.alpha_composite(glow)
    im.paste(grad, (0, 0), m)
    if morph > 0.85:
        p = ease_out(min(1, (c.lt - s.get("morph", 1.3) * 0.85) / 0.4))
        d = ImageDraw.Draw(im)
        fn, fd = F("sans_medium", 96), F("sans", 96)
        num = f"{v:.0f}"
        wn = fn.getlength(num)
        x = bx1 - fd.getlength("/100") - wn
        m2 = Image.new("L", im.size, 0)
        ImageDraw.Draw(m2).text((x, y - 90), num, font=fn, fill=int(255 * p), anchor="ls")
        im.paste(Image.fromarray(gradient(W, H)), (0, 0), m2)
        d.text((x + wn, y - 90), "/100", font=fd, fill=tuple(int(lerp(bb, mm, p)) for bb, mm in zip(G.bg, (190, 196, 225))), anchor="ls")
        if s.get("label"):
            text(d, (bx0, y + 90), s["label"], F("sans", 34), tuple(int(lerp(bb, mm, p)) for bb, mm in zip(G.bg, G.muted)), 0, "lm", max_w=bx1 - bx0)
    return arr(im)


def shot_done(c, s):
    """Glass check pops in, a word above it, confetti bursts outward."""
    im = canvas()
    p = ease_out(min(1, c.lt / 0.45))
    size = int(260 * lerp(0.5, 1, p) * (1 + 0.06 * math.sin(min(1, c.lt / 0.45) * math.pi)))
    ck = png(s.get("object", "glass_check")).resize((size, size), Image.LANCZOS)
    im.alpha_composite(fade(ck, p), (int(c.W / 2 - size / 2), int(c.H * 0.56 - size / 2)))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(7)
    cols = [G.blue, G.violet, (255, 150, 210), (120, 200, 255), (255, 200, 120)]
    for k in range(70):
        ang = rng.uniform(0, math.tau)
        sp = rng.uniform(300, 900)
        tt = max(0.0, c.lt - 0.2)
        if tt <= 0:
            break
        dist = sp * (1 - math.exp(-tt * 2.2))
        x = c.W / 2 + math.cos(ang) * dist
        y = c.H * 0.5 + math.sin(ang) * dist * 0.7 + 120 * tt ** 2
        r = rng.uniform(6, 14)
        rot = ang + tt * rng.uniform(4, 9)
        a = max(0, 1 - tt / 1.6)
        pts = [(x + r * math.cos(rot + q), y + r * 0.45 * math.sin(rot + q)) for q in (0, 1.9, math.pi, math.pi + 1.9)]
        d.polygon(pts, fill=tuple(int(lerp(bg, cc, a)) for bg, cc in zip(G.bg, cols[k % len(cols)])))
    draw_line(im, s.get("word", "*Done"), c.lt - 0.15, F("sans_medium", 88), c.H * 0.26)
    return arr(im)


def shot_hero(c, s):
    """A glass object (or the logo on a white tile) floating centre, words either side."""
    im = canvas()
    p = ease_out(min(1, c.lt / 0.5))
    size = int(s.get("object_size", 300) * lerp(0.6, 1, p))
    if s.get("object") == "logo":
        t = size
        tile = Image.new("RGBA", (t, t), (0, 0, 0, 0))
        sh = Image.new("L", (t, t), 0)
        ImageDraw.Draw(tile).rounded_rectangle((0, 0, t - 1, t - 1), int(t * 0.24), fill=(255, 255, 255, 255))
        lg = png("logo").resize((int(t * 0.66),) * 2, Image.LANCZOS)
        tile.alpha_composite(lg, ((t - lg.width) // 2, (t - lg.height) // 2))
        ob = tile
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle((c.W / 2 - t / 2, c.H / 2 - t / 2 + 20, c.W / 2 + t / 2, c.H / 2 + t / 2 + 20), int(t * 0.24),
                                               fill=G.blue + (70,))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    else:
        ob = png(s["object"]).resize((size, size), Image.LANCZOS)
    fl = math.sin(c.lt * 2.0) * 10
    rot = s.get("spin", 0) * (1 - p) * 90
    if rot:
        ob = ob.rotate(rot, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(fade(ob, p), (int(c.W / 2 - ob.width / 2), int(c.H / 2 - ob.height / 2 + fl)))
    f = F("sans_medium", s.get("size", 64))
    if s.get("left"):
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw_line(lay, s["left"], c.lt - 0.35, f, c.H / 2)
        bb = lay.getbbox()
        if bb:
            im.alpha_composite(lay, (int(c.W / 2 - size / 2 - 60 - bb[2]), 0))
    if s.get("right"):
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw_line(lay, s["right"], c.lt - 0.55, f, c.H / 2)
        bb = lay.getbbox()
        if bb:
            im.alpha_composite(lay, (int(c.W / 2 + size / 2 + 60 - bb[0]), 0))
    return arr(im)


def shot_carousel(c, s):
    """Panels sliding left in a slightly tilted row, fading at the edges."""
    im = canvas()
    items = s["media"]
    speed = s.get("speed", 380)
    gap = 60
    widths = []
    for name in items:
        img = panel(name)
        k = 420 / img.height
        widths.append(img.width * k)
    total = sum(widths) + gap * len(items)
    x = c.W * 0.55 - c.lt * speed
    for rep in range(2):
        for name, w in zip(items, widths):
            img = panel(name)
            k = 420 / img.height
            cx = x + w / 2
            if -w < cx < c.W + w:
                quad = project(img.width * k, img.height * k, 6, -10, 0, 1.0, cx, c.H * 0.54)
                im.alpha_composite(warp(img, quad, im.size, glow=0.4))
            x += w + gap
    edge = np.zeros((c.H, c.W), np.float32)
    xs = np.arange(c.W)
    edge[:] = np.clip(np.minimum(xs, c.W - xs) / 260, 0, 1)
    veil = Image.new("RGBA", im.size, G.bg + (0,))
    veil.putalpha(Image.fromarray(((1 - edge) * 255).astype(np.uint8)))
    im.alpha_composite(veil)
    if s.get("words"):
        draw_line(im, s["words"], c.lt - 0.2, F("sans_medium", 56), c.H * 0.13)
    return arr(im)


def shot_scatter(c, s):
    """Small tilted cards fly in from off-screen and orbit slowly around centre words."""
    im = canvas()
    spots = [(-0.32, -0.28, -14), (0.3, -0.3, 12), (-0.36, 0.26, 10), (0.34, 0.27, -12), (-0.05, -0.38, -6), (0.06, 0.39, 8)]
    items = s["media"]
    for k, (dx, dy, rz) in enumerate(spots):
        img = panel(items[k % len(items)])
        t0 = k * 0.08
        p = ease_out(min(1, max(0, (c.lt - t0) / 0.7)))
        kx = 460 / img.width
        drift = c.lt * 8
        cx = c.W * (0.5 + dx * lerp(1.9, 1, p)) + math.sin(c.lt + k) * drift * 0.3
        cy = c.H * (0.5 + dy * lerp(1.9, 1, p)) + math.cos(c.lt * 0.8 + k) * 6
        quad = project(img.width * kx, img.height * kx, 16 * (1 if dy < 0 else -1), 14 * (1 if dx < 0 else -1), rz + (1 - p) * 30, 1.0, cx, cy)
        im.alpha_composite(fade(warp(img, quad, im.size, glow=0.5), p))
    soft_veil(im, (c.W * 0.28, c.H * 0.4, c.W * 0.72, c.H * 0.6))
    draw_line(im, s["words"], c.lt - 0.4, F("sans_medium", s.get("size", 64)), c.H * 0.5)
    return arr(im)


def shot_sparkle(c, s):
    """The glass star pops and spins, then shrinks to sit after the last word as the words arrive."""
    im = canvas()
    words = s["words"].split("  ")
    t_words = s.get("words_at", 0.9)
    p_in = ease_out(min(1, c.lt / 0.4))
    f = F("sans_medium", s.get("size", 64))
    sp = f.getlength("   ")
    widths = [text_width(w.lstrip("*"), f) for w in words]
    star_s_small = 54
    total = sum(widths) + sp * (len(words) - 1) + 20 + star_s_small
    x0 = c.W / 2 - total / 2
    settle = ease_in_out(min(1, max(0, (c.lt - t_words) / 0.5)))
    star_big = 260
    ssz = int(lerp(star_big * lerp(0.4, 1, p_in), star_s_small, settle))
    sx = lerp(c.W / 2, x0 + total - star_s_small / 2, settle)
    sy = lerp(c.H / 2, c.H / 2 - 10, settle)
    st = png(s.get("object", "glass_star")).resize((ssz, ssz), Image.LANCZOS).rotate((1 - p_in) * 120 + c.lt * 10 * (1 - settle), resample=Image.BICUBIC)
    im.alpha_composite(fade(st, p_in), (int(sx - ssz / 2), int(sy - ssz / 2)))
    x = x0
    for k, w in enumerate(words):
        lt = c.lt - t_words - 0.25 - k * 0.35
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw_line(lay, w, lt, f, c.H / 2)
        bb = lay.getbbox()
        if bb:
            im.alpha_composite(lay, (int(x - bb[0]), 0))
        x += widths[k] + sp
    return arr(im)


def shot_logo(c, s):
    im = canvas()
    p = ease_out(min(1, c.lt / 0.5))
    lg = png("logo").resize((120, 120), Image.LANCZOS)
    f = F("sans_medium", 96)
    name = s.get("name", "")
    wn = f.getlength(name)
    total = 120 + 30 + wn
    x0 = c.W / 2 - total / 2
    im.alpha_composite(fade(lg, p), (int(x0), int(c.H / 2 - 60 + (1 - p) * 20)))
    ui.rise(im, (x0 + 150, c.H / 2 + 34), name, f, G.ink, ease_out(min(1, max(0, (c.lt - 0.2) / 0.4))), -1, "ls", max_w=c.W - 400)
    if s.get("url"):
        text(ImageDraw.Draw(im), (c.W / 2, c.H * 0.8), s["url"], F("sans", 30), G.muted, 0, "mm", max_w=c.W - 300)
    return arr(im)


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


SHOTS = {"words": shot_words, "tilt": shot_tilt, "tunnel": shot_tunnel, "stream": shot_stream, "done": shot_done,
         "hero": shot_hero, "carousel": shot_carousel, "scatter": shot_scatter, "sparkle": shot_sparkle, "logo": shot_logo,
         "pillars": shot_pillars, "flow": shot_flow, "orbit": shot_orbit}


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    scenes = []
    for k, s in enumerate(brief["shots"]):
        tr = Dissolve(s.get("tr_dur", 0.3), 14) if s.get("tr") == "blur" else None
        scenes.append(Scene(f"{k:02d}-{s['type']}", s["dur"], (lambda f, sh: lambda c: f(c, sh))(SHOTS[s["type"]], s), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["assets", "icons", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor-enterprise", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    if a.cmd == "icons":                                  # thesvg brand marks + lucide line icons used by the brief
        brief = json.load(open(a.brief))
        blob = json.dumps(brief["shots"])
        assets = os.path.join(base, brief.get("assets_dir", "assets"))
        brands = sorted(set(re.findall(r"brand:([a-z0-9-]+)", blob)) | {x for sh in brief["shots"] for ring in sh.get("rings", []) for x in ring})
        for m in fetch_icons(brands, os.path.join(assets, "icons")):
            print("brand:", m)
        lucide = sorted(set(re.findall(r"lucide:([a-z0-9-]+)", blob)))
        os.makedirs(os.path.join(assets, "lucide"), exist_ok=True)
        for n in lucide:
            pth = os.path.join(assets, "lucide", n + ".svg")
            if not os.path.exists(pth):
                open(pth, "wb").write(urllib.request.urlopen(f"https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{n}.svg", timeout=60).read())
            rasterize_svg(pth, pth[:-4] + ".png")
        print("lucide:", lucide)
        return
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
        trailing = [t for t in re.findall(r'"(?:line|words|word|left|right|label|name)": "([^"]+\.)"', blob)]
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
        print(tl.render(a.out or os.path.join(out, "promo.mp4"), a.audio))


if __name__ == "__main__":
    main()
