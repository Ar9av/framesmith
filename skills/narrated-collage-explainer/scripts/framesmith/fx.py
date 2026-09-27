"""Raster effects: ASCII art, word-mask fields, pixel mosaics, glitch rows, barcodes."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from .easing import h
from .typography import F, GLYPHS

RAMP = " .,:;-=+*cxoO#%@"


@lru_cache(None)
def atlas(size, cw, ch, fg, bg, chars=RAMP, role="mono"):
    """Pre-rendered glyph tiles: (len(chars), ch, cw, 3)."""
    f = F(role, size)
    tiles = np.zeros((len(chars), ch, cw, 3), np.uint8)
    for i, c in enumerate(chars):
        t = Image.new("RGB", (cw, ch), bg)
        ImageDraw.Draw(t).text((cw / 2, ch / 2), c, font=f, fill=fg, anchor="mm")
        tiles[i] = np.asarray(t)
    return tiles


def _tile(idx, tiles, w, hgt):
    rows, cols = idx.shape
    out = tiles[idx].transpose(0, 2, 1, 3, 4).reshape(rows * tiles.shape[1], cols * tiles.shape[2], 3)
    return out[:hgt, :w]


def ascii_render(gray, w, hgt, cw=7, ch=12, size=11, fg=(255,) * 3, bg=(0,) * 3, chars=RAMP):
    """Brightness-ramp ASCII art of a PIL 'L' image, returned as an (hgt, w, 3) array."""
    cols, rows = -(-w // cw), -(-hgt // ch)
    g = np.asarray(gray.resize((cols, rows), Image.BILINEAR), np.float32) / 255
    idx = np.clip((g * (len(chars) - 1)).round().astype(int), 0, len(chars) - 1)
    return _tile(idx, atlas(size, cw, ch, fg, bg, chars), w, hgt)


def word_field(g, fi, w, hgt, word, fg, bg, cw=11, ch=17, size=15, digits=0.06, thresh=0.5):
    """Binary text mask: `word` repeats wherever g (2D float array, 0..1) is lit; digits sprinkle in."""
    word = word.upper() + " "
    chars = " " + "".join(sorted(set(word) - {" "})) + "0123456789"
    cols, rows = -(-w // cw), -(-hgt // ch)
    gg = np.asarray(Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).resize((cols, rows), Image.BILINEAR)) / 255
    r, c = np.mgrid[0:rows, 0:cols]
    seq = np.array([chars.index(x) for x in word])
    idx = seq[(c + r * 5) % len(word)]
    rng = np.random.default_rng(fi // 2)
    idx = np.where(rng.random((rows, cols)) < digits, rng.integers(len(chars) - 10, len(chars), (rows, cols)), idx)
    idx = np.where(gg > thresh, idx, 0)
    return _tile(idx, atlas(size, cw, ch, fg, bg, chars), w, hgt)


def random_text_block(w, hgt, fi, seed, cw=6, ch=9, size=8, fg=(0,) * 3, bg=(255,) * 3, rate=2):
    """Dense flickering terminal noise, refreshed every `rate` frames."""
    chars = GLYPHS + "_-.,:"
    cols, rows = -(-w // cw), -(-hgt // ch)
    idx = np.random.default_rng(seed * 1000 + fi // rate).integers(0, len(chars), (rows, cols))
    return _tile(idx, atlas(size, cw, ch, fg, bg, chars), w, hgt)


@lru_cache(None)
def noise_tex(seed=7, size=900):
    """Tileable-ish multi-octave value noise stretched into horizontal streaks, 0..1."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size), np.float32)
    for sx, sy, amp in ((6, 60, 1.0), (14, 140, 0.5), (40, 300, 0.25)):
        n = Image.fromarray((rng.random((sy, sx)) * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        acc += np.asarray(n, np.float32) / 255 * amp
    return (acc - acc.min()) / (acc.max() - acc.min())


def mosaic(a, b, p, cols, rows, seed, flashes, width=0.18):
    """Pixel-block transition: every cell flips A → flash colour → B at its own hashed time."""
    H, W = a.shape[:2]
    out = a.copy()
    cw, ch = -(-W // cols), -(-H // rows)
    for r in range(rows):
        for c in range(cols):
            ti = h(seed, r, c) * (1 - width)
            ys, xs = slice(r * ch, (r + 1) * ch), slice(c * cw, (c + 1) * cw)
            if p >= ti + width:
                out[ys, xs] = b[ys, xs]
            elif p >= ti:
                out[ys, xs] = flashes[int(h(seed, r, c, "f") * len(flashes))]
    return out


def glitch_rows(w, hgt, fi, seed, density, words, ink, paper, row_h=22, size=12):
    """Rows of paper-coloured blocks carrying word fragments; re-rolls every 2 frames."""
    im = Image.new("RGB", (w, hgt), ink)
    d = ImageDraw.Draw(im)
    f = F("mono", size)
    k = fi // 2
    for r in range(hgt // row_h + 1):
        x, c = 0, 0
        while x < w:
            L = int(20 + h(seed, r, c, k) * 160)
            if h(seed, r, c, k, "on") < density:
                d.rectangle((x, r * row_h, x + L, r * row_h + row_h - 1), fill=paper)
                wd = words[int(h(seed, r, c, "w") * len(words))]
                d.text((x + 2, r * row_h + 4), wd[: max(1, L // 7)], font=f, fill=ink)
            x += L
            c += 1
    return im


def smear(frame, fi, color, max_shift=200):
    """Horizontal band displacement + monochrome tint of an RGB array."""
    lum = frame.astype(np.float32).mean(axis=2) / 255
    out = np.array(color, np.float32)[None, None] * lum[..., None]
    rng = np.random.default_rng(fi)
    y = 0
    while y < out.shape[0]:
        bh = int(rng.integers(3, 30))
        out[y:y + bh] = np.roll(out[y:y + bh], int(rng.integers(-max_shift, max_shift)), axis=1)
        y += bh
    return out.astype(np.uint8)


def barcode(d, x, y, w, hgt, col, seed):
    xx, k = x, 0
    while xx < x + w:
        bw = 1 + int(h(seed, k) * 4)
        if h(seed, k, "g") > 0.4:
            d.rectangle((xx, y, min(xx + bw - 1, x + w), y + hgt), fill=col)
        xx += bw + 1
        k += 1


def crosshair(d, x, y, col, s=6):
    d.line((x - s, y, x + s, y), fill=col)
    d.line((x, y - s, x, y + s), fill=col)


def dashed(d, a, b, col, w=1, dash=10, gap=6):
    (x1, y1), (x2, y2) = a, b
    L = math.hypot(x2 - x1, y2 - y1)
    if not L:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    s = 0
    while s < L:
        e = min(s + dash, L)
        d.line((x1 + ux * s, y1 + uy * s, x1 + ux * e, y1 + uy * e), fill=col, width=w)
        s += dash + gap
