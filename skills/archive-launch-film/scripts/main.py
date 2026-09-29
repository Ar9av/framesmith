"""Archive-to-product launch film: a dark documentary cold open (kinetic single words over a falling chart,
archival engravings, cutaway drawings that flood with colour, a document with a highlighter sweep), then a
hard turn into a chrome brand reveal and light product UI on a drifting pastel ground, driven by a cursor.
Enterprise beats: a fleet wall that pulls back from one device, a holographic reveal on black, enroll,
console panels and an end card with the open source repo.

    python3 main.py init my-film [prismor|prismor-enterprise]
    python3 main.py assets | voice | check | still 3 12 40 | sheet | render   [--brief path/brief.json]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Dissolve, Scene, Timeline, cover, ease_in_out, ease_out, generate_images, h, hex2rgb, lerp, overflow_report, text
from framesmith import narration, console, ui
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width
from framesmith.media import icon as _icon, is_light_mark

G = None
INK = (22, 22, 30)
WHITE = (255, 255, 255)


def cl(x):
    return max(0.0, min(1.0, x))


def pr(lt, a, d):
    return ease_out(cl((lt - a) / d)) if d > 0 else float(lt >= a)


def back_out(t, k=1.6):
    t = cl(t) - 1
    return 1 + (k + 1) * t ** 3 + k * t ** 2


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        self.W, self.H = brief.get("size", [1920, 1080])
        th = brief.get("theme", {})
        self.lav0 = hex2rgb(th.get("lav_top", "#f3f3fc"))
        self.lav1 = hex2rgb(th.get("lav_bottom", "#c7cdf6"))
        self.paper = hex2rgb(th.get("paper", "#f4f2ee"))
        self.assets = os.path.join(base, brief.get("assets_dir", "assets"))
        self._c = {}
        vo = brief["vo"]
        self.script = open(os.path.join(base, vo["script"])).read().strip()
        wpath = os.path.join(base, vo["words"])
        if os.path.exists(wpath):
            tr = json.load(open(wpath))
        else:
            ws = self.script.split()
            tr = {"duration": len(ws) / 2.4, "words": [{"word": w, "start": i / 2.4, "end": (i + 0.8) / 2.4} for i, w in enumerate(ws)]}
        self.toks = narration.align(self.script, tr["words"])
        self.vo_dur = tr["duration"]
        ap = os.path.join(base, vo["audio"])
        self.audio = ap if os.path.exists(ap) else None
        # holds: silence inserted into the voice after a phrase, so a visual beat can breathe
        holds = []
        for hd in brief.get("holds", []):
            i = narration.find(self.toks, hd["after"]) + len(hd["after"].split()) - 1
            holds.append((self.toks[i]["end"] + 0.05, hd["secs"]))
        for t_ins, secs in sorted(holds, reverse=True):
            for tk in self.toks:
                if tk["start"] >= t_ins:
                    tk["start"] += secs
                    tk["end"] += secs
            self.vo_dur += secs
        if holds and self.audio:
            src = os.path.join(base, "vo.wav")
            if not os.path.exists(src):                  # decode the shipped m4a once
                import subprocess
                src = os.path.join(base, ".vo_decoded.wav")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", self.audio, src], check=True)
            self.audio = self._held_audio(src, sorted(holds), os.path.join(base, ".vo_held.wav"))
        self.chunks = narration.chunks(self.toks, brief.get("words_per_card", 2))

    @staticmethod
    def _held_audio(src, holds, dst):
        import wave
        with wave.open(src) as w:
            pars, a = w.getparams(), w.readframes(w.getnframes())
        bpf = pars.sampwidth * pars.nchannels
        out, last = b"", 0
        for t_ins, secs in holds:
            k = int(t_ins * pars.framerate) * bpf
            out += a[last:k] + b"\0" * (int(secs * pars.framerate) * bpf)
            last = k
        out += a[last:]
        with wave.open(dst, "wb") as w:
            w.setnchannels(pars.nchannels); w.setsampwidth(pars.sampwidth); w.setframerate(pars.framerate)
            w.writeframes(out)
        return dst

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]

    def cue(self, phrase, after=0):
        i = narration.find(self.toks, phrase, after)
        return self.toks[i]["start"], i


def cue_t(s, key, default=0.0):
    """Beat-local time of a spoken cue (s[key] is a phrase from the script), or a number of seconds."""
    v = s.get(key)
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    t, _ = G.cue(v, s["_tok"])
    return max(0.0, t - s["_t0"])


def img(name):
    def load():
        for ext in (".png", ".jpg", ".webp"):
            p = os.path.join(G.assets, name + ext)
            if os.path.exists(p):
                return Image.open(p).convert("RGBA")
        raise FileNotFoundError(os.path.join(G.assets, name + ".png"))
    return G.cache(("img", name), load)


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def fade(im, p):
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * cl(p)).astype(np.uint8)
    return Image.fromarray(a)


def vgrad(w, hgt, top, bot):
    t = np.linspace(0, 1, hgt)[:, None, None]
    g = np.array(top, np.float32) * (1 - t) + np.array(bot, np.float32) * t
    return Image.fromarray(np.repeat(g, w, 1).astype(np.uint8)).convert("RGBA")


def dgrad(w, hgt, a, b):
    """Diagonal gradient, top-left a → bottom-right b."""
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, hgt)[:, None]
    t = np.clip((x * 0.6 + y * 0.4), 0, 1)[..., None]
    g = np.array(a, np.float32) * (1 - t) + np.array(b, np.float32) * t
    return Image.fromarray(g.astype(np.uint8)).convert("RGBA")


BLOBS = [((255, 214, 186), 0.18, 0.20, 0.42, 0.21, 0.13, 0.0),      # peach
         ((252, 200, 206), 0.82, 0.30, 0.40, 0.17, 0.19, 1.7),      # rose
         ((196, 230, 247), 0.12, 0.78, 0.46, 0.15, 0.17, 3.1),      # sky
         ((226, 214, 252), 0.78, 0.84, 0.44, 0.19, 0.14, 4.4),      # lavender
         ((255, 236, 214), 0.50, 0.55, 0.30, 0.23, 0.21, 2.2)]      # cream


def mesh(t, strength=1.0):
    """prismor.dev's hero ground: soft pastel blobs (peach, rose, sky, lavender) drifting on warm white."""
    w, hgt = 192, 108
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    xx /= w
    yy /= w
    a = np.full((hgt, w, 3), (252, 251, 249), np.float32)
    for col, x0, y0, r, sx, sy, ph in BLOBS:
        cx = x0 + 0.09 * math.sin(t * sx + ph)
        cy = (y0 + 0.08 * math.cos(t * sy + ph * 1.3)) * hgt / w
        k = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r * 0.5))[..., None] * 0.85 * strength
        a = a * (1 - k) + np.array(col, np.float32) * k
    return Image.fromarray(a.astype(np.uint8)).resize((G.W, G.H), Image.BICUBIC).convert("RGBA")


def lavender():
    return G.cache("lav", lambda: vgrad(G.W, G.H, G.lav0, G.lav1)).copy()


def grain(a, fi, k=10):
    rng = np.random.default_rng(fi % 997)
    n = rng.integers(-k, k + 1, a.shape[:2], dtype=np.int16)[..., None]
    return np.clip(a.astype(np.int16) + n, 0, 255).astype(np.uint8)


def zoom_about(im, z, fx, fy):
    """Zoom an RGBA canvas by z about the point (fx, fy) in pixels, keeping the canvas size."""
    if abs(z - 1) < 1e-3:
        return im
    w, hgt = im.size
    box = (fx - fx / z, fy - fy / z, fx + (w - fx) / z, fy + (hgt - fy) / z)
    return im.transform((w, hgt), Image.EXTENT, box, Image.BICUBIC)


def shadowed(im, layer, xy, blur=24, alpha=70, dy=14):
    """Composite an RGBA layer with a soft drop shadow."""
    a = layer.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", layer.size, (20, 24, 60, 0))
    sh.putalpha(a)
    pad = blur * 2
    big = Image.new("RGBA", (layer.width + pad * 2, layer.height + pad * 2), (0, 0, 0, 0))
    big.alpha_composite(sh, (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur))
    im.alpha_composite(big, (int(xy[0] - pad), int(xy[1] - pad + dy)))
    im.alpha_composite(layer, (int(xy[0]), int(xy[1])))


