#!/usr/bin/env python3
"""ui-macro-launch-film: a white, type-led product film made of the product's own UI at macro zoom (16:9, ~58 s).

    python3 main.py check  --brief brief.json
    python3 main.py still  --brief brief.json 1.2 7 14 18 25 33 39 52 56
    python3 main.py sheet  --brief brief.json
    python3 main.py score  --brief brief.json
    python3 main.py render --brief brief.json [--audio track.m4a]

A caret blinks, the brand is typed huge, then small with a trail of dots that swell into shapes. Three
"<Brand> is not a …" rows each end in a different UI object (a button, a card, a field) that gets
struck out. The logo mark grows into the app window and the camera pushes into one native-drawn UI
fragment after another: an AI composer, a "thinking" beat, an activity table with a detail panel, a
checklist writing itself, search with marker-highlighted matches, a team thread with a counter, an
integrations grid, a timeline row going to Done, and the team's reply. It ends on "<Brand> does" over
a checklist that cascades, one checkbox the cursor ticks, and the box turning into the logo.

Every UI element is drawn natively in design units (1920 wide) through a camera, so text stays sharp
at any zoom. Copy lives in the brief.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Scene, Theme, Timeline, prog, lerp, mix, hex2rgb, overflow_report
from framesmith import ease_out, ease_in_out, ease_drawer, typed
from framesmith.typography import F, text, text_width, OVERFLOWS, SHRINKS
from framesmith.motion import spring
from framesmith import ui
from framesmith.score import Score

G = None
SS = 2


def eo(p):
    return ease_out(p)


def eio(p):
    return ease_in_out(p)


# ------------------------------------------------------------------ state
class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.W, self.H = brief.get("size", [1920, 1080])
        self.fps = brief.get("fps", 30)
        th = brief.get("theme", {})
        self.th = Theme.from_dict({k: v for k, v in th.items() if isinstance(v, str)})
        self.col = {k: hex2rgb(v) for k, v in th.items() if isinstance(v, str)}
        self.col.setdefault("line", (231, 231, 231))
        self.col.setdefault("muted", (140, 140, 140))
        self.light = [hex2rgb(v) for v in th.get("light", ["#9C8CFF", "#B9A4FF", "#F2A6E6"])]
        self.ink, self.paper = self.th.ink, self.th.paper
        self.dir = os.path.join(base, brief.get("assets_dir", "assets"))
        self.DH = 1920 * self.H / self.W
        self._img = {}

    def image(self, name):
        if name not in self._img:
            path = os.path.join(self.dir, "logo.png") if name == "logo" else os.path.join(self.dir, "icons", name + ".png")
            if os.path.exists(path):
                im = Image.open(path).convert("RGBA")
                bb = im.getchannel("A").getbbox()
                self._img[name] = im.crop(bb) if bb else im
            else:
                self._img[name] = None
        return self._img[name]


def C(name, a=1.0, bg=None):
    """Theme colour by name (or an RGB tuple), faded toward the paper by alpha a."""
    c = G.col.get(name) if isinstance(name, str) else name
    if c is None:
        c = {"ink": G.ink, "paper": G.paper}[name]
    return mix(bg or G.paper, c, max(0.0, min(1.0, a)))


# ------------------------------------------------------------------ painter: design units → camera → pixels
class P:
    def __init__(self, cam=(960, 540, 1.0), bg=None):
        self.cx, self.cy, self.z = cam
        self.S = SS * G.W / 1920
        self.img = Image.new("RGB", (G.W * SS, G.H * SS), bg or G.paper)
        self.d = ImageDraw.Draw(self.img)

    def X(self, x):
        return ((x - self.cx) * self.z + 960) * self.S

    def Y(self, y):
        return ((y - self.cy) * self.z + G.DH / 2) * self.S

    def u(self, v):
        return v * self.z * self.S

    def box(self, b):
        return (self.X(b[0]), self.Y(b[1]), self.X(b[2]), self.Y(b[3]))

    def visible(self, b, pad=40):
        x0, y0, x1, y1 = self.box(b)
        return x1 > -pad and y1 > -pad and x0 < self.img.width + pad and y0 < self.img.height + pad

    def rect(self, b, r=0, fill=None, outline=None, w=1):
        if not self.visible(b):
            return
        bx = self.box(b)
        if bx[2] - bx[0] < 1 or bx[3] - bx[1] < 1:
            return
        r = min(self.u(r), (bx[2] - bx[0]) / 2, (bx[3] - bx[1]) / 2)
        self.d.rounded_rectangle(bx, radius=max(0, r), fill=fill, outline=outline,
                                 width=max(1, round(self.u(w))) if outline else 0)

    def shadow(self, b, r=16, a=0.09, spread=30, dy=14):
        if a <= 0 or not self.visible(b, 200):
            return
        X0, Y0, X1, Y1 = self.box(b)
        sp, oy = self.u(spread), self.u(dy)
        rx0, ry0, rx1, ry1 = int(X0 - 2 * sp), int(Y0 - 2 * sp + oy), int(X1 + 2 * sp), int(Y1 + 2 * sp + oy)
        q = 8
        sw, sh = max(1, (rx1 - rx0) // q), max(1, (ry1 - ry0) // q)
        m = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(m).rounded_rectangle(((X0 - rx0) / q, (Y0 + oy - ry0) / q, (X1 - rx0) / q, (Y1 + oy - ry0) / q),
                                            radius=self.u(r) / q, fill=int(255 * a))
        m = m.filter(ImageFilter.GaussianBlur(max(1, sp / q / 1.6))).resize((rx1 - rx0, ry1 - ry0), Image.BILINEAR)
        cx0, cy0 = max(0, rx0), max(0, ry0)
        cx1, cy1 = min(self.img.width, rx1), min(self.img.height, ry1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        m = m.crop((cx0 - rx0, cy0 - ry0, cx1 - rx0, cy1 - ry0))
        self.img.paste((0, 0, 0), (cx0, cy0, cx1, cy1), m)

    def font(self, role, size):
        return F(role, max(4, int(round(self.u(size)))))

    def text(self, x, y, s, role, size, fill, anchor="la", max_w=None, fit_to=None, track=0):
        if not s:
            return
        text(self.d, (self.X(x), self.Y(y)), s, self.font(role, size), fill, self.u(track), anchor,
             max_w=self.u(max_w) if max_w else None, fit_to=fit_to)

    def rise(self, x, y, s, role, size, fill, p, anchor="la", max_w=None):
        if p <= 0 or not s:
            return
        ui.rise(self.img, (self.X(x), self.Y(y)), s, self.font(role, size), fill, min(1, p), anchor=anchor,
                max_w=self.u(max_w) if max_w else None)

    def line(self, pts, fill, w=2):
        self.d.line([(self.X(x), self.Y(y)) for x, y in pts], fill=fill, width=max(1, round(self.u(w))), joint="curve")

    def circle(self, x, y, r, fill=None, outline=None, w=2):
        X, Y, R = self.X(x), self.Y(y), self.u(r)
        if R <= 0:
            return
        self.d.ellipse((X - R, Y - R, X + R, Y + R), fill=fill, outline=outline,
                       width=max(1, round(self.u(w))) if outline else 0)

    def icon(self, name, x, y, size, a=1.0, anchor="mm"):
        im = G.image(name)
        if im is None or a <= 0 or size <= 0:
            return
        px = max(2, int(self.u(size)))
        k = px / max(im.size)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        X, Y = self.X(x), self.Y(y)
        X -= im.width / 2 if anchor[0] == "m" else 0
        Y -= im.height / 2 if anchor[1] == "m" else 0
        alpha = im.getchannel("A")
        if a < 1:
            alpha = alpha.point(lambda v: int(v * a))
        self.img.paste(im.convert("RGB"), (int(X), int(Y)), alpha)

    def out(self):
        return np.asarray(self.img.reduce(SS) if SS > 1 else self.img)


def tw(s, role, size):
    """Text width in design units."""
    return text_width(s, F(role, size))


def cam(t, keys):
    """Camera keyframes [(t, cx, cy, z)], ease-in-out between keys, zoom interpolated in log space."""
    if t <= keys[0][0]:
        return keys[0][1:]
    for (t0, x0, y0, z0), (t1, x1, y1, z1) in zip(keys, keys[1:]):
        if t <= t1:
            p = eio(prog(t, t0, t1))
            return lerp(x0, x1, p), lerp(y0, y1, p), math.exp(lerp(math.log(z0), math.log(z1), p))
    return keys[-1][1:]


# ------------------------------------------------------------------ small drawn glyphs
def caret(pp, x, y, hgt, t, on_from=-1, solid=False):
    if solid or t < on_from or int(t / 0.27) % 2 == 0:
        pp.rect((x, y - hgt / 2, x + max(2.2, hgt * 0.035), y + hgt / 2), 0, G.ink)


def sparkle(pp, x, y, s, col, a=1.0):
    """AI action glyph: a rounded square with a four-point star in its corner."""
    c = C(col, a)
    pp.rect((x, y + s * 0.18, x + s * 0.78, y + s), s * 0.18, None, c, s * 0.09)
    cx, cy, r = x + s * 0.8, y + s * 0.2, s * 0.24
    pts = [(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
           (cx, cy + r), (cx - r * 0.28, cy + r * 0.28), (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)]
    pp.d.polygon([(pp.X(px), pp.Y(py)) for px, py in pts], fill=c)
    pp.line([(x + s * 0.2, y + s * 0.55), (x + s * 0.5, y + s * 0.55)], c, s * 0.08)
    pp.line([(x + s * 0.2, y + s * 0.75), (x + s * 0.42, y + s * 0.75)], c, s * 0.08)


def checkbox(pp, x, y, s, on=0.0, a=1.0, r=None):
    r = s * 0.2 if r is None else r
    if on > 0:
        pp.rect((x, y, x + s, y + s), r, C("ink", a))
        k = min(1, on * 1.4)
        p1, p2, p3 = (x + s * 0.24, y + s * 0.52), (x + s * 0.43, y + s * 0.7), (x + s * 0.77, y + s * 0.3)
        if k < 0.45:
            q = k / 0.45
            pts = [p1, (lerp(p1[0], p2[0], q), lerp(p1[1], p2[1], q))]
        else:
            q = (k - 0.45) / 0.55
            pts = [p1, p2, (lerp(p2[0], p3[0], q), lerp(p2[1], p3[1], q))]
        pp.line(pts, C("paper"), s * 0.11)
    else:
        pp.rect((x, y, x + s, y + s), r, C("paper"), C((150, 150, 150), a), max(1.5, s * 0.055))


def cursor(pp, x, y, s=34, press=0.0):
    """macOS-style arrow, drawn at a constant screen size."""
    s = s / pp.z * (1 - 0.12 * press)
    pts = [(0, 0), (0, 1.0), (0.26, 0.76), (0.43, 1.12), (0.58, 1.05), (0.41, 0.7), (0.74, 0.7)]
    poly = [(pp.X(x + px * s), pp.Y(y + py * s)) for px, py in pts]
    pp.d.polygon(poly, fill=G.ink, outline=G.paper, width=max(1, int(pp.u(2.2 / pp.z))))


def magnifier(pp, x, y, s, col):
    pp.circle(x + s * 0.42, y + s * 0.42, s * 0.32, None, col, s * 0.09)
    pp.line([(x + s * 0.66, y + s * 0.66), (x + s * 0.92, y + s * 0.92)], col, s * 0.1)


def logo(pp, x, y, size, a=1.0):
    pp.icon("logo", x, y, size, a)


def avatar(pp, x, y, s, name, a=1.0):
    """Monogram tile (initials, no faces)."""
    pp.rect((x, y, x + s, y + s), s * 0.24, C((236, 236, 236), a))
    ini = "".join(w[0] for w in name.split()[:2]).upper()
    pp.text(x + s / 2, y + s / 2, ini, "sans_bold", s * 0.36, C("ink", a), "mm")


# ------------------------------------------------------------------ scenes
def s_hook(c):
    t = c.lt
    hk = G.b["hook"]
    if t < 1.0:
        pp = P()
        caret(pp, 960, 540, 190, t, 0.25)
        return pp.out()
    if t < 1.6:
        pp = P()
        g = hk["giant"]
        w = tw(g, "sans_medium", 430)
        x0 = 960 - w / 2
        sub = g[:1 + int((t - 1.0) / 0.2)]
        pp.text(x0, 540, sub, "sans_medium", 430, G.ink, "lm")
        caret(pp, x0 + tw(sub, "sans_medium", 430) + 24, 540, 330, t, solid=True)
        return pp.out()
    line = hk["line"]
    size = 46
    w = tw(line, "sans_medium", size)
    x0 = 960 - w / 2
    # dots: a trail that swells into shapes; the camera follows its head
    xe = x0 + w + 6
    dots, x = [], xe
    for i in range(40):
        r = min(44, 3.0 * 1.085 ** i)
        wid = r * (1 + max(0, i - 22) * 0.16)
        dots.append((x + wid, r, wid))
        x += 2 * wid + 4 + r * 0.55
    D0, D1 = 2.85, 4.9

    def born(k):
        return D0 + (D1 - D0) * ((k + 1) / len(dots)) ** (1 / 1.7)
    n = sum(1 for k in range(len(dots)) if t >= born(k))
    head = dots[n - 1][0] + dots[n - 1][2] if n else xe
    cx = max(960, head - 760) if n else 960
    pp = P((cx, 540, 1.0))
    tl = typed(line, prog(t, 1.62, 2.3))
    pp.text(x0, 540, tl, "sans_medium", size, G.ink, "lm", fit_to=line)
    if n == 0:
        caret(pp, x0 + tw(tl, "sans_medium", size) + 4, 540, 56, t, 2.3, solid=t < 2.3)
    base = 540 + 14
    for k in range(n):
        dx, r, wid = dots[k]
        grow = eo(prog(t, born(k), born(k) + 0.14))
        rr = r * (0.4 + 0.6 * grow)
        ww = wid * (0.4 + 0.6 * grow)
        yc = lerp(base - r, 540, min(1, max(0, (r - 6) / 14)))
        pp.rect((dx - ww, yc - rr, dx + ww, yc + rr), rr, G.ink)
    return pp.out()


def _not_obj_width(row):
    lab = row["label"]
    if row["kind"] == "button":
        return 44 + tw(lab, "sans_medium", 56) + 30 + 64 + 22
    if row["kind"] == "card":
        return 36 + 62 + 28 + tw(lab, "sans_medium", 56) + 40
    return 30 + tw(lab, "sans", 56) + 26 + 40 + 30


def not_obj(pp, row, x, ymid, t0, t):
    k = row["kind"]
    lab = row["label"]
    p = eo(prog(t, t0, t0 + 0.4))
    if p <= 0:
        return
    w = _not_obj_width(row)
    dy = (1 - p) * 26
    y0, y1 = ymid - 50 + dy, ymid + 50 + dy
    if k == "button":
        pp.shadow((x, y0, x + w, y1), 26, 0.16 * p, 22, 12)
        pp.rect((x, y0, x + w, y1), 26, C((214, 230, 253), p), C((176, 206, 248), p), 2)
        pp.text(x + 44, ymid + dy, lab, "sans_medium", 56, C("blue", p), "lm")
        cx = x + w - 22 - 32
        pp.circle(cx, ymid + dy, 32, C("paper", p))
        bob = 8 * math.sin(max(0, t - t0 - 0.6) * 9) * math.exp(-max(0, t - t0 - 0.6) * 3)
        ay = ymid + dy + bob
        pp.line([(cx, ay - 16), (cx, ay + 15)], C("blue", p), 4.5)
        pp.line([(cx - 12, ay + 3), (cx, ay + 15), (cx + 12, ay + 3)], C("blue", p), 4.5)
        q = eo(prog(t, t0 + 0.75, t0 + 1.05))
        if q > 0:
            pp.line([(x + 34, ymid + dy + 2), (x + 34 + (tw(lab, "sans_medium", 56) + 20) * q, ymid + dy + 2)], C("blue", p), 4)
    elif k == "card":
        pp.shadow((x, y0, x + w, y1), 4, 0.1 * p, 18, 10)
        pp.rect((x, y0, x + w, y1), 3, C((251, 228, 228), p), C((233, 168, 168), p), 2)
        bx = x + 36
        pp.rect((bx, ymid + dy - 31, bx + 62, ymid + dy + 31), 2, None, C("red", p), 3)
        q = eo(prog(t, t0 + 0.6, t0 + 0.95))
        if q > 0:
            pp.line([(bx + 6, ymid + dy - 25), (bx + 6 + 50 * q, ymid + dy - 25 + 50 * q)], C("red", p), 3)
            q2 = eo(prog(t, t0 + 0.8, t0 + 1.1))
            if q2 > 0:
                pp.line([(bx + 56, ymid + dy - 25), (bx + 56 - 50 * q2, ymid + dy - 25 + 50 * q2)], C("red", p), 3)
        pp.text(bx + 62 + 28, ymid + dy, lab, "sans_medium", 56, C("red", p), "lm")
    else:
        pp.shadow((x, y0, x + w, y1), 6, 0.12 * p, 18, 10)
        pp.rect((x, y0, x + w, y1), 6, C("paper", p), C("line", p), 1.5)
        pp.rect((x, y0, x + w, y0 + 12), 4, C((248, 228, 160), p))
        tp = prog(t, t0 + 0.15, t0 + 0.6)
        pp.text(x + 30, ymid + dy + 4, typed(lab, tp), "sans", 56, C((118, 118, 118), p), "lm", fit_to=lab)
        lw = tw(lab, "sans", 56)
        q = eo(prog(t, t0 + 0.8, t0 + 1.15))
        if q > 0:
            pp.line([(x + 30, ymid + dy + 6), (x + 30 + lw * q, ymid + dy + 6)], C((118, 118, 118), p), 3.5)
        px = x + 30 + lw + 26
        pp.line([(px + 6, ymid + dy + 18), (px + 30, ymid + dy - 12)], C((130, 130, 130), p), 4)
        pp.line([(px + 3, ymid + dy + 22), (px + 6, ymid + dy + 18)], C((130, 130, 130), p), 4)


def s_not_a(c):
    t = c.lt
    na = G.b["not_a"]
    rows = na["rows"][:3]
    T = [0.0, 1.55, 3.1][:len(rows)]
    n = sum(1 for x in T if t >= x)
    nf = 1 + sum(eio(prog(t, x, x + 0.45)) for x in T[1:])     # the stack recentres as rows arrive
    pp = P((960, 540, lerp(1.08, 1.0, eio(prog(t, 0, 4.0)))))
    lead = na["lead"]
    lw = tw(lead, "sans_medium", 60)
    for i, row in enumerate(rows[:n]):
        y = 540 - (nf - 1) * 85 + i * 170
        ow = _not_obj_width(row)
        tot = 72 + 28 + lw + 34 + ow
        x0 = 960 - tot / 2 + (i - 1) * 40
        a = eo(prog(t, T[i], T[i] + 0.3))
        pp.icon(row.get("icon", ""), x0 + 36, y, 66, a)
        pp.text(x0 + 100, y, typed(lead, prog(t, T[i] + 0.05, T[i] + 0.5)), "sans_medium", 60, G.ink, "lm",
                max_w=1100, fit_to=lead)
        not_obj(pp, row, x0 + 100 + lw + 34, y, T[i] + 0.5, t)
    return pp.out()


def s_logo(c):
    t = c.lt
    con = G.b["console"]
    pp = P()
    s = spring(t, 260, 22)
    grow = eio(prog(t, 0.7, 1.3))
    wname = con["workspace"]
    ww = tw(wname, "sans_medium", 42)
    cw, chh = lerp(150, 120 + ww + 70, grow), lerp(150, 110, grow)
    if grow > 0:
        b = (960 - cw / 2, 540 - chh / 2, 960 + cw / 2, 540 + chh / 2)
        pp.shadow(b, 22, 0.1 * grow)
        pp.rect(b, 22, G.paper, C("line", grow), 1.5)
    mx = lerp(960, 960 - cw / 2 + 64, grow)
    logo(pp, mx, 540, max(1, lerp(120 * s, 64, grow)))
    if grow > 0.4:
        pp.text(mx + 56, 540, typed(wname, prog(t, 1.0, 1.45)), "sans_medium", 42, G.ink, "lm", fit_to=wname)
    return pp.out()


WIN = (180, 110, 1740, 990)


def s_console(c):
    t = c.lt
    con = G.b["console"]
    g = ease_drawer(prog(t, 0, 0.75))
    wname = con["workspace"]
    ww = tw(wname, "sans_medium", 42)
    start = (960 - (120 + ww + 70) / 2, 485, 960 + (120 + ww + 70) / 2, 595)
    b = tuple(lerp(s, e, g) for s, e in zip(start, WIN))
    cx, cy, z = cam(t, [(0, 960, 540, 1.0), (1.5, 960, 540, 1.0), (4.5, 1330, 690, 1.6)])
    pp = P((cx, cy, z))
    pp.shadow(b, 18, 0.1)
    pp.rect(b, 18, G.paper, C("line"), 1.5)
    a = eo(prog(t, 0.45, 1.0))
    x0, y0 = b[0], b[1]
    if a <= 0:
        logo(pp, lerp(start[0] + 64, x0 + 46, g), lerp(540, y0 + 40, g), lerp(64, 30, g))
        pp.text(lerp(start[0] + 120, x0 + 74, g), lerp(540, y0 + 40, g), wname, "sans_medium", lerp(42, 22, g),
                C("ink", 1 - g), "lm")
        return pp.out()

    def A(k):
        return eo(prog(t, 0.45 + k * 0.05, 0.95 + k * 0.05))
    # sidebar
    sx1 = x0 + 260
    pp.line([(sx1, y0), (sx1, b[3])], C("line", a), 1.5)
    logo(pp, x0 + 46, y0 + 40, 30)
    pp.text(x0 + 74, y0 + 40, G.c["brand"], "sans_medium", 22, C("ink", a), "lm", max_w=150)
    for i, nav in enumerate(con["nav"]):
        yy = y0 + 104 + i * 46
        if i == 0:
            pp.rect((x0 + 14, yy - 20, sx1 - 14, yy + 20), 8, C((240, 240, 240), A(i)))
        pp.rect((x0 + 34, yy - 8, x0 + 50, yy + 8), 3, None, C((120, 120, 120), A(i)), 1.6)
        pp.text(x0 + 64, yy, nav, "sans_medium" if i == 0 else "sans", 21, C("ink", A(i)), "lm", max_w=150)
        al = con.get("nav_alert", {}).get(nav)
        if al:
            pp.text(sx1 - 30, yy, al, "mono_bold", 20, C("red", A(i)), "rm")
    wy = y0 + 104 + len(con["nav"]) * 46 + 30
    pp.text(x0 + 30, wy, con["workspaces_label"], "sans_medium", 16, C("muted", a), "lm", track=1.2)
    pp.rect((x0 + 14, wy + 22, sx1 - 14, wy + 62), 8, C((244, 244, 244), a))
    pp.text(x0 + 34, wy + 42, wname, "sans", 20, C("ink", a), "lm", max_w=200)
    pp.text(x0 + 50, wy + 86, con["fleet"], "sans", 19, C("muted", a), "lm", max_w=190)
    # top bar
    pp.line([(sx1, y0 + 78), (b[2], y0 + 78)], C("line", a), 1.5)
    pp.text(sx1 + 30, y0 + 40, wname, "sans_medium", 21, C("ink", a), "lm", max_w=400)
    sb = (b[2] - 560, y0 + 20, b[2] - 120, y0 + 60)
    pp.rect(sb, 10, C((250, 250, 250), a), C("line", a), 1.5)
    magnifier(pp, sb[0] + 14, sb[1] + 11, 18, C("muted", a))
    pp.text(sb[0] + 44, y0 + 40, con["search"], "sans", 19, C("muted", a), "lm", max_w=300)
    pp.text(sb[2] - 14, y0 + 40, "Ctrl K", "sans_medium", 16, C("muted", a), "rm")
    pp.circle(b[2] - 60, y0 + 40, 18, C((236, 236, 236), a))
    pp.text(b[2] - 60, y0 + 40, "IV", "sans_bold", 14, C("ink", a), "mm")
    # heading
    mx = sx1 + 46
    pp.text(mx, y0 + 124, con["greeting"], "sans", 20, C("muted", A(1)), "lm", max_w=500)
    pp.text(mx, y0 + 162, wname, "sans_medium", 36, C("ink", A(1)), "lm", max_w=700)
    stats = "  ·  ".join(con["stats"]) + "  ·  "
    pp.text(mx, y0 + 204, stats, "sans", 20, C((110, 110, 110), A(2)), "lm")
    pp.text(mx + tw(stats, "sans", 20), y0 + 204, con["stats_alert"], "sans_medium", 20, C("red", A(2)), "lm")
    pp.rect((b[2] - 240, y0 + 140, b[2] - 46, y0 + 186), 10, C("ink", A(2)))
    pp.text(b[2] - 143, y0 + 163, "+  New policy", "sans_medium", 19, C("paper", 1, C("ink", A(2))), "mm")
    # focus card
    fb = (mx, y0 + 250, mx + 760, y0 + 560)
    pp.rect(fb, 14, C("paper", A(3)), C("line", A(3)), 1.5)
    sparkle(pp, fb[0] + 24, fb[1] + 24, 20, (110, 110, 110), A(3))
    pp.text(fb[0] + 56, fb[1] + 36, con["focus_title"], "sans_medium", 22, C("ink", A(3)), "lm", max_w=400)
    pp.text(fb[0] + 26, fb[1] + 70, con["focus_sub"], "sans", 18, C("muted", A(3)), "lm", max_w=700)
    for i, f in enumerate(con["focus"]):
        k = A(4 + i)
        ry = fb[1] + 104 + i * 66
        pp.rect((fb[0] + 20, ry, fb[2] - 20, ry + 56), 10, C("paper", k), C("line", k), 1.5)
        dark = i == 0
        pp.circle(fb[0] + 48, ry + 28, 13, C("ink" if dark else (236, 236, 236), k))
        pp.text(fb[0] + 48, ry + 28, str(i + 1), "sans_bold", 14,
                C("paper" if dark else "ink", 1 if dark else k, C("ink", k) if dark else None), "mm")
        pp.circle(fb[0] + 78, ry + 19, 5, C(f["col"], k))
        pp.text(fb[0] + 92, ry + 19, f["title"], "sans_medium", 19, C("ink", k), "lm", max_w=420)
        pp.text(fb[0] + 78, ry + 41, f["sub"], "sans", 16, C("muted", k), "lm", max_w=420)
        pp.text(fb[2] - 40, ry + 28, f["status"], "sans_medium", 17, C(f["col"], k), "rm", max_w=200)
    # fleet card
    lb = (mx, y0 + 586, mx + 360, y0 + 760)
    pp.rect(lb, 14, C("paper", A(7)), C("line", A(7)), 1.5)
    pp.text(lb[0] + 26, lb[1] + 38, con["fleet_title"], "sans_medium", 22, C("ink", A(7)), "lm", max_w=310)
    pp.text(lb[0] + 26, lb[1] + 72, con["fleet_line"], "sans", 18, C("muted", A(7)), "lm", max_w=310)
    pp.rect((lb[0] + 26, lb[1] + 118, lb[2] - 26, lb[1] + 126), 4, C((236, 236, 236), A(7)))
    pp.rect((lb[0] + 26, lb[1] + 118, lb[0] + 26 + (lb[2] - lb[0] - 52) * con["fleet_pct"] * eo(prog(t, 1.0, 2.0)),
             lb[1] + 126), 4, C("ink", A(7)))
    # ask panel slides up
    q = ease_drawer(prog(t, 1.6, 2.3))
    if q > 0:
        top = lerp(b[3] + 40, y0 + 250, q)
        ab = (b[2] - 540, top, b[2] - 46, top + 560)
        pp.shadow(ab, 16, 0.12 * q)
        pp.rect(ab, 16, G.paper, C("line", q), 1.5)
        pp.text(ab[0] + 24, ab[1] + 32, "Ask " + G.c["brand"], "sans_medium", 18, C("ink", q), "lm", max_w=300)
        sparkle(pp, (ab[0] + ab[2]) / 2 - 22, ab[1] + 76, 44, "accent", q)
        pp.text((ab[0] + ab[2]) / 2, ab[1] + 154, con["ask_title"], "sans_medium", 22, C("ink", q), "mm", max_w=440)
        ib = (ab[0] + 24, ab[1] + 196, ab[2] - 24, ab[1] + 330)
        pp.rect(ib, 12, C("paper", q), C("line", q), 1.5)
        pp.text(ib[0] + 18, ib[1] + 24, G.b["composer"]["crumb"], "sans", 15, C("muted", q), "lm", max_w=400)
        caret(pp, ib[0] + 20, ib[1] + 62, 24, t, 2.3)
        acts = G.b["composer"]["actions"]
        bx = ib[2] - 16
        for act in reversed(acts):
            w = 46 + tw(act, "sans", 15) + 14
            pp.rect((bx - w, ib[3] - 46, bx, ib[3] - 14), 8, C("paper", q), C("line", q), 1.3)
            sparkle(pp, bx - w + 10, ib[3] - 40, 18, "accent", q)
            pp.text(bx - w + 36, ib[3] - 30, act, "sans", 15, C("ink", q), "lm")
            bx -= w + 10
    return pp.out()


def s_composer(c):
    t = c.lt
    co = G.b["composer"]
    pp = P((960, 540, lerp(1.0, 1.05, eio(prog(t, 0, 4.0)))))
    cb = (130, 200, 1790, 880)
    pp.shadow(cb, 46, 0.1, 40, 18)
    pp.rect(cb, 46, G.paper, C("line"), 2)
    crumb = co["crumb"]
    cw = tw(crumb, "sans", 46)
    kb = (190, 250, 190 + 120 + cw + 34, 350)
    pp.rect(kb, 30, G.paper, C("line"), 2)
    for i in range(4):
        gx, gy = kb[0] + 34 + (i % 2) * 22, 278 + (i // 2) * 22
        pp.rect((gx, gy, gx + 16, gy + 16), 3, None, C((120, 120, 120)), 2.4)
    pp.text(kb[0] + 100, 300, crumb, "sans", 46, C((120, 120, 120)), "lm", max_w=1300)
    pr = co["prompt"]
    tp = prog(t, 0.3, 2.2)
    sub = typed(pr, tp)
    pp.text(190, 480, sub, "sans_medium", 80, G.ink, "lm", max_w=1540, fit_to=pr)
    k = min(1, 1540 / max(1, tw(pr, "sans_medium", 80)))
    caret(pp, 190 + tw(sub, "sans_medium", 80) * k + 6, 482, 92, t, 2.2, solid=tp < 1)
    sparkle(pp, 190, 732, 52, "accent")
    pp.text(262, 765, co["ai"], "sans", 50, C((150, 150, 150)), "lm", max_w=500)
    acts = co["actions"]
    x = 1735
    boxes = {}
    for j in reversed(range(len(acts))):
        w = 30 + 56 + 18 + tw(acts[j], "sans_medium", 50) + 34
        boxes[j] = (x - w, 700, x, 830)
        x -= w + 26
    hot_i = co.get("click", 0)
    press = eo(prog(t, 3.0, 3.1)) * (1 - eo(prog(t, 3.15, 3.5)))
    for j, bx in boxes.items():
        hot = j == hot_i
        fill = (238, 236, 250) if hot and t >= 3.05 else (246, 246, 246) if hot and t > 2.8 else G.paper
        pp.rect(bx, 26, fill, C("line"), 2)
        sparkle(pp, bx[0] + 30, 739, 54, "accent")
        pp.text(bx[0] + 104, 765, acts[j], "sans_medium", 50, G.ink, "lm")
    hot = boxes[hot_i]
    if t > 2.2:
        m = eio(prog(t, 2.3, 2.95))
        px, py = lerp(1560, (hot[0] + hot[2]) / 2 + 30, m), lerp(1080, (hot[1] + hot[3]) / 2 + 10, m)
        cursor(pp, px, py, 40, press)
    return pp.out()


def s_thinking(c):
    t = c.lt
    pp = P((960, 540, lerp(1.0, 1.06, prog(t, 0, 1.8))))
    word = G.b["thinking"]
    ww = tw(word, "sans_medium", 140)
    tot = 190 + 50 + ww + 60 + 3 * 60
    x0 = 960 - tot / 2
    s = spring(t, 300, 24)
    logo(pp, x0 + 95, 540, 190 * s)
    pp.rise(x0 + 240, 540, word, "sans_medium", 140, G.ink, eo(prog(t, 0.1, 0.5)), "lm", max_w=1100)
    for i, col in enumerate(G.light[:3]):
        a = eo(prog(t, 0.3 + i * 0.08, 0.6 + i * 0.08))
        bob = 12 * max(0, math.sin((t - 0.6) * 7 - i * 0.9)) if t > 0.6 else 0
        pp.circle(x0 + 240 + ww + 90 + i * 64, 552 - bob, 23 * a, C(col, 1))
    return pp.out()


VERD = {"Allowed": "green", "Blocked": "red", "Held": "amber"}


def s_table(c):
    t = c.lt
    tb = G.b["table"]
    cx, cy, z = cam(t, [(0, 960, 540, 1.04), (2.3, 960, 540, 1.0), (5.2, 1390, 470, 1.5)])
    pp = P((cx, cy, z))
    pp.text(170, 110, tb["title"], "sans_bold", 40, G.ink, "lm", max_w=400)
    x = 170 + tw(tb["title"], "sans_bold", 40) + 44
    for i, tab in enumerate(tb["tabs"]):
        w = tw(tab, "sans", 28) + 40
        if i == 1:
            pp.rect((x, 86, x + w, 134), 10, (240, 240, 240))
        pp.text(x + 20, 110, tab, "sans_medium" if i == 1 else "sans", 28, C("ink" if i == 1 else "muted"), "lm")
        x += w + 10
    pp.line([(120, 160), (1900, 160)], C("line"), 1.5)
    cols = [230, 900, 1180, 1420]
    for k, hd in enumerate(tb["cols"]):
        pp.text(cols[k], 200, hd, "sans_medium", 22, C("muted"), "lm", track=1.2)
    checkbox(pp, 168, 188, 24, 0)
    opened = tb.get("open", 0)
    click = 1.9
    for i, row in enumerate(tb["rows"]):
        y = 270 + i * 82
        a = eo(prog(t, 0.1 + i * 0.06, 0.5 + i * 0.06))
        if a <= 0:
            continue
        dy = (1 - a) * 18
        if i == opened and t > click:
            pp.rect((140, y - 38, 1880, y + 38), 10, (244, 244, 246))
        pp.line([(140, y + 41), (1880, y + 41)], C("line", a), 1.2)
        checkbox(pp, 168, y - 12 + dy, 24, 0, a)
        pp.text(cols[0], y + dy, row[0], "mono", 30, C("ink", a), "lm", max_w=640)
        pp.text(cols[1], y + dy, row[1], "sans", 30, C((90, 90, 90), a), "lm", max_w=260)
        vc = VERD.get(row[2], "muted")
        pp.circle(cols[2] + 7, y + dy, 7, C(vc, a))
        pp.text(cols[2] + 26, y + dy, row[2].upper(), "mono_medium", 24, C(vc, a), "lm", track=1.5, max_w=200)
        pp.text(cols[3], y + dy, row[3], "sans", 28, C("muted", a), "lm")
    if 0.9 < t < 2.4:
        m = eio(prog(t, 1.0, 1.8))
        ty = 270 + opened * 82
        cursor(pp, lerp(1250, 420, m), lerp(1000, ty + 8, m), 40,
               eo(prog(t, click - 0.08, click)) * (1 - eo(prog(t, click + 0.05, click + 0.3))))
    q = ease_drawer(prog(t, 2.0, 2.65))
    if q > 0:
        de = tb["detail"]
        x0 = lerp(1960, 1010, q)
        db = (x0, 70, x0 + 800, 1060)
        pp.shadow(db, 16, 0.14, 40, 10)
        pp.rect(db, 16, G.paper, C("line"), 1.5)
        pp.text(x0 + 40, 120, de["crumb"], "sans", 24, C("muted"), "lm", max_w=600)
        pp.line([(x0, 160), (x0 + 800, 160)], C("line"), 1.2)
        pp.text(x0 + 40, 220, de["title"], "sans_bold", 50, G.ink, "lm", max_w=700)
        pp.circle(x0 + 48, 282, 8, C("red"))
        pp.text(x0 + 66, 282, tb["rows"][opened][2].upper(), "mono_bold", 26, C("red"), "lm", track=2)
        pp.text(x0 + 40, 350, "Command", "sans_medium", 26, C("muted"), "lm")
        pp.rect((x0 + 40, 375, x0 + 760, 455), 10, (245, 245, 245))
        pp.text(x0 + 66, 415, de["cmd"], "mono_medium", 36, G.ink, "lm", max_w=660)
        pp.text(x0 + 40, 510, "Why", "sans_medium", 26, C("muted"), "lm")
        pp.text(x0 + 40, 556, de["why"], "pixel", 33, G.ink, "lm", max_w=700)
        for k, (lab, val) in enumerate(de["fields"]):
            y = 650 + k * 82
            pp.line([(x0 + 40, y - 38), (x0 + 760, y - 38)], C("line"), 1.2)
            pp.text(x0 + 40, y, lab, "sans", 28, C("muted"), "lm", max_w=200)
            pp.text(x0 + 260, y, val, "sans_medium", 30, G.ink, "lm", max_w=480)
    return pp.out()


def s_checklist(c):
    t = c.lt
    ck = G.b["checklist"]
    pp = P((960, 540, lerp(1.0, 1.1, eio(prog(t, 0, 3.6)))))
    cb = (380, 170, 1540, 900)
    pp.shadow(cb, 30, 0.1, 40, 16)
    pp.rect(cb, 30, G.paper, C("line"), 2)
    for i in range(3):
        y = 236 + i * 18
        pp.line([(450, y), (466, y)], C((90, 90, 90)), 3)
        pp.line([(476, y), (500, y)], C((90, 90, 90)), 3)
    pp.text(530, 254, ck["title"], "sans_medium", 56, G.ink, "lm", max_w=560)
    aw = tw(ck["action"], "sans", 40) + 104
    ab = (1490 - aw, 214, 1490, 294)
    pp.rect(ab, 16, G.paper, C("line"), 2)
    sparkle(pp, ab[0] + 24, 232, 42, "accent")
    pp.text(ab[0] + 80, 254, ck["action"], "sans", 40, G.ink, "lm")
    wr = 1 - eo(prog(t, 0.9, 1.1))
    if t > 0.15 and wr > 0:
        sh = 0.55 + 0.45 * math.sin(t * 10)
        col = C("accent", wr * sh)
        sparkle(pp, 450, 340, 40, col)
        pp.text(506, 362, typed(ck["writing"], prog(t, 0.15, 0.55)), "sans_medium", 40, col, "lm", fit_to=ck["writing"])
    for k, it in enumerate(ck["items"][:4]):
        t0 = 0.95 + k * 0.42
        a = eo(prog(t, t0, t0 + 0.35))
        if a <= 0:
            continue
        y = 380 + k * 118
        checkbox(pp, 450, y - 28, 56, 0, a, 12)
        pp.rise(540, y, it, "sans", 54, C("ink", a), a, "lm", max_w=900)
    return pp.out()


def _hl_text(pp, x, y, s, q, role, size, col, p, max_w):
    """Text with the first match of q highlighted by a marker sweep (progress p)."""
    i = s.lower().find(q.lower()) if q else -1
    if i >= 0 and p > 0:
        x0 = x + tw(s[:i], role, size)
        x1 = x0 + tw(s[i:i + len(q)], role, size)
        ui.marker(pp.d, (pp.X(x0 - 6), pp.Y(y - size * 0.62), pp.X(x1 + 6), pp.Y(y + size * 0.55)), C("marker"), p, 0)
    pp.text(x, y, s, role, size, col, "lm", max_w=max_w)


def s_search(c):
    t = c.lt
    se = G.b["search"]
    cx, cy, z = cam(t, [(0, 960, 540, 1.0), (1.3, 960, 540, 1.0), (2.4, 860, 520, 1.45), (3.3, 860, 520, 1.45),
                        (4.3, 960, 760, 1.4)])
    pp = P((cx, cy, z))
    logo(pp, 960, 70, 66)
    pp.text(960, 170, se["heading"], "sans_bold", 72, G.ink, "mm", max_w=1500)
    sb = (300, 240, 2000, 1000)
    pp.shadow(sb, 30, 0.08, 40, 10)
    pp.rect(sb, 30, G.paper, C("line"), 2)
    magnifier(pp, 350, 290, 52, C((120, 120, 120)))
    q = se["query"]
    tp = prog(t, 0.45, 1.05)
    if tp <= 0:
        pp.text(440, 316, se["placeholder"], "sans", 54, C((170, 170, 170)), "lm", max_w=1100)
        caret(pp, 438, 316, 60, t, 0)
    else:
        sub = typed(q, tp)
        pp.text(440, 316, sub, "sans", 54, G.ink, "lm")
        caret(pp, 444 + tw(sub, "sans", 54), 316, 60, t, 1.05, solid=tp < 1)
    pp.line([(300, 400), (2000, 400)], C("line"), 2)
    rt = 1.3
    if t < rt:
        pp.text(350, 450, se["works"], "sans", 30, C("muted"), "lm", max_w=700)
        x = 350 + tw(se["works"], "sans", 30) + 40
        for k, it in enumerate(G.b["agents"]["items"][:8]):
            pp.icon(it["icon"], x + k * 58, 450, 36)
        return pp.out()
    for k, r in enumerate(se["results"][:3]):
        y = 470 + k * 108
        a = eo(prog(t, rt + k * 0.08, rt + 0.35 + k * 0.08))
        if k == 0:
            pp.rect((320, y - 50, 1980, y + 50), 18, C((244, 244, 244), a))
        pp.text(350, y, r["kind"], "sans", 44, C("muted", a), "lm", max_w=220)
        _hl_text(pp, 590, y, r["text"], q, "sans", 50, C("ink", a),
                 eo(prog(t, rt + 0.3 + k * 0.15, rt + 0.6 + k * 0.15)), 980)
        pp.text(1620, y, r["where"], "sans", 40, C("muted", a), "lm", max_w=360)
    sy = 470 + 3 * 108 + 40
    st = prog(t, 3.3, 4.4)
    if st > 0:
        pp.line([(300, sy - 40), (2000, sy - 40)], C("line"), 2)
        sparkle(pp, 350, sy - 2, 40, "accent")
        pp.text(410, sy + 18, typed(se["summary"], st), "sans_medium", 40, G.ink, "lm", max_w=1150, fit_to=se["summary"])
    return pp.out()


def _bubble(pp, x, y, m, a, s=40, bold_lead=False, link=None):
    """Chat message: monogram tile, name + time, grey bubble. Returns the bubble box."""
    avatar(pp, x, y, s * 2.2, m["name"], a)
    nx = x + s * 2.2 + s * 0.65
    pp.text(nx, y + s * 0.5, m["name"], "sans_bold", s, C("ink", a), "lm", max_w=700)
    pp.text(nx + tw(m["name"], "sans_bold", s) + s * 0.5, y + s * 0.55, m["time"], "sans", s * 0.8, C("muted", a), "lm")
    txt = m["text"]
    lead = txt.split(" ")[0] if bold_lead and txt.startswith("@") else ""
    rest = txt[len(lead):]
    extra = ("  " + link) if link else ""
    w = tw(lead, "sans_bold", s) + tw(rest + extra, "sans", s)
    bb = (nx, y + s * 1.25, nx + w + s * 1.3, y + s * 3.05)
    pp.rect(bb, s * 0.75, C((239, 239, 239), a))
    my = (bb[1] + bb[3]) / 2
    if lead:
        pp.text(nx + s * 0.65, my, lead, "sans_bold", s, C("ink", a), "lm")
    rx = nx + s * 0.65 + tw(lead, "sans_bold", s)
    pp.text(rx, my, rest, "sans", s, C("ink", a), "lm", max_w=1300)
    if link:
        lx = rx + tw(rest + "  ", "sans", s)
        pp.text(lx, my, link, "sans", s, C((70, 70, 70), a), "lm")
        pp.line([(lx, my + s * 0.55), (lx + tw(link, "sans", s), my + s * 0.55)], C((70, 70, 70), a), 1.6)
    return bb


def s_thread(c):
    t = c.lt
    th = G.b["thread"]
    msgs = th["messages"][:3]
    rep = th["reply"]
    ry = 200 + len(msgs) * 160
    nx = 520 + 40 * 2.85
    bw = tw(rep["text"] + "  " + rep.get("link", ""), "sans", 40) + 52
    zf = min(2.3, 1920 * 0.86 / (bw + 60))
    fx = nx + bw / 2
    cx, cy, z = cam(t, [(0, 960, 470, 1.15), (2.4, 960, 560, 1.0), (3.3, fx, ry + 100, zf), (5.2, fx, ry + 115, zf * 1.06)])
    pp = P((cx, cy, z))
    for i, m in enumerate(msgs):
        a = eo(prog(t, i * 0.45, i * 0.45 + 0.4))
        if a > 0:
            _bubble(pp, 520, 200 + i * 160 + (1 - a) * 22, m, a)
    a = eo(prog(t, 1.7, 2.1))
    if a > 0:
        bb = _bubble(pp, 520, ry + (1 - a) * 22, rep, a, link=rep.get("link"))
        k = eo(prog(t, 3.1, 3.4))      # the counter: a drawn check and a number that ticks up
        if k > 0:
            cn = th["counter"]
            v = int(round(lerp(cn["from"], cn["to"], eio(prog(t, 3.5, 4.7)))))
            yy = bb[3] + 46
            checkbox(pp, bb[0] + 4, yy - 17, 34, 1.0, k, 8)
            pp.text(bb[0] + 54, yy, str(v), "sans_medium", 38, C("ink", k), "lm")
    return pp.out()


def s_agents(c):
    t = c.lt
    ag = G.b["agents"]
    items = ag["items"][:8]
    cells = [(300 + (i % 4) * 440, 450 + (i // 4) * 190) for i in range(len(items))]
    pk = min(ag.get("punch", 0), len(items) - 1)
    pxc, pyc = cells[pk]
    cxx, cyy, z = cam(t, [(0, 960, 540, 1.0), (2.1, 960, 540, 1.04), (2.85, pxc + 130, pyc, 2.6)])
    pp = P((cxx, cyy, z))
    order = [0, 4, 1, 5, 2, 6, 3, 7]
    for i, it in enumerate(items):
        x, y = cells[i]
        o = order.index(i)
        a = eo(prog(t, 0.1 + o * 0.09, 0.5 + o * 0.09))
        w = 52 + 18 + tw(it["name"], "sans_bold", 44)
        x0 = x - w / 2 + 130
        pp.icon(it["icon"], x0 + 26, y + (1 - a) * 20, 52, a)
        pp.rise(x0 + 70, y, it["name"], "sans_bold", 44, G.ink, a, "lm", max_w=330)
    return pp.out()


def s_timeline(c):
    t = c.lt
    rows = G.b["timeline"]["rows"][:3]
    pp = P((900, 470, lerp(1.18, 1.1, eio(prog(t, 0, 3.0)))))
    for i, r in enumerate(rows):
        y = 300 + i * 170
        a = eo(prog(t, i * 0.14, 0.4 + i * 0.14))
        if a <= 0:
            continue
        dy = (1 - a) * 20
        pp.line([(0, y + 85), (1920, y + 85)], C("line", a), 1.5)
        dp = eo(prog(t, 1.2, 1.55)) if r.get("done") else 0
        pp.circle(220, y + dy, 13, mix(C(r["col"], a), C("green", a), dp))
        tc = mix(C("ink", a), C((150, 150, 150), a), dp)
        pp.text(260, y + dy, r["text"], "sans", 66, tc, "lm", max_w=900)
        w = min(900, tw(r["text"], "sans", 66))
        if dp > 0:
            pp.line([(258, y + dy + 4), (258 + (w + 4) * dp, y + dy + 4)], tc, 4)
        lx0, lx1 = 260 + w + 50, 1330
        for k in range(max(0, int((lx1 - lx0) / 22))):
            pp.circle(lx0 + k * 22, y + dy + 10, 2.4, C((200, 200, 200), a))
        if dp > 0:
            pp.text(1370, y + dy, r["date"], "mono_medium", 50, C(r["col"], a * (1 - dp)), "lm", max_w=420)
            pp.text(1370, y + dy, G.b["timeline"]["done"], "mono_medium", 50, mix(C(r["col"], a * (1 - dp)), C("green", a), dp), "lm", max_w=420)
        else:
            pp.text(1370, y + dy, r["date"], "mono_medium", 50, C(r["col"], a), "lm", max_w=420)
    return pp.out()


def s_team(c):
    t = c.lt
    pp = P((960, 520, lerp(1.25, 1.18, prog(t, 0, 2.6))))
    for i, m in enumerate(G.b["team"][:3]):
        a = eo(prog(t, i * 0.5, i * 0.5 + 0.4))
        if a > 0:
            _bubble(pp, 560, 230 + i * 170 + (1 - a) * 22, m, a, 42, True)
    return pp.out()


OUT_SPLIT = 4.9


def s_outro(c):
    t = c.lt
    o = G.b["outro"]
    items = o["items"]
    brand = G.c["brand"]
    line = o["line"]
    size = 70
    lw = tw(line, "sans_medium", size)
    if t < OUT_SPLIT:
        # "<Brand> does" types, slides left, and a checklist cascades beside it
        shift = eio(prog(t, 1.55, 2.0))
        x0 = lerp(960 - lw / 2, 900 - lw, shift)
        cxx, cyy, z = cam(t, [(0, 960, 540, 1.0), (2.2, 960, 540, 1.0), (4.8, 1070, 545, 1.5)])
        pp = P((cxx, cyy, z))
        b = len(brand)
        sub = typed(line[:b], prog(t, 0.3, 0.8)) if t < 1.1 else line[:b] + typed(line[b:], prog(t, 1.1, 1.45))
        pp.text(x0, 540, sub, "sans_medium", size, G.ink, "lm", fit_to=line)
        if t < 1.8:
            caret(pp, x0 + tw(sub, "sans_medium", size) + 6, 542, 84, t, 1.45, solid=0.3 < t < 1.45)
        if t > 1.85:
            gaps = [0.5, 0.42, 0.34, 0.28, 0.24, 0.2, 0.18, 0.16, 0.15, 0.14, 0.13, 0.12]
            st, s = [], 1.85
            for k in range(len(items)):
                st.append(s)
                s += gaps[min(k, len(gaps) - 1)]
            rh, vis = 66, 5
            n = sum(1 for s0 in st if t >= s0)
            grow = [eio(prog(t, s0, s0 + 0.18)) for s0 in st]
            rows_h = min(vis, sum(grow))
            bx0 = 940
            bw = max(tw(it, "sans", 48) for it in items) + 150
            bot = 540 + 44
            top = bot - rows_h * rh - 24
            box = (bx0, top, bx0 + bw, bot)
            pp.shadow(box, 16, 0.1, 26, 10)
            pp.rect(box, 16, G.paper, C("line"), 1.5)
            for k in range(n):
                # the newest slides up from the card's bottom edge and pushes the rest up
                y = bot - 12 - rh * (0.5 + sum(grow[k + 1:n]) - (1 - grow[k]))
                a = min(1, max(0, (y - top) / (rh * 0.5))) * min(1, max(0, (bot - 12 - y) / (rh * 0.5)))
                if a <= 0:
                    continue
                on = eo(prog(t, st[k] + 0.3, st[k] + 0.46)) if k < len(items) - 1 else 0
                checkbox(pp, bx0 + 30, y - 21, 42, on, a, 8)
                tc = mix(C("ink", a), C((150, 150, 150), a), on)
                pp.text(bx0 + 96, y, items[k], "sans", 48, tc, "lm", max_w=bw - 120)
                if on > 0:
                    pp.line([(bx0 + 94, y + 3), (bx0 + 94 + tw(items[k], "sans", 48) * on, y + 3)], tc, 3)
        return pp.out()
    # one box left: the cursor ticks it, and it turns into the logo
    lt = t - OUT_SPLIT
    pp = P((960, 540, 1.0))
    fin = o["final"]
    fs = 84
    fw = tw(fin, "sans", fs)
    bx = 960 - (84 + 34 + fw) / 2
    morph = eio(prog(lt, 1.15, 1.6))
    bw_ = tw(brand, "sans_bold", 104)
    lx = 960 - (116 + 30 + bw_) / 2
    s = lerp(84, 116, morph)
    x = lerp(bx, lx, morph)
    yb = 540 - 40 * eio(prog(lt, 1.8, 2.3))
    if morph < 1:
        checkbox(pp, x, yb - s / 2, s, eo(prog(lt, 0.75, 0.95)), 1 - morph, s * 0.2)
    if morph > 0:
        logo(pp, x + s / 2, yb, s, morph)
    if lt < 1.15:
        pp.text(bx + 84 + 34, 540, fin, "sans", fs, C((130, 130, 130)), "lm", max_w=1500)
        m = eio(prog(lt, 0.1, 0.7))
        cursor(pp, lerp(1300, bx + 44, m), lerp(900, 552, m), 44,
               eo(prog(lt, 0.68, 0.75)) * (1 - eo(prog(lt, 0.8, 1.0))))
    else:
        pp.text(x + s + 30, yb, typed(brand, prog(lt, 1.3, 1.65)), "sans_bold", 104, G.ink, "lm", fit_to=brand,
                max_w=1500)
        pp.rise(960, 660, G.c["cta"], "sans_medium", 50, C((70, 70, 70)), eo(prog(lt, 1.95, 2.4)), "mm", max_w=1200)
    return pp.out()


SCENES = [("hook", 5.0, s_hook), ("not_a", 5.5, s_not_a), ("logo", 1.5, s_logo), ("console", 4.5, s_console),
          ("composer", 4.0, s_composer), ("thinking", 1.8, s_thinking), ("table", 5.2, s_table),
          ("checklist", 3.6, s_checklist), ("search", 4.8, s_search), ("thread", 5.2, s_thread),
          ("agents", 3.0, s_agents), ("timeline", 3.0, s_timeline), ("team", 2.6, s_team), ("outro", 7.8, s_outro)]


def starts():
    out, t = {}, 0.0
    for n, d, _ in SCENES:
        out[n] = t
        t += d
    return out, t


# ------------------------------------------------------------------ sound: soft keys, plucks, typing ticks, clicks
def score(path):
    st, dur = starts()
    sc = Score(100, dur + 0.4)
    chords = [["C3", "G3", "E4"], ["A2", "E3", "C4"], ["F2", "C3", "A3"], ["G2", "D3", "B3"]]
    bar8 = 8 * sc.spb
    for k in range(int((st["outro"] + OUT_SPLIT - st["not_a"]) / bar8) + 1):
        t0 = st["not_a"] + k * bar8
        sc.chord(chords[k % 4], t0, bar8 + 0.3, 0.32)
        root = chords[k % 4][0]
        sc.bass([(root, 0, 1.5), (root, 3, 1), (root, 4, 1.5), (root, 6, 1)], start=t0, gain=0.35)
    sc.pattern("tick", 1, start=st["not_a"] / sc.spb, end=(st["outro"] + OUT_SPLIT) / sc.spb, gain=0.1, pitch=1.4)

    def typing(t0, t1, n, gain=0.22):
        for i in range(n):
            sc.hit("tick", t0 + (t1 - t0) * i / max(1, n), gain, pitch=2.2 + 0.3 * ((i * 7) % 3))
    sc.hit("blip", st["hook"] + 1.0, 0.5, note="C6")
    sc.hit("blip", st["hook"] + 1.2, 0.5, note="E6")
    typing(st["hook"] + 1.62, st["hook"] + 2.3, len(G.b["hook"]["line"]))
    for i in range(3):
        typing(st["not_a"] + i * 1.55 + 0.05, st["not_a"] + i * 1.55 + 0.5, 8, 0.15)
        sc.hit("clack", st["not_a"] + i * 1.55 + 0.5, 0.35)
        sc.hit("blip", st["not_a"] + i * 1.55 + 0.9, 0.3, note="G5")
    sc.hit("blip", st["logo"] + 0.05, 0.6, note="C6")
    sc.hit("blip", st["logo"] + 0.15, 0.4, note="G6")
    typing(st["composer"] + 0.3, st["composer"] + 2.2, len(G.b["composer"]["prompt"]))
    sc.hit("clack", st["composer"] + 3.05, 0.6)
    for i in range(3):
        sc.hit("blip", st["thinking"] + 0.3 + i * 0.08, 0.3, note=["E6", "G6", "C7"][i])
    sc.hit("clack", st["table"] + 1.9, 0.6)
    for k in range(len(G.b["checklist"]["items"][:4])):
        sc.hit("blip", st["checklist"] + 0.95 + k * 0.42, 0.3, note=["C6", "D6", "E6", "G6"][k % 4])
    typing(st["search"] + 0.45, st["search"] + 1.05, len(G.b["search"]["query"]))
    typing(st["search"] + 3.3, st["search"] + 4.4, 20, 0.12)
    for tt in (0, 0.45, 0.9, 1.7):
        sc.hit("blip", st["thread"] + tt, 0.3, note="A5")
    cn = G.b["thread"]["counter"]
    steps = max(1, cn["to"] - cn["from"])
    for i in range(steps):
        sc.hit("tick", st["thread"] + 3.5 + 1.2 * i / steps, 0.25, pitch=2.8)
    sc.hit("blip", st["timeline"] + 1.2, 0.45, note="E6")
    sc.hit("blip", st["timeline"] + 1.32, 0.45, note="A6")
    typing(st["outro"] + 0.3, st["outro"] + 1.45, len(G.b["outro"]["line"]))
    sc.hit("clack", st["outro"] + OUT_SPLIT + 0.72, 0.6)
    sc.chord(["C3", "G3", "E4", "B4"], st["outro"] + OUT_SPLIT + 1.15, 3.0, 0.5)
    sc.hit("blip", st["outro"] + OUT_SPLIT + 1.15, 0.6, note="C7")
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


SECTIONS = ("hook", "not_a", "console", "composer", "table", "checklist", "search", "thread", "agents", "timeline",
            "team", "outro")


def check(tl):
    errs = []
    for k in ("brand", "url", "cta"):
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
        if s.rstrip().endswith("."):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "score", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        sys.exit(0 if check(tl) else 1)
    elif a.cmd == "assets":
        print("No generated images. Supply assets/logo.png (the real logo) and fetch agent icons with the "
              "brand-icons skill into assets/icons/.")
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), cols=6, rows=5, thumb_w=320))
    elif a.cmd == "score":
        print(score(os.path.join(out, "score.m4a")))
    else:
        audio = a.audio or score(os.path.join(out, "score.m4a"))
        print(tl.render(a.out or os.path.join(out, "ui-macro-launch-film.mp4"), audio))


if __name__ == "__main__":
    main()
