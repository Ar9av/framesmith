"""cartoon-launch-film: a ~45 s square hand-drawn cartoon launch film, music only. framesmith template.

Boiling linework (three displaced drawings per sprite, cycled on threes), squash and stretch, springs, camera
shake, a paper world. The cut sits on a 120 BPM grid from the burst at 4.2 s. All copy comes from the brief.

    python3 main.py init DIR | check | assets [name ...] | still T ... | sheet [T ...] | render [--from N --to M --out f.mp4]
    every verb takes --brief path/to/brief.json (default: examples/obsidian-wiki/brief.json)
"""
import json, math, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _brief_path():
    if "--brief" in sys.argv:
        return os.path.abspath(sys.argv[sys.argv.index("--brief") + 1])
    return os.path.join(HERE, "..", "examples", "obsidian-wiki", "brief.json")


BRIEF_PATH = _brief_path()
BRIEF = json.load(open(BRIEF_PATH))
C = BRIEF["copy"]
BASE = os.path.dirname(BRIEF_PATH)
ASSETS = os.path.join(BASE, BRIEF.get("assets_dir", "assets"))
CACHE = os.path.join(BASE, "out", "boil")
OUT = os.path.join(BASE, "out")
WARN = []                                   # copy that had to shrink below 80% of its designed size
S = 1080
FPS = 30
T_END = 32.4
INK = (35, 32, 42)
CREAM = (244, 239, 225)
CORAL = (227, 106, 78)
PINK = (242, 169, 176)
GREEN = (181, 219, 140)
MUSTARD = (240, 192, 74)
LAV = (140, 124, 240)
RED = (226, 72, 58)
DARK = (22, 32, 44)
GY = 800                     # ground line
B0 = 4.2                     # first downbeat (the burst)


def B(k):
    return B0 + 0.5 * k


# ------------------------------------------------------------------ easing / motion
def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = cl(t)
    return t * t * (3 - 2 * t)


def eout(t):
    t = cl(t)
    return 1 - (1 - t) ** 3


def ein(t):
    t = cl(t)
    return t ** 3


def back(t, k=1.7):
    t = cl(t)
    return 1 + (k + 1) * (t - 1) ** 3 + k * (t - 1) ** 2


def spring(t, k=260.0, c=14.0):
    if t <= 0:
        return 0.0
    w0 = math.sqrt(k)
    z = c / (2 * w0)
    if z >= 1:
        return 1 - math.exp(-w0 * t) * (1 + w0 * t)
    wd = w0 * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))


def squash(t, t_hit, amt=0.22, k=420, c=10):
    """Impact squash that springs back: returns (sx, sy)."""
    if t < t_hit:
        return 1.0, 1.0
    d = 1 - spring(t - t_hit, k, c)
    return 1 + amt * d, 1 - amt * d


def hop(t, t0, dur=0.42, h=60):
    """One hop: anticipation dip, arc, landing squash. Returns (dy, sx, sy)."""
    p = (t - t0) / dur
    if p < 0 or p > 1.6:
        return 0, 1, 1
    if p < 0.15:                                   # anticipation
        q = p / 0.15
        return 0, 1 + 0.12 * q, 1 - 0.12 * q
    if p < 1:
        q = (p - 0.15) / 0.85
        s = 1 + 0.1 * math.sin(q * math.pi)
        return -h * 4 * q * (1 - q), 1 / s, s
    q = (p - 1) / 0.6                             # land
    d = math.exp(-q * 5) * math.cos(q * 9)
    return 0, 1 + 0.14 * d, 1 - 0.14 * d


def boil(t):
    return int(t * 10) % 3                         # drawings change on threes (10 fps)


def rnd(seed):
    return np.random.default_rng(seed)


# ------------------------------------------------------------------ fonts
FONTS = os.path.join(HERE, "fonts")
EFONTS = os.path.join(HERE, "framesmith", "fonts")
_f = {}


def gfont(size, wght=850):
    k = ("g", size, wght)
    if k not in _f:
        f = ImageFont.truetype(os.path.join(FONTS, "Grandstander[wght].ttf"), size)
        f.set_variation_by_axes([wght])
        _f[k] = f
    return _f[k]


def mono(size, bold=False):
    k = ("m", size, bold)
    if k not in _f:
        _f[k] = ImageFont.truetype(os.path.join(EFONTS, "GeistMono-SemiBold.otf" if bold else "GeistMono-Regular.otf"), size)
    return _f[k]


NOLIG = ["-liga", "-calt"]

# ------------------------------------------------------------------ sprites with boil
_spr = {}


def clean_alpha(im):
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3]
    al = np.clip((al - 140) / 80, 0, 1) * 255                # kill the soft halo the model paints around cut-outs
    a[..., 3] = al
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def boil_variants(im, amp=2.2, seed=0, cell=28):
    """Three redrawn-looking variants: a smooth random mesh warp (PIL MESH, C speed)."""
    w, h = im.size
    nx, ny = w // cell + 2, h // cell + 2
    out = []
    for v in range(3):
        r = rnd(seed * 7 + v)
        dx = gaussian_filter(r.standard_normal((ny + 1, nx + 1)), 0.8)
        dy = gaussian_filter(r.standard_normal((ny + 1, nx + 1)), 0.8)
        dx *= amp / (dx.std() + 1e-6)
        dy *= amp / (dy.std() + 1e-6)
        mesh = []
        for j in range(ny):
            for i in range(nx):
                x0, y0, x1, y1 = i * cell, j * cell, (i + 1) * cell, (j + 1) * cell
                q = (x0 + dx[j, i], y0 + dy[j, i], x0 + dx[j + 1, i], y1 + dy[j + 1, i],
                     x1 + dx[j + 1, i + 1], y1 + dy[j + 1, i + 1], x1 + dx[j, i + 1], y0 + dy[j, i + 1])
                mesh.append(((x0, y0, x1, y1), q))
        out.append(im.transform((w, h), Image.MESH, mesh, Image.BILINEAR))
    return out


