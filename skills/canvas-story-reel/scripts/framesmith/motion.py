"""Motion primitives for kinetic launch films (ideas ported from howseen-ai/claude-motion-design, MIT, to
framesmith's pure-Python seek(t) model): closed-form springs, masked word rises synced to the voice, letter
stretch, words riding dashed paths, scatter, 3D perspective tilt, detection boxes, border and connector beams,
and code-synthesised sound effects. Every function is a pure function of time.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .typography import F, text_width
from .easing import ease_in_out, ease_out, lerp, h

# ------------------------------------------------------------------ springs
SNAPPY, DEFAULT, HEAVY, PLAYFUL = (320, 30), (170, 26), (120, 24), (180, 12)


def spring(t, k=320, d=30):
    """Closed-form step response of a unit mass spring (0 → 1, may overshoot when underdamped)."""
    if t <= 0:
        return 0.0
    w = math.sqrt(k)
    z = d / (2 * w)
    if z >= 1:
        return 1 - math.exp(-w * t) * (1 + w * t)
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * t) * (math.cos(wd * t) + z / math.sqrt(1 - z * z) * math.sin(wd * t))


# ------------------------------------------------------------------ accent fill
ACCENT = [(206, 52, 128), (226, 110, 40), (22, 146, 118), (44, 98, 224), (128, 70, 214)]


def accent_fill(x0, w, hgt, t, palette=ACCENT, period=900.0, speed=90.0):
    """A deep holographic gradient that scrolls along x (continuous across words: pass the word's global x)."""
    xs = (np.arange(w, dtype=np.float32) + x0 + t * speed) / period
    v = xs - np.floor(xs)
    pal = np.array(palette + [palette[0]], np.float32)
    stops = np.linspace(0, 1, len(pal))
    row = np.stack([np.interp(v, stops, pal[:, c]) for c in range(3)], -1)
    return np.repeat(row[None], hgt, 0).astype(np.uint8)


# ------------------------------------------------------------------ kinetic words
def parse(line):
    """'Your agents work *everywhere*' → [(word, accent)]."""
    out, acc = [], False
    for tok in line.split(" "):
        if not tok:
            continue
        a0 = tok.startswith("*")
        a1 = tok.endswith("*") and len(tok) > 1
        w = tok.strip("*")
        out.append((w, acc or a0))
        acc = (acc or a0) and not a1
    return out


def word_layer(word, font, fill, x_global, t, track=-1.0):
    """RGBA word image (glyphs filled with a colour or the scrolling accent) + its baseline offset."""
    asc, desc = font.getmetrics()
    w = int(text_width(word, font, track) + 8)
    hgt = asc + desc + 8
    m = Image.new("L", (w, hgt), 0)
    d = ImageDraw.Draw(m)
    x = 4
    for ch in word:
        d.text((x, 4), ch, font=font, fill=255)
        x += font.getlength(ch) + track
    if fill == "accent":
        tex = Image.fromarray(accent_fill(x_global, w, hgt, t))
    else:
        tex = Image.new("RGB", (w, hgt), fill)
    out = tex.convert("RGBA")
    out.putalpha(m)
    return out, asc + 4


def kinetic(im, lines, size, times, lt, t, cx, cy, ink=(22, 22, 30), align="center", lh=1.16, rot=5.0,
            stretch=None, fall=None, scatter=None, out_p=0.0, spring_kd=SNAPPY, role="sans_medium", track=None):
    """Lay out lines of (word, accent) and reveal each word with a masked spring rise at times[i] (beat-local).

    stretch = (word_index, letter_index, extra, t0, dur): rubber-band a letter ('everrrywhere').
    fall = (word_index, t0): the word tips off its baseline.  scatter = t0: every word flies apart.
    out_p: 0..1 exit (blur + lift), for swaps between phrases.
    """
    font = F(role, size)
    track = -size * 0.012 if track is None else track
    space = font.getlength(" ")
    lh_px = size * lh
    words, k = [], 0
    for li, ln in enumerate(lines):
        row = []
        for w, acc in ln:
            s = w
            if stretch and stretch[0] == k:
                wi, li_, extra, t0, dur = stretch
                q = min(1, max(0, (lt - times[k] - t0) / dur))
                n = int(round(extra * math.sin(math.pi * q)))
                s = w[:li_ + 1] + w[li_] * n + w[li_ + 1:]
            row.append((k, s, acc))
            k += 1
        words.append(row)
    total_h = lh_px * len(words)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for li, row in enumerate(words):
        widths = [text_width(s, font, track) for _, s, _ in row]
        lw = sum(widths) + space * (len(row) - 1)
        x = cx - lw / 2 if align == "center" else cx
        base_y = cy - total_h / 2 + li * lh_px + size * 0.86
        for (i, s, acc), ww in zip(row, widths):
            p = spring(lt - times[i], *spring_kd) if i < len(times) else 1.0
            if p <= 0.001:
                x += ww + space
                continue
            wl, asc = word_layer(s, font, "accent" if acc else ink, x, t, track)
            dy = (1 - p) * lh_px * 1.05
            ang = (1 - min(1, p)) * rot
            ox, oy = 0.0, 0.0
            if fall and fall[0] == i:
                q = spring(lt - times[i] - fall[1], *PLAYFUL)
                ang += -16 * q
                oy += 22 * q
            if scatter is not None and lt > scatter:
                q = ease_in_out(min(1, (lt - scatter) / 0.7))
                a = h(i, 3) * math.tau
                dist = 380 + 420 * h(i, 5)
                ox += math.cos(a) * dist * q
                oy += math.sin(a) * dist * q
                ang += (h(i, 7) - 0.5) * 80 * q
                wl = wl.filter(ImageFilter.GaussianBlur(6 * q)) if q > 0.05 else wl
                a8 = np.asarray(wl).copy()
                a8[..., 3] = (a8[..., 3] * (1 - q)).astype(np.uint8)
                wl = Image.fromarray(a8)
            if abs(ang) > 0.2:
                wl = wl.rotate(ang, Image.BICUBIC, expand=True)
            # mask: the word only exists inside its own line box while it rises
            top = int(base_y - asc - size * 0.25)
            box_h = int(lh_px * 1.3)
            px, py = int(x - (wl.width - ww) / 2 + ox), int(base_y - asc + dy + oy - (wl.height - (asc + font.getmetrics()[1] + 8)) / 2)
            if p < 0.999 and scatter is None:
                c0, c1 = max(0, top - py), min(wl.height, top + box_h - py)
                if c1 > c0:
                    piece = wl.crop((0, c0, wl.width, c1))
                    layer.paste(piece, (px, py + c0), piece)
            else:
                layer.paste(wl, (px, py), wl)
            x += ww + space
    if out_p > 0:
        layer = layer.filter(ImageFilter.GaussianBlur(14 * out_p))
        a8 = np.asarray(layer).copy()
        a8[..., 3] = (a8[..., 3] * (1 - out_p)).astype(np.uint8)
        layer = Image.fromarray(a8)
        im.alpha_composite(layer, (0, int(-30 * out_p)))
    else:
        im.alpha_composite(layer)


# ------------------------------------------------------------------ paths
def bezier(pts, n=80):
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = pts
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        out.append((mt ** 3 * ax + 3 * mt * mt * t * bx + 3 * mt * t * t * cx + t ** 3 * dx,
                    mt ** 3 * ay + 3 * mt * mt * t * by + 3 * mt * t * t * cy + t ** 3 * dy))
    return out


def dashed_path(d, pts, p, col, width=3, dash=14, gap=11):
    """Draw the first p (0..1) of a polyline as dashes."""
    L = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L.append(L[-1] + math.hypot(x1 - x0, y1 - y0))
    end = L[-1] * p
    s = 0.0
    while s < end:
        e = min(end, s + dash)
        seg = _sub(pts, L, s, e)
        if len(seg) > 1:
            d.line(seg, fill=col, width=width, joint="curve")
        s += dash + gap


def _sub(pts, L, s, e):
    out = []
    for i in range(len(pts) - 1):
        if L[i + 1] < s or L[i] > e:
            continue
        for (a, b) in ((max(s, L[i]), None), (min(e, L[i + 1]), None)):
            f = (a - L[i]) / max(1e-6, L[i + 1] - L[i])
            out.append((lerp(pts[i][0], pts[i + 1][0], f), lerp(pts[i][1], pts[i + 1][1], f)))
    return out


def point_at(pts, dist):
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if acc + seg >= dist:
            f = (dist - acc) / max(1e-6, seg)
            return lerp(x0, x1, f), lerp(y0, y1, f), math.degrees(math.atan2(y1 - y0, x1 - x0))
        acc += seg
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    return x1, y1, math.degrees(math.atan2(y1 - y0, x1 - x0))


def text_on_path(im, pts, s, font, fill, start, p=1.0, lift=6):
    """Glyphs set along a polyline from arc length `start`, each rotated to the tangent; reveal by p."""
    dist = start
    n = int(round(len(s) * p))
    for ch in s[:n]:
        w = font.getlength(ch)
        x, y, ang = point_at(pts, dist + w / 2)
        g = Image.new("RGBA", (int(w + 12), int(font.size * 1.6)), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((6, font.size * 0.1), ch, font=font, fill=fill)
        g = g.rotate(-ang, Image.BICUBIC, expand=True)
        nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
        im.alpha_composite(g, (int(x - g.width / 2 - nx * lift), int(y - g.height / 2 - ny * lift)))
        dist += w


# ------------------------------------------------------------------ 3D tilt
def _coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def tilt(layer, canvas_size, cx, cy, ry=-14.0, rx=8.0, rz=0.0, scale=1.0, f=2200.0):
    """Project a flat RGBA layer as a card rotated in 3D (degrees) and centred at (cx, cy)."""
    w, hgt = layer.size
    corners = [(-w / 2, -hgt / 2), (w / 2, -hgt / 2), (w / 2, hgt / 2), (-w / 2, hgt / 2)]
    a, b, c = math.radians(rx), math.radians(ry), math.radians(rz)
    dst = []
    for x, y in corners:
        x, y = x * scale, y * scale
        x, y = x * math.cos(c) - y * math.sin(c), x * math.sin(c) + y * math.cos(c)
        y, z = y * math.cos(a), y * math.sin(a)
        x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
        k = f / (f + z)
        dst.append((cx + x * k, cy + y * k))
    co = _coeffs(dst, [(0, 0), (w, 0), (w, hgt), (0, hgt)])
    return layer.transform(canvas_size, Image.PERSPECTIVE, co, Image.BICUBIC), dst


# ------------------------------------------------------------------ boxes & beams
def detect_box(d, box, col, p, fill_a=46, r=8, width=3):
    """A detection overlay: outline + translucent fill that grows from the box centre (p: 0→1 spring)."""
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    q = min(1.0, p)
    bx = (mx - (mx - x0) * q, my - (my - y0) * q, mx + (x1 - mx) * q, my + (y1 - my) * q)
    d.rounded_rectangle(bx, r, fill=col + (int(fill_a * q),), outline=col + (int(255 * q),), width=width)


def border_beam(size, box, r, t, colors=((206, 52, 128), (44, 98, 224)), length=0.28, width=3):
    """A light that travels around a rounded-rect border (21st.dev Border Beam, seeked by t)."""
    w, hgt = size
    x0, y0, x1, y1 = box
    per = 2 * (x1 - x0 + y1 - y0)
    pts = []
    for i in range(240):
        s = i / 240 * per
        if s < x1 - x0:
            pts.append((x0 + s, y0))
        elif s < x1 - x0 + y1 - y0:
            pts.append((x1, y0 + s - (x1 - x0)))
        elif s < 2 * (x1 - x0) + y1 - y0:
            pts.append((x1 - (s - (x1 - x0) - (y1 - y0)), y1))
        else:
            pts.append((x0, y1 - (s - 2 * (x1 - x0) - (y1 - y0))))
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    head = (t % 1.0) * len(pts)
    n = int(length * len(pts))
    for j in range(n):
        i = int(head - j) % len(pts)
        i2 = (i + 1) % len(pts)
        q = 1 - j / n
        c = tuple(int(lerp(colors[1][k], colors[0][k], q)) for k in range(3))
        d.line((pts[i], pts[i2]), fill=c + (int(255 * q),), width=width)
    return lay


def beam(d, pts, p, t, base=(255, 255, 255, 170), pulse=(44, 98, 224), width=3, speed=0.8, phase=0.0):
    """Connector drawn to p, then a gradient pulse that travels along it (Animated Beam)."""
    m = int(p * (len(pts) - 1))
    if m < 1:
        return
    d.line(pts[:m + 1], fill=base, width=width, joint="curve")
    if p >= 1:
        head = ((t * speed + phase) % 1.0) * len(pts)
        for j in range(18):
            i = int(head - j)
            if 0 <= i < len(pts) - 1:
                q = 1 - j / 18
                d.line((pts[i], pts[i + 1]), fill=pulse + (int(255 * q),), width=width + 1)


def spinner(d, cx, cy, r, t, col, width=4):
    a = (t * 360 * 1.3) % 360
    d.arc((cx - r, cy - r, cx + r, cy + r), a, a + 270, fill=col, width=width)


# ------------------------------------------------------------------ synthesised sound
SR = 48000


def _env(n, a=0.004, dcy=6.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t * dcy)


def sfx(kind):
    """Short effects synthesised in code: click, tick, pop, whoosh, thump."""
    if kind == "click":
        n = int(0.03 * SR)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * 2300 * t) * _env(n, 0.001, 160) * 0.6
    if kind == "tick":
        n = int(0.05 * SR)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * 1500 * t) * _env(n, 0.001, 90) * 0.5
    if kind == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        f = 520 + 520 * t / t[-1]
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.003, 32) * 0.7
    if kind == "thump":
        n = int(0.25 * SR)
        t = np.arange(n) / SR
        f = 140 * np.exp(-t * 9) + 45
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 14)
    if kind == "whoosh":
        n = int(0.45 * SR)
        rng = np.random.default_rng(4)
        x = rng.standard_normal(n)
        k = np.hanning(int(0.004 * SR) + 1)
        x = np.convolve(x, k / k.sum(), "same")                     # soft low-pass
        env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
        return x * env * 0.5
    raise KeyError(kind)


def mix(voice_wav, events, out_wav, sfx_gain=1.0):
    """Voice + effects placed at their times: events = [(t, kind, gain)]. Writes 16-bit mono at 48 kHz."""
    import subprocess, wave
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", voice_wav, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    end = max([len(v) / SR] + [t + 1 for t, _, _ in events])
    out = np.zeros(int(end * SR) + SR, np.float32)
    out[:len(v)] += v
    cache = {}
    for t, kind, g in events:
        s = cache.setdefault(kind, sfx(kind))
        i = int(t * SR)
        out[i:i + len(s)] += s[:len(out) - i] * g * sfx_gain
    out /= max(1.0, np.abs(out).max() / 0.95)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return out_wav
