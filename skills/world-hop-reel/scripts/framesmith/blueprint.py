"""Vector engineering drawings, redrawn per frame so zooms stay crisp.

All functions take `s` (scale), colours, and `t` (drives counting dimensions).
`draw` in [0,1] is the draw-on progress.
"""
import math

from PIL import Image, ImageDraw

from .easing import h, lerp, prog
from .fx import dashed
from .typography import F


def dim_label(img, xy, s, col, bg, size=14, vertical=False):
    f = F("mono_bold", size)
    lab = Image.new("RGB", (int(f.getlength(s)) + 10, size + 8), col)
    ImageDraw.Draw(lab).text((5, 3), s, font=f, fill=bg)
    if vertical:
        lab = lab.rotate(90, expand=True)
    img.paste(lab, (int(xy[0] - lab.width / 2), int(xy[1] - lab.height / 2)))


def arrow_dim(img, a, b, s, col, bg, lw, size=14):
    d = ImageDraw.Draw(img)
    (x1, y1), (x2, y2) = a, b
    d.line((x1, y1, x2, y2), fill=col, width=lw)
    ang = math.atan2(y2 - y1, x2 - x1)
    for (px, py), sgn in (((x1, y1), 1), ((x2, y2), -1)):
        for da in (0.45, -0.45):
            d.line((px, py, px + sgn * 12 * math.cos(ang + da), py + sgn * 12 * math.sin(ang + da)), fill=col, width=lw)
    dim_label(img, ((x1 + x2) / 2, (y1 + y2) / 2), s, col, bg, size, vertical=abs(x2 - x1) < abs(y2 - y1))


def top_view(img, cx, cy, s, col, bg, t, draw=1.0, lw=2, seed=0, labels=True, label="BASE DIA"):
    """Plan view of a round base: concentric rings, bolt circle, housings, centre lines, dims."""
    d = ImageDraw.Draw(img)
    for i, r in enumerate((1.0, 0.86, 0.72, 0.5, 0.3, 0.16)):
        R = 200 * s * r
        end = -90 + 360 * min(1, max(0, draw * 1.6 - i * 0.12))
        if end > -90:
            d.arc((cx - R, cy - R, cx + R, cy + R), -90, end, fill=col, width=lw)
    for k in range(8):
        a = k / 8 * math.tau + 0.2
        bx, by = cx + 186 * s * math.cos(a), cy + 186 * s * math.sin(a)
        if draw > 0.4 + k * 0.05:
            d.ellipse((bx - 7 * s, by - 7 * s, bx + 7 * s, by + 7 * s), outline=col, width=lw)
    if draw > 0.5:
        d.rectangle((cx - 130 * s, cy - 110 * s, cx + 40 * s, cy + 110 * s), outline=col, width=lw)
        d.rectangle((cx - 200 * s, cy + 90 * s, cx - 60 * s, cy + 230 * s), outline=col, width=lw)
        d.rectangle((cx - 170 * s, cy + 120 * s, cx - 90 * s, cy + 260 * s), outline=col, width=lw)
        for yy in range(6):
            y = cy + (180 + yy * 16) * s
            d.line((cx - 60 * s, y, cx + 60 * s, y), fill=col, width=lw)
        dashed(d, (cx - 260 * s, cy), (cx + 260 * s, cy), col, 1)
        dashed(d, (cx, cy - 260 * s), (cx, cy + 260 * s), col, 1)
    if labels and draw > 0.7:
        p = prog(t, 0, 3)
        n1 = int(lerp(500, 748, p)) + int(h(seed, "a") * 60)
        n2, n3 = int(lerp(512, 527, p)), int(lerp(600, 932, p))
        z = min(s, 2.4)
        dim_label(img, (cx, cy - 250 * s), f"{label} {n1}", col, bg, max(10, int(12 * min(s, 2))))
        arrow_dim(img, (cx - 40 * s, cy - 20 * s), (cx + 40 * s, cy - 20 * s), f"S{n2 % 100}", col, bg, lw, max(10, int(11 * z)))
        arrow_dim(img, (cx + 250 * s, cy + 40 * s), (cx + 250 * s, cy + 150 * s), f"{n3 % 1000}", col, bg, lw, max(10, int(11 * z)))


def front_view(img, cx, top, s, col, bg, t, draw=1.0, lw=2, label="BASE DIA"):
    """Front elevation: base rings at top, column, joint, wrist and a two-finger end effector."""
    d = ImageDraw.Draw(img)
    top_view(img, cx, top + 170 * s, s * 0.8, col, bg, t, draw, lw, seed=1, labels=False)
    y = top + 340 * s
    if draw > 0.3:
        d.rectangle((cx - 40 * s, y, cx + 40 * s, y + 360 * s), outline=col, width=lw)
        d.rectangle((cx - 25 * s, y + 20 * s, cx + 25 * s, y + 340 * s), outline=col, width=lw)
        d.ellipse((cx - 60 * s, y + 340 * s, cx + 60 * s, y + 460 * s), outline=col, width=lw)
        d.ellipse((cx - 25 * s, y + 375 * s, cx + 25 * s, y + 425 * s), outline=col, width=lw)
        d.rectangle((cx - 45 * s, y + 460 * s, cx + 45 * s, y + 560 * s), outline=col, width=lw)
        for sgn in (-1, 1):
            d.line((cx + sgn * 30 * s, y + 560 * s, cx + sgn * 55 * s, y + 620 * s, cx + sgn * 25 * s, y + 690 * s), fill=col, width=lw)
        n = int(lerp(300, 522, prog(t, 0, 2)))
        dim_label(img, (cx, top - 10 * s), f"{label} {n + 180}", col, bg, 12)
        arrow_dim(img, (cx + 90 * s, y + 470 * s), (cx + 90 * s, y + 560 * s), f"{n % 100}", col, bg, lw, 11)
        dim_label(img, (cx, y + 395 * s), f"S{(n // 3) % 100}", col, bg, 11)
