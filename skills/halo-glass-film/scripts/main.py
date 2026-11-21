#!/usr/bin/env python3
"""halo-glass-film: a pale-grey, iridescent "labs launch" film (16:9, ~33 s, music only).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1.0 4 8.6 12.6 15.2 17.8 21 23.5 26 30 32
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a] [--ig]

A white ring with an orbiting dot floats on a pale grey ground over soft iridescent light, then lands as
the "o" of the brand's wordmark while the other letters slide in. The ring turns into a frosted glass
input card, a prompt is typed and applied. A huge light heading sits over glass metric cards with
gradient charts, a findings list by severity zooms into one finding whose fix row lights up and opens a
code card. A capsule chart falls, a tall gradient card fills with agent tiles, then one dot draws two
rings with the loop's four steps, the rings merge back into the wordmark, and the real logo closes.

Everything is drawn natively (no screenshots, no generated images) through a camera, so it stays sharp
when the camera pushes in. Copy lives in the brief. `--ig` also writes a 1080x1350 letterboxed cut.
"""
import argparse, functools, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Scene, Theme, Timeline, prog, lerp, hex2rgb, overflow_report
from framesmith import ease_out, ease_in_out
from framesmith.typography import fit, text_width, OVERFLOWS, SHRINKS, WARN_SCALE
from framesmith.typography import F as _F
from framesmith.score import Score, pluck

G = None


def eo(p):
    return ease_out(max(0.0, min(1.0, p)))


def eio(p):
    return ease_in_out(max(0.0, min(1.0, p)))


def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def back(p, k=1.5):
    """Ease out with a small overshoot (pop-ins)."""
    if p <= 0:
        return 0.0
    p = min(1.0, p) - 1
    return 1 + (k + 1) * p ** 3 + k * p ** 2


@functools.lru_cache(maxsize=512)
def F(role, size):
    return _F(role, max(4, int(size)))


def tw(s, role, size):
    return text_width(s, F(role, size))