def paste_scaled(im, layer, cx, cy, s, alpha=1.0, shadow=True):
    if s <= 0.01 or alpha <= 0.01:
        return
    L = layer.resize((max(1, int(layer.width * s)), max(1, int(layer.height * s))), Image.BICUBIC)
    if alpha < 1:
        L = fade(L, alpha)
    xy = (cx - L.width / 2, cy - L.height / 2)
    (shadowed(im, L, xy, int(20 * s) + 2, int(60 * alpha)) if shadow else im.alpha_composite(L, (int(xy[0]), int(xy[1]))))


def mono(d, xy, s, size, fill, anchor="lm", max_w=None):
    """Literal code in Geist Mono with ligatures off (so -- stays two hyphens); shrinks to max_w."""
    f = F("mono", size)
    while max_w and size > 12 and f.getlength(s, features=ui.CODE_FEATURES) > max_w:
        size -= 1
        f = F("mono", size)
    d.text(xy, s, font=f, fill=fill, anchor=anchor, features=ui.CODE_FEATURES)


# ------------------------------------------------------------------ icons / cursor / cards
def icon_img(ref, size, dark=INK):
    def mk():
        if ref.startswith("lucide:"):
            return console.lucide(ref[7:], size, dark)
        p = os.path.join(G.assets, "icons", ref + ".svg")
        im = _icon(p, size)
        return _icon(p, size, dark) if is_light_mark(im) else im
    return G.cache(("icon", ref, size), mk)


def cursor(im, x, y, press=0.0, s=1.0):
    s *= 1 - 0.12 * press
    pts = [(0, 0), (0, 36), (9, 28), (15.5, 42), (21.5, 39.5), (15, 26), (27, 26)]
    pts = [(x + px * s * 1.25, y + py * s * 1.25) for px, py in pts]
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.polygon([(px + 2, py + 5) for px, py in pts], fill=(0, 0, 30, 70))
    lay = lay.filter(ImageFilter.GaussianBlur(4))
    d = ImageDraw.Draw(lay)
    d.polygon(pts, fill=(12, 12, 16, 255), outline=(255, 255, 255, 255), width=3)
    if press > 0:
        r = 26 + 30 * press
        d.ellipse((x - r, y - r, x + r, y + r), outline=(40, 40, 60, int(120 * (1 - press))), width=3)
    im.alpha_composite(lay)


def cursor_path(lt, keys):
    """keys: [(t, x, y), ...] → eased position between keyframes."""
    if lt <= keys[0][0]:
        return keys[0][1:]
    for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
        if lt <= t1:
            p = ease_in_out(cl((lt - t0) / max(0.01, t1 - t0)))
            return lerp(x0, x1, p), lerp(y0, y1, p)
    return keys[-1][1:]


def card(w, hgt, r=20, fill=WHITE, outline=(226, 228, 236)):
    im = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, hgt - 1), r, fill=fill + (255,), outline=outline + (255,), width=2)
    return im