def sprite(name, maxh=None):
    maxh = 900 if name == "notebook" else 640
    if name not in _spr:
        cache = CACHE
        fs = [os.path.join(cache, f"{name}_{v}.png") for v in range(3)]
        if all(os.path.exists(f) for f in fs):
            _spr[name] = [Image.open(f).convert("RGBA") for f in fs]
        else:
            im = clean_alpha(Image.open(os.path.join(ASSETS, name + ".png")).convert("RGBA"))
            im = im.crop(im.getbbox())
            s = min(1.0, maxh / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            _spr[name] = boil_variants(im, seed=sum(map(ord, name)))
            os.makedirs(cache, exist_ok=True)
            for f, v in zip(fs, _spr[name]):
                v.save(f)
    return _spr[name]


def icon(slug, size):
    k = ("icon", slug, size)
    if k not in _spr:
        im = Image.open(os.path.join(ASSETS, "icons", slug + ".png")).convert("RGBA")
        im = im.crop(im.getbbox())
        s = size / max(im.size)
        _spr[k] = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return _spr[k]


def put(im, name, x, y, h, t, rot=0.0, sx=1.0, sy=1.0, a=1.0, flip=False, anchor="bottom", src=None):
    """Draw a boiling sprite. (x, y) is bottom-centre (or centre) in frame px; h is the height in px."""
    if h <= 2 or a <= 0.01:
        return
    base = src if src is not None else sprite(name)[boil(t)]
    w = base.width * h / base.height * sx
    hh = h * sy
    L = base.resize((max(1, int(w)), max(1, int(hh))), Image.BILINEAR)
    if flip:
        L = L.transpose(Image.FLIP_LEFT_RIGHT)
    if abs(rot) > 0.05:
        L = L.rotate(rot, resample=Image.BILINEAR, expand=True)
    if a < 1:
        L.putalpha(L.getchannel("A").point(lambda v: int(v * a)))
    if anchor == "bottom":
        px, py = x - L.width / 2, y - L.height + (L.height - hh) / 2
    else:
        px, py = x - L.width / 2, y - L.height / 2
    im.alpha_composite(L, (int(px), int(py))) if 0 <= px and 0 <= py and px + L.width <= im.width and py + L.height <= im.height \
        else paste_clip(im, L, int(px), int(py))


def paste_clip(im, L, px, py):
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(im.width, px + L.width), min(im.height, py + L.height)
    if x1 <= x0 or y1 <= y0:
        return
    im.alpha_composite(L.crop((x0 - px, y0 - py, x1 - px, y1 - py)), (x0, y0))


# ------------------------------------------------------------------ paper world
def make_paper(v):
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    band = ((xx + yy) // 92) % 2
    a = np.zeros((S, S, 3), np.float32) + np.array(CREAM, np.float32)
    a -= band[..., None] * np.array([5, 6, 9], np.float32)
    r = rnd(100 + v)
    g = gaussian_filter(r.standard_normal((S, S)), 0.7) * 5.5
    a += g[..., None]
    fib = gaussian_filter(r.standard_normal((S // 3, S // 3)), 2.0)
    fib = np.asarray(Image.fromarray(fib.astype(np.float32)).resize((S, S), Image.BICUBIC)) * 9
    a += fib[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


def _cached(name, fn, v):
    p = os.path.join(CACHE, f"{name}_{v}.png")
    if os.path.exists(p):
        return Image.open(p).convert("RGBA")
    im = fn(v)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    im.save(p)
    return im


PAPER = [_cached("_paper", make_paper, v) for v in range(3)]


def make_ground(v):
    lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    r = rnd(300 + v)
    pts = [(x, GY + 2.2 * math.sin(x / 47 + v) + r.normal(0, 0.6)) for x in range(-10, S + 20, 12)]
    d.polygon(pts + [(S + 20, S), (-10, S)], fill=GREEN + (255,))
    # hatching in the grass
    for k in range(380):
        x = r.uniform(0, S)
        y = r.uniform(GY + 18, S)
        d.line((x, y, x + 7, y - 4), fill=(150, 196, 110, 150), width=2)
    d.line(pts, fill=INK + (255,), width=4)
    for k in range(70):                          # tufts along the horizon
        x = r.uniform(0, S)
        y = GY + 2.2 * math.sin(x / 47 + v)
        for j in range(3):
            ang = -math.pi / 2 + (j - 1) * 0.35 + r.normal(0, 0.08)
            ln = r.uniform(9, 17)
            d.line((x + j * 3, y, x + j * 3 + math.cos(ang) * ln, y + math.sin(ang) * ln), fill=INK + (255,), width=2)
    for k in range(12):                          # daisies
        x, y = r.uniform(20, S - 20), r.uniform(GY + 40, S - 30)
        for j in range(5):
            ang = j * 2 * math.pi / 5
            d.ellipse((x + math.cos(ang) * 6 - 4, y + math.sin(ang) * 6 - 4, x + math.cos(ang) * 6 + 4, y + math.sin(ang) * 6 + 4),
                      fill=(255, 255, 250, 255), outline=INK + (255,), width=1)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=MUSTARD + (255,))
    return lay


GROUND = [_cached("_ground", make_ground, v) for v in range(3)]


def world(t, ground=True, sun=True, sun_xy=(965, 285)):
    im = PAPER[boil(t)].copy()
    if sun:
        put(im, "sun", sun_xy[0], sun_xy[1], 150, t, rot=t * 6 % 360, anchor="center")
    if ground:
        im.alpha_composite(GROUND[boil(t)])
    return im


# ------------------------------------------------------------------ drawing helpers
def wobble_line(d, pts, fill, width, t, seed=0, amp=1.2):
    r = rnd(seed * 31 + boil(t))
    q = [(x + r.normal(0, amp), y + r.normal(0, amp)) for x, y in pts]
    d.line(q, fill=fill, width=width, joint="curve")


def marker_ellipse(im, cx, cy, rx, ry, p, t, col=RED, width=6, seed=1):
    """Hand-drawn marker loop drawn on with progress p, overshooting its start like a real pen stroke."""
    if p <= 0:
        return
    d = ImageDraw.Draw(im)
    n = 70
    total = 1.12 * eout(p)
    pts = []
    r = rnd(seed)
    ph = r.uniform(0, 6)
    for i in range(int(n * total) + 1):
        u = i / n
        ang = 2.5 + u * 2 * math.pi
        k = 1 + 0.06 * math.sin(u * 7 + ph) + 0.05 * u
        pts.append((cx + rx * k * math.cos(ang), cy + ry * k * math.sin(ang) + 4 * u))
    if len(pts) > 1:
        wobble_line(d, pts, col + (255,), width, t, seed, amp=0.6)


def marker_under(im, x0, x1, y, p, t, col=RED, width=7, seed=2):
    if p <= 0:
        return
    d = ImageDraw.Draw(im)
    xe = x0 + (x1 - x0) * eout(p)
    pts = [(x, y + 3 * math.sin((x - x0) / 40 + seed)) for x in np.linspace(x0, xe, 24)]
    wobble_line(d, pts, col + (255,), width, t, seed, amp=0.5)


def dashed(im, p0, p1, p, col=LAV, width=4, dash=14, gap=10, phase=0.0):
    if p <= 0:
        return
    d = ImageDraw.Draw(im)
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0) * cl(p)
    ux, uy = (x1 - x0) / max(1e-6, math.hypot(x1 - x0, y1 - y0)), (y1 - y0) / max(1e-6, math.hypot(x1 - x0, y1 - y0))
    s = -phase % (dash + gap)
    while s < L:
        a, b = max(0, s), min(L, s + dash)
        if b > a:
            d.line((x0 + ux * a, y0 + uy * a, x0 + ux * b, y0 + uy * b), fill=col + (255,), width=width)
        s += dash + gap


def check(im, x, y, size, p):
    if p <= 0:
        return
    d = ImageDraw.Draw(im)
    pts = [(x - size * 0.45, y), (x - size * 0.1, y + size * 0.35), (x + size * 0.5, y - size * 0.4)]
    seg1 = cl(p / 0.4)
    seg2 = cl((p - 0.4) / 0.6)
    q = [pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * seg1, pts[0][1] + (pts[1][1] - pts[0][1]) * seg1)]
    if seg2 > 0:
        q.append((pts[1][0] + (pts[2][0] - pts[1][0]) * seg2, pts[1][1] + (pts[2][1] - pts[1][1]) * seg2))
    d.line(q, fill=INK + (255,), width=int(size * 0.28), joint="curve")
    d.line(q, fill=(116, 196, 98, 255), width=int(size * 0.15), joint="curve")


def text_rise(im, s, x, y, size, t0, t, col=INK, wght=850, anchor="center", stagger=0.07, under=None, out_at=None):
    """Words spring up into place one after another. under=(word_index, t_start) adds a red marker underline."""
    f = gfont(size, wght)
    words = s.split()
    size0 = size
    while True:
        sp = f.getlength(" ")
        ws = [f.getlength(w) for w in words]
        tot = sum(ws) + sp * (len(words) - 1)
        if tot <= S - 150 or size <= 20:
            break
        size -= 2
        f = gfont(size, wght)
    if size < 0.8 * size0:
        WARN.append(f"caption shrank to {size / size0:.0%}: {s!r}")
    x0 = x - tot / 2 if anchor == "center" else x
    fade = 1.0 if out_at is None else 1 - cl((t - out_at) / 0.25)
    if fade <= 0:
        return
    asc, desc = f.getmetrics()
    xx = x0
    spans = []
    for i, (w, wl) in enumerate(zip(words, ws)):
        tw = t0 + i * stagger
        p = spring(t - tw, 300, 16)
        if t >= tw:
            a = cl((t - tw) / 0.08) * fade
            lay = Image.new("RGBA", (int(wl) + 20, asc + desc + 20), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((10, 10), w, font=f, fill=col + (int(255 * a),))
            sc = 0.82 + 0.18 * p
            L = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))), Image.BILINEAR)
            L = L.rotate((1 - p) * 8 * (1 if i % 2 else -1), resample=Image.BILINEAR, expand=True)
            cx, cy = xx + wl / 2, y + (1 - p) * 30
            paste_clip(im, L, int(cx - L.width / 2), int(cy - L.height / 2))
        spans.append((xx, xx + wl))
        xx += wl + sp
    if under and t >= under[1]:
        i = under[0]
        marker_under(im, spans[i][0] - 4, spans[i][1] + 6, y + asc * 0.62, (t - under[1]) / 0.35, t)
    return spans


def caption(im, s, t0, t1, t, y=120, size=58):
    if t0 - 0.01 <= t <= t1 + 0.3:
        text_rise(im, s, S / 2, y, size, t0, t, out_at=t1)


def shake(t, hits, amp=16):
    dx = dy = 0.0
    for th, a in hits:
        if 0 <= t - th < 0.5:
            k = math.exp(-(t - th) * 9) * a / 16 * amp
            dx += math.sin((t - th) * 83) * k
            dy += math.cos((t - th) * 61) * k
    return dx, dy


def camera(im, z=1.0, cx=S / 2, cy=S / 2, dx=0.0, dy=0.0, rot=0.0):
    if abs(z - 1) < 1e-3 and abs(dx) < 0.3 and abs(dy) < 0.3 and abs(rot) < 0.01:
        return im
    z = max(z, 1 + 2.2 * (abs(dx) + abs(dy)) / S)
    w = S / z
    cx = min(max(cx - dx, w / 2), S - w / 2)
    cy = min(max(cy - dy, w / 2), S - w / 2)
    out = im.transform((S, S), Image.EXTENT, (cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2), Image.BILINEAR)
    if abs(rot) > 0.01:
        out = out.rotate(rot, resample=Image.BILINEAR, fillcolor=CREAM)
    return out


# ------------------------------------------------------------------ S1 terminal
MENU = [tuple(m) for m in C["terminal"]["menu"]]
PICK = MENU[C["terminal"].get("pick", 0)][0]


def typed(s, t, t0, t1):
    if t < t0:
        return ""
    return s[:int(len(s) * cl((t - t0) / max(0.01, t1 - t0)))]


def wrap(s, f, maxw):
    lines, cur = [], ""
    for w in s.split():
        c = (cur + " " + w).strip()
        if not cur or f.getlength(c) <= maxw:
            cur = c
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(s, maxw, size, wght=850, mono_=False, minsize=12):
    mk = (lambda z: mono(z)) if mono_ else (lambda z: gfont(z, wght))
    f = mk(size)
    size0 = size
    while f.getlength(s) > maxw and size > minsize:
        size -= 1
        f = mk(size)
    if size < 0.8 * size0:
        WARN.append(f"text shrank to {size / size0:.0%}: {s!r}")
    return f


