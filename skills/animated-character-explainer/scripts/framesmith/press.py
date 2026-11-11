"""Print finishes: paper tooth, ink plates multiplied onto paper with misregistration, riso grain,
halftone screens, hatching and wobbly pencil strokes. All pure numpy, all seeded.

The model is subtractive: a frame is paper, and each plate is an ink colour plus a coverage mask
(float 0–1, HxW). `plates()` multiplies every ink onto the paper at its own offset, so overlaps
darken like real ink (magenta over green goes near-black, blue over yellow goes green).

    paper = press.paper((W, H), (241, 233, 218), seed=3)
    out = press.plates(paper, [(red_mask, RED, (2, -1)), (blue_mask, BLUE, (0, 0))], tooth=press.tooth((W, H), 3))
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .easing import h

_CACHE = {}


def _cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def tooth(size, seed=0, scale=1.0):
    """Paper tooth: a fine 0–1 fibre/grain field (mean ≈ 0.5), cached per size and seed."""
    def make():
        w, hgt = size
        rng = np.random.default_rng(seed)
        fine = rng.random((hgt, w), dtype=np.float32)
        lo = rng.random((hgt // 6 + 2, w // 6 + 2), dtype=np.float32)
        lo = np.asarray(Image.fromarray((lo * 255).astype(np.uint8)).resize((w, hgt), Image.BICUBIC), np.float32) / 255
        fib = rng.random((hgt // 2 + 1, w // 14 + 2), dtype=np.float32)       # horizontal fibres
        fib = np.asarray(Image.fromarray((fib * 255).astype(np.uint8)).resize((w, hgt), Image.BILINEAR), np.float32) / 255
        t = 0.45 * fine + 0.35 * lo + 0.2 * fib
        if scale != 1.0:
            t = 0.5 + (t - 0.5) * scale
        return np.clip(t, 0, 1)
    return _cached(("tooth", size, seed, scale), make)


def paper(size, col, seed=0, strength=0.06):
    """Paper ground (HxWx3 float32, 0–255) with tooth multiplied in at `strength` (cached; don't mutate)."""
    def make():
        t = tooth(size, seed)
        base = np.empty((size[1], size[0], 3), np.float32)
        base[:] = col
        return base * (1 - strength * (t[..., None] - 0.5) * 2)
    return _cached(("paper", size, tuple(col), seed, strength), make)


def grain(size, fi, amount=0.18, cell=2, seed=0, hold=1):
    """Riso grain multiplier (HxW, ≤1): each cell keeps 1 - amount·r²·2 of its ink, reseeded every `hold` frames."""
    w, hgt = size
    gw, gh = w // cell + 1, hgt // cell + 1
    rng = np.random.default_rng(int(h(seed, fi // max(1, hold)) * 2 ** 31))
    r = rng.random((gh, gw), dtype=np.float32)
    g = np.clip(1 - amount * r * r * 2, 0, 1)
    return np.repeat(np.repeat(g, cell, 0), cell, 1)[:hgt, :w]


def shift(mask, dx, dy):
    """Integer-shift a mask (zeros fill the exposed edge)."""
    dx, dy = int(round(dx)), int(round(dy))
    if not dx and not dy:
        return mask
    out = np.zeros_like(mask)
    hgt, w = mask.shape[:2]
    ys, yd = (slice(0, hgt - dy), slice(dy, hgt)) if dy >= 0 else (slice(-dy, hgt), slice(0, hgt + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = mask[ys, xs]
    return out


def plates(ground, layers, tooth_field=None, tooth_k=0.35, density=1.0):
    """Multiply ink plates onto a paper ground. layers = [(mask HxW 0–1, rgb, (dx, dy)) ...].

    tooth_field knocks ink out where the paper is low (ink skips over the fibres), by tooth_k.
    density > 1 deepens every ink (the 'press lock' moment). Returns HxWx3 uint8.
    """
    out = ground.astype(np.float32, copy=True)
    for mask, col, off in layers:
        m = shift(mask, *off) if off else mask
        m = np.clip(m * density, 0, 1)
        if tooth_field is not None:
            m = m * (1 - tooth_k * np.clip(0.55 - tooth_field, 0, 1) * 2)
        ink = np.asarray(col, np.float32) / 255
        out *= 1 - m[..., None] * (1 - ink)
    return np.clip(out, 0, 255).astype(np.uint8)


def mask_from(draw_fn, size, ss=2):
    """Draw with PIL onto an L mask (supersampled ss× for clean edges), return float 0–1.

    draw_fn(draw, s) gets an ImageDraw and the scale factor; multiply every coordinate by s.
    """
    w, hgt = size
    m = Image.new("L", (w * ss, hgt * ss), 0)
    draw_fn(ImageDraw.Draw(m), ss)
    if ss > 1:
        m = m.reduce(ss)
    return np.asarray(m, np.float32) / 255


def halftone(field, pitch=12, angle=15.0, gamma=1.0, soft=0.9):
    """Halftone screen: field (HxW, 0–1 ink coverage) → dot mask. Dot area tracks coverage.

    The screen is rotated by `angle`; each cell's dot radius is sampled at the cell centre so dots
    stay round (a real AM screen), with an anti-aliased edge `soft` px wide.
    """
    hgt, w = field.shape
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    u = (xx * ca + yy * sa) / pitch
    v = (-xx * sa + yy * ca) / pitch
    cu, cv = np.floor(u) + 0.5, np.floor(v) + 0.5
    du, dv = (u - cu) * pitch, (v - cv) * pitch
    # sample the field at the cell centre
    cx = (cu * ca - cv * sa) * pitch
    cy = (cu * sa + cv * ca) * pitch
    sx = np.clip(cx.astype(np.int32), 0, w - 1)
    sy = np.clip(cy.astype(np.int32), 0, hgt - 1)
    cov = np.clip(field[sy, sx], 0, 1) ** gamma
    r = np.sqrt(cov / math.pi) * pitch * 1.08             # area-true radius; >0.5 pitch dots merge like real ink
    d = np.sqrt(du * du + dv * dv)
    return np.clip((r - d) / soft + 0.5, 0, 1)


def dot_grid(size, pitch, radius_fn, offset=(0, 0), ss=2):
    """A square grid of round dots whose radius is radius_fn(cx, cy) → px (vectorised over centres).

    Faster and crisper than `halftone` when the field is analytic (distance from a point, a wave …).
    """
    w, hgt = size
    ox, oy = offset
    cols = np.arange(-1, w / pitch + 2)
    rows = np.arange(-1, hgt / pitch + 2)
    cx, cy = np.meshgrid(cols * pitch + ox % pitch, rows * pitch + oy % pitch)
    r = np.asarray(radius_fn(cx, cy), np.float32)

    def draw(d, s):
        for x, y, rr in zip(cx.ravel(), cy.ravel(), r.ravel()):
            if rr > 0.25:
                d.ellipse(((x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s), fill=255)
    return mask_from(draw, size, ss)


def hatch(mask, pitch=7, angle=45.0, width=1.6, p=1.0, seed=0):
    """Diagonal hatching clipped to a mask. p (0–1) draws the lines on one at a time across the shape."""
    hgt, w = mask.shape
    a = math.radians(angle)
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    u = xx * math.cos(a) + yy * math.sin(a)
    k = np.floor(u / pitch)
    frac = np.abs(u - (k + 0.5) * pitch)
    lines = np.clip((width / 2 - frac) + 0.5, 0, 1)
    if p < 1:
        ys, xs = np.nonzero(mask > 0.05)
        if len(xs) == 0:
            return mask * 0
        uu = xs * math.cos(a) + ys * math.sin(a)
        lo, hi = uu.min() / pitch, uu.max() / pitch
        lines = lines * (k <= lo + (hi - lo + 1) * p)
    return lines * mask


def wobble(pts, fi, amp=1.2, seed=0, rate=8, fps=30, step=6.0):
    """Pencil wobble: resample a polyline every `step` px and push it off true by low sine waves whose
    phase re-rolls `rate` times a second (the line 'boils')."""
    pts = np.asarray(pts, np.float32)
    if len(pts) < 2:
        return pts
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(1))
    L = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(L[-1] / step) + 1)
    s = np.linspace(0, L[-1], n)
    x = np.interp(s, L, pts[:, 0])
    y = np.interp(s, L, pts[:, 1])
    k = int(fi * rate / fps)
    ph1, ph2 = h(seed, k, 1) * 6.283, h(seed, k, 2) * 6.283
    f1, f2 = 0.011 + 0.006 * h(seed, k, 3), 0.031 + 0.01 * h(seed, k, 4)
    off = amp * (np.sin(s * f1 + ph1) * 0.7 + np.sin(s * f2 + ph2) * 0.3)
    dx, dy = np.gradient(x), np.gradient(y)
    nl = np.sqrt(dx * dx + dy * dy) + 1e-6
    return np.stack([x - dy / nl * off, y + dx / nl * off], 1)


def partial(pts, p):
    """The first fraction p (0–1, by length) of a polyline."""
    pts = np.asarray(pts, np.float32)
    if p >= 1 or len(pts) < 2:
        return pts
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(1))
    L = np.concatenate([[0], np.cumsum(seg)])
    target = L[-1] * max(0.0, p)
    i = int(np.searchsorted(L, target, side="right"))
    if i <= 0:
        return pts[:1]
    if i >= len(pts):
        return pts
    q = (target - L[i - 1]) / max(seg[i - 1], 1e-6)
    return np.vstack([pts[:i], pts[i - 1] + (pts[i] - pts[i - 1]) * q])


def circle_pts(cx, cy, r, a0=0.0, a1=360.0, n=None):
    n = n or max(24, int(abs(a1 - a0) / 360 * r * 0.9))
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1)


def stroke(d, pts, width, s=1, fill=255):
    """Round-capped polyline on an ImageDraw (scaled by s)."""
    pts = [(float(x) * s, float(y) * s) for x, y in pts]
    if len(pts) < 2:
        return
    w = max(1, int(round(width * s)))
    d.line(pts, fill=fill, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def outline(mask, width=3):
    """The outline ring of a mask (dilate − erode), width px."""
    im = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8))
    k = max(3, int(width) | 1)
    a = np.asarray(im.filter(ImageFilter.MaxFilter(k)), np.float32)
    b = np.asarray(im.filter(ImageFilter.MinFilter(3)), np.float32)
    return np.clip(a - b, 0, 255) / 255
