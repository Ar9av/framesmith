"""Interface primitives for software / dev-tool videos: windows, terminals, kinetic type, cards, holo light.

No pill/chip/badge primitive on purpose: status is typeset, never boxed in a rounded label."""
import math

import numpy as np
from PIL import Image, ImageDraw

from PIL import features as _features

from .typography import F, text

# Code must render literally: no programming ligatures (Geist Mono turns "<!--" and "-->" into arrows).
CODE_FEATURES = ["-liga", "-calt"] if _features.check("raqm") else None


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([int(v) for v in box], radius=int(r), fill=fill, outline=outline, width=width)


def window(img, box, bg, bar, title="", title_col=(140, 140, 140), dots=True, r=14, font_size=14):
    """macOS-style window chrome. Returns the content box (x0, y0, x1, y1)."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    rrect(d, box, r, fill=bg, outline=bar, width=1)
    bh = int(font_size * 2.6)
    d.rounded_rectangle((x0, y0, x1, y0 + bh), radius=r, fill=bar)
    d.rectangle((x0, y0 + bh - r, x1, y0 + bh), fill=bar)
    if dots:
        for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            cx, cy = x0 + 22 + i * 22, y0 + bh / 2
            d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=c)
    if title:
        text(d, ((x0 + x1) / 2, y0 + bh / 2), title, F("mono", font_size), title_col, 0, "mm")
    return (x0, y0 + bh, x1, y1)


def _span(sp, size, default_role="mono"):
    """Span = (text, rgb) or (text, rgb, font_role)."""
    return sp[0], sp[1], F(sp[2] if len(sp) > 2 else default_role, size)


def _wrap_spans(spans, size, max_w):
    """Split spans into rows no wider than max_w, breaking at spaces (long words hard-break)."""
    chars = []
    for sp in spans:
        s_, col, f = _span(sp, size)
        chars += [(ch, col, f) for ch in s_]
    rows, start = [], 0
    while start < len(chars):
        w, end, last_space = 0.0, start, -1
        while end < len(chars):
            cw = chars[end][2].getlength(chars[end][0], features=CODE_FEATURES)
            if max_w and w + cw > max_w and end > start:
                break
            if chars[end][0] == " ":
                last_space = end
            w += cw
            end += 1
        if end < len(chars) and last_space > start:
            end = last_space + 1
        row, cur, key = [], "", None
        for ch, col, f in chars[start:end]:
            if (col, f) != key and cur:
                row.append((cur, key[0], key[1]))
                cur = ""
            cur, key = cur + ch, (col, f)
        if cur:
            row.append((cur.rstrip() if end < len(chars) else cur, key[0], key[1]))
        rows.append(row)
        start = end
    return rows or [[]]


def terminal(img, origin, lines, t, size=24, lh=1.55, cursor_col=(230, 230, 230), fi=0, max_lines=None, max_width=None):
    """Time-scheduled terminal transcript that never overflows its window.

    lines: [{"spans": [(text, rgb[, font_role]), ...], "t": start_s, "type": seconds_to_type (0 = instant),
             "mark": optional rgb highlighter swept behind the line, "mark_dur": seconds}]
    Lines appear at t and type over `type` seconds; long lines word-wrap at max_width. Scrolls to keep
    the last `max_lines` rows. Returns {line_index: [(x0, y, x_end), ...rows]} for overlays.
    """
    d = ImageDraw.Draw(img)
    x0, y0 = origin
    rows = []
    for i, ln in enumerate(lines):
        if t < ln.get("t", 0):
            continue
        n = sum(len(sp[0]) for sp in ln["spans"])
        dur = ln.get("type", 0)
        k = n if dur <= 0 else int(n * min(1.0, (t - ln["t"]) / dur))
        before = 0
        for r in _wrap_spans(ln["spans"], size, max_width):
            rl = sum(len(sp[0]) for sp in r)
            if before < k or before == 0:
                rows.append((i, r, min(rl, max(0, k - before)), ln))
            before += rl
    if max_lines and len(rows) > max_lines:
        rows = rows[-max_lines:]
    pos, cur = {}, None
    for ri, (i, spans, k, ln) in enumerate(rows):
        y = y0 + ri * size * lh
        if ln.get("mark") and k:
            w = sum(f.getlength(s_, features=CODE_FEATURES) for s_, _, f in spans)
            mp = (t - ln["t"]) / max(ln.get("mark_dur", 0.22), 1e-3)
            marker(d, (x0 - 10, y - size * 0.18, x0 + w + 10, y + size * 1.22), ln["mark"], mp)
        x, left = x0, k
        for s_, col, f in spans:
            part = s_[:max(0, left)]
            if part:
                d.text((x, y + (size - f.size) * 0.5), part, font=f, fill=col, features=CODE_FEATURES)
                x += f.getlength(part, features=CODE_FEATURES)
            left -= len(s_)
        pos.setdefault(i, []).append((x0, y, x))
        cur = (x, y)
    if cur and (fi // 8) % 2 == 0:
        d.rectangle((cur[0] + 3, cur[1] + 2, cur[0] + size * 0.58, cur[1] + size * 1.2), fill=cursor_col)
    return pos


def holo_field(w, hgt, t, palette, scale=1.0, seed=0):
    """Iridescent holographic light: flowing interference bands mapped through a pastel palette."""
    yy, xx = np.mgrid[0:hgt, 0:w].astype(np.float32)
    xx /= w
    yy /= hgt
    k = 6.0 / scale
    v = (np.sin(xx * k + yy * k * 0.6 + t * 0.9 + seed)
         + 0.6 * np.sin(math.cos(seed) * xx * k * 1.7 - yy * k * 1.3 - t * 0.6)
         + 0.4 * np.sin((xx * xx + yy) * k * 2.2 + t * 1.3))
    v = (v - v.min()) / (np.ptp(v) + 1e-6)
    pal = np.array(palette + [palette[0]], np.float32)
    stops = np.linspace(0, 1, len(pal))
    out = np.stack([np.interp(v, stops, pal[:, c]) for c in range(3)], axis=-1)
    return out.astype(np.uint8)


def stat_card(img, box, label, value, bg, fg, sub_col, r=12, size=44):
    d = ImageDraw.Draw(img)
    rrect(d, box, r, fill=bg)
    x0, y0, x1, y1 = box
    text(d, (x0 + 20, y0 + 18), label.upper(), F("mono", 13), sub_col, 1)
    text(d, (x0 + 20, y1 - 18), value, F("sans_medium", size), fg, -1, "ls")


def _text_layer(size, xy, s, font, track, anchor, max_w, fit_to):
    m = Image.new("L", size, 0)
    text(ImageDraw.Draw(m), xy, s, font, 255, track, anchor, max_w=max_w, fit_to=fit_to)
    return m


def rise(img, xy, s, font, fill, p, track=0, anchor="la", max_w=None, fit_to=None, overshoot=0.18):
    """Kinetic-type entrance: text rises out of a mask at its own baseline (p: 0→1, pass eased progress).

    `fill` is an RGB tuple, or a callable (w, h) -> HxWx3 array to fill the glyphs with a texture.
    """
    if p <= 0:
        return None
    m = _text_layer(img.size, xy, s, font, track, anchor, max_w, fit_to)
    bb = m.getbbox()
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    hgt = y1 - y0
    pad = int(hgt * overshoot)
    glyphs = m.crop((x0, y0 - pad, x1, y1 + pad))
    shift = int((1 - min(p, 1)) * (hgt + pad))
    moved = Image.new("L", glyphs.size, 0)
    moved.paste(glyphs, (0, shift))
    tex = Image.new("RGB", glyphs.size, fill) if isinstance(fill, tuple) else Image.fromarray(fill(*glyphs.size))
    img.paste(tex, (x0, y0 - pad), moved)
    return bb


def fill_text(img, xy, s, font, fill_fn, track=0, anchor="la", max_w=None, fit_to=None):
    """Text whose glyphs are filled by fill_fn(w, h) -> HxWx3 array (gradients, holo light, video)."""
    m = _text_layer(img.size, xy, s, font, track, anchor, max_w, fit_to)
    bb = m.getbbox()
    if bb:
        img.paste(Image.fromarray(fill_fn(bb[2] - bb[0], bb[3] - bb[1])), bb[:2], m.crop(bb))
    return bb


def marker(d, box, col, p, skew=6):
    """Highlighter swipe: a solid block that grows left→right over box as p goes 0→1."""
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    xe = x0 + (x1 - x0) * min(p, 1)
    d.polygon([(x0 + skew, y0), (xe + skew, y0), (xe, y1), (x0, y1)], fill=col)
