"""Interface primitives for software / dev-tool videos: windows, terminals, chips, cards, holo light."""
import math

import numpy as np
from PIL import Image, ImageDraw

from .typography import F, text


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


def chip(img, xy, label, fg, bg, size=18, pad=(14, 7), anchor="lm", role="mono_bold", outline=None):
    """Pill label. Returns its box."""
    d = ImageDraw.Draw(img)
    f = F(role, size)
    w = f.getlength(label) + pad[0] * 2
    h = size + pad[1] * 2
    x, y = xy
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    if anchor[1] == "m":
        y -= h / 2
    box = (x, y, x + w, y + h)
    rrect(d, box, h / 2, fill=bg, outline=outline)
    d.text((x + pad[0], y + h / 2), label, font=f, fill=fg, anchor="lm")
    return box


def terminal(img, origin, lines, t, size=24, lh=1.55, cursor_col=(230, 230, 230), fi=0, max_lines=None):
    """Time-scheduled terminal transcript.

    lines: [{"spans": [(text, rgb), ...], "t": start_s, "type": seconds_to_type (0 = instant),
             "bg": optional highlight rgb}]
    Lines appear at t, type over `type` seconds (linear, like a real terminal). Scrolls to keep the
    last `max_lines` visible. Returns a dict line_index → (x0, y, x_end) for overlays.
    """
    d = ImageDraw.Draw(img)
    f = F("mono", size)
    x0, y0 = origin
    vis = [(i, ln) for i, ln in enumerate(lines) if t >= ln.get("t", 0)]
    if max_lines and len(vis) > max_lines:
        vis = vis[-max_lines:]
    pos, cur = {}, None
    for row, (i, ln) in enumerate(vis):
        y = y0 + row * size * lh
        n = sum(len(s_) for s_, _ in ln["spans"])
        dur = ln.get("type", 0)
        k = n if dur <= 0 else int(n * min(1.0, (t - ln["t"]) / dur))
        x = x0
        if ln.get("bg") and k:
            w = sum(f.getlength(s_) for s_, _ in ln["spans"])
            d.rectangle((x0 - 6, y - 4, x0 + w + 6, y + size * 1.25), fill=ln["bg"])
        left = k
        for s_, col in ln["spans"]:
            part = s_[:max(0, left)]
            if part:
                d.text((x, y), part, font=f, fill=col)
                x += f.getlength(part)
            left -= len(s_)
        pos[i] = (x0, y, x)
        cur = (x, y) if k < n or row == len(vis) - 1 else cur
    if cur and (fi // 8) % 2 == 0:
        d.rectangle((cur[0] + 3, cur[1] + 2, cur[0] + size * 0.62, cur[1] + size * 1.2), fill=cursor_col)
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
