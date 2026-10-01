"""Abstract journey title film: a small glowing orb travels through a chain of worlds (data field, UI chamber,
wireframes that become a page, a room of panels, a bubble horizon, a vortex of cards, neon diamonds, a
construction grid that builds a sphere, a room of spheres, isometric panels, a pastel world of pillars,
ribbons and glass, a frosted sphere, pink frames, a portal of rings, an illustrated landscape, space) and lands
on the logo. Music-only: the score is synthesised in code.

    python3 main.py init my-film                 copy the Prismor example
    python3 main.py assets [name…]               generate the image set (gpt-image-2.5-sunburst by default)
    python3 main.py still 3 20 | sheet | render  [--brief path/brief.json]
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Dissolve, Scene, Timeline, cover, ease_in_out, ease_out, h, lerp
from framesmith.typography import F, text_width
from framesmith import motion as M

W, H = 1920, 1080
G = None


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        self.assets = os.path.join(base, brief.get("assets_dir", "assets"))
        self._c = {}

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


# ------------------------------------------------------------------ helpers
def cl(x):
    return max(0.0, min(1.0, x))


def ph(lt, a, b):
    return ease_in_out(cl((lt - a) / max(1e-6, b - a)))


def img(name):
    def load():
        for ext in (".png", ".jpg", ".webp"):
            p = os.path.join(G.assets, name + ext)
            if os.path.exists(p):
                return Image.open(p).convert("RGBA")
        raise FileNotFoundError(os.path.join(G.assets, name + ".png"))
    return G.cache(("img", name), load)


def trimmed(name):
    def mk():
        im = img(name)
        bb = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        return im.crop(bb) if bb else im
    return G.cache(("trim", name), mk)


def sprite(name, d):
    """A transparent asset scaled so its larger side is d px (cached in 6 px buckets)."""
    d = max(4, int(round(d / 6) * 6))
    def mk():
        im = trimmed(name)
        s = d / max(im.size)
        return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return G.cache(("spr", name, d), mk)


def put(im, name, cx, cy, d, alpha=1.0, blur=0.0, rot=0.0):
    if d < 3 or alpha <= 0.01:
        return
    s = sprite(name, d)
    if rot:
        s = s.rotate(rot, Image.BICUBIC, expand=True)
    if blur > 0.4:
        s = s.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.99:
        a = np.asarray(s).copy()
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        s = Image.fromarray(a)
    im.paste(s, (int(cx - s.width / 2), int(cy - s.height / 2)), s)


def _gauss():
    y, x = np.mgrid[-1:1:256j, -1:1:256j]
    return Image.fromarray((np.exp(-(x * x + y * y) * 4.0) * 255).astype(np.uint8))


def glow(im, cx, cy, r, col, a=1.0):
    """A soft additive-looking light blob (gaussian), r = radius in px."""
    if r < 2 or a <= 0:
        return
    m = G.cache("gauss", _gauss).resize((int(r * 2), int(r * 2)), Image.BILINEAR)
    m = m.point(lambda v: int(v * min(1.0, a)))
    im.paste(col + (255,) if len(col) == 3 else col, (int(cx - r), int(cy - r)), m)


def vgrad(top, bot, w=W, hh=H):
    def mk():
        t = np.linspace(0, 1, hh)[:, None, None]
        g = np.array(top, np.float32) * (1 - t) + np.array(bot, np.float32) * t
        return Image.fromarray(np.repeat(g, w, 1).astype(np.uint8))
    return G.cache(("vg", top, bot, w, hh), mk).copy()


def vignette(im, k=0.55):
    v = G.cache(("vig", k), lambda: Image.fromarray((np.clip(1 - k * (((np.mgrid[0:H, 0:W][1] - W / 2) / (W / 2)) ** 2 +
                                                                       ((np.mgrid[0:H, 0:W][0] - H / 2) / (H / 2)) ** 2) / 2, 0, 1) * 255).astype(np.uint8)))
    black = Image.new(im.mode, im.size, 0)
    return Image.composite(im, black, v)


def orb(im, x, y, r=34, a=1.0):
    glow(im, x, y, r * 4.2, (120, 170, 255), 0.55 * a)
    glow(im, x, y, r * 2.0, (220, 235, 255), 0.7 * a)
    put(im, "orb", x, y, r * 2.2, a)


def zoom(im, z, fx=W / 2, fy=H / 2):
    if abs(z - 1) < 1e-3:
        return im
    box = (fx - fx / z, fy - fy / z, fx + (W - fx) / z, fy + (H - fy) / z)
    return im.transform((W, H), Image.EXTENT, box, Image.BICUBIC)


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def flash(a, p, col=(255, 255, 255)):
    if p <= 0:
        return a
    return (a.astype(np.float32) * (1 - p) + np.array(col, np.float32) * p).astype(np.uint8)


INDIGO = [(58, 58, 196), (84, 76, 232), (48, 92, 220), (70, 110, 240), (40, 44, 150), (100, 96, 255)]


# ------------------------------------------------------------------ 1 data field
def s_data(c):
    lt = c.lt
    im = Image.new("RGB", (W, H), (7, 7, 16))
    d = ImageDraw.Draw(im, "RGBA")
    band = H * (0.02 + 0.48 * ph(lt, 0.3, 3.4))
    dens = ph(lt, 0.1, 2.4)
    col_in = ph(lt, c.dur - 0.9, c.dur)
    for gx in range(0, W, 160):
        d.line((gx, H / 2 - band, gx, H / 2 + band), fill=(40, 40, 80, int(40 * dens)))
    R = G.cache("datarng", lambda: np.random.default_rng(11).random((2000, 9)))
    for i in range(1300):
        rr = R[i]
        row = int(rr[0] * 70)
        y = H / 2 + (row - 35) * 15
        if abs(y - H / 2) > band or rr[1] > dens:
            continue
        L = 8 + rr[2] ** 2 * 120
        sp = (rr[3] - 0.3) * 260 * (1 if row % 2 else -0.6)
        x = (rr[4] * (W + 400) + sp * lt) % (W + 400) - 200
        r = rr[5]
        col = (232, 72, 104) if r > 0.965 else (120, 232, 130) if r > 0.94 else (80, 190, 240) if r > 0.86 else INDIGO[int(rr[6] * 6)]
        if col_in > 0:                                       # converge into the centre hex
            x = lerp(x, W / 2 + (x - W / 2) * 0.18, col_in)
            y = lerp(y, H / 2 + (y - H / 2) * 0.2, col_in)
            L *= 1 - 0.6 * col_in
        a = int(255 * (0.7 + 0.3 * rr[7]))
        if r > 0.94 and L > 30:
            L = 9
        d.rounded_rectangle((x, y - 3, x + L, y + 3), 2, fill=col + (a,))
    if col_in > 0:
        cx, cy, R = W / 2, H / 2, 260 * (0.6 + 0.4 * col_in)
        pts = [(cx + R * 1.6 * math.cos(math.radians(a)), cy + R * 0.7 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
        d.polygon(pts, outline=(90, 90, 200, int(160 * col_in)))
        for p in pts:
            d.line((cx, cy, p[0], p[1]), fill=(70, 70, 170, int(70 * col_in)))
    return arr(vignette(im))


# ------------------------------------------------------------------ 2 chamber
def s_chamber(c):
    lt = c.lt
    im = vgrad((12, 12, 34), (8, 8, 20))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay, "RGBA")
    vx, vy = W / 2, H / 2 + 20
    for x0, x1 in ((0, 560), (W, W - 560)):
        d.polygon([(x0, vy - 420), (x1, vy - 70), (x1, vy + 70), (x0, vy + 420)], fill=(50, 90, 200, 60))
    lay = lay.filter(ImageFilter.GaussianBlur(40))
    im.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(im, "RGBA")
    for x in (640, W - 640):
        d.line((x, 0, x, H), fill=(70, 80, 200, 90), width=2)
    for k in range(-6, 7):
        d.line((vx, vy, vx + k * 400, H), fill=(60, 60, 150, 35))
    q = M.spring(lt - 0.1, 170, 26)
    cw, chh = 780 * lerp(0.82, 1, q), 390 * lerp(0.82, 1, q)
    x0, y0 = W / 2 - cw / 2, H / 2 - chh / 2
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + chh), 16, fill=(18, 18, 40, 240), outline=(60, 50, 110, 255), width=2)
    s = cw / 520
    bars = [((80, 18, 250, 42), (196, 66, 96)), ((250, 62, 470, 78), (52, 56, 150)), ((80, 92, 250, 116), (196, 66, 96))]
    for k, ((a, b, e, f), col) in enumerate(bars):
        w = cl((lt - 0.4 - k * 0.2) / 0.4)
        d.rounded_rectangle((x0 + a * s, y0 + b * s, x0 + (a + (e - a) * w) * s, y0 + f * s), 6, fill=col + (255,)) if w > 0 else None
    d.rectangle((x0 + 52 * s, y0 + 96 * s, x0 + 66 * s, y0 + 110 * s), fill=(232, 72, 104, 255))
    d.line((x0 + 40 * s, y0 + 160 * s, x0 + 130 * s, y0 + 160 * s), fill=(60, 70, 160, 255), width=3)
    d.rounded_rectangle((x0 + 380 * s, y0 + 200 * s, x0 + 480 * s, y0 + 232 * s), 14, fill=(40, 46, 140, 255))
    d.line((x0 + 425 * s, y0 + 210 * s, x0 + 433 * s, y0 + 216 * s, x0 + 425 * s, y0 + 222 * s), fill=(200, 200, 255, 255), width=2)
    return arr(zoom(vignette(im), 1 + 0.06 * ph(lt, 0, c.dur)))


# ------------------------------------------------------------------ 3 wireframes → page
RECTS = [(380, 210, 860, 470), (980, 250, 1560, 520), (300, 560, 900, 930), (1000, 600, 1600, 900)]
PERI = (96, 110, 240)


def page_img():
    def mk():
        im = Image.new("RGB", (W, H), (52, 62, 226))
        d = ImageDraw.Draw(im, "RGBA")
        d.rectangle((0, 0, W, 120), fill=(40, 46, 210, 255))
        d.rounded_rectangle((90, 40, 230, 80), 20, fill=(90, 150, 255, 255))
        for x in (1180, 1400):
            d.line((x, 62, x + 150, 62), fill=(110, 120, 255, 255), width=3)
        d.rectangle((230, 230, 900, 560), fill=(46, 54, 200, 255))
        d.pieslice((330, 330, 800, 800), 180, 360, fill=(38, 40, 160, 255))
        g = Image.new("RGBA", (720, 90))
        ga = np.zeros((90, 720, 4), np.uint8)
        xs = np.linspace(0, 1, 720)[None, :]
        ga[..., 0] = (120 + 120 * xs).astype(np.uint8); ga[..., 1] = (120 + 120 * xs).astype(np.uint8); ga[..., 2] = 255; ga[..., 3] = 255
        im.paste(Image.fromarray(ga), (1000, 360), Image.fromarray(ga))
        d.rounded_rectangle((1040, 395, 1110, 405), 4, fill=(220, 70, 100, 255))
        d.rounded_rectangle((1140, 395, 1240, 405), 4, fill=(40, 40, 140, 255))
        d.rounded_rectangle((1560, 395, 1620, 405), 4, fill=(120, 230, 120, 255))
        d.rounded_rectangle((1440, 420, 1680, 470), 25, fill=(90, 110, 250, 255))
        d.rectangle((1000, 500, 1320, 506), fill=(80, 90, 230, 255))
        d.rectangle((1000, 530, 1260, 536), fill=(80, 90, 230, 255))
        for x0 in (190, 1000):
            d.rectangle((x0, 640, x0 + 760, 1080), fill=(70, 80, 236, 255))
            d.rectangle((x0 + 690, 670, x0 + 720, 710), fill=(40, 40, 160, 255))
        d.polygon([(260, 1080), (480, 860), (620, 1000), (740, 900), (900, 1080)], fill=(60, 66, 210, 255))
        d.ellipse((1180, 820, 1520, 1160), fill=(60, 66, 210, 255))
        d.rectangle((1820, 140, 1832, 330), fill=(20, 20, 60, 255))
        return im
    return G.cache("page", mk)


def s_wire(c):
    lt = c.lt
    im = Image.new("RGB", (W, H), (10, 10, 26))
    d = ImageDraw.Draw(im, "RGBA")
    for k, (x0, y0, x1, y1) in enumerate(RECTS):
        p = cl((lt - k * 0.12) / 0.5)
        if p <= 0:
            continue
        xe = x0 + (x1 - x0) * p
        d.rectangle((x0, y0, xe, y1), outline=(80, 80, 200, 255), width=2)
        d.line((x0, y0, xe, y0 + (y1 - y0) * p), fill=(60, 60, 160, 200))
        d.line((x0, y1, xe, y1 - (y1 - y0) * p), fill=(60, 60, 160, 200))
        for (hx, hy), col in zip(((x0, y0), (x1, y0), (x0, y1), (x1, y1)), ((120, 230, 130), (232, 72, 104), (80, 190, 240), (120, 230, 130))):
            if p >= 1:
                d.polygon([(hx, hy - 7), (hx + 7, hy), (hx, hy + 7), (hx - 7, hy)], fill=col + (255,))
        fp = cl((lt - 0.9 - k * 0.18) / 0.35)
        if fp > 0:
            my = (y0 + y1) / 2
            d.rectangle((x0, my - (my - y0) * fp, x1, my + (y1 - my) * fp), fill=PERI + (255,))
    pp = ph(lt, 1.9, 2.6)
    if pp > 0:
        pg = zoom(page_img(), lerp(1.35, 1.0, ph(lt, 1.9, c.dur)))
        im = Image.blend(im, pg, pp)
    return arr(im)


# ------------------------------------------------------------------ 4 UI room
def panel_tex(k):
    def mk():
        w, hh = 420, 260
        im = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        base = [(28, 30, 90), (40, 46, 150), (22, 20, 60), (60, 70, 220), (34, 24, 70)][k % 5]
        d.rounded_rectangle((0, 0, w - 1, hh - 1), 10, fill=base + (235,), outline=(90, 90, 220, 120), width=2)
        d.rectangle((0, 0, w, 34), fill=tuple(min(255, v + 18) for v in base) + (255,))
        for j in range(4):
            col = [(232, 72, 104), (120, 232, 130), (120, 140, 255), (80, 190, 240)][(k + j) % 4]
            d.rounded_rectangle((24, 60 + j * 44, 24 + 80 + 220 * h(k, j), 72 + j * 44), 5, fill=col + (220,) if j < 2 else (90, 100, 220, 200))
        for j in range(3):
            d.rectangle((300 + j * 36, 200, 320 + j * 36, 220), fill=[(120, 232, 130), (120, 140, 255), (232, 72, 104)][(k + j) % 3] + (255,))
        return im
    return G.cache(("ptex", k), mk)


def s_room(c):
    lt = c.lt
    im = vgrad((18, 14, 46), (40, 12, 46))
    camz = lt * 1.8
    items = []
    for i in range(46):
        z = 1.5 + h(i, 11) * 12
        x = (h(i, 12) - 0.5) * 3.6
        y = (h(i, 13) - 0.5) * 2.0
        if i == 7:
            x, y, z = 0.05, 0.02, 7.8
        items.append((z, x, y, i))
    for z, x, y, i in sorted(items, reverse=True):
        dz = z - camz
        if dz < 0.35:
            continue
        s = 1.25 / dz
        cx, cy = W / 2 + x * W * 0.5 * s, H / 2 + y * H * 0.5 * s
        tex = panel_tex(3 if i == 7 else i)
        tw = int(tex.width * s * (1.4 if i == 7 else 1))
        if tw < 6 or tw > 5000:
            continue
        t2 = tex.resize((tw, int(tw * tex.height / tex.width)), Image.BILINEAR)
        a = cl((12 - dz) / 4) * cl((dz - 0.35) / 0.6)
        if dz > 6:
            t2 = t2.filter(ImageFilter.GaussianBlur(min(6, (dz - 6) * 1.2)))
        if a < 1:
            aa = np.asarray(t2).copy(); aa[..., 3] = (aa[..., 3] * a).astype(np.uint8); t2 = Image.fromarray(aa)
        im.paste(t2, (int(cx - t2.width / 2), int(cy - t2.height / 2)), t2)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(160):
        y = H * 0.72 + h(i, 21) * H * 0.28
        x = (h(i, 22) * W * 1.3 - lt * (300 + 500 * h(i, 23))) % (W + 200) - 100
        d.rectangle((x, y, x + 6 + 30 * h(i, 24), y + 3), fill=INDIGO[i % 6] + (200,))
    glow(im, W * 0.5, H * 1.05, 700, (150, 40, 120), 0.35)
    return arr(vignette(im))


# ------------------------------------------------------------------ 5 orb flight
def s_flight(c):
    lt = c.lt
    im = vgrad((14, 10, 30), (10, 8, 24))
    glow(im, W * 0.35, H * 0.5, 900, (110, 30, 80), 0.6)
    glow(im, W * 0.8, H * 0.3, 700, (40, 30, 120), 0.5)
    d = ImageDraw.Draw(im, "RGBA")
    if lt < 1.5:
        ox, oy = lerp(W * 0.42, W * 0.66, ease_out(cl(lt / 1.5))), H * 0.5
        for i in range(220):
            y = oy + (h(i, 31) - 0.5) * 70 * (1 - h(i, 32) * 0.5)
            back = h(i, 33) * 900
            x = ox - 60 - back + ((lt * 600 * (0.5 + h(i, 34))) % 120)
            L = 6 + 28 * h(i, 35)
            a = int(255 * (1 - back / 900))
            d.rectangle((x, y - 2, x + L, y + 2), fill=INDIGO[i % 6] + (a,) if h(i, 36) < 0.92 else (232, 72, 104, a))
        orb(im, ox, oy, 46)
    else:
        q = ph(lt, 1.5, c.dur)
        for i in range(26):
            x = W * (0.05 + 0.9 * h(i, 41))
            top = H * (0.55 + 0.4 * h(i, 42)) - q * 160 * h(i, 43)
            wv = 10 + 16 * h(i, 44)
            col = INDIGO[i % 6]
            d.rounded_rectangle((x, top, x + wv, H + 40), int(wv / 2), fill=col + (int(120 + 100 * h(i, 45)),))
            glow(im, x + wv / 2, top, wv * 2.4, (150, 160, 255), 0.5)
        orb(im, lerp(W * 0.5, W * 0.55, q), lerp(H * 0.62, H * 0.32, q), 26)
    return arr(vignette(im))


# ------------------------------------------------------------------ 6 horizon
def s_horizon(c):
    lt = c.lt
    hy = lerp(H * 0.36, H * 0.06, ph(lt, 1.6, c.dur))
    im = Image.new("RGB", (W, H), (8, 10, 34))
    sky = G.cache("sky", lambda: cover(img("bubbles_sky").convert("RGB"), W, H, 1.05))
    im.paste(sky.crop((0, int(H - hy), W, H)), (0, 0))
    water = vgrad((40, 60, 200), (8, 8, 28), W, H)
    im.paste(water.crop((0, 0, W, int(H - hy))), (0, int(hy)))
    glow(im, W / 2, hy + 160, 520, (150, 170, 255), 0.55)
    d = ImageDraw.Draw(im, "RGBA")
    pts = [(x, hy + 6 * math.sin(x / 90 + lt * 2.2)) for x in range(0, W + 20, 20)]
    d.line(pts, fill=(255, 255, 255, 230), width=5)
    for i in range(60):
        x = h(i, 51) * W
        y = hy + 40 + h(i, 52) * (H - hy)
        r = 4 + 12 * h(i, 53)
        glow(im, x, y - (lt * 40 * h(i, 54)) % 200, r * 2, (80, 100, 230), 0.45)
    rise = ph(lt, 0.2, 1.5)
    ox, oy = W / 2, lerp(hy + 260, hy - 160, rise)
    d.line((ox, hy + 280, ox, oy), fill=(160, 220, 255, 200), width=4)
    orb(im, ox, oy, 22)
    return arr(im)


# ------------------------------------------------------------------ 7 vortex
VORTEX_COLS = [((255, 120, 110), (255, 190, 140)), ((120, 110, 255), (170, 150, 255)), ((150, 230, 120), (240, 240, 140)),
               ((90, 150, 255), (150, 220, 255)), ((240, 110, 170), (255, 170, 120)), ((110, 90, 230), (90, 200, 240))]


def card_tex(k):
    def mk():
        w, hh = 640, 420
        xs = np.linspace(0, 1, w)[None, :, None]
        ys = np.linspace(0, 1, hh)[:, None, None]
        a, b = VORTEX_COLS[k % len(VORTEX_COLS)]
        t = xs * 0.7 + ys * 0.3
        g = np.array(a, np.float32) * (1 - t) + np.array(b, np.float32) * t
        im = Image.fromarray(g.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(im, "RGBA")
        for j in range(8):
            y = 40 + j * 22
            d.line((30, y, 30 + 200 * h(k, j), y), fill=(255, 255, 255, 60), width=3)
        return im
    return G.cache(("card", k), mk)


def s_vortex(c):
    lt = c.lt
    im = vgrad((24, 26, 90), (10, 10, 40))
    cxh, cyh = W * (0.5 + 0.08 * math.sin(lt * 0.6)), H * (0.5 + 0.06 * math.cos(lt * 0.5))
    n = 96
    fade_in = ph(lt, 0, 1.2)
    items = []
    for i in range(n):
        z = ((i / n) * 9 - lt * 1.6) % 9 + 0.45
        items.append((z, i))
    for z, i in sorted(items, reverse=True):
        s = 1.0 / z
        ang = i * 137.5 + lt * 28 + z * 22
        r = 380 * s
        cx = cxh + math.cos(math.radians(ang)) * r * 1.4
        cy = cyh + math.sin(math.radians(ang)) * r
        tex = card_tex(i)
        tw = int(tex.width * s * 0.55)
        if tw < 8 or tw > 4200:
            continue
        t2 = tex.resize((tw, int(tw * 0.66)), Image.BILINEAR).rotate(-ang * 0.6, Image.BILINEAR, expand=True)
        dark = cl((z - 2.5) / 6)
        if dark > 0:
            arr_ = np.asarray(t2).astype(np.float32)
            arr_[..., :3] *= (1 - 0.8 * dark)
            arr_[..., 3] *= fade_in
            t2 = Image.fromarray(arr_.astype(np.uint8))
        im.paste(t2, (int(cx - t2.width / 2), int(cy - t2.height / 2)), t2)
    glow(im, cxh, cyh, 120, (6, 6, 24), 1.0)
    a = arr(im)
    return flash(a, 1 - fade_in, (8, 8, 20))


# ------------------------------------------------------------------ 8 neon diamonds
def s_neon(c):
    lt = c.lt
    im = Image.new("RGB", (W, H), (12, 12, 34))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay, "RGBA")
    for i in range(14):
        a = math.radians(h(i, 61) * 90 + lt * 6 * (h(i, 62) - 0.5))
        R = 200 + 700 * h(i, 63)
        cx, cy = W * h(i, 64), H * h(i, 65)
        pts = [(cx + R * math.cos(a + k * math.pi / 2), cy + R * math.sin(a + k * math.pi / 2)) for k in range(4)]
        d.polygon(pts, outline=(70, 70, 170, 120), width=2)
    z = math.exp(lerp(0, math.log(7), ph(lt, 0.3, c.dur)))
    for k in range(5):
        R = 140 * (1.9 ** k) * z / 2.2
        if R > 2600:
            continue
        col = (226, 80, 200) if k % 2 == 0 else (110, 90, 255)
        pts = [(W / 2, H / 2 - R), (W / 2 + R, H / 2), (W / 2, H / 2 + R), (W / 2 - R, H / 2)]
        d.polygon(pts, outline=col + (255,), width=3)
        d.line((W / 2 - R * 2, H / 2 - R * 2 + R, W / 2 + R * 2, H / 2 + R * 2 + R), fill=col + (60,), width=1)
    g = lay.filter(ImageFilter.GaussianBlur(6))
    im.paste(g, (0, 0), g)
    im.paste(lay, (0, 0), lay)
    return arr(vignette(im))


# ------------------------------------------------------------------ 9 dark UI icons → corridor
def s_icons(c):
    lt = c.lt
    im = vgrad((14, 14, 40), (10, 10, 30))
    if lt < 1.9:
        for layer, (sp, bl, sc) in enumerate(((60, 8, 0.8), (140, 3, 1.0), (260, 0, 1.2))):
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay, "RGBA")
            for i in range(26):
                k = layer * 100 + i
                x = (h(k, 71) * (W + 600) - lt * sp) % (W + 600) - 300
                y = H * (0.12 + 0.76 * h(k, 72))
                s = 26 * sc
                kind = int(h(k, 73) * 6)
                col = INDIGO[k % 6] + (230,)
                if kind == 0:
                    d.line((x, y - s, x + s * 0.7, y, x, y + s), fill=(130, 130, 220, 230), width=3)
                elif kind == 1:
                    d.line((x - s, y, x + s, y), fill=(200, 200, 230, 230), width=3); d.line((x, y - s, x, y + s), fill=(200, 200, 230, 230), width=3)
                elif kind == 2:
                    d.rectangle((x - s, y - s, x + s, y + s), fill=col)
                elif kind == 3:
                    d.rounded_rectangle((x - s * 4, y - s * 0.7, x + s * 4, y + s * 0.7), 6, fill=(60, 70, 200, 200))
                elif kind == 4:
                    d.polygon([(x, y - s * 0.8), (x + s * 0.8, y), (x, y + s * 0.8), (x - s * 0.8, y)], fill=[(232, 72, 104), (120, 232, 130), (80, 120, 255)][k % 3] + (230,))
                else:
                    d.rectangle((x - s * 3, y - s, x + s * 3, y + s), outline=(80, 90, 200, 200), width=2)
            if bl:
                lay = lay.filter(ImageFilter.GaussianBlur(bl))
            im.paste(lay, (0, 0), lay)
        orb(im, W / 2, H / 2, 30)
    else:
        q = lt - 1.9
        d = ImageDraw.Draw(im, "RGBA")
        for k in range(14):
            z = ((k / 14) * 6 - q * 2.4) % 6 + 0.2
            s = 1 / z
            w2, h2 = 700 * s, 420 * s
            a = int(200 * cl((6 - z) / 3))
            d.rectangle((W / 2 - w2, H / 2 - h2, W / 2 + w2, H / 2 + h2), outline=(70, 80, 200, a), width=max(1, int(3 * s)))
        for i in range(180):
            ang = h(i, 81) * math.tau
            r = ((h(i, 82) * 900 + q * 900 * (0.6 + h(i, 83))) % 1000)
            x, y = W / 2 + math.cos(ang) * r * 1.6, H / 2 + math.sin(ang) * r
            L = 4 + r * 0.04
            d.rectangle((x, y, x + L * abs(math.cos(ang)) + 3, y + L * abs(math.sin(ang)) + 3), fill=INDIGO[i % 6] + (200,))
        orb(im, W / 2, H / 2, 30 + q * 20)
    return arr(vignette(im))


# ------------------------------------------------------------------ 10 geometry → sphere burst
BURST = ["sphere_cyan", "sphere_peach", "sphere_violet", "sphere_cyan", "sphere_lime", "sphere_pink", "sphere_cyan", "sphere_violet"]


def s_geometry(c):
    lt = c.lt
    im = vgrad((12, 10, 30), (24, 24, 80))
    glow(im, W / 2, H * 1.0, 900, (50, 60, 200), 0.5)
    d = ImageDraw.Draw(im, "RGBA")
    cx, cy, R = W / 2, H / 2, 150
    d.line((0, cy, W, cy), fill=(180, 60, 110, 120)); d.line((cx, 0, cx, H), fill=(180, 60, 110, 120))
    for x in (cx - 560, cx + 560):
        d.line((x, 0, x, H), fill=(110, 70, 160, 90))
    burst = ph(lt, 3.2, 4.4)
    if lt < 0.9:
        a = ph(lt, 0, 0.9)
        d.arc((cx - R * 2.4, cy - R * 0.8, cx + R * 0.4, cy + R * 2.4), 230, 230 + 80 * a, fill=(200, 200, 255, 200), width=2)
    elif lt < 2.0:
        a = ph(lt, 0.9, 2.0)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lay).pieslice((cx - R, cy - R, cx + R, cy + R), -90, -90 + 360 * a, fill=(240, 240, 255, 255))
        grad = vgrad((255, 255, 255), (60, 70, 230))
        im.paste(grad, (0, 0), lay.getchannel("A"))
        ex = cx + R * math.cos(math.radians(-90 + 360 * a)); ey = cy + R * math.sin(math.radians(-90 + 360 * a))
        d = ImageDraw.Draw(im, "RGBA")
        d.line((cx, cy, ex, ey), fill=(160, 200, 255, 220), width=2)
        d.ellipse((ex - 6, ey - 6, ex + 6, ey + 6), outline=(160, 220, 255, 255), width=2)
    else:
        glow(im, cx, cy, R * 2.2, (120, 140, 255), 0.6 * (1 - burst))
        d = ImageDraw.Draw(im, "RGBA")
        sat = lt - 2.0
        if burst < 1:
            d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(250, 250, 255, 255))
            d.rectangle((cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8), outline=(130, 140, 220, 160))
            sx, sy = cx + 260 * math.cos(sat * 2.4 - 1), cy + 160 * math.sin(sat * 2.4 - 1)
            d.ellipse((sx - 20, sy - 20, sx + 20, sy + 20), outline=(140, 180, 255, 180), width=2)
            orb(im, sx, sy, 8)
        if burst > 0:
            for k, name in enumerate(BURST):
                ang = k / len(BURST) * math.tau + 0.4
                rr = lerp(10, 300, M.spring(lt - 3.2, 170, 18))
                x, y = cx + math.cos(ang) * rr * 1.1, cy + math.sin(ang) * rr
                put(im, name, x, y, lerp(60, 120, burst))
                if k in (2, 6):
                    ImageDraw.Draw(im, "RGBA").rectangle((x - 70, y - 70, x + 70, y + 70), outline=(140, 150, 230, 120))
            d = ImageDraw.Draw(im, "RGBA")
            d.ellipse((cx - R * 0.6, cy - R * 0.6, cx + R * 0.6, cy + R * 0.6), fill=(250, 250, 255, 255))
    return arr(im)


# ------------------------------------------------------------------ 11 sphere room
ROOM_SPH = ["sphere_pink", "sphere_cyan", "sphere_lime", "sphere_violet", "sphere_peach", "sphere_cyan"]


def s_sroom(c):
    lt = c.lt
    im = Image.new("RGB", (W, H), (70, 80, 240))
    d = ImageDraw.Draw(im, "RGBA")
    bx0, by0, bx1, by1 = W / 2 - 340, H / 2 - 250, W / 2 + 340, H / 2 + 250
    walls = [([(0, 0), (W, 0), (bx1, by0), (bx0, by0)], (120, 130, 255)), ([(0, H), (W, H), (bx1, by1), (bx0, by1)], (60, 60, 210)),
             ([(0, 0), (bx0, by0), (bx0, by1), (0, H)], (150, 170, 255)), ([(W, 0), (bx1, by0), (bx1, by1), (W, H)], (100, 110, 250))]
    for poly, col in walls:
        d.polygon(poly, fill=col + (255,))
    d.rectangle((bx0, by0, bx1, by1), fill=(22, 20, 70, 255), outline=(170, 180, 255, 200), width=2)
    glow(im, W / 2, H / 2, 260, (40, 40, 120), 0.6)
    items = []
    for i in range(16):
        z = ((h(i, 91) * 6) - lt * 0.9) % 6 + 0.6
        items.append((z, i))
    for z, i in sorted(items, reverse=True):
        s = 1.4 / z
        x = W / 2 + (h(i, 92) - 0.5) * W * 1.2 * s
        y = H / 2 + (h(i, 93) - 0.5) * H * 1.0 * s
        put(im, ROOM_SPH[i % 6], x, y, 140 * s, cl((6 - z) / 1.5), blur=max(0, (z - 4) * 1.5))
    for i in range(40):
        z = ((h(i, 94) * 5) - lt * 1.2) % 5 + 0.4
        s = 1 / z
        glow(im, W / 2 + (h(i, 95) - 0.5) * W * s, H / 2 + (h(i, 96) - 0.5) * H * s, 10 * s + 3, (255, 255, 255), 0.9)
    return arr(im)


# ------------------------------------------------------------------ 12 isometric panels
def s_iso(c):
    lt = c.lt
    im = vgrad((22, 20, 70), (16, 14, 50))
    d = ImageDraw.Draw(im, "RGBA")
    panels = [(40, 40, 600, 520), (40, 560, 600, 1040), (650, 40, 1270, 1040), (1320, 40, 1880, 1040)]
    for k, (x0, y0, x1, y1) in enumerate(panels):
        d.rounded_rectangle((x0, y0, x1, y1), 18, fill=[(30, 28, 90), (36, 34, 110), (26, 24, 80), (30, 26, 86)][k] + (255,))
    glow(im, 1700, 960, 420, (60, 180, 110), 0.4)
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle((760, 120, 1160, 210), 10, fill=(80, 100, 240, 255))
    d.rounded_rectangle((800, 155, 1000, 170), 6, fill=(150, 170, 255, 255))
    g = Image.fromarray(np.dstack([np.full((120, 200), 230, np.uint8), np.tile(np.linspace(60, 140, 200, dtype=np.uint8), (120, 1)),
                                   np.full((120, 200), 230, np.uint8), np.full((120, 200), 255, np.uint8)]))
    im.paste(g, (160, 150), g)
    bob = math.sin(lt * 2) * 8
    put(im, "iso_house", 320, 800 + bob, 380)
    put(im, "iso_stairs", 960, 640 - bob, 520)
    put(im, "iso_shield", 1600, 520 + bob, 420)
    path = [(260, 210), (330, 780), (960, 560), (1600, 500), (1600, 500)]
    q = ph(lt, 0.2, c.dur - 0.3) * (len(path) - 2)
    i = min(len(path) - 2, int(q))
    f = q - i
    ox, oy = lerp(path[i][0], path[i + 1][0], ease_in_out(f)), lerp(path[i][1], path[i + 1][1], ease_in_out(f))
    pts = path[:i + 1] + [(ox, oy)]
    if len(pts) > 1:
        ImageDraw.Draw(im, "RGBA").line(pts, fill=(170, 190, 255, 120), width=2)
    orb(im, ox, oy, 18)
    return arr(im)


# ------------------------------------------------------------------ 13 horizon flash
def s_flash(c):
    lt = c.lt
    hy = H * 0.42
    im = Image.new("RGB", (W, H), (10, 10, 30))
    sky = G.cache("sky_blur", lambda: cover(img("bubbles_sky").convert("RGB"), W, H, 1.2).filter(ImageFilter.GaussianBlur(14)))
    im.paste(sky.crop((0, 0, W, int(hy))), (0, 0))
    for i in range(22):
        x = W * h(i, 101)
        y = hy + 80 + H * 0.5 * h(i, 102)
        put(im, ROOM_SPH[i % 6], x + math.sin(lt + i) * 10, y, 70 + 120 * h(i, 103), 0.9, blur=3 + 6 * h(i, 104))
    p = ph(lt, 0.9, c.dur)
    glow(im, W / 2, hy, 900 * (0.4 + p), (255, 240, 255), 0.6 + 0.4 * p)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle((0, hy - 4 - 300 * p, W, hy + 4 + 30 * p), fill=(255, 250, 255, int(200 + 55 * p)))
    return flash(arr(im), ph(lt, c.dur - 0.5, c.dur), (238, 236, 255))


# ------------------------------------------------------------------ pastel ground
def pastel(lt, seed=0):
    im = vgrad((236, 234, 255), (196, 196, 250))
    for i in range(6):
        k = seed * 10 + i
        glow(im, W * h(k, 111) + 120 * math.sin(lt * 0.3 + i), H * h(k, 112), 380 + 300 * h(k, 113),
             [(255, 200, 230), (190, 210, 255), (230, 190, 255), (180, 160, 250)][i % 4], 0.55)
    return im


def s_pillars(c):
    lt = c.lt
    im = pastel(lt, 1)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(16):
        x = W * (0.04 + 0.92 * h(i, 121))
        top = H * (0.25 + 0.6 * h(i, 122)) - ph(lt, 0, c.dur) * 140 * h(i, 123)
        wv = 14 + 30 * h(i, 124)
        col = [(140, 120, 255), (120, 210, 250), (255, 170, 210), (170, 150, 255)][i % 4]
        g = Image.fromarray(np.dstack([np.tile(np.linspace(255, col[j], 400, dtype=np.uint8)[:, None], (1, int(wv))) for j in range(3)] +
                                      [np.full((400, int(wv)), 230, np.uint8)]))
        m = Image.new("L", g.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, g.width - 1, g.height - 1), int(wv / 2), fill=230)
        g.putalpha(m)
        g = g.resize((int(wv), int(H - top + 40)))
        im.paste(g, (int(x), int(top)), g)
        if h(i, 125) > 0.45:
            put(im, ROOM_SPH[i % 6], x + wv / 2, top - wv * 0.8, wv * 2.2)
    for i in range(30):
        glow(im, W * h(i, 126), H * h(i, 127) - lt * 30, 6, (255, 255, 255), 0.9)
    return arr(zoom(im, 1 + 0.05 * ph(lt, 0, c.dur), W / 2, H * 0.3))


def s_ribbons(c):
    lt = c.lt
    im = pastel(lt, 2)
    glow(im, W / 2, H * 0.4, 700, (255, 255, 255), 0.7)
    rb = img("ribbon")
    q = ph(lt, 0, c.dur)
    s = lerp(1.0, 1.5, q)
    r2 = rb.resize((int(rb.width * s), int(rb.height * s)), Image.BILINEAR).rotate(lerp(-10, 12, q), Image.BILINEAR, expand=True)
    im.paste(r2, (int(lerp(-500, -200, q)), int(lerp(200, -100, q))), r2)
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(5):
        cx, cy = W * (0.15 + 0.18 * k), H * (0.65 + 0.15 * math.sin(k * 2.1 + lt * 0.5))
        w2, h2 = 140 + 50 * h(k, 131), 190
        a = math.radians(-12 + 18 * h(k, 132) + lt * 4)
        pts = [(cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)) for dx, dy in ((-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2))]
        d.polygon(pts, fill=(255, 255, 255, 70), outline=(255, 255, 255, 170))
    items = []
    for i in range(34):
        z = ((h(i, 133) * 5) - lt * 0.7) % 5 + 0.5
        items.append((z, i))
    for z, i in sorted(items, reverse=True):
        s = 1 / z
        x = W / 2 + (h(i, 134) - 0.5) * W * 1.6 * s
        y = H / 2 + (h(i, 135) - 0.5) * H * 1.4 * s
        put(im, ROOM_SPH[i % 6], x, y, 60 * s + 8, cl((5 - z) / 1.2), blur=max(0, 2.2 - z) * 2)
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(3):
        R = 500 + 220 * k
        d.arc((W / 2 - R, H / 2 - R * 0.55, W / 2 + R, H / 2 + R * 0.55), (lt * 20 + k * 70) % 360, (lt * 20 + k * 70) % 360 + 120, fill=(255, 255, 255, 160), width=2)
    return arr(im)


def s_frost(c):
    lt = c.lt
    im = pastel(lt, 3)
    glow(im, W / 2, H * 0.78, 360, (255, 255, 255), 0.8)
    R = 380
    enter = ph(lt, 0.2, 1.6)
    ox, oy = lerp(W * 0.8, W / 2 + 40, enter), lerp(H * 0.85, H / 2 + 40, enter)
    put(im, "sphere_frost", W / 2, H / 2, R * 2)
    fill = ph(lt, 1.5, 2.6)
    if fill > 0:
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((W / 2 - R * 0.92, H / 2 - R * 0.92, W / 2 + R * 0.92, H / 2 + R * 0.92), fill=int(200 * fill))
        blue = Image.new("RGB", (W, H), (60, 60, 230))
        glow(blue, W / 2 + 80, H / 2 - 80, R * 0.9, (150, 160, 255), 0.9)
        im.paste(blue, (0, 0), m.filter(ImageFilter.GaussianBlur(30)))
    if lt < 1.7:
        orb(im, ox, oy, 14)
    z = math.exp(lerp(0, math.log(3.2), ph(lt, 2.4, c.dur)))
    return flash(arr(zoom(im, z, W / 2 + 60, H / 2 - 40)), ph(lt, c.dur - 0.35, c.dur), (240, 236, 255))


def s_frames(c):
    lt = c.lt
    im = Image.new("RGB", (W, H), (150, 110, 230))
    d = ImageDraw.Draw(im, "RGBA")
    z = math.exp(lerp(0, math.log(4.0), ph(lt, 0, c.dur)))
    for k in range(6, -1, -1):
        s = z / (1.6 ** k)
        w2, h2 = 620 * s, 380 * s
        if w2 > 4000:
            continue
        col = [(230, 120, 190), (140, 100, 240), (240, 160, 210), (120, 90, 230)][k % 4]
        d.rectangle((W / 2 - w2, H / 2 - h2, W / 2 + w2, H / 2 + h2), fill=col + (255,))
        d.rectangle((W / 2 - w2 * 0.86, H / 2 - h2 * 0.82, W / 2 + w2 * 0.86, H / 2 + h2 * 0.82), fill=tuple(int(v * 0.85) for v in col) + (255,))
    d.rectangle((W / 2 - 110 * z, H / 2 - 60 * z, W / 2 + 110 * z, H / 2 + 60 * z), fill=(255, 210, 230, 255))
    put(im, "sphere_peach", W * 0.22 - lt * 40, H * 0.72, 300 * z ** 0.5)
    put(im, "sphere_peach", W * 0.7 + lt * 30, H * 0.4, 140 * z ** 0.5)
    rb = img("ribbon")
    r2 = rb.resize((int(rb.width * 0.8), int(rb.height * 0.8)), Image.BILINEAR)
    im.paste(r2, (int(-200 - lt * 150), int(H * 0.45)), r2)
    return flash(arr(im), ph(lt, c.dur - 0.4, c.dur), (250, 200, 230))


def s_pworld(c):
    lt = c.lt
    q = ph(lt, 0, c.dur)
    im = cover(img("pastel_world").convert("RGB"), W, H, lerp(1.18, 1.05, q), lerp(0.35, 0.6, q), 0.55)
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(3):
        x = W * (0.75 + 0.1 * k) - lt * 160 * (k + 1)
        d.rounded_rectangle((x, H * 0.18 + k * 60, x + 220, H * 0.55 + k * 60), 14, fill=(255, 255, 255, 60), outline=(255, 255, 255, 150), width=2)
    return arr(im)


def s_portal(c):
    lt = c.lt
    im = vgrad((214, 210, 252), (186, 182, 246))
    z = math.exp(lerp(0, math.log(2.6), ph(lt, 0.3, c.dur)))
    cx, cy = W / 2, H / 2 + 40
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay, "RGBA")
    rings = [(820, (120, 90, 240)), (640, (140, 120, 250)), (470, (110, 180, 250)), (320, (150, 220, 250)), (190, (210, 240, 255)), (100, (250, 230, 240))]
    for k, (R, col) in enumerate(rings):
        R *= z
        dy = 26 * k * z
        d.ellipse((cx - R, cy - R * 0.5 + dy, cx + R, cy + R * 0.5 + dy), fill=tuple(max(0, v - 30) for v in col) + (255,))
        d.ellipse((cx - R * 0.97, cy - R * 0.48 + dy - 10 * z, cx + R * 0.97, cy + R * 0.48 + dy - 10 * z), fill=col + (255,))
    im.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(3):
        R = (560 + 180 * k) * z
        a0 = (lt * 30 * (1 + k * 0.4) + k * 120) % 360
        d.arc((cx - R, cy - R * 0.5, cx + R, cy + R * 0.5), a0, a0 + 150, fill=(255, 255, 255, 200), width=2)
        x = cx + R * math.cos(math.radians(a0 + 150)); y = cy + R * 0.5 * math.sin(math.radians(a0 + 150))
        glow(im, x, y, 14, (255, 255, 255), 1.0)
    for i in range(30):
        glow(im, W * h(i, 141), H * h(i, 142), 4 + 4 * h(i, 143), (255, 255, 255), 0.9)
    put(im, "sphere_peach", W * 0.62 * 1, H * 0.06, 50)
    put(im, "sphere_violet", W * 0.82, H * 0.18, 90)
    return arr(im)


def s_land(c):
    lt = c.lt
    q = ph(lt, 0, c.dur)
    im = cover(img("landscape").convert("RGB"), W, H, lerp(1.08, 1.2, q), 0.5, lerp(0.62, 0.5, q))
    cl_ = img("clouds")
    for k, (sp, sc, y) in enumerate(((60, 0.7, -60), (120, 1.0, 40))):
        s2 = cl_.resize((int(cl_.width * sc), int(cl_.height * sc)), Image.BILINEAR)
        x = int(-200 + lt * sp - k * 400)
        im.paste(s2, (x, y), s2)
    sun = ph(lt, 1.6, c.dur)
    orb(im, W * 0.5, lerp(H * 0.62, H * 0.22, sun), lerp(30, 60, sun), 0.4 + 0.6 * sun)
    dusk = ph(lt, c.dur - 1.6, c.dur)
    a = arr(im)
    return flash(a, dusk * 0.55, (24, 24, 110))


def s_space(c):
    lt = c.lt
    q = ph(lt, 0, c.dur)
    im = cover(img("space").convert("RGB"), W, H, lerp(1.05, 1.25, q))
    glow(im, W / 2, H * 0.45, 260 + 40 * math.sin(lt * 3), (255, 220, 200), 0.35)
    for name, x0, y0, dsz, par in (("planet_peach", 0.75, 0.05, 700, 0.4), ("planet_blue", 0.18, 0.62, 360, 1.0),
                                   ("planet_lime", 0.9, 0.72, 240, 1.4), ("planet_peach", 0.12, 0.2, 200, 0.7)):
        put(im, name, W * x0 + (lt * 30 - 60) * par, H * y0 - (lt * 12) * par, dsz * lerp(1.0, 1.18, q) * (1 if name != "planet_peach" or x0 > 0.5 else 0.6))
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse((W * 0.66 + lt * 20, H * 0.5, W * 0.66 + 520 + lt * 20, H * 0.5 + 520), fill=(10, 6, 24, 240))
    orb(im, lerp(W * 0.3, W * 0.5, q), lerp(H * 0.5, H * 0.45, q), 16)
    return flash(arr(im), ph(lt, c.dur - 0.5, c.dur) ** 1.5, (255, 255, 255))


def s_logo(c):
    lt = c.lt
    im = Image.new("RGBA", (W, H), (247, 246, 242, 255))
    lg = G.cache("logo", lambda: (lambda x: x.crop(x.getbbox()))(img("logo")))
    hgt = 150
    lg2 = lg.resize((int(lg.width * hgt / lg.height), hgt), Image.LANCZOS)
    f = F("sans_medium", 140)
    word = G.b.get("name", "Prismor")
    tw = text_width(word, f, -3)
    x0 = W / 2 - (lg2.width + 40 + tw) / 2
    q = M.spring(lt - 0.15, 180, 14)
    s = max(0.01, q)
    l3 = lg2.resize((max(1, int(lg2.width * s)), max(1, int(lg2.height * s))), Image.LANCZOS)
    im.alpha_composite(l3, (int(x0 + lg2.width / 2 - l3.width / 2), int(H / 2 - l3.height / 2)))
    M.kinetic(im, [[(word, False)]], 140, [0.45], lt, c.t, x0 + lg2.width + 40 + tw / 2, H / 2, ink=(16, 16, 30), spring_kd=M.DEFAULT)
    a = arr(im)
    return flash(a, 1 - ph(lt, 0, 0.35), (255, 255, 255))


SCENES = [("data", 4.6, s_data, None), ("chamber", 2.2, s_chamber, "cut"), ("wire", 3.2, s_wire, "cut"), ("room", 4.0, s_room, "fade"),
          ("flight", 2.8, s_flight, "fade"), ("horizon", 3.0, s_horizon, "cut"), ("vortex", 6.6, s_vortex, "fade"),
          ("neon", 4.0, s_neon, "fade"), ("icons", 3.8, s_icons, "fade"), ("geometry", 4.6, s_geometry, "cut"),
          ("sroom", 3.0, s_sroom, "cut"), ("iso", 4.2, s_iso, "fade"), ("flash", 2.6, s_flash, "cut"), ("pillars", 3.4, s_pillars, None),
          ("ribbons", 5.0, s_ribbons, "fade"), ("frost", 3.8, s_frost, "fade"), ("frames", 2.6, s_frames, None),
          ("pworld", 3.0, s_pworld, None), ("portal", 3.2, s_portal, "fade"), ("land", 4.8, s_land, "fade"),
          ("space", 5.2, s_space, "fade"), ("logo", 3.8, s_logo, None)]


# ------------------------------------------------------------------ score
def score(tl, out_wav, sr=48000):
    """An ambient score in code: slow pad chords, a soft pulse, shimmer notes on scene changes, risers into the
    bright worlds and a final hit on the logo."""
    import wave
    n = int(tl.duration * sr) + sr
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 52, 55, 60], [55, 59, 62, 67]]           # Am F C G
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = 4.0
    for k in range(int(tl.duration / bar) + 2):
        st = k * bar
        i0, i1 = int(st * sr), min(n, int((st + bar + 1.5) * sr))
        tt = t[i0:i1] - st
        env = np.minimum(1, tt / 1.2) * np.exp(-np.maximum(0, tt - bar) * 2.5)
        for m in chords[k % 4]:
            f = hz(m)
            out[i0:i1] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt)) * env * 0.035
        out[i0:i1] += np.sin(2 * np.pi * hz(chords[k % 4][0] - 24) * tt) * env * 0.06
    bright = tl.starts[[s.name for s in tl.scenes].index("flash")]
    for b in np.arange(bright, tl.starts[-1], 0.5):                                                 # soft pulse once the world turns bright
        i0 = int(b * sr); tt = t[i0:i0 + int(0.3 * sr)] - b
        out[i0:i0 + len(tt)] += np.sin(2 * np.pi * 110 * tt) * np.exp(-tt * 18) * 0.12
    rng = np.random.default_rng(3)
    for k, st in enumerate(tl.starts[1:], 1):
        for j in range(3):                                                                         # shimmer notes
            m = chords[int(st / bar) % 4][j] + 24
            i0 = int((st + j * 0.12) * sr); tt = t[i0:i0 + int(1.6 * sr)] - st - j * 0.12
            out[i0:i0 + len(tt)] += np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt * 3) * 0.035
        i0 = int(max(0, st - 0.5) * sr); L = int(0.6 * sr)                                          # whoosh
        x = rng.standard_normal(L); x = np.convolve(x, np.hanning(60) / 30, "same")
        out[i0:i0 + L] += x * np.sin(np.pi * np.linspace(0, 1, L)) ** 2 * 0.05
    i0 = int(tl.starts[-1] * sr); tt = t[i0:] - tl.starts[-1]                                       # logo hit
    out[i0:] += (np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 3) * 0.3 + sum(np.sin(2 * np.pi * hz(m) * tt) for m in (57, 64, 69, 76)) * np.exp(-tt * 1.2) * 0.04)
    fade = np.ones(n); fade[-int(1.0 * sr):] = np.linspace(1, 0, int(1.0 * sr))
    out *= fade
    out /= max(1e-6, np.abs(out).max() / 0.9)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return out_wav


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    over = brief.get("scenes", {})
    scenes = []
    for name, dur, fn, tr in SCENES:
        dur = over.get(name, dur)
        if dur:
            scenes.append(Scene(name, dur, fn, {"fade": Dissolve(0.4, 8), "cut": None, None: None}[tr]))
    return Timeline(scenes, W, H, brief.get("fps", 24), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "assets", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    a = ap.parse_intermixed_args()
    if a.cmd == "init":
        import shutil
        dst = os.path.abspath(a.args[0] if a.args else "film")
        if os.path.exists(dst):
            sys.exit(f"{dst} already exists")
        shutil.copytree(os.path.join(HERE, "..", "examples", "prismor"), dst, ignore=shutil.ignore_patterns("out", "score.wav"))
        print(f"created {dst}: put your logo in assets/logo.png, set name in brief.json, restyle assets.json, then assets → sheet → render")
        return
    if a.cmd == "assets":
        from framesmith import generate_images
        bdir = os.path.dirname(os.path.abspath(a.brief))
        brief = json.load(open(a.brief))
        specs = json.load(open(os.path.join(bdir, brief.get("assets", "assets.json"))))
        for m in generate_images(specs, os.path.join(bdir, brief.get("assets_dir", "assets")), names=a.args or None, force=bool(a.args)):
            print(m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(G.base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "still":
        for x in a.args or ["2"]:
            print(tl.still(float(x), os.path.join(out, f"still_{float(x):05.2f}.png")), "·", tl.scene_at(float(x)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 5, 320))
    else:
        wav = score(tl, os.path.join(G.base, "score.wav"))
        print(tl.render(a.out or os.path.join(out, "film.mp4"), wav))


if __name__ == "__main__":
    main()