def s_terminal(t):
    im = Image.new("RGBA", (S, S), DARK + (255,))
    d = ImageDraw.Draw(im)
    f = mono(42)
    fb = mono(42, True)
    X = 90
    TX = X + 50
    R_ = S - 90                                   # right margin every line must stay inside
    caret = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 38)
    d.text((X, 70), C["terminal"]["header"], font=fit(C["terminal"]["header"], R_ - X, 26, mono_=True), fill=(98, 112, 132), features=NOLIG)
    d.line((0, 125, S, 125), fill=(52, 66, 84), width=2)
    y = 175
    d.text((X, y), "❯", font=caret, fill=(126, 220, 140))
    lines = wrap(C["terminal"]["prompt"], f, R_ - TX)[:2]
    shown = len(typed(C["terminal"]["prompt"], t, 0.25, 1.45))
    for i, ln in enumerate(lines):
        d.text((TX, y + i * 56), ln[:max(0, shown)], font=f, fill=(236, 238, 244), features=NOLIG)
        shown -= len(ln) + 1
    yr = y + len(lines) * 56 + 26
    if t >= 1.65:
        a = int(255 * cl((t - 1.65) / 0.2))
        d.text((TX, yr), C["terminal"]["reply"], font=fit(C["terminal"]["reply"], R_ - TX, 42, mono_=True), fill=(140, 150, 170, a), features=NOLIG)
        hit = C["terminal"]["reply_hit"]
        d.text((TX, yr + 60), hit, font=fb, fill=(255, 214, 102, a), features=NOLIG)
        ew = fb.getlength(hit)
        marker_ellipse(im, TX + ew / 2, yr + 86, ew / 2 + 26, 32, (t - 2.05) / 0.4, t, col=(255, 100, 92), width=6, seed=4)
    d.line((0, 520, S, 520), fill=(52, 66, 84), width=2)
    y2 = 560
    if t >= 2.55:
        d.text((X, y2), "❯", font=caret, fill=(126, 220, 140))
        cmd = typed("/wiki", t, 2.6, 2.85)
        if t >= 3.55:
            cmd = PICK + typed(C["terminal"].get("arg", ""), t, 3.65, 3.95)
        d.text((TX, y2), cmd, font=f, fill=(206, 196, 255), features=NOLIG)
        cw = f.getlength(cmd)
        if int(t * 2.5) % 2 == 0 and t < 4.0:
            d.rectangle((TX + 6 + cw, y2 + 4, TX + 26 + cw, y2 + 46), fill=(232, 72, 128))
    if 2.9 <= t < 3.55:
        pk = C["terminal"].get("pick", 0)
        sel = min(pk, 0 if t < 3.12 else (1 if t < 3.3 else 2))
        fc = mono(30)
        dx_ = TX + max(fc.getlength(c) for c, _ in MENU) + 34
        for i, (c, desc) in enumerate(MENU):
            yy = y2 + 82 + i * 64
            a = int(255 * cl((t - 2.9 - i * 0.04) / 0.12))
            if i == sel:
                d.rectangle((TX - 14, yy - 10, R_ + 14, yy + 44), fill=(40, 56, 78, a))
            d.text((TX, yy), c, font=mono(30, i == sel), fill=((206, 196, 255) if i == sel else (150, 160, 180)) + (a,), features=NOLIG)
            fd = fit(desc, R_ - dx_, 24, mono_=True)
            d.text((dx_, yy + 5), desc, font=fd, fill=(110, 122, 142, a), features=NOLIG)
        if sel == pk and t >= 3.3:
            marker_under(im, TX - 2, TX + mono(30, True).getlength(PICK), y2 + 82 + pk * 64 + 44, (t - 3.32) / 0.2, t,
                         col=(255, 100, 92), width=6)
    if t >= 3.95:
        a = int(255 * cl((t - 3.95) / 0.1))
        d.text((TX, y2 + 82), C["terminal"]["status"], font=fit(C["terminal"]["status"], R_ - TX, 32, mono_=True), fill=(126, 220, 140, a), features=NOLIG)
    # gentle push-in; margins are wider than the crop, so nothing is ever cut off
    z = 1.0 + 0.05 * ease(t / 4.2)
    return camera(im, z, S / 2, S / 2 + 20 * ease((t - 2.3) / 1.4))


# ------------------------------------------------------------------ burst transition
def burst_over(im, t, t0, dur=0.55, flip_bg_at=0.45, bg_after=None):
    p = (t - t0) / dur
    if p < 0:
        return im
    if bg_after is not None and p >= flip_bg_at:
        im = bg_after.copy()
    sc = 0.15 + 3.6 * eout(p)
    put(im, "burst", S / 2, S / 2, S * sc, t, rot=p * 40, anchor="center", a=1 - cl((p - 0.8) / 0.2))
    return im


# ------------------------------------------------------------------ S2 title (notebook slam)
def notebook_label(text, sub=None, w=520):
    nb = sprite("notebook", 900)[0]
    return nb


def draw_notebook(im, cx, bottom, h, t, label, sub=None, rot=0.0, sx=1.0, sy=1.0, sub_k=0.042):
    base = sprite("notebook", 900)[boil(t)].copy()
    d = ImageDraw.Draw(base)
    # label rectangle sits at ~ (0.21..0.79, 0.31..0.53) of the cover
    W_, H_ = base.size
    lx0, lx1, ly0, ly1 = 0.17 * W_, 0.79 * W_, 0.29 * H_, 0.55 * H_
    f = gfont(int(H_ * 0.075), 900)
    while f.getlength(label) > (lx1 - lx0) * 0.9:
        f = gfont(f.size - 2, 900)
    d.text(((lx0 + lx1) / 2, (ly0 + ly1) / 2 - (H_ * 0.03 if sub else 0)), label, font=f, fill=(92, 72, 196), anchor="mm")
    if sub:
        f2 = fit(sub, (lx1 - lx0) * 0.88, int(H_ * sub_k), 700)
        d.text(((lx0 + lx1) / 2, (ly0 + ly1) / 2 + H_ * 0.06), sub, font=f2, fill=INK, anchor="mm")
    put(im, None, cx, bottom, h, t, rot=rot, sx=sx, sy=sy, src=base)


def dust(im, x, y, t, t0, n=7, spread=1, seed=3):
    p = (t - t0) / 0.6
    if p < 0 or p > 1:
        return
    d = ImageDraw.Draw(im)
    r = rnd(seed)
    for k in range(n):
        ang = math.pi + r.uniform(-0.5, 0.5) if k % 2 == 0 else r.uniform(-0.5, 0.5)
        dist = (60 + r.uniform(0, 120)) * eout(p) * spread
        rad = (16 + r.uniform(0, 18)) * (1 - p) + 2
        px, py = x + math.cos(ang) * dist * (1 if k % 2 else 1), y - abs(math.sin(ang)) * dist * 0.3 - 10 * p
        px = x + (dist if k % 2 else -dist) * (0.6 + 0.4 * r.random())
        d.ellipse((px - rad, py - rad, px + rad, py + rad), fill=(250, 248, 240, int(255 * (1 - p))), outline=INK + (int(255 * (1 - p)),), width=3)


def s_title(t):
    im = world(t)
    t_hit = 5.2
    # Mo peeks up from behind, then waves
    if t >= 5.45:
        rise = spring(t - 5.45, 200, 13)
        dy, sx, sy = hop(t, 6.0, 0.4, 30)
        put(im, "mo_wave", 760, GY - 210 + (1 - rise) * 260 + dy, 300, t, sx=sx, sy=sy)
    # notebook falls and slams
    if t < t_hit:
        p = ein((t - 4.7) / 0.5)
        y = -700 + (GY + 20 + 700) * p
        draw_notebook(im, S / 2 - 60, y, 640, t, C["title"], C["title_sub"], sy=1.08, sx=0.95)
    else:
        sx, sy = squash(t, t_hit, 0.18)
        lift = ein((t - 6.45) / 0.3)
        draw_notebook(im, S / 2 - 60, GY + 20 - lift * 1500, 640, t, C["title"], C["title_sub"], sx=sx, sy=sy,
                      rot=lift * 12)
        dust(im, S / 2 - 60, GY + 10, t, t_hit, n=10, spread=2.2)
    dx, dy = shake(t, [(t_hit, 22)])
    return camera(im, 1.0, dx=dx, dy=dy)


# ------------------------------------------------------------------ S3 forget -> ingest
STUFF = ["paper", "chat", "shot", "paper", "chat", "shot", "paper", "chat", "shot", "paper"]


def stuff_pos(i, t):
    r = rnd(40 + i)
    ang0 = r.uniform(0, 2 * math.pi)
    rad = r.uniform(260, 420)
    cx, cy = 470, 480
    ang = ang0 + t * (0.35 + 0.1 * (i % 3))
    return cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.55 - 40, r.uniform(-25, 25) + math.sin(t * 2 + i) * 10