# ------------------------------------------------------------------ kinetic words
def words(im, c, s, dark_bg=True):
    """One or two words at a time, centred, entering with a short masked rise, synced to the voice."""
    t = c.t
    cur = None
    for k, (a, b, txt) in enumerate(G.chunks):
        nxt = G.chunks[k + 1][0] if k + 1 < len(G.chunks) else b + 0.6
        if a - 0.04 <= t < min(nxt, b + 0.7):
            cur = (a, txt)
    if not cur:
        return
    a, txt = cur
    txt = txt.rstrip(".,;:!?")
    p = ease_out(cl((t - a + 0.04) / 0.16))
    y = s.get("words_y", 0.5) * G.H
    f = F("sans_medium", s.get("words_size", 84))
    m = Image.new("L", im.size, 0)
    ui_layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ui.rise(ui_layer, (G.W / 2, y), txt, f, WHITE, p, -1.2, "mm", max_w=G.W - 240)
    m = ui_layer.getchannel("A").filter(ImageFilter.GaussianBlur(18))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(m.point(lambda v: min(255, v * 2) * 150 // 255))
    im.alpha_composite(sh)
    im.alpha_composite(ui_layer)


# ------------------------------------------------------------------ act one
def chart_pts():
    pts, y = [], 0.18
    for i in range(70):
        x = i / 69
        y = 0.16 + 0.62 * x ** 1.1 + 0.07 * math.sin(i * 0.55) * (0.4 + x) + 0.02 * (h(i, 5) - 0.5)
        pts.append((x, min(0.9, y)))
    return pts


def b_grid(c, s):
    W, H = G.W, G.H
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    bx0, by0, bx1, by1 = 300, 190, 1620, 880
    pts = [(bx0 + x * (bx1 - bx0), by0 + y * (by1 - by0)) for x, y in chart_pts()]
    pen = ease_in_out(cl(c.lt / (c.dur * 0.85)))
    zc = ease_in_out(cl(c.lt / (c.dur * 0.95)))
    n = max(1, int(pen * (len(pts) - 1)))
    tip = pts[n]
    z = lerp(2.6, 1.0, zc)
    fx, fy = lerp(tip[0], W / 2, zc), lerp(tip[1], H / 2, zc)
    T = lambda x, y: (W / 2 + (x - fx) * z, H / 2 + (y - fy) * z)
    step = 80
    for gx in range(-2000, 4000, step):
        X, _ = T(gx, 0)
        if 0 <= X <= W:
            d.line((X, 0, X, H), fill=(34, 34, 36), width=max(1, int(z)))
    for gy in range(-2000, 3000, step):
        _, Y = T(0, gy)
        if 0 <= Y <= H:
            d.line((0, Y, W, Y), fill=(34, 34, 36), width=max(1, int(z)))
    fp = pr(c.lt, c.dur * 0.3, c.dur * 0.5)
    if fp > 0:
        a0, a1 = T(bx0, by0), T(bx1, by1)
        col = (235, 235, 235)
        L = fp
        d.line((a0[0], a0[1], a0[0] + (a1[0] - a0[0]) * L, a0[1]), fill=col, width=2)
        d.line((a0[0], a1[1], a0[0] + (a1[0] - a0[0]) * L, a1[1]), fill=col, width=2)
        d.line((a0[0], a0[1], a0[0], a0[1] + (a1[1] - a0[1]) * L), fill=col, width=2)
        d.line((a1[0], a0[1], a1[0], a0[1] + (a1[1] - a0[1]) * L), fill=col, width=2)
        for k in range(1, 8):
            X = a0[0] + (a1[0] - a0[0]) * k / 8
            if k / 8 <= L:
                d.line((X, a1[1], X, a1[1] - 10), fill=col, width=2)
    acc = 0.0
    r = max(2.5, 2.2 * math.sqrt(z))
    for (x0, y0), (x1, y1) in zip(pts[:n], pts[1:n + 1]):
        A, B = T(x0, y0), T(x1, y1)
        seg = math.hypot(B[0] - A[0], B[1] - A[1])
        gap = 16 * math.sqrt(z)
        k = (gap - acc % gap) if acc else 0
        while k < seg:
            px, py = A[0] + (B[0] - A[0]) * k / seg, A[1] + (B[1] - A[1]) * k / seg
            d.ellipse((px - r, py - r, px + r, py + r), fill=(240, 240, 240))
            k += gap
        acc += seg
    words(im, c, s)
    return grain(arr(im), c.fi, 6)


def b_photo(c, s):
    """Archival still: slow push, gate weave, grain, darkened for white words; optional icon row."""
    mv = s.get("move", [1.04, 1.16, 0.5, 0.5, 0.5, 0.5])
    p = ease_in_out(cl(c.lt / c.dur))
    src = img(s["image"]).convert("RGB")
    wx = 2 * math.sin(c.fi * 1.7) if s.get("weave", True) else 0
    im = cover(src, G.W, G.H, lerp(mv[0], mv[1], p), lerp(mv[2], mv[3], p) + wx / 4000, lerp(mv[4], mv[5], p)).convert("RGBA")
    a = np.asarray(im.convert("RGB"), np.float32)
    if s.get("bw"):
        g = a @ np.array([0.3, 0.59, 0.11], np.float32)
        a = np.repeat(g[..., None], 3, 2)
    dk = s.get("darken", 0.72)
    yy, xx = np.mgrid[0:G.H, 0:G.W]
    vig = 1 - 0.45 * (((xx - G.W / 2) / (G.W / 2)) ** 2 + ((yy - G.H / 2) / (G.H / 2)) ** 2) / 2
    a = a * dk * vig[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    icons = s.get("icons", [])
    n = len(icons)
    for k, ic in enumerate(icons):
        t0 = cue_t(dict(s, _cue=ic["at"]), "_cue") + ic.get("delay", 0)
        q = cl((c.lt - t0) / 0.45)
        if q <= 0:
            continue
        cx = G.W / 2 + (k - (n - 1) / 2) * s.get("icons_gap", 230)
        tile = G.cache(("ptile", ic["icon"], s.get("tile", 170)), lambda: _photo_tile(ic, s.get("tile", 170)))
        paste_scaled(im, tile, cx, s.get("icons_y", 0.33) * G.H, back_out(q), min(1, q * 3), shadow=False)
    more = s.get("more", [])
    if more:
        t0 = cue_t(s, "more_at")
        m = len(more)
        for k, ref in enumerate(more):
            q = cl((c.lt - t0 - k * 0.06) / 0.4)
            if q <= 0:
                continue
            cx = G.W / 2 + (k - (m - 1) / 2) * 140
            tile = G.cache(("ptile", ref, 110), lambda: _photo_tile({"icon": ref}, 110))
            paste_scaled(im, tile, cx, s.get("more_y", 0.5) * G.H, back_out(q) * 0.9, min(1, q * 3) * 0.85, shadow=False)
    words(im, c, s)
    return grain(arr(im), c.fi, 9)


def _photo_tile(ic, sz=170):
    t = card(sz, sz, int(sz * 0.2), (250, 250, 252), (255, 255, 255))
    ico = icon_img(ic["icon"], int(sz * 0.54))
    t.alpha_composite(ico, ((sz - ico.width) // 2, (sz - ico.height) // 2))
    return t


def interior_mask(name, thicken=5):
    """Pixels enclosed by the drawing's lines (white not reachable from the border), at image resolution."""
    def mk():
        g = img(name).convert("L")
        lines = g.point(lambda v: 0 if v < 200 else 255).filter(ImageFilter.MinFilter(thicken))
        w, hgt = lines.size
        for seed in [(0, 0), (w - 1, 0), (0, hgt - 1), (w - 1, hgt - 1), (w // 2, 0), (w // 2, hgt - 1), (0, hgt // 2), (w - 1, hgt // 2)]:
            if lines.getpixel(seed) == 255:
                ImageDraw.floodfill(lines, seed, 128)
        a = np.asarray(lines)
        m = ((a == 255) | (a == 0)).astype(np.uint8) * 255
        gm = np.asarray(g)
        m[gm >= 200] = m[gm >= 200]
        mi = Image.fromarray(m).filter(ImageFilter.MaxFilter(thicken)).filter(ImageFilter.MinFilter(3))
        return np.asarray(mi, np.float32) / 255
    return G.cache(("mask", name), mk)


def b_cutaway(c, s):
    """Line drawing on white; the enclosed interior floods with colour (rising, or sweeping from one side)."""
    src = img(s["image"]).convert("RGB")
    a = np.asarray(src, np.float32)
    m = interior_mask(s["image"])
    hgt, w = m.shape
    ys, xs = np.nonzero(m > 0.5)
    y0, y1, x0, x1 = (ys.min(), ys.max(), xs.min(), xs.max()) if len(ys) else (0, hgt, 0, w)
    t0 = cue_t(s, "fill_at", 0.35)
    p = ease_in_out(cl((c.lt - t0) / s.get("fill_dur", 1.6)))
    top_col = np.array(hex2rgb(s.get("surface", "#ffd84a")), np.float32)
    deep_col = np.array(hex2rgb(s.get("deep", "#f06a3c")), np.float32)
    yy = np.arange(hgt, dtype=np.float32)[:, None]
    xx = np.arange(w, dtype=np.float32)[None, :]
    cap = y0 + (y1 - y0) * s.get("cap", 0.0)                 # the flood never rises above this fraction of the shape
    if s.get("sweep") == "right_to_left":
        front = x1 - (x1 - x0) * p
        lvl = cap
        wet = (xx >= front) & (yy >= lvl)
        dist = np.clip((yy - lvl) / max(1, (y1 - lvl)), 0, 1)
    else:
        lvl = y1 - (y1 - cap) * p
        wet = (yy >= lvl) & np.ones_like(xx, bool)
        dist = np.clip((yy - lvl) / max(1, (y1 - y0) * 0.5), 0, 1)
    col = top_col * (1 - dist[..., None]) + deep_col * dist[..., None]
    k = (m * wet)[..., None] * 0.92
    a = a * (1 - k) + (a / 255 * col) * k
    im = Image.fromarray(a.astype(np.uint8))
    mv = s.get("move", [1.0, 1.08, 0.5, 0.5, 0.5, 0.5])
    q = ease_in_out(cl(c.lt / c.dur))
    im = cover(im, G.W, G.H, lerp(mv[0], mv[1], q), lerp(mv[2], mv[3], q), lerp(mv[4], mv[5], q))
    return arr(im)


def b_doc(c, s):
    """A document page: everything but one paragraph greys out, then a highlighter sweeps across the key phrase."""
    S = 1.25
    W, H = int(G.W * S), int(G.H * S)
    im = Image.new("RGBA", (W, H), (250, 249, 246, 255))
    d = ImageDraw.Draw(im)
    x0, colw = int(420 * S), int(1080 * S)
    y = int(150 * S)
    t_dim = cue_t(s, "dim_at", 0.5)
    t_hl = cue_t(s, "hl_at", 0.9)
    dim = pr(c.lt, t_dim, 0.5)
    text(d, (x0, y), s.get("kicker", ""), F("sans_medium", int(28 * S)), (214, 70, 80), 0, "la", max_w=colw)
    y += int(56 * S)
    text(d, (x0, y), s["title"], F("sans_medium", int(64 * S)), tuple(int(lerp(v, 205, dim)) for v in INK), -1, "la", max_w=colw)
    y += int(116 * S)
    f = F("sans", int(34 * S))
    lh = int(52 * S)
    focus_y = y
    for k, para in enumerate(s["paras"]):
        target = k == s.get("target", 0)
        col = INK if target else tuple(int(lerp(v, 200, dim)) for v in (60, 60, 70))
        hl = s.get("hl", "") if target else ""
        ws = para.split()
        hs = set()
        if hl:
            m = para.find(hl)
            pos = 0
            for i, wd in enumerate(ws):
                st = para.find(wd, pos)
                pos = st + len(wd)
                if m <= st < m + len(hl):
                    hs.add(i)
        lines, cur = [], []
        for i, wd in enumerate(ws):
            trial = " ".join(ws[j] for j in cur + [i])
            if cur and f.getlength(trial) > colw:
                lines.append(cur)
                cur = []
            cur.append(i)
        lines.append(cur)
        if target:
            focus_y = y + lh * len(lines) / 2
            segs = []
            for li, ln in enumerate(lines):
                xs = [i for i in ln if i in hs]
                if xs:
                    pre = " ".join(ws[j] for j in ln if j < xs[0])
                    a = x0 + (f.getlength(pre + " ") if pre else 0)
                    b = x0 + f.getlength(" ".join(ws[j] for j in ln if j <= xs[-1]))
                    segs.append((li, a, b))
            tot = sum(b - a for _, a, b in segs) or 1
            hp = cl((c.lt - t_hl) / s.get("hl_dur", 1.0)) * tot
            for li, a, b in segs:
                seg = min(b - a, max(0, hp))
                hp -= b - a
                ui.marker(d, (a - 6, y + li * lh + 4, a + seg + 6, y + li * lh + lh - 2), (255, 230, 64), 1 if seg else 0, skew=0)
        for li, ln in enumerate(lines):
            d.text((x0, y + li * lh), " ".join(ws[j] for j in ln), font=f, fill=col)
        y += lh * len(lines) + int(30 * S)
        if k == s.get("target", 0) - 1:
            d.line((x0 - int(20 * S), y - int(8 * S), x0 - int(20 * S), y + lh * 3), fill=(255, 255, 255))
    zp = ease_in_out(cl((c.lt - t_dim) / (c.dur - t_dim + 0.01)))
    im = zoom_about(im, lerp(1.0, 1.28, zp), W * 0.42, lerp(H / 2, focus_y, 0.8))
    return arr(im.resize((G.W, G.H), Image.LANCZOS))


def b_words(c, s):
    """Words on black; the ground can warm into the lavender brand gradient at the end."""
    gp = pr(c.lt, cue_t(s, "grad_at", c.dur * 0.7), max(0.1, c.dur - cue_t(s, "grad_at", c.dur * 0.7)))
    im = Image.new("RGBA", (G.W, G.H), (0, 0, 0, 255))
    if gp > 0:                                           # dawn: black lifts from the bottom into the site's pastel ground
        g = mesh(c.t)
        ramp = np.clip((np.linspace(1, 0, G.H)[:, None] - 1 + gp * 2.0), 0, 1) * gp
        m = Image.fromarray((np.repeat(ramp, G.W, 1) * 255).astype(np.uint8))
        im.paste(g, (0, 0), m)
    words(im, c, s)
    return arr(im)


# ------------------------------------------------------------------ act two
def logo_lockup(size):
    def mk():
        lg = img("logo")
        bb = lg.getbbox()
        lg = lg.crop(bb) if bb else lg
        lh = size
        lg = lg.resize((int(lg.width * lh / lg.height), lh), Image.LANCZOS)
        return lg
    return G.cache(("logo", size), mk)


def chrome(im, name, cx, cy, size, rot, blur=0.0, alpha=1.0):
    ob = G.cache(("chrome", name, size), lambda: img(name).resize((size, size), Image.LANCZOS))
    ob = ob.rotate(rot, Image.BICUBIC, expand=True)
    if blur > 0.3:
        ob = ob.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 1:
        ob = fade(ob, alpha)
    im.alpha_composite(ob, (int(cx - ob.width / 2), int(cy - ob.height / 2)))


def b_brand(c, s):
    im = mesh(c.t)
    lt = c.lt
    ep = ease_out(cl(lt / 1.1))
    drift = lt * 6
    chrome(im, s.get("obj_a", "chrome_torus"), lerp(-300, 170, ep), lerp(1300, 900, ep) + math.sin(lt * 1.3) * 10, 620, 18 + drift, (1 - ep) * 14)
    chrome(im, s.get("obj_b", "chrome_key"), lerp(2250, 1720, ep), lerp(-260, 150, ep) + math.cos(lt * 1.1) * 10, 460, -25 - drift * 0.7, (1 - ep) * 14 + 1.2)
    word = s.get("name", "Prismor")
    f = F("sans_medium", 120)
    lg = logo_lockup(124)
    gap = 34
    ww = text_width(word, f, -2)
    tot = lg.width + gap + ww
    x = G.W / 2 - tot / 2
    lp = cl((lt - 0.35) / 0.45)
    if lp > 0:
        paste_scaled(im, lg, x + lg.width / 2, G.H / 2, back_out(lp, 1.3), min(1, lp * 2.5), shadow=False)
    t0 = 0.75
    n = int(cl((lt - t0) / (len(word) * 0.07)) * len(word))
    d = ImageDraw.Draw(im)
    if n:
        text(d, (x + lg.width + gap, G.H / 2), word[:n], f, INK, -2, "lm", max_w=G.W)
    if lt > t0 - 0.1 and (n < len(word) or int(lt * 2.5) % 2 == 0) and lt < t0 + len(word) * 0.07 + 1.0:
        cx = x + lg.width + gap + text_width(word[:n], f, -2) + 8
        d.rectangle((cx, G.H / 2 - 58, cx + 5, G.H / 2 + 58), fill=(90, 96, 220))
    return arr(im)


def agent_tile(name, ref, w=380, hgt=440):
    def mk():
        t = card(w, hgt, 26, (236, 238, 252), (255, 255, 255))
        ico = icon_img(ref, 150)
        t.alpha_composite(ico, ((w - ico.width) // 2, int(hgt * 0.42 - ico.height / 2)))
        d = ImageDraw.Draw(t)
        text(d, (28, hgt - 70), name, F("sans_medium", 30), INK, -0.3, "lm", max_w=w - 56)
        d.ellipse((28, hgt - 40, 40, hgt - 28), fill=console.PC["allow"])
        text(d, (50, hgt - 34), "Guarded by Prismor", F("sans", 22), console.PC["ink2"], 0, "lm", max_w=w - 80)
        return t
    return G.cache(("tile", name), mk)


def secret_card(s):
    """Tool call with the key as a placeholder; the placeholder gets a violet highlight."""
    def mk():
        w, hgt = 900, 330
        t = card(w, hgt, 22)
        d = ImageDraw.Draw(t)
        t.alpha_composite(console.lucide("terminal", 30, console.PC["ink2"]), (34, 36))
        text(d, (78, 51), s.get("secret_title", "Tool call · claude-code"), F("sans_medium", 28), INK, -0.2, "lm", max_w=w - 300)
        d.ellipse((w - 190, 45, w - 178, 57), fill=console.PC["redact"])
        text(d, (w - 168, 51), "Cloaked", F("sans_medium", 24), console.PC["redact"], 0, "lm")
        d.line((34, 92, w - 34, 92), fill=console.PC["line"], width=2)
        return t
    return G.cache("secret_card", mk)


def b_session(c, s):
    lt = c.lt
    im = mesh(c.t)
    t_panel = cue_t(s, "panel_at", 1.6)
    t_pop = cue_t(s, "pop_at", 3.5)
    pp = ease_in_out(cl((lt - t_panel) / 0.8))
    zp = ease_in_out(cl((lt - t_pop + 0.3) / 1.0))
    agents = s["agents"]
    sc = lerp(1.0, 0.64, pp)
    n = len(agents)
    for k, ag in enumerate(agents):
        q = cl((lt - 0.1 - k * 0.12) / 0.5)
        if q <= 0:
            continue
        tile = agent_tile(ag["name"], ag["icon"])
        rx, ry = G.W / 2 + (k - (n - 1) / 2) * (tile.width + 40), G.H / 2 + (1 - ease_out(q)) * 80
        # second layout: a 2-column grid on the left
        colx, coly = 250 + (k % 2) * (tile.width * 0.64 + 24), G.H / 2 + (k // 2 - 0.5) * (tile.height * 0.64 + 24)
        if n <= 2:
            colx, coly = 380, G.H / 2 + (k - (n - 1) / 2) * (tile.height * 0.64 + 24)
        paste_scaled(im, tile, lerp(rx, colx, pp), lerp(ry, coly, pp), sc, min(1, q * 2))
    if pp > 0:
        panel = console.render("feed", s["feed"], max(0, lt - t_panel), 1040)
        px = lerp(G.W + 40, 760, pp)
        im.alpha_composite(panel, (int(px), int(G.H / 2 - panel.height / 2)))
    if zp > 0:
        im = zoom_about(im, lerp(1.0, 1.1, zp), 1150, 560)
    if lt >= t_pop:
        q = cl((lt - t_pop) / 0.4)
        sc_ = secret_card(s).copy()
        d = ImageDraw.Draw(sc_)
        cmd = s["secret_cmd"]
        ph = "@" * 2 + "SECRET:" + s.get("secret_name", "openai-prod") + "@" * 2
        full = cmd.replace("{secret}", ph)
        fm = F("mono", 27)
        x, y = 34, 130
        hp = cl((lt - t_pop - 0.5) / 0.6)
        a_idx = full.find(ph)
        pre, post = full[:a_idx], full[a_idx + len(ph):]
        # wrap: pre on line 1, placeholder on line 2, rest after it
        mono(d, (x, y), pre.rstrip(), 27, INK, "lm", 830)
        y2 = y + 50
        pw = fm.getlength(ph)
        ui.marker(d, (x - 6, y2 - 22, x + pw + 6, y2 + 22), (231, 222, 252), hp, skew=0)
        d.text((x, y2), ph, font=fm, fill=console.PC["redact"], anchor="lm", features=["-liga", "-calt"])
        mono(d, (x + pw + fm.getlength(" "), y2), post.strip(), 27, INK, "lm", 830 - pw - 20)
        text(d, (x, y2 + 80), s.get("secret_note", ""), F("sans", 25), console.PC["ink2"], 0, "lm", max_w=830)
        paste_scaled(im, sc_, G.W / 2 + 120, G.H / 2 + 150, lerp(0.9, 1.0, back_out(q)), min(1, q * 2.5))
        kx, ky = cursor_path(lt - t_pop, [(0, 1700, 1050), (0.9, 1000, 800), (1.8, 980, 792)])
        cursor(im, kx, ky)
    return arr(im)


def b_approve(c, s):
    lt = c.lt
    im = mesh(c.t)
    w, hgt = 1100, 470
    t_click = cue_t(s, "click_at", 1.8)
    q = cl(lt / 0.45)
    cd = card(w, hgt, 24)
    d = ImageDraw.Draw(cd)
    PC = console.PC
    text(d, (44, 60), s.get("title", "Waiting for approval"), F("sans_medium", 34), INK, -0.4, "lm", max_w=600)
    done = lt >= t_click + 0.15
    word, col = (s.get("done", "Approved by Priya"), PC["allow"]) if done else ("Held", PC["warn"])
    fw = F("sans_medium", 26)
    ww = fw.getlength(word)
    d.ellipse((w - 44 - ww - 26, 53, w - 44 - ww - 12, 67), fill=col)
    d.text((w - 44, 60), word, font=fw, fill=col, anchor="rm")
    d.line((44, 108, w - 44, 108), fill=PC["line"], width=2)
    cd.alpha_composite(console.lucide(s.get("icon", "git-branch"), 34, PC["ink2"]), (44, 142))
    text(d, (96, 160), s["action"], F("sans_medium", 30), INK, -0.2, "lm", max_w=w - 150)
    mono(d, (96, 210), s["cmd"], 27, PC["ink2"], "lm", w - 150)
    text(d, (96, 256), s["who"], F("sans", 25), PC["ink3"], 0, "lm", max_w=w - 150)
    by = hgt - 110
    press = cl(1 - abs(lt - t_click) / 0.18)
    bp = 1 - pr(lt, t_click + 0.3, 0.4)
    if bp > 0:
        d.rounded_rectangle((w - 480, by, w - 280, by + 66), 12, outline=PC["line_strong"] + (int(255 * bp),), width=2, fill=WHITE + (255,))
        d.text((w - 380, by + 33), "Deny", font=F("sans_medium", 27), fill=PC["ink"] + (int(255 * bp),), anchor="mm")
        s2 = 1 - 0.04 * press
        bx0, bx1 = w - 260, w - 44
        cxm, cym = (bx0 + bx1) / 2, by + 33
        d.rounded_rectangle((cxm - 108 * s2, cym - 33 * s2, cxm + 108 * s2, cym + 33 * s2), 12, fill=INK + (int(255 * bp),))
        d.text((cxm, cym), "Approve", font=F("sans_medium", 27), fill=WHITE + (int(255 * bp),), anchor="mm")
    if done:
        dp = pr(lt, t_click + 0.4, 0.4)
        text(d, (44, by + 33), s.get("note", ""), F("sans", 25), PC["ink2"] + (int(255 * dp),), 0, "lm", max_w=w - 100)
    cx, cy = G.W / 2, G.H / 2 + (1 - ease_out(q)) * 60
    K = 1.3
    paste_scaled(im, cd, cx, cy, K, min(1, q * 2))
    bx, byy = cx + (w / 2 - 152) * K, cy + (-hgt / 2 + by + 33) * K
    kx, ky = cursor_path(lt, [(0, G.W - 120, G.H + 60), (t_click - 0.2, bx + 10, byy + 8), (t_click + 0.6, bx + 14, byy + 12), (c.dur, bx + 90, byy + 120)])
    cursor(im, kx, ky, press)
    return arr(im)


def node_card(ref, label):
    def mk():
        t = Image.new("RGBA", (220, 190), (0, 0, 0, 0))
        tile = card(128, 128, 22)
        ico = icon_img(ref, 66)
        tile.alpha_composite(ico, ((128 - ico.width) // 2, (128 - ico.height) // 2))
        t.alpha_composite(tile, (46, 0))
        text(ImageDraw.Draw(t), (110, 162), label, F("sans_medium", 24), (40, 52, 80), 0, "mm", max_w=210)
        return t
    return G.cache(("node", ref, label), mk)


def bezier(a, b, c1, c2, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append((mt ** 3 * a[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * b[0],
                    mt ** 3 * a[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * b[1]))
    return out


def b_flow(c, s):
    """Sources around a central document: connectors draw in, packets travel, the document's sections fill."""
    lt = c.lt
    im = mesh(c.t)
    d = ImageDraw.Draw(im)
    cxm, cym = G.W / 2, G.H / 2 + 10
    dw, dh = 520, 660
    nodes = s["nodes"]
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    placed = []
    for k, nd in enumerate(nodes):
        side = -1 if k % 2 == 0 else 1
        row = k // 2
        rows = (len(nodes) + 1) // 2
        nx = cxm + side * (560 + 90 * (1 - abs(row - (rows - 1) / 2) / rows * 2))
        ny = 170 + row * (G.H - 300) / max(1, rows - 1)
        ny += math.sin(lt * 1.4 + k) * 8
        t0 = 0.15 + k * 0.16
        q = cl((lt - t0) / 0.45)
        placed.append((nd, nx, ny, q, t0, side))
        if q <= 0:
            continue
        a = (nx - side * 60, ny - 20)
        b = (cxm + side * dw / 2, cym - dh / 2 + 150 + (k % 4) * 110)
        pts = bezier(a, b, (a[0] - side * 160, a[1]), (b[0] + side * 200, b[1]))
        lp = cl((lt - t0 - 0.25) / 0.7)
        m = int(lp * (len(pts) - 1))
        if m > 0:
            ld.line(pts[:m + 1], fill=(255, 255, 255, 210), width=3, joint="curve")
        if lp >= 1:
            ph = ((lt - t0) * 0.6 + k * 0.13) % 1
            px, py = pts[int(ph * (len(pts) - 1))]
            ld.ellipse((px - 7, py - 7, px + 7, py + 7), fill=(84, 120, 230, 255))
    im.alpha_composite(lay)
    for nd, nx, ny, q, t0, side in placed:
        if q > 0:
            paste_scaled(im, node_card(nd["icon"], nd["label"]), nx, ny + 20, back_out(q, 1.4), min(1, q * 2))
    # the document
    q = cl(lt / 0.5)
    doc = card(dw, dh, 26)
    dd = ImageDraw.Draw(doc)
    PC = console.PC
    text(dd, (dw / 2, 62), s.get("doc_title", "Fleet policy"), F("sans_medium", 40), INK, -0.6, "mm", max_w=dw - 60)
    text(dd, (dw / 2, 108), s.get("doc_sub", "acme/org · version 15"), F("mono", 22), PC["ink3"], 0, "mm", max_w=dw - 60)
    y = 160
    for k, sec in enumerate(s["sections"]):
        sp = cl((lt - 0.9 - k * 0.55) / 0.6)
        text(dd, (44, y), f"{k + 1}. {sec['title']}", F("sans_medium", 26), INK, 0, "lm", max_w=dw - 88)
        for j, row in enumerate(sec["rows"]):
            rp = cl((sp - j * 0.25) / 0.75)
            if rp <= 0:
                continue
            yy = y + 44 + j * 38
            dd.ellipse((44, yy - 6, 56, yy + 6), fill=console.vcol(row[1]))
            text(dd, (70, yy), row[0][:max(0, int(len(row[0]) * rp))], F("sans", 22), PC["ink2"], 0, "lm", max_w=dw - 200)
            if rp >= 1:
                text(dd, (dw - 44, yy), row[1], F("sans_medium", 22), console.vcol(row[1]), 0, "rm", max_w=140)
        y += 44 + len(sec["rows"]) * 38 + 30
    sgp = pr(lt, cue_t(s, "sign_at", c.dur - 1.2), 0.4)
    if sgp > 0:
        dd.line((44, dh - 76, dw - 44, dh - 76), fill=PC["line"], width=2)
        doc.alpha_composite(console.lucide("badge-check", 30, PC["allow"]), (44, dh - 58))
        text(dd, (86, dh - 43), s.get("signed", "Signed and published to 63 devices"), F("sans_medium", 23), PC["allow"] + (int(255 * sgp),), 0, "lm", max_w=dw - 130)
    zp = ease_in_out(cl(lt / c.dur))
    paste_scaled(im, doc, cxm, cym + (1 - ease_out(q)) * 60, lerp(0.96, 1.0, zp), min(1, q * 2))
    im = zoom_about(im, lerp(1.0, 1.06, zp), cxm, cym)
    return arr(im)


def record_card(s, rec, hl_p, w=1000):
    hgt = 330
    cd = card(w, hgt, 22)
    d = ImageDraw.Draw(cd)
    PC = console.PC
    text(d, (40, 52), rec["title"], F("sans_medium", 32), INK, -0.3, "lm", max_w=w * 0.55)
    col = console.vcol(rec["verdict"])
    fw = F("sans_medium", 24)
    d.ellipse((w - 190 - fw.getlength(rec["verdict"]) + 150, 45, w - 190 - fw.getlength(rec["verdict"]) + 164, 59), fill=col) if False else None
    ww = fw.getlength(rec["verdict"])
    d.ellipse((w - 40 - ww - 26, 45, w - 40 - ww - 12, 59), fill=col)
    d.text((w - 40, 52), rec["verdict"], font=fw, fill=col, anchor="rm")
    y = 110
    for k, ln in enumerate(rec["lines"]):
        f = F("mono" if ln.startswith("$") else "sans", 25)
        s_ = ln.lstrip("$ ")
        lw = min(w - 80, text_width(s_, f))
        p = cl(hl_p * len(rec["lines"]) - k)
        if p > 0:
            g = Image.new("RGBA", (int(lw) + 16, 34), (0, 0, 0, 0))
            ga = np.zeros((34, int(lw) + 16, 4), np.uint8)
            xs = np.linspace(0, 1, ga.shape[1])[None, :]
            ga[..., 0] = 255
            ga[..., 1] = (236 - 60 * xs).astype(np.uint8)
            ga[..., 2] = (90 - 50 * xs).astype(np.uint8)
            ga[..., 3] = ((xs <= p) * 200).astype(np.uint8)
            cd.alpha_composite(Image.fromarray(ga), (32, y - 17))
        if ln.startswith("$"):
            mono(d, (40, y), s_, 25, PC["ink2"], "lm", w - 80)
        else:
            text(d, (40, y), s_, f, INK if k == 0 else PC["ink2"], 0, "lm", max_w=w - 80)
        y += 50
    text(d, (w - 40, hgt - 34), rec.get("foot", ""), F("sans", 21), PC["ink3"], 0, "rm", max_w=w - 80)
    return cd


def b_records(c, s):
    lt = c.lt
    im = mesh(c.t)
    t_hist = cue_t(s, "history_at", 1.8)
    recs = s["records"]
    hp = ease_in_out(cl((lt - t_hist - 0.25) / 1.1))
    q = cl(lt / 0.45)
    hl = cl((lt - 0.4) / 1.0)
    # older records slide out underneath and the stack scrolls up
    for k in range(len(recs) - 1, 0, -1):
        if hp <= 0:
            break
        cd = G.cache(("rec", k), lambda: record_card(s, recs[k], 0))
        y = G.H / 2 + lerp(0, k * 310, hp) - hp * 330
        paste_scaled(im, cd, G.W / 2, y, 0.9, 0.55 * hp)
    top = record_card(s, recs[0], hl)
    y = G.H / 2 - hp * 330
    paste_scaled(im, top, G.W / 2, y + (1 - ease_out(q)) * 60, lerp(1.0, 0.9, hp), min(1, q * 2))
    bq = pr(lt, 1.0, 0.3) * (1 - hp)
    if bq > 0:
        d = ImageDraw.Draw(im)
        bx, by = G.W / 2, G.H / 2 + 225
        press = cl(1 - abs(lt - t_hist) / 0.16)
        d.rounded_rectangle((bx - 90, by - 26, bx + 90, by + 26), 10, fill=WHITE + (int(255 * bq),), outline=(210, 214, 226, int(255 * bq)), width=2)
        d.text((bx, by), s.get("history_label", "See history"), font=F("sans_medium", 23), fill=INK + (int(255 * bq),), anchor="mm")
        kx, ky = cursor_path(lt, [(0.6, G.W / 2 + 500, G.H + 40), (t_hist - 0.15, bx + 30, by + 6), (c.dur, bx + 60, by + 40)])
        cursor(im, kx, ky, press)
    return arr(im)


def b_tagline(c, s):
    lt = c.lt
    im = mesh(c.t)
    d = ImageDraw.Draw(im)
    t_logo = cue_t(s, "logo_at", c.dur - 2.5)
    out = pr(lt, t_logo - 0.35, 0.3)
    f = F("sans_medium", 50)
    for k, ln in enumerate(s["lines"]):
        p = pr(lt, 0.15 + k * 0.12, 0.5) * (1 - out)
        if p > 0:
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ui.rise(lay, (G.W / 2, G.H / 2 - 36 + k * 70), ln, f, INK, p, -0.8, "mm", max_w=G.W - 400)
            im.alpha_composite(fade(lay, min(1, p * 1.5)))
    if s.get("repo"):                                    # the open source repo: GitHub mark + owner/name
        rp = pr(lt, cue_t(s, "repo_at", 1.0), 0.5) * (1 - out)
        if rp > 0:
            gh = icon_img("github", 60)
            fr = F("sans_medium", 46)
            tw = text_width(s["repo"], fr, -0.6)
            x0 = G.W / 2 - (gh.width + 22 + tw) / 2
            y = G.H / 2 + 150 + (1 - rp) * 30
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            lay.alpha_composite(gh, (int(x0), int(y - gh.height / 2)))
            text(ImageDraw.Draw(lay), (x0 + gh.width + 22, y), s["repo"], fr, INK, -0.6, "lm", max_w=G.W - 400)
            ul = pr(lt, cue_t(s, "repo_at", 1.0) + 0.3, 0.6) * (1 - out)
            ImageDraw.Draw(lay).line((x0, y + 50, x0 + (gh.width + 22 + tw) * ul, y + 50), fill=INK + (255,), width=3)
            im.alpha_composite(fade(lay, min(1, rp * 1.6)))
    lp = cl((lt - t_logo) / 0.5)
    if lp > 0:
        lg = logo_lockup(170)
        paste_scaled(im, lg, G.W / 2, G.H / 2 - 30, back_out(lp, 1.2), min(1, lp * 2), shadow=False)
        up = pr(lt, t_logo + 0.4, 0.5)
        text(d, (G.W / 2, G.H / 2 + 110), s.get("url", "prismor.dev"), F("sans_medium", 40), tuple(int(lerp(G.lav1[i], INK[i], up)) for i in range(3)), -0.4, "mm", max_w=800)
    bk = pr(lt, c.dur - 0.6, 0.5)
    a = arr(im)
    return (a * (1 - bk)).astype(np.uint8) if bk > 0 else a


# ------------------------------------------------------------------ enterprise
def device_tile(sz, name=None, col=None):
    def mk():
        t = card(sz, sz, max(6, sz // 5))
        ico = console.lucide("laptop", int(sz * 0.46), console.PC["ink2"])
        t.alpha_composite(ico, ((sz - ico.width) // 2, int(sz * 0.36 - ico.height / 2)))
        d = ImageDraw.Draw(t)
        if name:
            text(d, (sz / 2, sz * 0.72), name, F("sans_medium", max(8, sz // 9)), INK, 0, "mm", max_w=sz * 0.86)
        r = max(3, sz // 18)
        d.ellipse((sz - r * 5, r * 3, sz - r * 3, r * 5), fill=col or console.PC["allow"])
        return t
    return G.cache(("dev", sz, name, col), mk)


def b_fleetwall(c, s):
    """One enrolled laptop; the camera pulls back and hundreds of devices light up around it in a wave."""
    lt = c.lt
    im = mesh(c.t)
    cols, rows, step, base = 25, 13, 84, 64
    t_fill = cue_t(s, "fill_at", 1.2)
    zp = ease_in_out(cl((lt - 0.4) / max(0.5, t_fill + 0.8 - 0.4)))
    z = lerp(6.0, 1.0, zp)
    cx0, cy0 = G.W / 2, G.H / 2
    PC = console.PC
    for r in range(rows):
        for k in range(cols):
            wx, wy = cx0 + (k - cols // 2) * step, cy0 + (r - rows // 2) * step
            dist = math.hypot(k - cols // 2, r - rows // 2)
            centre = dist == 0
            q = 1.0 if centre else cl((lt - t_fill + 0.9 - dist * 0.07) / 0.35)
            if q <= 0:
                continue
            sx, sy = cx0 + (wx - cx0) * z, cy0 + (wy - cy0) * z
            sz = base * z * (0.6 + 0.4 * back_out(q))
            if sx + sz < 0 or sx - sz > G.W or sy + sz < 0 or sy - sz > G.H:
                continue
            hv = h(k * 31 + r, 9)
            col = PC["block"] if hv > 0.97 else PC["warn"] if hv > 0.9 else PC["allow"]
            if centre:
                tile = device_tile(int(sz), "alice-mbp")
            else:
                tile = device_tile(base, None, col)
                if abs(sz - base) > 1:
                    tile = tile.resize((max(1, int(sz)), max(1, int(sz))), Image.BILINEAR)
            if q < 1:
                tile = fade(tile, q)
            im.alpha_composite(tile, (int(sx - tile.width / 2), int(sy - tile.height / 2)))
    cp = pr(lt, t_fill + 0.4, 0.5)
    if cp > 0:
        n = int(cols * rows * cp)
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        f = F("sans_medium", 44)
        label = f"{n} devices"
        tw = text_width(label, f, -0.6)
        wash = Image.new("L", im.size, 0)                  # a soft light wash behind the count, no box
        ImageDraw.Draw(wash).ellipse((G.W / 2 - tw / 2 - 160, G.H - 190, G.W / 2 + tw / 2 + 160, G.H - 30), fill=235)
        lay.paste((250, 249, 247, 255), (0, 0), wash.filter(ImageFilter.GaussianBlur(40)))
        text(ImageDraw.Draw(lay), (G.W / 2, G.H - 110), label, f, INK, -0.6, "mm", max_w=800)
        im.alpha_composite(fade(lay, cp))
    return arr(im)


HOLO = [(255, 170, 200), (255, 214, 150), (170, 240, 210), (150, 200, 255), (205, 165, 255)]


def b_reveal(c, s):
    """Black stage, chrome orbit, then the lockup: logo + Prismor + a holographic 'Enterprise'."""
    lt = c.lt
    im = Image.new("RGBA", (G.W, G.H), (6, 6, 10, 255))
    glow = pr(lt, 0.0, 1.2)
    g = mesh(c.t, 1.0).filter(ImageFilter.GaussianBlur(40))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse((G.W / 2 - 900, G.H / 2 - 420, G.W / 2 + 900, G.H / 2 + 420), fill=int(70 * glow))
    im.paste(g, (0, 0), m.filter(ImageFilter.GaussianBlur(160)))
    ang = lt * 0.9
    for name, rad, size, ph in ((s.get("obj_a", "chrome_torus"), 1.0, 380, 0.0), (s.get("obj_b", "chrome_key"), 1.0, 300, math.pi)):
        a = ang + ph
        depth = math.sin(a)
        if depth < 0:
            chrome(im, name, G.W / 2 + math.cos(a) * 760, G.H / 2 + depth * 260, int(size * (0.75 + 0.2 * depth)), a * 30, 6 * -depth, 0.85)
    t_ent = cue_t(s, "ent_at", 0.9)
    lg = logo_lockup(120)
    f = F("sans_medium", 118)
    w1 = text_width("Prismor", f, -2)
    w2 = text_width("Enterprise", f, -2)
    gap = 30
    total_final = lg.width + gap + w1 + 34 + w2
    ep = ease_in_out(cl((lt - t_ent) / 0.6))
    total = lerp(lg.width + gap + w1, total_final, ep)
    x = G.W / 2 - total / 2
    y = G.H / 2
    lp = cl((lt - 0.15) / 0.45)
    if lp > 0:
        paste_scaled(im, lg, x + lg.width / 2, y, back_out(lp, 1.3), min(1, lp * 2.5), shadow=False)
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ui.rise(lay, (x + lg.width + gap, y), "Prismor", f, (250, 250, 252), pr(lt, 0.3, 0.5), -2, "lm", max_w=G.W)
        im.alpha_composite(lay)
    if lt >= t_ent:
        q = pr(lt, t_ent + 0.15, 0.55)
        ex = x + lg.width + gap + w1 + 34
        mask = Image.new("L", im.size, 0)
        text(ImageDraw.Draw(mask), (ex, y), "Enterprise", f, 255, -2, "lm", max_w=G.W)
        bb = mask.getbbox()
        if bb:
            wv = int((bb[2] - bb[0]) * q)
            clip = Image.new("L", im.size, 0)
            ImageDraw.Draw(clip).rectangle((bb[0], bb[1] - 20, bb[0] + wv, bb[3] + 20), fill=255)
            mk = Image.fromarray(np.minimum(np.asarray(mask), np.asarray(clip)))
            holo = Image.fromarray(ui.holo_field(bb[2] - bb[0], bb[3] - bb[1], c.t * 1.4, HOLO, 0.8, 2))
            layer = Image.new("RGB", im.size, (0, 0, 0))
            layer.paste(holo, bb[:2])
            im.paste(layer, (0, 0), mk)
            if q < 1:
                dd = ImageDraw.Draw(im)
                dd.rectangle((bb[0] + wv, bb[1] - 14, bb[0] + wv + 5, bb[3] + 14), fill=(255, 255, 255))
        sub = pr(lt, t_ent + 0.9, 0.5)
        if sub > 0:
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ui.rise(lay, (G.W / 2, y + 130), s.get("sub", "The control plane for every AI agent in your company"), F("sans", 38), (190, 192, 204), sub, -0.3, "mm", max_w=G.W - 300)
            im.alpha_composite(lay)
    for name, rad, size, ph in ((s.get("obj_a", "chrome_torus"), 1.0, 380, 0.0), (s.get("obj_b", "chrome_key"), 1.0, 300, math.pi)):
        a = ang + ph
        depth = math.sin(a)
        if depth >= 0:
            chrome(im, name, G.W / 2 + math.cos(a) * 760, G.H / 2 + depth * 260, int(size * (0.75 + 0.2 * depth)), a * 30, 0, 1.0)
    return grain(arr(im), c.fi, 5)


def b_enroll(c, s):
    """A terminal card types the enroll command; enrolled devices stream into the coverage table beside it."""
    lt = c.lt
    im = mesh(c.t)
    PC = console.PC
    q = cl(lt / 0.45)
    tw, th = 760, 300
    term = card(tw, th, 22, (20, 21, 28), (44, 46, 58))
    d = ImageDraw.Draw(term)
    for k, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse((30 + k * 28, 28, 44 + k * 28, 42), fill=col)
    cmd = s.get("cmd", "prismor enroll acme-prod")
    n = int(cl((lt - 0.4) / (len(cmd) * 0.035)) * len(cmd))
    y = 100
    mono(d, (34, y), "$ " + cmd[:n], 28, (236, 236, 242), "lm", tw - 60)
    if n < len(cmd) or int(lt * 2.5) % 2 == 0:
        cxp = 34 + F("mono", 28).getlength("$ " + cmd[:n], features=ui.CODE_FEATURES) + 4
        d.rectangle((cxp, y - 16, cxp + 14, y + 16), fill=(236, 236, 242))
    done_t = 0.4 + len(cmd) * 0.035 + 0.3
    for k, ln in enumerate(s.get("out", [])):
        lp = cl((lt - done_t - k * 0.35) / 0.2)
        if lp > 0:
            mono(d, (34, y + 52 + k * 42), ln, 24, (150, 220, 170) if k == len(s["out"]) - 1 else (170, 172, 186), "lm", tw - 60)
    paste_scaled(im, term, 500, G.H / 2 + (1 - ease_out(q)) * 60, 1.15, min(1, q * 2))
    tp = cl((lt - done_t - 0.2) / 0.5)
    if tp > 0:
        tb = console.render("table", s["table"], lt - done_t, 900)
        paste_scaled(im, tb, 1420, G.H / 2 + (1 - ease_out(tp)) * 60, 0.88, min(1, tp * 2))
    return arr(im)


def b_panel(c, s):
    """One enterprise-console component, rising in on the pastel ground with a slow push."""
    lt = c.lt
    im = mesh(c.t)
    q = cl(lt / 0.5)
    comp = console.render(s["component"], s["data"], lt, s.get("w", 1400))
    sc = min(1.0, (G.W - 200) / comp.width, (G.H - 120) / comp.height) * lerp(0.96, 1.0, ease_in_out(cl(lt / c.dur)))
    paste_scaled(im, comp, G.W / 2, G.H / 2 + (1 - ease_out(q)) * 60, sc, min(1, q * 2))
    if s.get("caption"):
        d = ImageDraw.Draw(im)
        cp = pr(lt, 0.3, 0.5)
        mono(d, (G.W / 2, 60), s["caption"], 26, tuple(int(lerp(250, 60, cp)) for _ in range(3)), "mm", G.W - 400)
    return arr(im)


def b_ent_end(c, s):
    lt = c.lt
    im = mesh(c.t)
    t_repo = cue_t(s, "repo_at", 1.5)
    t_cta = cue_t(s, "cta_at", c.dur - 2.5)
    lg = logo_lockup(96)
    f = F("sans_medium", 92)
    w1, w2 = text_width("Prismor", f, -1.5), text_width("Enterprise", f, -1.5)
    total = lg.width + 26 + w1 + 26 + w2
    x = G.W / 2 - total / 2
    y = G.H / 2 - 150
    q = cl(lt / 0.5)
    paste_scaled(im, lg, x + lg.width / 2, y, back_out(q, 1.2), min(1, q * 2), shadow=False)
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ui.rise(lay, (x + lg.width + 26, y), "Prismor", f, INK, pr(lt, 0.1, 0.5), -1.5, "lm", max_w=G.W)
    im.alpha_composite(lay)
    mask = Image.new("L", im.size, 0)
    text(ImageDraw.Draw(mask), (x + lg.width + 26 + w1 + 26, y), "Enterprise", f, 255, -1.5, "lm", max_w=G.W)
    bb = mask.getbbox()
    ep = pr(lt, 0.25, 0.5)
    if bb and ep > 0:
        holo = ui.holo_field(bb[2] - bb[0], bb[3] - bb[1], c.t * 1.4, [(236, 90, 150), (240, 150, 60), (40, 170, 140), (60, 120, 230), (140, 90, 220)], 0.8, 2)
        layer = Image.new("RGB", im.size, (0, 0, 0))
        layer.paste(Image.fromarray(holo), bb[:2])
        im.paste(layer, (0, 0), mask.point(lambda v: int(v * ep)))
    lines = s.get("lines", [])
    for k, ln in enumerate(lines):
        p = pr(lt, 0.5 + k * 0.12, 0.5)
        if p > 0:
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ui.rise(lay, (G.W / 2, y + 120 + k * 60), ln, F("sans", 42), (60, 62, 74), p, -0.4, "mm", max_w=G.W - 400)
            im.alpha_composite(lay)
    rp = pr(lt, t_repo, 0.5)
    if rp > 0 and s.get("repo"):
        gh = icon_img("github", 54)
        fr = F("sans_medium", 42)
        tw = text_width(s["repo"], fr, -0.5)
        x0 = G.W / 2 - (gh.width + 20 + tw) / 2
        yy = y + 120 + len(lines) * 60 + 70 + (1 - rp) * 30
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        lay.alpha_composite(gh, (int(x0), int(yy - gh.height / 2)))
        dd = ImageDraw.Draw(lay)
        text(dd, (x0 + gh.width + 20, yy), s["repo"], fr, INK, -0.5, "lm", max_w=G.W - 400)
        dd.line((x0, yy + 46, x0 + (gh.width + 20 + tw) * pr(lt, t_repo + 0.3, 0.6), yy + 46), fill=INK + (255,), width=3)
        im.alpha_composite(fade(lay, min(1, rp * 1.6)))
    cp = pr(lt, t_cta, 0.5)
    if cp > 0:
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ui.rise(lay, (G.W / 2, G.H - 170), s.get("cta", "Book a demo at prismor.dev"), F("sans_medium", 50), INK, cp, -0.6, "mm", max_w=G.W - 400)
        im.alpha_composite(lay)
    bk = pr(lt, c.dur - 0.6, 0.5)
    a = arr(im)
    return (a * (1 - bk)).astype(np.uint8) if bk > 0 else a


BEATS = {"grid": b_grid, "photo": b_photo, "cutaway": b_cutaway, "doc": b_doc, "words": b_words, "brand": b_brand,
         "session": b_session, "approve": b_approve, "flow": b_flow, "records": b_records, "tagline": b_tagline,
         "fleetwall": b_fleetwall, "reveal": b_reveal, "enroll": b_enroll, "panel": b_panel, "ent_end": b_ent_end}


class Cut0:
    dur = 0.0


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    beats, tok = [], 0
    for k, b in enumerate(brief["beats"]):
        t0, tok = G.cue(b["at"], tok)
        b["_t0"], b["_tok"] = (0.0 if k == 0 else t0 - brief.get("lead", 0.08)), tok
        beats.append(b)
    end = G.vo_dur + brief.get("tail", 1.6)
    scenes = []
    for k, b in enumerate(beats):
        t1 = beats[k + 1]["_t0"] if k + 1 < len(beats) else end
        tr = {"fade": Dissolve(0.35, 6), "cut": None}.get(b.get("tr", "cut"))
        scenes.append(Scene(f"{k:02d}-{b['type']}", t1 - b["_t0"], (lambda bb: lambda c: BEATS[bb["type"]](c, bb))(b), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "assets", "voice", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    a = ap.parse_intermixed_args()
    if a.cmd == "init":                                  # start a new film from an example
        import shutil
        src = os.path.join(HERE, "..", "examples", (a.args[1:] or ["prismor"])[0])
        dst = os.path.abspath(a.args[0] if a.args else "film")
        if os.path.exists(dst):
            sys.exit(f"{dst} already exists")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", ".vo_*"))
        bp = os.path.join(dst, "brief.json")
        b = json.load(open(bp))
        if b.get("assets_dir", "assets").startswith(".."):
            shutil.copytree(os.path.normpath(os.path.join(src, b["assets_dir"])), os.path.join(dst, "assets"))
            b["assets_dir"] = "assets"
            json.dump(b, open(bp, "w"), indent=1, ensure_ascii=False)
        print(f"created {dst}: edit vo.txt, assets.json and brief.json, then assets → voice → check → still → render")
        return
    base = os.path.dirname(os.path.abspath(a.brief))
    brief = json.load(open(a.brief))
    if a.cmd == "assets":
        specs = json.load(open(os.path.join(base, brief.get("assets", "assets.json"))))
        for m in generate_images(specs, os.path.join(base, brief.get("assets_dir", "assets")), names=a.args or None):
            print(m)
        return
    if a.cmd == "voice":
        vo = brief["vo"]
        script = open(os.path.join(base, vo["script"])).read().strip()
        wav = narration.tts(script, os.path.join(base, "vo.wav"), model=vo.get("model", "gpt-4o-mini-tts-2025-12-15"),
                            voice=vo.get("voice", "marin"), instructions=vo.get("instructions"))
        json.dump(narration.transcribe_windows(wav), open(os.path.join(base, vo["words"]), "w"), indent=1)
        os.system(f"ffmpeg -v error -y -i {wav} -c:a aac -b:a 128k {os.path.join(base, vo['audio'])}")
        print("voice ok")
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 3)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep + ["! " + w for w in overflow_report(warn=True)]:
            print("  ", r)
        trail = [x for x in re.findall(r'"(?:lines|title|action|note|label|doc_title|signed|secret_note|done)": "([^"]*)"', json.dumps(brief["beats"])) if x.endswith(".")]
        if trail:
            print(f"  ! {len(trail)} on-screen lines end with a period, e.g. {trail[0]!r}")
        for s, st in zip(tl.scenes, tl.starts):
            print(f"  {st:6.2f}s  {s.dur:5.2f}s  {s.name}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} beats")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["2"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 4, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "film.mp4"), G.audio))


if __name__ == "__main__":
    main()