def wrap(s, role, size, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if cur and tw(nxt, role, size) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ state
class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.W, self.H = brief.get("size", [1920, 1080])
        self.fps = brief.get("fps", 30)
        th = brief.get("theme", {})
        self.col = {k: hex2rgb(v) for k, v in th.items() if isinstance(v, str)}
        for k, v in {"ground": "#E2E2E4", "ink": "#17171A", "muted": "#86868E", "line": "#C6C6CC", "red": "#D5452F",
                     "amber": "#C27A16", "green": "#23935A", "accent": "#5672E0"}.items():
            self.col.setdefault(k, hex2rgb(v))
        self.col["white"] = (255, 255, 255)
        self.aura = [hex2rgb(v) for v in th.get("aura", ["#86E3F2", "#A9F2D6", "#B3A6F6", "#F5B3DA", "#8FA8F0"])]
        self.th = Theme.from_dict({"ink": th.get("ink", "#17171A"), "paper": th.get("ground", "#E2E2E4")})
        self.dir = os.path.join(base, brief.get("assets_dir", "assets"))
        self.S = self.W / 1920
        self._img = {}
        aw, ah = 240, 135
        yy, xx = np.mgrid[0:ah, 0:aw].astype(np.float32)
        self.ax, self.ay = (xx + 0.5) * 1920 / aw, (yy + 0.5) * 1080 / ah
        rng = np.random.default_rng(3)
        self.grain = (rng.random((self.H, self.W, 1), np.float32) - 0.5) * 2.2
        self.WM = 300
        self.o_idx = self.c["brand"].lower().find("o")
        self._wordmark()

    def image(self, name):
        if name not in self._img:
            path = os.path.join(self.dir, "logo.png") if name == "logo" else os.path.join(self.dir, "icons", name + ".png")
            im = None
            if os.path.exists(path):
                im = Image.open(path).convert("RGBA")
                bb = im.getchannel("A").getbbox()
                im = im.crop(bb) if bb else im
            self._img[name] = im
        return self._img[name]

    def _wordmark(self):
        """The brand drawn huge; its first 'o' is replaced by a ring so the ring can travel in and out."""
        s, size = self.c["brand"], self.WM
        f = F("sans", size)
        x = 960 - text_width(s, f) / 2
        self.letters = []
        for ch in s:
            self.letters.append((ch, x))
            x += f.getlength(ch)
        self.base_y = 640
        if self.o_idx >= 0:
            l, t, r, b = f.getbbox("o", anchor="ls")
            ox = self.letters[self.o_idx][1]
            im = Image.new("L", (int(r - l) + 8, int(b - t) + 8), 0)
            ImageDraw.Draw(im).text((4 - l, 4 - t), "o", font=f, fill=255, anchor="ls")
            row = np.asarray(im)[im.height // 2] > 127
            xs = np.flatnonzero(row)
            stroke = 0.09 * size
            if len(xs):
                runs = np.split(xs, np.flatnonzero(np.diff(xs) > 1) + 1)
                stroke = float(len(runs[0]))
            self.o_c = (ox + (l + r) / 2, self.base_y + (t + b) / 2)
            self.o_r = (r - l) / 2 - stroke / 2
            self.o_w = stroke
        else:
            self.o_c, self.o_r, self.o_w = (960, 540), 90, 26


def C(name, a=1.0):
    c = G.col.get(name, name) if isinstance(name, str) else name
    return tuple(int(v) for v in c[:3]) + (int(255 * cl(a)),)


# ------------------------------------------------------------------ painter: design units → camera → pixels
class P:
    def __init__(self, cam=(960, 540, 1.0), blobs=()):
        self.cx, self.cy, self.z = cam
        self.S = G.S
        self.img = aura([(self.X(x) / self.S, self.Y(y) / self.S, r * self.z, c, a) for x, y, r, c, a in blobs])

    def X(self, x):
        return ((x - self.cx) * self.z + 960) * self.S

    def Y(self, y):
        return ((y - self.cy) * self.z + 540) * self.S

    def u(self, v):
        return v * self.z * self.S

    def box(self, b):
        return (self.X(b[0]), self.Y(b[1]), self.X(b[2]), self.Y(b[3]))

    def comp(self, layer, x, y):
        W, H = self.img.size
        x, y = int(round(x)), int(round(y))
        l, t, r, b = max(0, x), max(0, y), min(W, x + layer.width), min(H, y + layer.height)
        if r <= l or b <= t:
            return
        self.img.alpha_composite(layer.crop((l - x, t - y, r - x, b - y)), (l, t))

    def rrect(self, b, r, fill=None, outline=None, w=1.0, ss=2):
        """Anti-aliased rounded rect (design units) with RGBA fill/outline."""
        x0, y0, x1, y1 = self.box(b)
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        ww = self.u(w) if outline else 0
        pad = ww + 2
        X0, Y0 = math.floor(x0 - pad), math.floor(y0 - pad)
        W, H = int(math.ceil(x1 + pad) - X0), int(math.ceil(y1 + pad) - Y0)
        if W > 5000 or H > 5000:
            return
        lay = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        rr = min(self.u(r), (x1 - x0) / 2, (y1 - y0) / 2) * ss
        bx = ((x0 - X0) * ss, (y0 - Y0) * ss, (x1 - X0) * ss, (y1 - Y0) * ss)
        ImageDraw.Draw(lay).rounded_rectangle(bx, radius=max(0, rr), fill=fill, outline=outline,
                                              width=max(1, round(ww * ss)) if outline else 0)
        self.comp(lay.resize((W, H), Image.LANCZOS), X0, Y0)

    def mask(self, b, r, ss=3):
        x0, y0, x1, y1 = self.box(b)
        X0, Y0 = int(math.floor(x0)), int(math.floor(y0))
        W, H = max(1, int(math.ceil(x1)) - X0), max(1, int(math.ceil(y1)) - Y0)
        m = Image.new("L", (W * ss, H * ss), 0)
        rr = min(self.u(r), (x1 - x0) / 2, (y1 - y0) / 2) * ss
        ImageDraw.Draw(m).rounded_rectangle(((x0 - X0) * ss, (y0 - Y0) * ss, (x1 - X0) * ss - 1, (y1 - Y0) * ss - 1),
                                            radius=max(0, rr), fill=255)
        return m.resize((W, H), Image.LANCZOS), X0, Y0

    def shadow(self, b, r, a=0.10, spread=34, dy=18):
        if a <= 0:
            return
        x0, y0, x1, y1 = self.box(b)
        sp, oy, q = self.u(spread), self.u(dy), 6
        X0, Y0 = int(x0 - 2 * sp), int(y0 - 2 * sp + oy)
        W, H = int(x1 - x0 + 4 * sp), int(y1 - y0 + 4 * sp)
        if W <= q or H <= q:
            return
        m = Image.new("L", (W // q, H // q), 0)
        ImageDraw.Draw(m).rounded_rectangle((2 * sp / q, 2 * sp / q, (x1 - x0 + 2 * sp) / q, (y1 - y0 + 2 * sp) / q),
                                            radius=self.u(r) / q, fill=int(255 * cl(a)))
        m = m.filter(ImageFilter.GaussianBlur(max(1, sp / q / 1.7))).resize((W, H), Image.BILINEAR)
        lay = Image.new("RGBA", (W, H), (40, 40, 60, 0))
        lay.putalpha(m)
        self.comp(lay, X0, Y0)

    def glass(self, b, r=26, a=1.0, tint=0.0, frost=0.62, shadow=0.09, edge=0.9):
        """Frosted glass card: the frame under it blurred and lifted toward white, a bright rim, a soft shadow.
        tint (0..1) washes the lower part with the aura colours, like light coming through."""
        if a <= 0:
            return
        x0, y0, x1, y1 = self.box(b)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        self.shadow(b, r, shadow * a)
        m, X0, Y0 = self.mask(b, r)
        W, H = m.size
        reg = self.img.crop((X0, Y0, X0 + W, Y0 + H))
        q = 8
        sm = reg.resize((max(1, W // q), max(1, H // q)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2.5))
        reg = Image.blend(sm.resize((W, H), Image.BILINEAR), Image.new("RGBA", (W, H), (255, 255, 255, 255)), frost)
        if tint > 0:
            g = hgrad(W, H, [G.aura[0], G.aura[4], G.aura[2]])
            ys = np.linspace(0, 1, H, dtype=np.float32)[:, None]
            al = (np.clip((ys - 0.25) / 0.75, 0, 1) ** 1.4 * 255 * tint).astype(np.uint8)
            g.putalpha(Image.fromarray(np.ascontiguousarray(np.broadcast_to(al, (H, W)))))
            reg.alpha_composite(g)
        reg.putalpha(m.point(lambda v: int(v * a)))
        self.comp(reg, X0, Y0)
        if edge > 0:
            self.rrect(b, r, outline=C("white", edge * a), w=1.6)

    def ring(self, x, y, r, w, col="white", a=1.0, a0=0.0, a1=360.0, glow=0.0):
        """Anti-aliased ring (design units). a0/a1: arc in degrees clockwise from 12 o'clock."""
        if a <= 0 or r <= 0 or a1 <= a0:
            return
        if glow > 0:
            self.ring(x, y, r, w * 1.7, "white", a * glow * 0.22, a0, a1)
        X, Y, R, Wd = self.X(x), self.Y(y), self.u(r), max(0.8, self.u(w))
        pad = Wd / 2 + 2
        W, H = self.img.size
        X0, Y0 = max(0, int(math.floor(X - R - pad))), max(0, int(math.floor(Y - R - pad)))
        X1, Y1 = min(W, int(math.ceil(X + R + pad))), min(H, int(math.ceil(Y + R + pad)))
        if X1 <= X0 or Y1 <= Y0:
            return
        yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        dx, dy = xx + 0.5 - X, yy + 0.5 - Y
        d = np.sqrt(dx * dx + dy * dy)
        cov = np.clip(Wd / 2 - np.abs(d - R) + 0.5, 0, 1)
        if a1 - a0 < 359.9:
            ang = (np.degrees(np.arctan2(dx, -dy)) + 360) % 360
            span = (ang - a0 % 360) % 360
            cov *= np.clip(((a1 - a0) - span) * R * math.pi / 180 + 0.5, 0, 1)
        self._paint(cov * a, col, X0, Y0)

    def disc(self, x, y, r, col="ink", a=1.0):
        if a <= 0 or r <= 0:
            return
        X, Y, R = self.X(x), self.Y(y), self.u(r)
        W, H = self.img.size
        X0, Y0 = max(0, int(X - R - 2)), max(0, int(Y - R - 2))
        X1, Y1 = min(W, int(X + R + 3)), min(H, int(Y + R + 3))
        if X1 <= X0 or Y1 <= Y0:
            return
        yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        d = np.sqrt((xx + 0.5 - X) ** 2 + (yy + 0.5 - Y) ** 2)
        self._paint(np.clip(R - d + 0.5, 0, 1) * a, col, X0, Y0)

    def _paint(self, cov, col, X0, Y0):
        c = C(col)
        h, w = cov.shape
        lay = np.empty((h, w, 4), np.uint8)
        lay[..., :3] = c[:3]
        lay[..., 3] = (cov * 255).astype(np.uint8)
        self.comp(Image.fromarray(lay, "RGBA"), X0, Y0)

    def line(self, pts, col, w=2.0, a=1.0, ss=3):
        if a <= 0 or len(pts) < 2:
            return
        sp = [(self.X(x), self.Y(y)) for x, y in pts]
        xs, ys = [p[0] for p in sp], [p[1] for p in sp]
        pad = self.u(w) + 3
        X0, Y0 = math.floor(min(xs) - pad), math.floor(min(ys) - pad)
        W, H = int(math.ceil(max(xs) + pad) - X0), int(math.ceil(max(ys) + pad) - Y0)
        lay = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        ImageDraw.Draw(lay).line([((x - X0) * ss, (y - Y0) * ss) for x, y in sp], fill=C(col, a),
                                 width=max(1, round(self.u(w) * ss)), joint="curve")
        self.comp(lay.resize((W, H), Image.LANCZOS), X0, Y0)

    def hair(self, x, y0, y1, a=1.0, col="line"):
        X, Y0, Y1 = int(round(self.X(x))), int(self.Y(y0)), int(self.Y(y1))
        if Y1 > Y0 and a > 0:
            self.comp(Image.new("RGBA", (1, Y1 - Y0), C(col, a)), X, Y0)

    def rule(self, x0, x1, y, a=1.0, col="line"):
        X0, X1, Y = int(self.X(x0)), int(self.X(x1)), int(round(self.Y(y)))
        if X1 > X0 and a > 0:
            self.comp(Image.new("RGBA", (X1 - X0, 1), C(col, a)), X0, Y)

    def area(self, b, vals, p=1.0, a=1.0):
        """Gradient area chart inside box b (design units), revealed left to right by p."""
        if p <= 0 or a <= 0:
            return
        n = len(vals)
        lo, hi = min(vals), max(vals)
        dp = [(b[0] + (b[2] - b[0]) * i / (n - 1), b[3] - (b[3] - b[1]) * (0.12 + 0.88 * (v - lo) / max(1e-6, hi - lo)))
              for i, v in enumerate(vals)]
        x0, y0, x1, y1 = self.box(b)
        W, H = int(x1 - x0) + 2, int(y1 - y0) + 2
        if W < 4 or H < 4:
            return
        ss = 2
        m = Image.new("L", (W * ss, H * ss), 0)
        poly = [((self.X(x) - x0) * ss, (self.Y(y) - y0) * ss) for x, y in dp] + [(W * ss, H * ss), (0, H * ss)]
        ImageDraw.Draw(m).polygon(poly, fill=255)
        m = np.asarray(m.resize((W, H), Image.LANCZOS), np.float32) / 255
        m[:, max(0, int(W * p)):] = 0
        ys = np.linspace(1.0, 0.3, H, dtype=np.float32)[:, None]
        g = hgrad(W, H, [G.aura[0], G.aura[4], G.aura[2]])
        g.putalpha(Image.fromarray((m * ys * a * 255).astype(np.uint8)))
        self.comp(g, int(x0), int(y0))
        k = p * (n - 1)
        kk = int(k)
        path = dp[: kk + 1]
        if kk < n - 1:
            f = k - kk
            path = path + [(lerp(dp[kk][0], dp[kk + 1][0], f), lerp(dp[kk][1], dp[kk + 1][1], f))]
        self.line(path, "white", 3, a)

    # -- text
    def text(self, x, y, s, role, size, col="ink", a=1.0, anchor="ls", max_w=None, fit_to=None, rise=1.0):
        if not s or a <= 0 or rise <= 0:
            return
        if max_w is not None:
            ref = fit_to or s
            if tw(ref, role, size) > max_w:
                f2 = fit(ref, F(role, size), max_w)
                k = f2.size / size
                if k < WARN_SCALE:
                    SHRINKS.append((ref, k))
                if tw(ref, role, f2.size) > max_w + 1:
                    OVERFLOWS.append((ref, int(tw(ref, role, f2.size)), int(max_w)))
                size = f2.size
        f = F(role, self.u(size))
        l, t, r, b = f.getbbox(s, anchor=anchor)
        im = Image.new("RGBA", (int(r - l) + 6, int(b - t) + 6), (0, 0, 0, 0))
        kw = {"features": ["-liga", "-calt"]} if role.startswith("mono") else {}
        ImageDraw.Draw(im).text((3 - l, 3 - t), s, font=f, fill=C(col, a), anchor=anchor, **kw)
        X, Y = self.X(x) + l - 3, self.Y(y) + t - 3
        if rise < 1:
            # masked rise: the line slides up inside its own box
            dy = int(round((1 - eo(rise)) * im.height))
            if dy >= im.height:
                return
            im = im.crop((0, 0, im.width, im.height - dy))
            k = cl(rise * 1.6)
            im.putalpha(im.getchannel("A").point(lambda v: int(v * k)))
            Y += dy
        self.comp(im, X, Y)

    def icon(self, name, x, y, size, a=1.0):
        im = G.image(name)
        if im is None or a <= 0 or size <= 0:
            return
        px = max(2, int(self.u(size)))
        k = px / max(im.size)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        if a < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        self.comp(im, self.X(x) - im.width / 2, self.Y(y) - im.height / 2)

    def out(self):
        arr = np.asarray(self.img.convert("RGB"), np.float32) + G.grain
        return np.clip(arr, 0, 255).astype(np.uint8)


def hgrad(W, H, cols):
    cols = np.array(cols, np.float32)
    xs = np.linspace(0, len(cols) - 1, W, dtype=np.float32)
    i = np.clip(xs.astype(int), 0, len(cols) - 2)
    f = (xs - i)[:, None]
    row = cols[i] * (1 - f) + cols[i + 1] * f
    arr = np.ascontiguousarray(np.broadcast_to(row[None], (H, W, 3))).astype(np.uint8)
    return Image.fromarray(np.dstack([arr, np.full((H, W), 255, np.uint8)]), "RGBA")


def aura(blobs):
    """Pale ground with soft iridescent light pools. blobs: (x, y, radius, aura index or rgb, alpha) in screen design units."""
    out = np.empty(G.ax.shape + (3,), np.float32)
    out[:] = G.col["ground"]
    for x, y, r, c, a in blobs:
        if a <= 0:
            continue
        rgb = np.array(G.aura[c % len(G.aura)] if isinstance(c, int) else c, np.float32)
        wgt = a * np.exp(-((G.ax - x) ** 2 + (G.ay - y) ** 2) / (2 * (r * 0.5) ** 2))
        out += wgt[..., None] * (rgb - out)
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).resize((G.W, G.H), Image.BICUBIC)
    return im.convert("RGBA")


def cam(t, keys):
    if t <= keys[0][0]:
        return keys[0][1:]
    for (t0, x0, y0, z0), (t1, x1, y1, z1) in zip(keys, keys[1:]):
        if t <= t1:
            p = eio(prog(t, t0, t1))
            return lerp(x0, x1, p), lerp(y0, y1, p), math.exp(lerp(math.log(z0), math.log(z1), p))
    return keys[-1][1:]


def drift(t):
    return math.sin(t * 0.7) * 30, math.cos(t * 0.53) * 22


# ------------------------------------------------------------------ shared pieces
def wordmark(pp, t, enter=1.0, leave=0.0, ring_c=None, ring_r=None, ring_w=None, ring_a=1.0, dot=True):
    """Brand letters in solid white; the 'o' is a ring with a small ink dot orbiting it."""
    n = len(G.letters)
    for i, (ch, x) in enumerate(G.letters):
        if i == G.o_idx:
            continue
        side = -1 if i < G.o_idx else 1
        k = abs(i - G.o_idx)
        pe = eo((enter - 0.06 * k) / 0.7) if enter < 1 else 1.0
        pl = eio((leave - 0.04 * (n - k)) / 0.6) if leave > 0 else 0.0
        off = side * (1 - pe) * (260 + 90 * k) + side * pl * (300 + 80 * k)
        a = pe * (1 - pl)
        if a > 0:
            pp.text(x + off, G.base_y, ch, "sans", G.WM, "white", a)
    c = ring_c or G.o_c
    r = ring_r if ring_r is not None else G.o_r
    w = ring_w if ring_w is not None else G.o_w
    pp.ring(c[0], c[1], r, w, "white", ring_a, glow=0.5)
    if dot and ring_a > 0:
        ang = t * 2 * math.pi / 2.4
        pp.disc(c[0] + math.sin(ang) * r, c[1] - math.cos(ang) * r, max(4, w * 0.2), "ink", ring_a)


def word_blobs(t, a=1.0):
    dx, dy = drift(t)
    ox, oy = G.o_c
    x0 = G.letters[0][1]
    x1 = G.letters[-1][1] + 120
    return [(x0 + 120 + dx, 560 + dy, 520, 2, 0.55 * a), (ox + dy, oy + 40 - dx, 460, 0, 0.75 * a),
            (x1 - 80 - dx, 600, 420, 1, 0.6 * a), (ox - 260 + dy * 2, 450, 300, 3, 0.35 * a),
            (960 + dx * 3, 380 + dy, 700, 4, 0.18 * a)]


def rails(pp, xs, y0, y1, p, labels=(), a=1.0):
    """Vertical hairlines that draw downward, with small ticks and tiny mono marks."""
    for i, x in enumerate(xs):
        q = eo((p - 0.08 * i) / 0.8)
        if q <= 0:
            continue
        ye = lerp(y0, y1, q)
        pp.hair(x, y0, ye, a)
        for k in range(6):
            yk = y0 + (y1 - y0) * k / 5
            if yk <= ye:
                pp.rule(x - 4, x + 4, yk, a)
        if i < len(labels):
            pp.text(x + 10, y0 + 14, labels[i], "mono", 13, "muted", a * q)


def dot_grid(pp, x, y, cols, rows, gap, r, t0, t, a=1.0):
    for j in range(rows):
        for i in range(cols):
            q = back((t - t0 - 0.05 * (i + j)) / 0.35)
            if q > 0:
                pp.disc(x + i * gap, y + j * gap, r * q, "white", a * cl(q))


def brand_row(pp, y, a, size=1.0):
    """Real logo + brand name + kicker, centred."""
    if a <= 0:
        return
    lh, fs, ks = 40 * size, 30 * size, 22 * size
    name, kick = G.c["brand"], G.c.get("kicker", "")
    w = lh + 14 * size + tw(name, "sans_medium", fs) + (18 * size + tw(kick, "sans", ks) if kick else 0)
    x = 960 - w / 2
    pp.icon("logo", x + lh / 2, y, lh, a)
    x += lh + 14 * size
    pp.text(x, y, name, "sans_medium", fs, "ink", a, "lm")
    x += tw(name, "sans_medium", fs) + 18 * size
    if kick:
        pp.text(x, y + 1, kick, "sans", ks, "muted", a, "lm")


# ------------------------------------------------------------------ scenes
HALO = (960, 540, 230, 30)          # opening ring: centre x, y, radius, stroke


def s_halo(c):
    t = c.lt
    ap = eo(t / 0.5)
    lv = eio(prog(t, c.dur - 0.75, c.dur))
    pp = P((960, 540, 1.0 + 0.05 * eio(t / c.dur)), word_blobs(t, 0.6 + 0.4 * ap))
    m = eio(prog(t, 1.05, 1.85))
    hx, hy, hr, hw = HALO
    rc = (lerp(hx, G.o_c[0], m), lerp(hy, G.o_c[1], m))
    rr, rw = lerp(hr, G.o_r, m) * (0.86 + 0.14 * ap), lerp(hw, G.o_w, m)
    if lv > 0:
        rc = (lerp(rc[0], hx, lv), lerp(rc[1], hy, lv))
        rr, rw = lerp(rr, 200, lv), lerp(rw, 30, lv)
    wordmark(pp, t, enter=prog(t, 1.2, 2.2), leave=prog(t, c.dur - 0.8, c.dur - 0.1) * 1.6,
             ring_c=rc, ring_r=rr, ring_w=rw, ring_a=ap)
    brand_row(pp, 300, eo(prog(t, 1.9, 2.5)) * (1 - eo(prog(t, c.dur - 0.9, c.dur - 0.5))))
    lines = G.c.get("lines", [])[:2]
    for i, s in enumerate(lines):
        t0 = 2.9 + i * 1.75
        t1 = t0 + 1.55 if i < len(lines) - 1 else c.dur - 0.85
        if t0 <= t < t1 + 0.4:
            out = eio(prog(t, t1, t1 + 0.35))
            pp.text(960, 790 - 30 * out, s, "sans", 40, "ink", 1 - out, "ms", max_w=1400, rise=prog(t, t0, t0 + 0.5))
    return pp.out()


CARD = (610, 400, 1310, 640)
BTN = (610, 664, 1310, 724)


def s_policy(c):
    t, b = c.lt, G.b["policy"]
    z = 1.0 + 0.32 * eio(prog(t, c.dur - 0.55, c.dur))
    pp = P((960, 560, z), [(700, 560, 620, 2, 0.5), (1250, 600, 560, 0, 0.6), (960, 760, 500, 1, 0.4),
                           (1400, 360, 380, 3, 0.25)])
    rails(pp, (380, 470, 1450, 1540), 150, 930, prog(t, 0.1, 1.3), b.get("rails", []))
    m = eio(prog(t, 0.0, 0.6))
    hx, hy = HALO[:2]
    rb = (hx - 200, hy - 200, hx + 200, hy + 200)
    bx = tuple(lerp(rb[i], CARD[i], m) for i in range(4))
    rad = lerp(200, 28, m)
    if m < 1:
        pp.rrect(bx, rad, outline=C("white", 1 - m * 0.6), w=lerp(30, 2, m))
    pp.glass(bx, rad, a=m, tint=0.55 * m)
    a = eo(prog(t, 0.45, 0.8))
    cw = CARD[2] - CARD[0]
    pp.text(CARD[0], CARD[1] - 22, b["label"], "sans_medium", 22, "muted", a)
    if t < 1.15:
        pp.text(CARD[0] + 36, CARD[1] + 62, b["placeholder"], "sans", 30, "muted", a * (1 - eo(prog(t, 0.95, 1.15))),
                max_w=cw - 72)
    tp = prog(t, 1.15, 2.25)
    if tp > 0:
        n = int(round(len(b["prompt"]) * tp))
        lines = wrap(b["prompt"], "sans", 34, cw - 80)
        k = 0
        for i, ln in enumerate(lines):
            vis = ln[: max(0, n - k)]
            k += len(ln) + 1
            pp.text(CARD[0] + 36, CARD[1] + 66 + i * 46, vis, "sans", 34, "ink", 1, max_w=cw - 72)
            if n < k or i == len(lines) - 1:
                cx = CARD[0] + 36 + tw(vis, "sans", 34) + 4
                if tp < 1 or int(t / 0.3) % 2 == 0:
                    pp.rrect((cx, CARD[1] + 36 + i * 46, cx + 3, CARD[1] + 74 + i * 46), 1, fill=C("accent"))
                break
    ba = eo(prog(t, 0.55, 0.95))
    pp.glass(BTN, 16, a=ba, frost=0.7, shadow=0.06)
    fp = eio(prog(t, 2.45, 3.05))
    if fp > 0:
        m2, mx, my = pp.mask(BTN, 16)
        W = int(m2.width * fp)
        if W > 2:
            g = hgrad(m2.width, m2.height, [G.aura[0], G.aura[4], G.aura[2]]).crop((0, 0, W, m2.height))
            g.putalpha(m2.crop((0, 0, W, m2.height)).point(lambda v: int(v * 0.85)))
            pp.comp(g, mx, my)
    my_ = (BTN[1] + BTN[3]) / 2
    pp.text(960, my_, b["button"], "sans_medium", 24, "ink", ba, "mm", max_w=cw - 140)
    pp.ring(BTN[2] - 32, my_, 10, 2, "ink", ba * 0.6)
    if fp >= 1:
        pp.line([(BTN[2] - 37, my_), (BTN[2] - 33, my_ + 4), (BTN[2] - 26, my_ - 5)], "ink", 2.2, ba)
    return pp.out()


def s_stats(c):
    t, b = c.lt, G.b["stats"]
    cx, cy, z = cam(t, [(0, 720, 430, 1.32), (1.7, 720, 440, 1.3), (2.6, 960, 560, 1.0), (c.dur, 975, 560, 0.98)])
    pp = P((cx, cy, z), [(500, 700, 700, 0, 0.45), (1100, 900, 600, 2, 0.4), (1500, 400, 500, 1, 0.35),
                         (300, 300, 400, 3, 0.25)])
    pp.ring(290, 262, 6, 1.6, "ink", eo(t / 0.4))
    pp.text(312, 300, b["heading"], "sans", 140, "ink", 1, rise=prog(t, 0.0, 0.55), max_w=800)
    boxes = [(300, 340, 1100, 560), (300, 590, 1100, 715), (300, 745, 1100, 870)]
    for i, (card, bx) in enumerate(zip(b["cards"][:3], boxes)):
        t0 = 0.25 if i == 0 else 1.9 + 0.2 * i
        a = eo(prog(t, t0, t0 + 0.45))
        if a <= 0:
            continue
        off = (1 - a) * 40
        bx = (bx[0], bx[1] + off, bx[2], bx[3] + off)
        pp.glass(bx, 24, a, tint=0.35 if i == 0 else 0.15)
        pp.text(bx[0] + 28, bx[1] + 42, card["label"], "sans_medium", 22, "ink", a, max_w=400)
        vp = eo(prog(t, t0 + 0.2, t0 + 1.4))
        vs = f"{int(round(card['value'] * vp)):,}" + (f" of {card['of']}" if "of" in card else "")
        pp.text(bx[2] - 28, bx[1] + 42, vs, "sans_medium", 26, "ink", a, "rs")
        inner = (bx[0] + 28, bx[1] + 64, bx[2] - 28, bx[3] - 22)
        if card["kind"] == "area":
            pp.area(inner, card["series"], eio(prog(t, t0 + 0.2, t0 + 1.5)), a)
        elif card["kind"] == "bars":
            sr = card["series"]
            n, mx = len(sr), max(sr)
            bw = (inner[2] - inner[0]) / n
            for k, val in enumerate(sr):
                q = eo(prog(t, t0 + 0.2 + 0.05 * k, t0 + 0.6 + 0.05 * k))
                h = (inner[3] - inner[1]) * val / mx * q
                last = k == n - 1
                if h > 1:
                    pp.rrect((inner[0] + k * bw + 6, inner[3] - h, inner[0] + (k + 1) * bw - 6, inner[3]), 6,
                             fill=C("red" if last else G.aura[4], a * (0.9 if last else 0.75)))
        else:
            n = card.get("of", card["value"])
            sw = (inner[2] - inner[0]) / n
            for k in range(n):
                q = eo(prog(t, t0 + 0.2 + 0.08 * k, t0 + 0.5 + 0.08 * k))
                fill = C(G.aura[[0, 4, 2][k % 3]], a * (0.3 + 0.65 * q * (k < card["value"])))
                pp.rrect((inner[0] + k * sw + 5, inner[1] + 6, inner[0] + (k + 1) * sw - 5, inner[3] - 4), 8, fill=fill)
    # live activity column on the right
    fa = eo(prog(t, 1.9, 2.5))
    if fa > 0:
        pp.text(1180, 365, "LIVE ACTIVITY", "mono_medium", 15, "muted", fa)
        pp.hair(1160, 340, 870, fa)
        scroll = max(0.0, t - 2.0) * 22
        for i, (tm, agent, cmd, verdict, col) in enumerate(b["feed"]):
            y = 420 + i * 46 - scroll
            if y < 395 or y > 870:
                continue
            q = eo(prog(t, 1.95 + 0.06 * i, 2.35 + 0.06 * i)) * fa * cl((y - 395) / 30) * cl((870 - y) / 40)
            pp.text(1180, y, tm, "mono", 16, "muted", q)
            pp.text(1240, y, agent, "sans_medium", 18, "ink", q, max_w=150)
            pp.text(1400, y, cmd, "mono", 16, "ink", q, max_w=200)
            pp.text(1680, y, verdict, "mono_medium", 16, col, q, "rs")
    return pp.out()


def s_findings(c):
    t, b = c.lt, G.b["findings"]
    cx, cy, z = cam(t, [(0, 960, 600, 1.0), (0.55, 960, 560, 1.0), (c.dur, 720, 290, 2.3)])
    pp = P((cx, cy, z), [(900, 600, 700, 0, 0.4), (1300, 300, 500, 2, 0.35), (500, 800, 500, 1, 0.35)])
    rails(pp, (420, 1500), 120, 960, 1.0)
    dot_grid(pp, 1560, 300, 2, 4, 44, 14, 0.1, t)
    y = 260
    for gi, g in enumerate(b["groups"]):
        a = eo(prog(t, 0.05 * gi, 0.05 * gi + 0.3))
        pp.ring(569, y - 7, 9, 2, g["col"], a)
        pp.text(590, y, g["level"], "mono_medium", 18, g["col"], a)
        y += 46
        for txt, where in g["rows"]:
            pp.text(560, y, txt, "sans", 24, "ink", a, max_w=580)
            pp.text(1380, y, where, "mono", 15, "muted", a, "rs", max_w=220)
            pp.rule(560, 1380, y + 18, a)
            y += 48
        y += 30
    return pp.out()


def s_detail(c):
    t, d = c.lt, G.b["detail"]
    fi = d.get("focus", 1)
    push = eio(prog(t, 1.55, 2.2))
    rows_y = [370, 490, 610]
    fy = rows_y[fi]
    cx, cy, z = cam(t, [(0, 920, 450, 1.0), (1.5, 920, 450, 1.0), (2.2, 960, fy + 70, 1.12), (c.dur, 960, fy + 70, 1.16)])
    pp = P((cx, cy, z), [(700, 500, 700, 2, 0.45), (1250, 650, 600, 0, 0.5), (900, 250, 500, 1, 0.3)])
    rails(pp, (330, 1500), 120, 960, 1.0)
    dim = 1 - 0.65 * eo(prog(t, 1.0, 1.5))
    for j in range(4):                                   # dot-matrix mark
        for i in range(4):
            if (i + j) % 3 != 1:
                pp.disc(410 + i * 17, 205 + j * 17, 5.5, "ink", eo(prog(t, 0.02 * (i + j), 0.3 + 0.02 * (i + j))) * dim)
    for i, ln in enumerate(d["heading"][:2]):
        pp.text(500, 238 + i * 56, ln, "sans", 50, "ink", dim, max_w=1000, rise=prog(t, 0.05 + 0.1 * i, 0.6 + 0.1 * i))
    hl = eio(prog(t, 1.0, 1.45))
    for i, row in enumerate(d["rows"][:3]):
        y0 = rows_y[i]
        a = eo(prog(t, 0.25 + 0.1 * i, 0.7 + 0.1 * i))
        bx = (500, y0, 1420, y0 + 100)
        foc = i == fi
        ra = a * (1.0 if foc else dim)
        if foc and hl > 0:
            # light spills through the focused row, wider than the row itself
            X0, Y0, X1, Y1 = pp.box((410, y0 - 8, 1510, y0 + 108))
            W, H = int(X1 - X0), int(Y1 - Y0)
            g = hgrad(W, H, [G.aura[0], G.aura[4], (120, 140, 235), G.aura[2], G.aura[0]])
            xs = np.linspace(-1, 1, W, dtype=np.float32)[None]
            ys = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
            al = np.clip(1.2 - np.abs(xs) ** 4, 0, 1) * np.clip(1.3 - np.abs(ys) ** 6, 0, 1) * hl * 0.9
            g.putalpha(Image.fromarray((np.clip(al, 0, 1) * 255).astype(np.uint8)))
            pp.comp(g, X0, Y0)
        pp.glass(bx, 22, ra, frost=0.55 if (foc and hl > 0) else 0.68)
        pp.ring(538, y0 + 30, 10, 2, "accent" if foc else "ink", ra * 0.8)
        pp.text(566, y0 + 38, row["title"], "sans_medium", 24, "ink", ra, max_w=640)
        for k, ln in enumerate(wrap(row["desc"], "sans", 18, 660)[:2]):
            pp.text(566, y0 + 66 + k * 22, ln, "sans", 18, "muted", ra, max_w=680)
        bb = (1290, y0 + 30, 1392, y0 + 70)
        pp.rrect(bb, 12, fill=C("white", ra * 0.9), outline=C("line", ra), w=1)
        pp.text((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, d.get("action", "Apply"), "sans_medium", 18, "ink", ra, "mm", max_w=90)
    if push > 0:                                         # the focused row opens into a code card
        tgt = (470, fy + 120, 1450, fy + 120 + 66 + 44 * len(d["code"]))
        src = (500, fy, 1420, fy + 100)
        bx = tuple(lerp(src[k], tgt[k], push) for k in range(4))
        pp.glass(bx, 22, push, frost=0.8, tint=0.25, shadow=0.14)
        for k, ln in enumerate(d["code"]):
            q = prog(t, 2.15 + 0.22 * k, 2.5 + 0.22 * k)
            if q <= 0:
                continue
            s = ln["text"][: int(round(len(ln["text"]) * min(1, q * 1.4)))]
            col = "muted" if ln.get("muted") else ("accent" if ln.get("accent") else "ink")
            pp.text(tgt[0] + 40, tgt[1] + 54 + 44 * k, s, "mono", 22, col, push, max_w=tgt[2] - tgt[0] - 80,
                    fit_to=ln["text"])
    return pp.out()


def s_trend(c):
    t, b = c.lt, G.b["trend"]
    cx, cy, z = cam(t, [(0, 820, 470, 1.08), (1.9, 860, 480, 1.02), (c.dur, 1180, 520, 1.1)])
    pp = P((cx, cy, z), [(650, 560, 620, 2, 0.45), (900, 520, 500, 0, 0.5), (1400, 700, 500, 1, 0.3)])
    rails(pp, (240, 1120, 1210), 120, 960, prog(t, 0, 0.9), ("02", "7 DAYS"))
    for i, ln in enumerate(b["heading"][:2]):
        pp.text(300, 260 + i * 92, ln, "sans", 96, "ink", 1, max_w=780, rise=prog(t, -0.12 + 0.05 * i, 0.4 + 0.05 * i))
    cap = (300, 420, 1060, 640)
    a = eo(prog(t, 0.05, 0.45))
    pp.glass(cap, 110, a, tint=0.5)
    ser = b["series"]
    n = len(ser)
    mx = max(v for _, v in ser)
    pts = [(390 + 560 * i / (n - 1), 480 + 110 * (1 - v / mx)) for i, (_, v) in enumerate(ser)]
    lp = eio(prog(t, 0.45, 1.6))
    k = lp * (n - 1)
    kk = int(k)
    path = pts[: kk + 1]
    if kk < n - 1:
        f = k - kk
        path = path + [(lerp(pts[kk][0], pts[kk + 1][0], f), lerp(pts[kk][1], pts[kk + 1][1], f))]
    pp.line(path, "ink", 2.4, a)
    for i, (lab, v) in enumerate(ser):
        if i <= k + 0.01:
            q = eo(prog(t, 0.45 + 1.15 * i / (n - 1), 0.65 + 1.15 * i / (n - 1)))
            pp.disc(pts[i][0], pts[i][1], 5.5, "ink", q)
            pp.text(pts[i][0] + 10, pts[i][1] - 12, f"{lab} {v}", "mono", 13, "muted", q)
    pp.text(320, 690, b.get("note", ""), "mono", 16, "muted", eo(prog(t, 1.3, 1.7)), max_w=700)
    dot_grid(pp, 1250, 360, 4, 6, 64, 22, 0.9, t)
    return pp.out()


def s_agents(c):
    t, b = c.lt, G.b["agents"]
    pp = P((960, 540, 1.0 + 0.03 * eio(t / c.dur)), [(960, 300, 700, 2, 0.35), (960, 800, 600, 0, 0.4), (500, 540, 400, 1, 0.3)])
    ga = 1 - eio(prog(t, c.dur - 0.5, c.dur))
    for j in range(6):                                   # the dot grid carried over, on the left
        for i in range(3):
            pp.disc(330 + i * 64, 220 + j * 64, 22, "white", ga)
    rails(pp, (620, 1300, 1390), 100, 980, 1.0)
    shrink = eio(prog(t, c.dur - 0.55, c.dur))
    card = (720, 150, 1200, 930)
    sc = eo(prog(t, 0.0, 0.4)) * (1 - shrink)
    bx = (lerp(960, card[0], sc), lerp(540, card[1], sc), lerp(960, card[2], sc), lerp(540, card[3], sc))
    x0, y0, x1, y1 = pp.box(bx)
    if x1 - x0 > 4 and y1 - y0 > 4:                      # tall gradient glass card
        pp.shadow(bx, 34, 0.12)
        m, mx, my = pp.mask(bx, 34 * sc + 4)
        W, H = m.size
        top, mid, bot = (np.array(G.aura[i], np.float32) for i in (2, 4, 0))
        ys = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        col = np.where(ys < 0.5, top + (mid - top) * (ys / 0.5), mid + (bot - mid) * ((ys - 0.5) / 0.5))
        xs = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
        col = col * (0.92 + 0.08 * xs) + 25 * (1 - xs)
        im = Image.fromarray(np.clip(np.broadcast_to(col, (H, W, 3)), 0, 255).astype(np.uint8)).convert("RGBA")
        im.putalpha(m)
        pp.comp(im, mx, my)
        pp.rrect(bx, 34 * sc + 4, outline=C("white", 0.8), w=1.5)
    if shrink > 0.85:
        pp.disc(960, 540, 9, "ink", prog(shrink, 0.85, 1.0))
    ia = 1 - eo(prog(t, c.dur - 0.75, c.dur - 0.5))
    pp.text(960, 222, b["heading"], "sans_medium", 26, "ink", ia, "ms", max_w=420, rise=prog(t, 0.2, 0.6))
    for i, it in enumerate(b["items"][:8]):
        x, y = 870 + (i % 2) * 180, 320 + (i // 2) * 150
        q = back(prog(t, 0.35 + 0.1 * i, 0.75 + 0.1 * i))
        if q <= 0:
            continue
        s = 46 * q
        pp.rrect((x - s, y - s, x + s, y + s), 18 * q, fill=C("white", 0.92 * ia))
        pp.icon(it["icon"], x, y, 50 * q, ia)
        pp.text(x, y + 72, it["name"].upper(), "mono_medium", 14, "ink", cl(q) * ia, "ms", max_w=170)
    return pp.out()


L_C, R_C, L_R = (770, 540), (1150, 540), 190


def s_loop(c):
    t, nodes = c.lt, G.b["loop"]["nodes"]
    merge = eio(prog(t, 2.0, 2.7))
    form = prog(t, 2.6, c.dur)
    f = eio(form)
    z = lerp(lerp(1.0, 0.92, eio(prog(t, 1.4, 2.0))), 1.0, merge)
    blobs = [(L_C[0], 560, 360, 0, 0.55 * eo(prog(t, 0.4, 1.2))), (R_C[0], 520, 360, 1, 0.5 * eo(prog(t, 0.9, 1.7))),
             (960, 540, 800, 2, 0.25)]
    if form > 0:
        blobs = [(x, y, r, col, a * (1 - f)) for x, y, r, col, a in blobs] + [(x, y, r, col, a * f) for x, y, r, col, a in word_blobs(t)]
    pp = P((960, 540, z), blobs)
    oc = G.o_c
    lc = (lerp(lerp(L_C[0], R_C[0], merge), oc[0], f), lerp(L_C[1], oc[1], f))
    rc = (lerp(R_C[0], oc[0], f), lerp(R_C[1], oc[1], f))
    rr, rw = lerp(L_R, G.o_r, f), lerp(26, G.o_w, f)
    d1, d2 = eio(prog(t, 0.35, 1.15)), eio(prog(t, 0.9, 1.7))
    # left ring draws counter-clockwise from the contact point (3 o'clock), the right one clockwise from 9
    if d1 > 0 and merge < 1:
        pp.ring(lc[0], lc[1], rr, rw, "white", 1 - merge * 0.5, 90 - 360 * d1, 90, glow=0.4)
    if d2 > 0:
        pp.ring(rc[0], rc[1], rr, rw, "white", 1, 270, 270 + 360 * d2, glow=0.5)
    ca = (1 - eio(prog(t, 2.0, 2.4))) * eo(prog(t, 1.4, 1.8))   # a thin comet runs the figure-eight
    if ca > 0:
        ph = (t - 1.4) * 0.9 % 2
        if ph < 1:
            pp.ring(lc[0], lc[1], rr, 4, "accent", ca, 90 - 360 * ph - 60, 90 - 360 * ph)
        else:
            pp.ring(rc[0], rc[1], rr, 4, "accent", ca, 270 + 360 * (ph - 1) - 60, 270 + 360 * (ph - 1))
    na = 1 - eio(prog(t, 1.9, 2.3))
    pos = [((960, 540), "c", -0.3), ((L_C[0] - L_R, 540), "l", 0.75), ((R_C[0] + L_R, 540), "r", 1.3), ((R_C[0], 540 + L_R), "b", 1.55)]
    for i, ((x, y), side, t0) in enumerate(pos[: len(nodes)]):
        q = back(prog(t, t0, t0 + 0.3))
        if q <= 0 or na <= 0:
            continue
        x = lerp(x, 960, merge)
        pp.disc(x, y, 9 * q, "ink", na)
        lab, al = nodes[i], na * cl(q)
        if side == "l":
            pp.text(x - 22, y - 6, lab, "mono_medium", 17, "ink", al, "rs")
        elif side == "b":
            pp.text(x, y + 44, lab, "mono_medium", 17, "ink", al, "ms")
        else:
            pp.text(x + 22, y - 6, lab, "mono_medium", 17, "ink", al, "ls")
    if form > 0:
        wordmark(pp, t, enter=prog(t, 2.75, c.dur), ring_a=0)
        pp.ring(rc[0], rc[1], rr, rw, "white", 1, glow=0.5)
    return pp.out()


def s_end(c):
    t = c.lt
    col = eio(prog(t, 1.1, 1.8))           # letters fold away, the ring shrinks into the logo
    pp = P((960, 540, 1.0), word_blobs(t, 1 - 0.75 * col))
    if col < 1:
        wordmark(pp, t, leave=col * 1.6, ring_c=(lerp(G.o_c[0], 960, col), lerp(G.o_c[1], 440, col)),
                 ring_r=lerp(G.o_r, 60, col), ring_w=lerp(G.o_w, 8, col), ring_a=1 - prog(col, 0.6, 1.0), dot=col < 0.3)
    lg = eo(prog(t, 1.45, 2.0))
    grow = eio(prog(t, 2.5, 3.2))
    pp.icon("logo", 960, lerp(440, 420, grow), lerp(130, 170, grow) * (0.6 + 0.4 * lg), lg)
    na = lg * (1 - eio(prog(t, 2.4, 2.7)))
    pp.text(960, 616, G.c["brand"], "sans_medium", 72, "ink", na, "ms", rise=prog(t, 1.6, 2.1))
    pp.text(960, 672, G.c.get("independent", ""), "sans", 30, "muted", na, "ms", max_w=1200, rise=prog(t, 1.75, 2.25))
    pp.text(960, 616, G.c["cta"], "sans_medium", 52, "ink", eo(prog(t, 2.6, 3.1)), "ms", max_w=1400, rise=prog(t, 2.6, 3.1))
    return pp.out()


SCENES = [("halo", 7.0, s_halo), ("policy", 3.6, s_policy), ("stats", 4.0, s_stats), ("findings", 1.3, s_findings),
          ("detail", 3.8, s_detail), ("trend", 2.6, s_trend), ("agents", 2.6, s_agents), ("loop", 3.6, s_loop),
          ("end", 4.4, s_end)]


def starts():
    out, t = {}, 0.0
    for n, d, _ in SCENES:
        out[n] = t
        t += d
    return out, t


# ------------------------------------------------------------------ sound: airy pad, soft plucks, glass blips
def score(path):
    st, dur = starts()
    sc = Score(96, dur + 0.6)
    bar = 4 * sc.spb
    chords = [["D3", "A3", "E4", "F#4"], ["B2", "F#3", "D4", "A4"], ["G2", "D3", "B3", "F#4"], ["A2", "E3", "C#4", "E4"]]
    k, t0 = 0, 0.0
    while t0 < dur - 3:
        sc.chord(chords[k % 4], t0, bar * 2 + 0.4, 0.26)
        if st["policy"] - 0.1 <= t0 < st["end"]:
            root = chords[k % 4][0]
            sc.bass([(root, 0, 1.5), (root, 3, 1), (root, 5, 1.5)], start=t0, gain=0.26)
        k += 1
        t0 += bar * 2
    sc.pattern("tick", 1, start=st["policy"] / sc.spb, end=st["loop"] / sc.spb, gain=0.06, pitch=1.6)
    sc.pattern("hat", 0.5, start=st["stats"] / sc.spb, end=st["loop"] / sc.spb, gain=0.035)
    for i, n in enumerate(["F#5", "A5", "D6", "E6", "F#6", "A6", "D7"][: len(G.c["brand"])]):
        sc.hit("blip", st["halo"] + 1.25 + 0.07 * i, 0.22, note=n)
    for i in range(2):
        sc.add(pluck(["D4", "A4"][i], 0.6), st["halo"] + 2.9 + 1.75 * i, 0.35)
    sc.hit("blip", st["policy"] + 0.3, 0.3, note="A5")
    p = G.b["policy"]["prompt"]
    for i, ch in enumerate(p):
        if ch != " ":
            sc.hit("tick", st["policy"] + 1.15 + 1.1 * i / len(p), 0.12, pitch=2.3 + 0.3 * ((i * 7) % 3))
    sc.hit("riser", st["policy"] + 2.45, 0.25, dur=0.6)
    sc.hit("clack", st["policy"] + 3.05, 0.4)
    sc.hit("blip", st["stats"] + 0.05, 0.35, note="D6")
    for i in range(3):
        sc.hit("blip", st["stats"] + 1.9 + 0.2 * i, 0.22, note=["A5", "D6", "F#6"][i])
    sc.hit("riser", st["findings"] + 0.2, 0.3, dur=1.0)
    sc.hit("blip", st["detail"] + 1.0, 0.4, note="E6")
    sc.hit("blip", st["detail"] + 1.1, 0.3, note="A6")
    for k2 in range(len(G.b["detail"]["code"])):
        sc.hit("tick", st["detail"] + 2.15 + 0.22 * k2, 0.18, pitch=2.6)
    for i in range(7):
        sc.add(pluck(["A4", "F#4", "E4", "D4", "B3", "A3", "F#3"][i], 0.6), st["trend"] + 0.45 + 1.15 * i / 6, 0.16)
    for i in range(len(G.b["agents"]["items"][:8])):
        sc.hit("blip", st["agents"] + 0.4 + 0.1 * i, 0.2, note=["D6", "E6", "F#6", "A6"][i % 4])
    sc.hit("blip", st["loop"] + 0.05, 0.35, note="D6")
    sc.hit("riser", st["loop"] + 1.6, 0.35, dur=1.0)
    sc.hit("thud", st["loop"] + 2.65, 0.5)
    sc.chord(["D3", "A3", "D4", "F#4", "A4"], st["end"] + 1.45, 3.4, 0.4)
    sc.hit("blip", st["end"] + 1.45, 0.4, note="D7")
    sc.hit("blip", st["end"] + 2.6, 0.3, note="A6")
    return sc.write(path)


# ------------------------------------------------------------------ CLI
def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    tl = Timeline([Scene(n, d, f) for n, d, f in SCENES], G.W, G.H, G.fps, data=G, theme=G.th)
    return tl, brief


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("icon", "kind", "col"):
                yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


SECTIONS = ("policy", "stats", "findings", "detail", "trend", "agents", "loop")


def check(tl):
    errs = []
    for k in ("brand", "cta"):
        if k not in G.c:
            errs.append(f"copy.{k} missing")
    for sec in SECTIONS:
        if sec not in G.b:
            errs.append(f"{sec} missing")
    if G.image("logo") is None:
        errs.append("assets/logo.png missing: supply the brand's real logo")
    for it in G.b.get("agents", {}).get("items", []):
        if G.image(it["icon"]) is None:
            errs.append(f"icon {it['icon']} missing from assets/icons (fetch it with the brand-icons skill)")
    for s in _strings({k: G.b[k] for k in SECTIONS + ("copy",) if k in G.b}):
        if s.rstrip().endswith(".") and not s.rstrip().endswith(".."):
            errs.append(f"trailing period: {s!r}")
    if errs:
        print("\n".join("✗ " + e for e in errs))
        return False
    del OVERFLOWS[:], SHRINKS[:]
    st, dur = starts()
    for t in np.arange(0.2, dur - 0.05, 0.5):
        tl.frame(int(t * tl.fps))
    if OVERFLOWS:
        errs.append("; ".join(overflow_report()))
    elif SHRINKS:
        print("warn:", overflow_report(warn=True))
    print(f"{dur:.2f}s, {tl.n_frames} frames, {len(SCENES)} scenes")
    for e in errs:
        print("✗", e)
    return not errs


def ig_cut(src, dst):
    """1080x1350 feed cut: the 16:9 film letterboxed on black, like the reference post."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                    "scale=1080:-2:flags=lanczos,pad=1080:1350:(ow-iw)/2:(oh-ih)/2:black", "-c:v", "libx264",
                    "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                    dst], check=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--ig", action="store_true")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("No generated images. Supply assets/logo.png (the real logo) and fetch agent icons with the "
              "brand-icons skill into assets/icons/ (--theme light).")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=6, rows=5, thumb_w=320))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        dst = tl.render(a.out or os.path.join(out, "halo-glass-film.mp4"), a.audio or score(os.path.join(out, "score.m4a")))
        print(dst)
        if a.ig:
            print(ig_cut(dst, dst.replace(".mp4", "_4x5.mp4")))


if __name__ == "__main__":
    main()