def s_ingest(t):
    im = world(t)
    t_gulp = B(9)          # 8.7
    eat_every = 0.22
    mo_x, mo_bottom = 470, GY + 18
    grow = 0.0
    eaten = [t_gulp + 0.25 + i * eat_every for i in range(len(STUFF))]
    for te in eaten:
        if t >= te:
            grow += 1
    # Mo size: small and sad, then grows with every bite, pops at the end
    pop = spring(t - B(15), 240, 9) if t >= B(15) else 0
    h = 250 + 14 * grow + 70 * pop
    # stuff floating / getting sucked in
    for i, (nm, te) in enumerate(zip(STUFF, eaten)):
        x, y, rot = stuff_pos(i, t)
        if t > te - 0.45:
            q = ein((t - (te - 0.45)) / 0.45)
            mx, my = mo_x + 10, mo_bottom - h * 0.48
            x, y = x + (mx - x) * q, y + (my - y) * q
            sc = 1 - q
            rot += q * 360
        else:
            sc = 1.0
        if t < te:
            appear = spring(t - (6.75 + i * 0.09), 260, 14)
            put(im, nm, x, y, 120 * sc * appear, t, rot=rot, anchor="center")
    # Mo
    if t < t_gulp:
        nm = "mo_sad"
        sx, sy = 1, 1
        breathe = 1 + 0.02 * math.sin(t * 5)
        put(im, nm, mo_x, mo_bottom, h * breathe, t)
    elif t < B(14):
        nm = "mo_gulp"
        k = sum(1 for te in eaten if te <= t)
        last = max([te for te in eaten if te <= t], default=t_gulp)
        sx, sy = squash(t, last, 0.12, 500, 12)
        ant = 1 - 0.1 * math.exp(-max(0, t - t_gulp) * 12) if t < t_gulp + 0.25 else 1
        put(im, nm, mo_x, mo_bottom, h * sy * ant, t, sx=sx)
    elif t < B(15):
        sx, sy = squash(t, B(14), 0.2, 300, 8)
        put(im, "mo_chomp", mo_x, mo_bottom, h, t, sx=sx * (1 + 0.05 * math.sin((t - B(14)) * 30)), sy=sy)
    else:
        dy, sx, sy = hop(t, B(15) + 0.05, 0.45, 70)
        put(im, "mo", mo_x, mo_bottom + dy, h, t, sx=sx, sy=sy)
        sparkle(im, mo_x, mo_bottom - h * 0.6, h * 0.8, t, B(15))
    caption(im, C["cap_forget"], 6.95, B(8) + 0.3, t)
    caption(im, C["cap_ingest"], B(9) + 0.1, B(15) + 0.3, t)
    dx, dy = shake(t, [(B(14), 10), (B(15), 8)])
    z = 1.0 + 0.04 * ease((t - 6.7) / 5)
    return camera(im, z, 480, 520, dx, dy)


def sparkle(im, x, y, r, t, t0, n=8, col=LAV):
    p = (t - t0) / 0.6
    if p < 0 or p > 1:
        return
    d = ImageDraw.Draw(im)
    for k in range(n):
        ang = k * 2 * math.pi / n + 0.3
        dd = r * (0.55 + 0.6 * eout(p))
        cx, cy = x + math.cos(ang) * dd, y + math.sin(ang) * dd
        s = 18 * (1 - p) + 2
        d.polygon([(cx, cy - s), (cx + s * 0.3, cy - s * 0.3), (cx + s, cy), (cx + s * 0.3, cy + s * 0.3), (cx, cy + s),
                   (cx - s * 0.3, cy + s * 0.3), (cx - s, cy), (cx - s * 0.3, cy - s * 0.3)], fill=col + (255,), outline=INK + (255,))


# ------------------------------------------------------------------ S4 the graph
NOTES = (C["notes"] + ["notes"] * 6)[:6]
LINKS = [(0, 1), (1, 4), (2, 3), (3, 0), (4, 5), (5, 2), (0, 2)]


def note_pos(i, t):
    ang = -math.pi / 2 + i * 2 * math.pi / 6 + 0.25
    cx, cy = S / 2, 470
    return cx + math.cos(ang) * 360, cy + math.sin(ang) * 250 + 6 * math.sin(t * 2 + i)


def card_img(title, t, w=230):
    base = sprite("card", 400)[boil(t)].copy()
    d = ImageDraw.Draw(base)
    f = gfont(int(base.height * 0.17), 800)
    txt = f"[[{title}]]"
    while f.getlength(txt) > base.width * 0.86:
        f = gfont(f.size - 1, 800)
    d.text((base.width / 2, base.height * 0.55), txt, font=f, fill=(92, 72, 196), anchor="mm")
    return base


def s_graph(t):
    im = world(t)
    t0 = B(16)
    # dashed orbit
    if t >= t0:
        d = ImageDraw.Draw(im)
        p = eout((t - t0) / 0.8)
        pts = [(S / 2 + math.cos(a) * 375, 470 + math.sin(a) * 255) for a in np.linspace(-math.pi / 2, -math.pi / 2 + 2 * math.pi * p, 90)]
        for k in range(0, len(pts) - 1, 2):
            d.line((pts[k], pts[k + 1]), fill=(170, 160, 210, 255), width=3)
    hub = (S / 2, GY - 150)
    # links go down first so Mo and the cards always sit on top of them
    for i in range(6):
        tl = B(19) + i * 0.12
        if t >= tl:
            dashed(im, hub, note_pos(i, t), (t - tl) / 0.35, phase=t * 40)
    for k, (a, b) in enumerate(LINKS):
        tl = B(21) + k * 0.12
        if t >= tl:
            dashed(im, note_pos(a, t), note_pos(b, t), (t - tl) / 0.35, col=CORAL, phase=-t * 40)
    put(im, "mo_read", S / 2, GY + 10, 300 + 6 * math.sin(t * 4), t)
    for i, nm in enumerate(NOTES):
        tp = B(16.5) + i * 0.25
        if t >= tp:
            s = spring(t - tp, 300, 12)
            x, y = note_pos(i, t)
            put(im, None, x, y, 165 * s, t, rot=(1 - s) * 30 + (i % 2 * 2 - 1) * 3, anchor="center", src=card_img(nm, t))
    caption(im, C["cap_graph"], B(16.2), B(23.3), t, y=96, size=54)
    # whip into the next scene
    z = 1.0 + 1.6 * ein((t - (B(24) - 0.3)) / 0.3)
    return camera(im, z, S / 2, GY - 160)


# ------------------------------------------------------------------ S5 agents grid
AGENTS = [tuple(a) for a in C["agents"][:8]]
TINTS = [(250, 228, 214), (226, 236, 250), (236, 230, 252), (246, 246, 226), (226, 244, 232), (252, 232, 238), (236, 238, 244), (248, 236, 222)]


def panel_rects():
    m, g = 40, 22
    cw = (S - 2 * m - 2 * g) / 3
    top = 150
    chh = (S - top - m - 2 * g) / 3
    return [(m + c * (cw + g), top + r * (chh + g), cw, chh) for r in range(3) for c in range(3)]


def panel_content(k, w, h, t):
    """One mini scene for a panel: grass, an agent's monitor, or Mo in the centre."""
    p = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    gy = h * 0.8
    tint = TINTS[k % len(TINTS)] if k != 4 else CREAM
    d.rectangle((0, 0, w, gy), fill=tint + (255,))
    d.rectangle((0, gy, w, h), fill=GREEN + (255,))
    d.line((0, gy, w, gy), fill=INK + (255,), width=3)
    if k == 4:
        dy, sx, sy = hop(t, B(26), 0.4, 18)
        if t > B(29):
            dy, sx, sy = hop(t, B(30), 0.4, 26)
        put(p, "mo_point", w / 2, gy + 6 + dy, h * 0.78, t, sx=sx, sy=sy)
    else:
        j = k if k < 4 else k - 1
        slug, name = AGENTS[j]
        mh = h * 0.6
        put(p, "monitor", w / 2, gy + 4, mh, t)
        ic = icon(slug, int(mh * 0.34))
        p.alpha_composite(ic, (int(w / 2 - ic.width / 2), int(gy - mh * 0.63 - ic.height / 2)))
        f = fit(name, w - 16, 22, 800)
        d.text((w / 2, gy + (h - gy) / 2), name, font=f, fill=INK, anchor="mm")
    return p


def s_grid(t):
    im = PAPER[boil(t)].copy()
    rects = panel_rects()
    t0 = B(24)
    out_t = B(31.5)
    centre = rects[4]
    ccx, ccy = centre[0] + centre[2] / 2, centre[1] + centre[3] / 2
    order = [4, 0, 1, 2, 5, 8, 7, 6, 3]
    for n, k in enumerate(order):
        x, y, w, h = rects[k]
        tp = t0 + n * 0.05
        if t < tp:
            continue
        s = spring(t - tp, 320, 15)
        fly = ein((t - out_t - n * 0.02) / 0.3)
        vx, vy = (x + w / 2 - ccx), (y + h / 2 - ccy)
        if k == 4:
            vx, vy = 0, -1
        nn = max(1e-6, math.hypot(vx, vy))
        ox, oy = vx / nn * 1300 * fly, vy / nn * 1300 * fly
        pc = panel_content(k, w, h, t)
        frame_ = Image.new("RGBA", pc.size, (0, 0, 0, 0))
        frame_.alpha_composite(pc)
        ImageDraw.Draw(frame_).rectangle((1, 1, pc.width - 2, pc.height - 2), outline=INK + (255,), width=5)
        put(im, None, x + w / 2 + ox, y + h / 2 + oy, h * s, t, anchor="center", src=frame_, rot=(1 - s) * (8 if n % 2 else -8))
    for n, k in enumerate([0, 1, 2, 5, 8, 7, 6, 3]):
        x, y, w, h = rects[k]
        tc = B(26.5) + n * 0.25
        if t >= tc and t < out_t + 0.05:
            check(im, x + w - 40, y + 40, 52, (t - tc) / 0.18)
    caption(im, C["cap_agents"], B(24) + 0.1, B(31.3), t, y=82, size=50)
    return im


# ------------------------------------------------------------------ S6 the answer + gauge
def s_answer(t):
    im = world(t)
    # gauge: answer time, 81 s (plain agent) -> 19 s (with obsidian-wiki)
    if t >= B(35):
        g = spring(t - B(35), 240, 14)
        gx, gb, gh = S / 2, GY + 30, 470 * g
        put(im, "gauge", gx, gb + (1 - g) * 300, 470, t)
        # needle angle: 0 = pointing left (fast), 180 = right (slow)
        sw = (t - B(36)) / 0.5
        a81, a19 = 160, 38
        if sw < 0:
            ang = a81 + 2 * math.sin(t * 40)            # rattling at the limit
        else:
            ang = a19 + (a81 - a19) * (1 - spring(t - B(36), 160, 7))
        cx, cy = gx, gb - 470 * 0.165 + (1 - g) * 300
        ln = 470 * 0.36
        ex, ey = cx - math.cos(math.radians(ang)) * ln, cy - math.sin(math.radians(ang)) * ln
        d = ImageDraw.Draw(im)
        d.line((cx, cy, ex, ey), fill=INK + (255,), width=16)
        d.line((cx, cy, ex, ey), fill=CORAL + (255,), width=8)
        d.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=INK + (255,))
        g0, g1 = C["gauge"]["before"], C["gauge"]["after"]
        secs = g0 + (g1 - g0) * cl(sw)
        f = gfont(64, 900)
        d.text((gx, gb - 470 - 40 + (1 - g) * 300), C["gauge"]["label"], font=fit(C["gauge"]["label"], 520, 46, 900), fill=INK, anchor="mm")
        d.text((gx, gb + 70), f"{secs:0.0f}s", font=f, fill=(INK if sw < 1 else (70, 150, 70)), anchor="mm")
        if sw >= 1:
            a = int(255 * cl((t - B(36) - 0.5) / 0.2))
            d.text((gx + 90, gb + 72), f"down from {g0}s", font=gfont(32, 700), fill=(120, 110, 120, a), anchor="lm")
    # 4.4x faster burst, top right, clear of the gauge title
    if t >= B(37):
        p = spring(t - B(37), 300, 10)
        put(im, "burst", 870, 185, 300 * p, t, rot=10, anchor="center")
        lay = Image.new("RGBA", (420, 200), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay)
        dd.text((210, 70), C["gauge"]["burst"], font=fit(C["gauge"]["burst"], 300, 86, 950), fill=INK, anchor="mm")
        dd.text((210, 140), C["gauge"]["burst_sub"], font=fit(C["gauge"]["burst_sub"], 300, 48, 900), fill=INK, anchor="mm")
        put(im, None, 870, 185, 150 * p, t, rot=-8, anchor="center", src=lay)
        f = gfont(30, 700)
        a = int(255 * cl((t - B(37.5)) / 0.3))
        ImageDraw.Draw(im).text((S / 2, 1000), C["gauge"]["footnote"], font=fit(C["gauge"]["footnote"], S - 120, 30, 700), fill=INK + (a,), anchor="mm")
    dx, dy = shake(t, [(B(36) + 0.2, 12), (B(37), 16)])
    return camera(im, 1.0, dx=dx, dy=dy)


# ------------------------------------------------------------------ explosion -> smoke
def smoke_over(im, t, t0):
    p = (t - t0)
    if p < 0:
        return im
    r = rnd(77)
    n = 9
    for k in range(n):
        tk = t0 + k * 0.03
        gr = eout((t - tk) / 0.35)
        shrink = ein((t - (t0 + 0.75 + k * 0.03)) / 0.3)
        x = S / 2 + r.uniform(-420, 420)
        y = S / 2 + r.uniform(-380, 380)
        sz = (700 + r.uniform(0, 300)) * gr * (1 - shrink)
        put(im, "smoke", x + (x - S / 2) * shrink * 0.8, y + (y - S / 2) * shrink * 0.8, sz, t, rot=k * 40, anchor="center")
    return im


# ------------------------------------------------------------------ S7 stars
CROWD = [("mo_cheer", 300, 0.0, False), ("mo_wave", 130, 0.13, True), ("mo_point", 900, 0.27, True), ("mo_cheer", 560, 0.4, True),
         ("mo", 760, 0.2, False), ("mo_chomp", 420, 0.33, False)]


def crowd(im, t, base_h=210, beat0=B(41), hopping=True, y=GY + 18, alpha=1.0):
    for k, (nm, x, off, fl) in enumerate(CROWD):
        h = base_h * (1.25 if k == 0 else 0.85 + 0.1 * (k % 3))
        dy, sx, sy = (0, 1, 1)
        if hopping:
            n = int((t - beat0 - off) / 0.5)
            if n >= 0:
                dy, sx, sy = hop(t, beat0 + off + n * 0.5, 0.42, 50 + 15 * (k % 2))
        put(im, nm, x, y + dy, h, t, sx=sx, sy=sy, flip=fl, a=alpha)


def star_rain(im, t, t0, n=40):
    r = rnd(9)
    for k in range(n):
        tk = t0 + r.uniform(0, 2.4)
        if t < tk:
            continue
        x = r.uniform(40, S - 40)
        fall = (t - tk) * (700 + r.uniform(0, 300))
        y = -60 + fall
        if y > GY + 10:
            y = GY + 10 - r.uniform(0, 12)
        put(im, "star", x, y, 46 + r.uniform(0, 30), t, rot=(t - tk) * r.uniform(-300, 300) if y < GY else r.uniform(-30, 30), anchor="center")


def s_stars(t):
    im = world(t)
    t0 = B(41)
    star_rain(im, t, t0)
    crowd(im, t)
    # counter
    p = eout((t - (t0 + 0.2)) / 2.0)
    n = int(round(C["stars"]["count"] * p))
    pop = spring(t - (t0 + 0.2), 260, 12)
    lay = Image.new("RGBA", (900, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.text((450, 100), f"{n:,}", font=gfont(170, 950), fill=INK, anchor="mm")
    put(im, None, S / 2 + 40, 330, 220 * pop, t, anchor="center", src=lay)
    put(im, "star", S / 2 - 300, 330, 150 * pop, t, rot=t * 40 % 360, anchor="center")
    if t >= t0 + 2.2:
        sx, sy = squash(t, t0 + 2.2, 0.25)
        put(im, "star", S / 2 - 300, 330, 150 * sx, t, rot=0, anchor="center")
    caption(im, C["stars"]["caption"], t0 + 0.5, B(48) + 1, t, y=480, size=56)
    dx, dy = shake(t, [(t0 + 2.2, 10)])
    return camera(im, 1.0, dx=dx, dy=dy)


# ------------------------------------------------------------------ S8 end card
def s_end(t):
    im = world(t, sun_xy=(940, 610))
    t0 = B(48)
    pull = ease((t - t0) / 0.7)
    crowd(im, t, base_h=210 - 50 * pull, beat0=B(41))
    t_hit = B(54)
    gone = t_hit - 0.4                            # copy clears before the notebook lands on it
    fo = 1 - cl((t - gone) / 0.2)
    E = C["end"]
    text_rise(im, E["line1"], S / 2, 200, 92, t0 + 0.2, t, out_at=gone)
    text_rise(im, E["line2"], S / 2, 310, 92, t0 + 0.7, t, under=(E.get("underline_word", 0), t0 + 1.3) if t < gone else None,
              out_at=gone)
    a = cl((t - (t0 + 1.4)) / 0.3) * fo
    if a > 0:
        d = ImageDraw.Draw(im)
        f = gfont(40, 800)
        s1 = C["title"]
        s2 = E["meta"]
        w1, w2 = gfont(40, 900).getlength(s1), f.getlength(s2)
        x0 = S / 2 - (w1 + w2) / 2
        y = 420 + (1 - eout(a)) * 12
        d.text((x0, y), s1, font=gfont(40, 900), fill=(92, 72, 196, int(255 * a)), anchor="lm")
        d.text((x0 + w1, y), s2, font=f, fill=INK + (int(255 * a),), anchor="lm")
    a2 = cl((t - (t0 + 1.9)) / 0.3) * fo
    if a2 > 0:
        ImageDraw.Draw(im).text((S / 2, 490), E["install"], font=fit(E["install"], S - 160, 34, mono_=True), fill=(90, 86, 100, int(255 * a2)), anchor="mm",
                                features=NOLIG)
    # final gag: the notebook slams back with the repo on it
    if t >= t_hit - 0.3:
        if t < t_hit:
            y = -100 + (S + 20 + 100) * ein((t - (t_hit - 0.3)) / 0.3)
            draw_notebook(im, S / 2, y, 940, t, C["title"], E["repo"], sy=1.08, sx=0.95, sub_k=0.028)
        else:
            sx, sy = squash(t, t_hit, 0.18)
            draw_notebook(im, S / 2, S + 20, 940, t, C["title"], E["repo"], sx=sx, sy=sy, sub_k=0.028)
            dust(im, S / 2, GY + 50, t, t_hit, n=12, spread=2.6)
    dx, dy = shake(t, [(t_hit, 24)])
    return camera(im, 1.0, dx=dx, dy=dy)


# ------------------------------------------------------------------ S5b the Brain extension in Chrome
D1, D2 = 11.0, 3.0                      # browser scene, answer card
TB = B(32)
TA = TB + D1
SH = D1 + D2 - 1.5                      # the old timeline from B(35) on plays this much later
LAVINK = (92, 72, 196)
OKG = (88, 168, 76)
GREY = (118, 110, 124)
WIN = (50, 150, 1030, 1020)
TAB_H, BAR_H = 54, 66
PAGE_Y = WIN[1] + TAB_H + BAR_H
PX0, PX1 = WIN[0] + 50, WIN[2] - 50
ICON_C = (WIN[2] - 50, WIN[1] + TAB_H + BAR_H // 2)
POP_W = 430
POP_X1 = WIN[2] - 22
POP_X0 = POP_X1 - POP_W
POP_Y0 = PAGE_Y + 8

BR = C["browser"]
ART = BR["article"]
ART_TITLE, ART_URL, ART_P, ART_CODE = ART["title"], ART["url"], ART["paragraphs"][:2], ART["code"][:3]
FORM = BR["form"]
FORM_TITLE, FORM_URL = FORM["title"], FORM["url"]
FIELDS = [tuple(f) for f in FORM["fields"][:4]]
FIELD_Y0, FIELD_STEP = PAGE_Y + 156, 132
SUBMIT = (PX0, FIELD_Y0 + 4 * FIELD_STEP - 6, PX0 + 170, FIELD_Y0 + 4 * FIELD_STEP + 40)


COLW = 440                               # article column; the popup only ever covers the sidebar to its right
SIDE_X0 = POP_X0 + 16
ART_F = 26
ART_LH = 38
ART_TITLE_LINES = wrap(ART_TITLE, gfont(44, 900), COLW)
TOC = ART["toc"][:5]


def _article_layout():
    f = gfont(ART_F, 600)
    out, y = [], PAGE_Y + 40 + 54 * len(ART_TITLE_LINES) + 52
    for pi, p in enumerate(ART_P):
        for ln in wrap(p, f, COLW):
            out.append((pi, ln, PX0, y))
            y += ART_LH
        y += 16
    return out, y


ART_LINES, ART_END = _article_layout()
SEL = [(ln, x, y) for pi, ln, x, y in ART_LINES if pi == ART.get("select", len(ART_P) - 1)]
SEL_START = (SEL[0][1] + 4, SEL[0][2] + 18)
SEL_END = (SEL[-1][1] + gfont(ART_F, 600).getlength(SEL[-1][0]), SEL[-1][2] + 18)


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def page_article(sel):
    L = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    for i, ln in enumerate(ART_TITLE_LINES):
        d.text((PX0, PAGE_Y + 34 + i * 54), ln, font=gfont(44, 900), fill=INK)
    d.text((PX0, PAGE_Y + 40 + 54 * len(ART_TITLE_LINES)), ART["meta"], font=fit(ART["meta"], COLW, 22, 700), fill=GREY)
    f = gfont(ART_F, 600)
    total = sum(len(s[0]) for s in SEL)
    left = int(total * cl(sel))
    for ln, x, y in SEL:                                  # highlight sits under the words
        k = min(len(ln), left)
        if k > 0:
            d.rectangle((x - 4, y - 3, x + f.getlength(ln[:k]) + 4, y + 34), fill=MUSTARD + (170,))
        left -= len(ln) + 1
    for pi, ln, x, y in ART_LINES:
        d.text((x, y), ln, font=f, fill=INK)
    # sidebar: contents (hidden under the popup when it opens) and the config snippet below it
    d.line((SIDE_X0 - 24, PAGE_Y + 36, SIDE_X0 - 24, WIN[3] - 40), fill=INK + (50,), width=2)
    d.text((SIDE_X0, PAGE_Y + 44), "ON THIS PAGE", font=gfont(17, 900), fill=LAVINK)
    for i, s in enumerate(TOC):
        d.text((SIDE_X0, PAGE_Y + 80 + i * 40), s, font=fit(s, PX1 - SIDE_X0, 23, 700 if i != 2 else 850), fill=INK if i == 2 else GREY)
    cy = PAGE_Y + 440
    rrect(d, (SIDE_X0, cy, PX1, cy + 36 * len(ART_CODE) + 70), 10, fill=(238, 234, 222, 255), outline=INK + (255,), width=3)
    d.text((SIDE_X0 + 20, cy + 16), ART["code_name"], font=fit(ART["code_name"], PX1 - SIDE_X0 - 40, 19, 900), fill=GREY)
    for i, c in enumerate(ART_CODE):
        d.text((SIDE_X0 + 20, cy + 52 + i * 36), c, font=fit(c, PX1 - SIDE_X0 - 40, 22, mono_=True), fill=INK if i else LAVINK,
               features=NOLIG)
    return L


def page_form(u):
    L = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    d.text((PX0, PAGE_Y + 34), FORM_TITLE, font=fit(FORM_TITLE, PX1 - PX0, 46, 900), fill=INK)
    d.text((PX0, PAGE_Y + 96), FORM["meta"], font=fit(FORM["meta"], PX1 - PX0, 22, 700), fill=GREY)
    fv = gfont(25, 700)
    for i, (q, ans, src) in enumerate(FIELDS):
        fy = FIELD_Y0 + i * FIELD_STEP
        d.text((PX0, fy), q, font=fit(q, PX1 - PX0, 24, 800), fill=INK)
        box = (PX0, fy + 36, PX1, fy + 92)
        tf = 7.35 + i * 0.5
        done = u >= tf + 0.35
        if ans is None and u >= tf:
            rrect(d, box, 8, fill=(255, 255, 255, 255))
            for (a, b) in [((box[0], box[1]), (box[2], box[1])), ((box[2], box[1]), (box[2], box[3])),
                           ((box[2], box[3]), (box[0], box[3])), ((box[0], box[3]), (box[0], box[1]))]:
                dashed(L, a, b, 1, col=RED, width=4, dash=12, gap=8)
            a_ = int(255 * cl((u - tf) / 0.25))
            d.text((PX1, fy + 100), FORM["blank"], font=fit(FORM["blank"], PX1 - PX0, 19, 800), fill=RED + (a_,), anchor="ra")
            continue
        rrect(d, box, 8, fill=(255, 255, 255, 255), outline=(OKG if done else INK) + (255,), width=5 if done else 3)
        if ans:
            s = typed(ans, u, tf, tf + 0.35)
            if s:
                d.text((PX0 + 18, fy + 64), s, font=fit(ans, PX1 - PX0 - 80, 25, 700), fill=INK, anchor="lm")
            if done:
                check(L, PX1 - 32, fy + 64, 30, (u - tf - 0.35) / 0.15)
                a_ = int(255 * cl((u - tf - 0.4) / 0.25))
                d.text((PX1, fy + 100), f"from [[{src}]]", font=fit(f"from [[{src}]]", PX1 - PX0, 19, 800), fill=LAVINK + (a_,), anchor="ra")
    rrect(d, SUBMIT, 10, fill=INK + (255,))
    d.text(((SUBMIT[0] + SUBMIT[2]) / 2, (SUBMIT[1] + SUBMIT[3]) / 2), FORM["submit"], font=fit(FORM["submit"], SUBMIT[2] - SUBMIT[0] - 24, 24, 850), fill=CREAM, anchor="mm")
    return L


def brain_icon(size):
    return icon(BR["icon"], size)


def chrome(L, title, url):
    d = ImageDraw.Draw(L)
    x0, y0, x1, y1 = WIN
    rrect(d, (x0 + 10, y0 + 12, x1 + 10, y1 + 12), 20, fill=INK + (70,))
    rrect(d, WIN, 20, fill=(252, 250, 244, 255), outline=INK + (255,), width=5)
    rrect(d, (x0 + 3, y0 + 3, x1 - 3, y0 + TAB_H + 10), 18, fill=(228, 222, 244, 255))
    d.rectangle((x0 + 3, y0 + TAB_H, x1 - 3, y0 + TAB_H + 10), fill=(252, 250, 244, 255))
    for i, c in enumerate([CORAL, MUSTARD, GREEN]):
        cx = x0 + 32 + i * 28
        d.ellipse((cx - 9, y0 + 18, cx + 9, y0 + 36), fill=c + (255,), outline=INK + (255,), width=2)
    tx0 = x0 + 130
    d.rounded_rectangle((tx0, y0 + 10, tx0 + 380, y0 + TAB_H + 4), radius=12, fill=(252, 250, 244, 255), outline=INK + (255,), width=3)
    d.rectangle((tx0 + 3, y0 + TAB_H - 2, tx0 + 377, y0 + TAB_H + 6), fill=(252, 250, 244, 255))
    d.text((tx0 + 22, y0 + 33), title, font=fit(title, 336, 20, 800), fill=INK, anchor="lm")
    d.line((x0 + 3, y0 + TAB_H, tx0, y0 + TAB_H), fill=INK + (255,), width=3)
    d.line((tx0 + 380, y0 + TAB_H, x1 - 3, y0 + TAB_H), fill=INK + (255,), width=3)
    by = y0 + TAB_H + BAR_H / 2
    for i, sgn in enumerate([-1, 1]):                         # back / forward chevrons
        cx = x0 + 40 + i * 40
        d.line((cx - 6 * sgn, by - 10, cx + 6 * sgn, by, cx - 6 * sgn, by + 10), fill=INK + (255,), width=4, joint="curve")
    ux0, ux1 = x0 + 120, ICON_C[0] - 40
    rrect(d, (ux0, by - 22, ux1, by + 22), 10, fill=(238, 234, 222, 255), outline=INK + (255,), width=3)
    d.text((ux0 + 18, by), url, font=fit(url, ux1 - ux0 - 36, 21, mono_=True), fill=INK, anchor="lm", features=NOLIG)
    d.line((x0 + 3, PAGE_Y, x1 - 3, PAGE_Y), fill=INK + (255,), width=3)


def popup(mode, u, opened, closed, press, tab_p=None, status=""):
    """The Brain popup, drawn in the film's line style with the extension's real labels and icon."""
    H = 340 if mode == "capture" else 400
    P = Image.new("RGBA", (POP_W + 14, H + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(P)
    rrect(d, (10, 10, POP_W + 10, H + 10), 16, fill=INK + (80,))
    rrect(d, (0, 0, POP_W, H), 16, fill=(252, 250, 244, 255), outline=INK + (255,), width=4)
    bi = brain_icon(60)
    P.alpha_composite(bi, (18, 18))
    d.text((92, 22), BR["product"], font=fit(BR["product"], POP_W - 110, 22, 900), fill=LAVINK)
    lede = BR["capture"]["lede"] if mode == "capture" else BR["fill"]["lede"]
    d.text((92, 54), lede, font=fit(lede, POP_W - 110, 19, 700), fill=GREY)
    ft = gfont(22, 850)
    w1 = ft.getlength(BR["tabs"][0])
    x2 = 18 + w1 + 30
    w2 = ft.getlength(BR["tabs"][1])
    tp = (0.0 if mode == "capture" else 1.0) if tab_p is None else tab_p
    d.text((18, 100), BR["tabs"][0], font=ft, fill=INK if tp < 0.5 else GREY)
    d.text((x2, 100), BR["tabs"][1], font=ft, fill=INK if tp >= 0.5 else GREY)
    ux = 18 + (x2 - 18) * ease(tp)
    uw = w1 + (w2 - w1) * ease(tp)
    d.line((ux, 134, ux + uw, 134), fill=CORAL + (255,), width=5)
    d.line((14, 140, POP_W - 14, 140), fill=(205, 200, 196, 255), width=2)
    fl = gfont(16, 900)
    if mode == "capture":
        rows = [(BR["capture"]["target_label"], BR["capture"]["target"])]
        btn, by = BR["capture"]["button"], 230
    else:
        rows = [tuple(r) for r in BR["fill"]["rows"][:2]]
        btn, by = BR["fill"]["button"], 290
    for i, (k, v) in enumerate(rows):
        d.text((18, 156 + i * 62), k, font=fl, fill=LAVINK)
        d.text((18, 178 + i * 62), v, font=fit(v, POP_W - 36, 23, 800), fill=INK)
    pr = 4 if press else 0
    rrect(d, (18 + pr, by + pr, POP_W - 18 + pr, by + 56 + pr), 10, fill=CORAL + (255,), outline=INK + (255,), width=3)
    d.text((POP_W / 2 + pr, by + 28 + pr), btn, font=fit(btn, POP_W - 70, 23, 900), fill=(255, 255, 255), anchor="mm")
    if status:
        d.text((18, by + 76), status, font=fit(status, POP_W - 36, 17, mono_=True), fill=OKG if mode == "capture" else GREY,
               features=NOLIG)
    s = spring(u - opened, 320, 34) if u < closed else 1 - ein((u - closed) / 0.18)
    if s <= 0.02:
        return None
    w, h = int(P.width * s), int(P.height * s)
    return P.resize((max(1, w), max(1, h)), Image.BILINEAR), (int(POP_X1 + 10 - w), POP_Y0)


CURSOR_KEYS = [(0.6, 1100, 1100), (1.25, *SEL_START), (1.95, *SEL_END), (2.35, *ICON_C), (2.95, POP_X0 + POP_W / 2, POP_Y0 + 258),
               (3.6, POP_X0 + POP_W / 2 + 20, POP_Y0 + 290), (4.4, 640, 760), (5.55, *ICON_C),
               (5.95, POP_X0 + 18 + gfont(22, 850).getlength(BR["tabs"][0]) + 30 + 50, POP_Y0 + 114),
               (6.4, POP_X0 + POP_W / 2, POP_Y0 + 318), (7.1, 860, 700), (9.4, 860, 700),
               (9.9, (SUBMIT[0] + SUBMIT[2]) / 2 + 40, SUBMIT[1] + 30)]
CLICKS = [2.4, 3.05, 5.6, 6.0, 6.5]


def cursor_xy(u):
    ks = CURSOR_KEYS
    if u <= ks[0][0]:
        return ks[0][1:]
    for (ta, xa, ya), (tb, xb, yb) in zip(ks, ks[1:]):
        if u <= tb:
            p = (u - ta) / (tb - ta)
            p = p if (ta, tb) == (1.25, 1.95) else ease(p)       # the drag runs at a steady hand speed
            return xa + (xb - xa) * p, ya + (yb - ya) * p
    return ks[-1][1:]


def draw_cursor(L, x, y, u):
    d = ImageDraw.Draw(L)
    for c in CLICKS:
        p = (u - c) / 0.3
        if 0 <= p <= 1:
            r = 10 + 30 * eout(p)
            d.ellipse((x - r, y - r, x + r, y + r), outline=CORAL + (int(255 * (1 - p)),), width=4)
    sc = 1.0 - 0.15 * max([math.exp(-(u - c) * 25) for c in CLICKS if u >= c] or [0])
    pts = [(0, 0), (0, 38), (10, 29), (17, 44), (24, 41), (17, 26), (30, 26)]
    q = [(x + px * sc * 1.15, y + py * sc * 1.15) for px, py in pts]
    d.polygon(q, fill=(255, 255, 255, 255), outline=INK + (255,), width=3)


_snap = {}


def capture_snapshot():
    if "a" not in _snap:
        L = page_article(1.0).crop((WIN[0] + 4, PAGE_Y, WIN[2] - 4, WIN[3] - 4))
        W_ = Image.new("RGBA", L.size, (252, 250, 244, 255))
        W_.alpha_composite(L)
        ImageDraw.Draw(W_).rectangle((0, 0, W_.width - 1, W_.height - 1), outline=INK + (255,), width=10)
        _snap["a"] = W_.resize((W_.width // 2, W_.height // 2), Image.LANCZOS)
    return _snap["a"]


def s_browser(t):
    u = t - TB
    im = world(t, ground=False, sun=False)
    L = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    form = u >= 4.85
    title = FORM_TITLE if form else ART_TITLE
    url = (FORM_URL[:max(1, len(typed(FORM_URL, u, 4.85, 5.15)))] if form else ART_URL)
    chrome(L, title, url)
    # page body, clipped to the viewport; the article slides up and out as the form slides in
    sw = ease((u - 4.85) / 0.5)
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    if sw < 1:
        paste_clip(body, page_article((u - 1.25) / 0.7), 0, int(-760 * sw))
    if sw > 0:
        paste_clip(body, page_form(u), 0, int(760 * (1 - sw)))
    vp = (WIN[0] + 5, PAGE_Y + 2, WIN[2] - 5, WIN[3] - 5)
    L.alpha_composite(body.crop(vp), (vp[0], vp[1]))
    # the extension's real icon in the toolbar, with a pop when clicked
    k = max([math.exp(-(u - c) * 12) for c in (2.4, 5.6) if u >= c] or [0])
    ic = brain_icon(int(46 * (1 + 0.25 * k)))
    L.alpha_composite(ic, (int(ICON_C[0] - ic.width / 2), int(ICON_C[1] - ic.height / 2)))
    # popups
    if 2.4 <= u < 4.7:
        st = typed(BR["capture"]["saved"], u, 3.75, 4.05)
        pp = popup("capture", u, 2.4, 4.45, 3.05 <= u < 3.2, status=st)
        if pp:
            paste_clip(L, pp[0], *pp[1])
            if u >= 3.7 and pp[0].width > POP_W * 0.9:
                sparkle(L, POP_X0 + 48, POP_Y0 + 48, 70, u, 3.7, n=7)
    if 5.6 <= u < 7.3:
        tab_p = cl((u - 6.0) / 0.15)
        st = typed(BR["fill"]["reading"], u, 6.55, 6.85)
        pp = popup("fill" if tab_p >= 0.5 else "capture", u, 5.6, 7.0, 6.5 <= u < 6.65, tab_p=tab_p, status=st)
        if pp:
            paste_clip(L, pp[0], *pp[1])
    # the captured page shrinks into the brain icon in the popup
    if 3.1 <= u < 3.72:
        p = ein((u - 3.1) / 0.6)
        snp = capture_snapshot()
        sx0, sy0 = (WIN[0] + WIN[2]) / 2, (PAGE_Y + WIN[3]) / 2
        tx, ty = POP_X0 + 48, POP_Y0 + 48
        x, y = sx0 + (tx - sx0) * p, sy0 + (ty - sy0) * p - 160 * math.sin(p * math.pi)
        put(L, None, x, y, snp.height * (1 - 0.94 * p) * 0.9, u, rot=p * 25, anchor="center", src=snp)
    draw_cursor(L, *cursor_xy(u), u)
    oy = -(1 - spring(u, 200, 15)) * 1100 - 1300 * ein((u - 10.7) / 0.3)
    paste_clip(im, L, 0, int(oy))
    caption(im, BR["cap_capture"], TB + 0.25, TB + 4.6, t, y=82, size=50)
    caption(im, BR["cap_fill"], TB + 4.9, TB + 8.7, t, y=82, size=50)
    caption(im, BR["cap_blank"], TB + 8.9, TB + 10.6, t, y=82, size=50)
    dx, dy = shake(t, [(TB + 0.35, 8)])
    return camera(im, 1.0, dx=dx, dy=dy)


# ------------------------------------------------------------------ S6a the answer, with its source note
AN = C["answer"]
ANS_BODY = AN["body"]


def mixc(c, a, bg=(252, 250, 244)):
    k = a / 255
    return tuple(int(bg[i] + (c[i] - bg[i]) * k) for i in range(3))


def answer_card(v):
    W_, H_ = 560, 600
    Cd = Image.new("RGBA", (W_ + 14, H_ + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(Cd)
    rrect(d, (12, 12, W_ + 12, H_ + 12), 18, fill=INK + (80,))
    rrect(d, (0, 0, W_, H_), 18, fill=(252, 250, 244, 255), outline=INK + (255,), width=5)
    head = f"[[{AN['note']}]]"
    fh = fit(head, W_ - 68, 42, 900)
    d.text((34, 30), head, font=fh, fill=LAVINK)
    d.text((34, 90), AN["meta"], font=fit(AN["meta"], W_ - 68, 20, 700), fill=GREY)
    d.line((30, 130, W_ - 30, 130), fill=(196, 192, 190, 255), width=2)
    f = gfont(27, 700)
    lines = wrap(ANS_BODY, f, W_ - 68)[:8]
    for i, ln in enumerate(lines):
        a = int(255 * cl((v - 0.8 - i * 0.12) / 0.15))
        dy = 10 * (1 - eout((v - 0.8 - i * 0.12) / 0.25))
        d.text((34, 154 + i * 42 + dy), ln, font=f, fill=mixc(INK, a))
    yr = 154 + len(lines) * 42 + 26
    a = int(255 * cl((v - 1.5) / 0.2))
    d.text((34, yr), "SOURCES", font=gfont(17, 900), fill=mixc(LAVINK, a))
    srcs = "   ".join(f"[[{x}]]" for x in AN["sources"])
    d.text((34, yr + 26), srcs, font=fit(srcs, W_ - 68, 25, 850),
           fill=mixc(LAVINK, a))
    if v >= 1.4:
        marker_under(Cd, 30, 34 + fh.getlength(head) + 4, 84, (v - 1.4) / 0.3, v)
    return Cd


def s_answer_intro(t):
    v = t - TA
    im = world(t, sun=False)
    out = ein((v - 2.7) / 0.3)
    q = spring(v, 220, 14)
    bub = sprite("chat", 700)[boil(t)].copy()
    W_, H_ = bub.size
    a = np.asarray(bub).copy()                    # paint out the dots in the bubble's own fill colour, no patch
    y0, y1, x0, x1 = int(H_ * 0.3), int(H_ * 0.62), int(W_ * 0.18), int(W_ * 0.86)
    reg = a[y0:y1, x0:x1]
    reg[reg[..., :3].mean(-1) < 225] = (246, 239, 222, 255)
    bub = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(bub)
    q1, q2 = (AN["question"] + [""])[:2]
    f = fit(max(q1, q2, key=len), W_ * 0.62, int(H_ * 0.105), 850)
    d.text((W_ * 0.52, H_ * 0.38), q1, font=f, fill=INK, anchor="mm")
    d.text((W_ * 0.52, H_ * 0.53), q2, font=f, fill=INK, anchor="mm")
    put(im, None, -260 + 520 * q - out * 700, 300, 340, t, anchor="center", src=bub, rot=-4)
    if v >= 0.25:
        r = spring(v - 0.25, 240, 12)
        put(im, "mo_point", 220 - out * 700, GY + 18 + (1 - r) * 400, 300, t)
    if v >= 0.5:
        s = spring(v - 0.5, 260, 13)
        put(im, None, 760 + out * 800, 470, 600 * (0.3 + 0.7 * s), t, rot=(1 - s) * 8 + 1.5, anchor="center", src=answer_card(v))
    caption(im, AN["caption"], TA + 0.1, TA + 2.6, t, y=82, size=50)
    return im


# ------------------------------------------------------------------ timeline
T_END = 32.4 + SH


def frame(t):
    if t < TB:
        im = frame_old(t)
    elif t < TA:
        im = s_browser(t)
    elif t < TA + D2:
        im = s_answer_intro(t)
    else:
        im = frame_old(t - SH)
    a = np.asarray(im.convert("RGB"), np.float32)
    if t < 0.25:
        a *= t / 0.25
    if t >= T_END - 0.25:
        a *= 0.0
    return a.astype(np.uint8)


def frame_old(t):
    if t < B(0):
        im = s_terminal(t)
    elif t < 4.7:
        im = burst_over(s_terminal(min(t, 4.19)), t, B(0) - 0.05, dur=0.6, bg_after=world(t))
    elif t < 6.75:
        im = s_title(t)
    elif t < B(16):
        im = s_ingest(t)
        if t < 6.75 + 0.01:
            pass
    elif t < B(24):
        im = s_graph(t)
    elif t < B(32):
        im = s_grid(t)
        if t < B(24) + 0.25:                                   # land from the whip: zoomed, settling
            z = 1 + 0.6 * (1 - eout((t - B(24)) / 0.25))
            im = camera(im, z)
    elif t < B(39):
        im = s_answer(t)
        if t >= B(38.4):
            im = burst_over(im, t, B(38.4), dur=0.7)
    elif t < B(41):
        im = s_answer(B(39) - 0.01) if t < B(39) + 0.3 else s_stars(B(41))
        im = burst_over(im, t, B(38.4), dur=0.7) if t < B(39) + 0.3 else im
        im = smoke_over(im, t, B(38.9))
    elif t < B(48):
        im = s_stars(t)
        if t < B(41) + 0.35:
            im = smoke_over(im, t, B(38.9))
    else:
        im = s_end(t)
    return im


def _times():
    out, skip = [], False
    for a in sys.argv[2:]:
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = True
            continue
        try:
            out.append(float(a))
        except ValueError:
            pass
    return out


def _arg(k, d):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


def cmd_assets():
    from framesmith.media import generate_images
    spec = json.load(open(os.path.join(BASE, "assets.json")))
    style, mascot = spec["style"], spec["mascot"]
    base = spec["base"]["name"]
    specs = {base: {"prompt": style + mascot + spec["base"]["prompt"], "size": "1024x1024", "quality": "high",
                    "background": "transparent"}}
    for k, v in spec["poses"].items():
        specs[k] = {"prompt": style + v + " Keep the exact same character design, colours, proportions and line style as the reference.",
                    "ref": base, "size": "1024x1024", "quality": "medium", "background": "transparent"}
    for k, v in spec["props"].items():
        specs[k] = {"prompt": style + v, "size": "1024x1024", "quality": "medium", "background": "transparent"}
    names = [a for a in sys.argv[2:] if not a.startswith("--") and a != BRIEF_PATH] or None
    for r in generate_images(specs, ASSETS, names=names, workers=6):
        print(r, flush=True)
    shutil.rmtree(CACHE, ignore_errors=True)              # boil variants are rebuilt from the new drawings


def cmd_check():
    """Sample the cut; fail when any copy had to shrink below 80% of its designed size or an asset is missing."""
    need = ["mo", "mo_sad", "mo_gulp", "mo_chomp", "mo_read", "mo_point", "mo_cheer", "mo_wave", "paper", "chat", "shot",
            "card", "notebook", "sun", "burst", "smoke", "monitor", "gauge", "star"]
    missing = [n for n in need if not os.path.exists(os.path.join(ASSETS, n + ".png"))]
    missing += [f"icons/{s}" for s, _ in AGENTS if not os.path.exists(os.path.join(ASSETS, "icons", s + ".png"))]
    if not os.path.exists(os.path.join(ASSETS, "icons", BR["icon"] + ".png")):
        missing.append(f"icons/{BR['icon']}")
    for i in range(int(T_END * 2)):
        frame(i * 0.5 + 0.25)
    for m in missing:
        print("✗ missing asset", m)
    for w in sorted(set(WARN)):
        print("✗", w, "(shorten the copy)")
    print("ok" if not (missing or WARN) else "problems found")
    sys.exit(1 if (missing or WARN) else 0)


def render(dst, f0, f1):
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{S}x{S}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", os.environ.get("FRAMESMITH_PRESET", "medium"), "-crf", "18",
                           "-pix_fmt", "yuv420p", dst], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        ff.stdin.write(frame(fi / FPS).tobytes())
        if fi % 90 == 0:
            print(f"frame {fi}/{f1}", flush=True)
    ff.stdin.close()
    ff.wait()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "still"
    os.makedirs(OUT, exist_ok=True)
    if cmd == "init":
        dst = os.path.abspath(sys.argv[2])
        shutil.copytree(os.path.join(HERE, "..", "examples", "obsidian-wiki"), dst, ignore=shutil.ignore_patterns("out", "*.mp4"))
        print(f"{dst}: edit brief.json (copy) and assets.json (cast prompts), swap icons/, then: check, assets, sheet, render")
    elif cmd == "check":
        cmd_check()
    elif cmd == "assets":
        cmd_assets()
    elif cmd == "still":
        for a in _times():
            p = os.path.join(OUT, f"still_{a:05.2f}.png")
            Image.fromarray(frame(a)).save(p)
            print(p)
    elif cmd == "sheet":
        ts = _times() or [i * 1.5 + 0.5 for i in range(int(T_END / 1.5))]
        cols = 6
        rows = (len(ts) + cols - 1) // cols
        sh = Image.new("RGB", (cols * 360, rows * 360), "white")
        for i, tt in enumerate(ts):
            fr = Image.fromarray(frame(tt)).resize((360, 360))
            ImageDraw.Draw(fr).text((6, 6), f"{tt:.2f}", fill=(255, 0, 0))
            sh.paste(fr, ((i % cols) * 360, (i // cols) * 360))
        sh.save(os.path.join(OUT, "sheet.jpg"), quality=85)
        print(os.path.join(OUT, "sheet.jpg"))
    elif cmd == "render":
        f0, f1 = int(_arg("--from", 0)), int(_arg("--to", int(T_END * FPS)))
        if "--from" in sys.argv or "--to" in sys.argv:            # a part, for rendering halves in parallel
            dst = _arg("--out", os.path.join(OUT, f"part_{f0}.mp4"))
            render(dst, f0, f1)
            print(dst)
            return
        silent = os.path.join(OUT, "video_silent.mp4")
        render(silent, f0, f1)
        subprocess.run([sys.executable, os.path.join(HERE, "audio.py"), "score", OUT], check=True)
        dst = _arg("--out", os.path.join(OUT, f"{BRIEF.get('name', 'film')}.mp4"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", os.path.join(OUT, "mix.m4a"), "-c:v", "copy", "-c:a", "copy",
                        "-shortest", dst], check=True)
        print(dst)


if __name__ == "__main__":
    main()
