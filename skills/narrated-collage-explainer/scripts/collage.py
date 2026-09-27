#!/usr/bin/env python3
"""narrated-collage-explainer: a square, voiceover-driven explainer built as a paper-white collage.

Visual grammar: one big pixel-type keyword at a time, tiny synced subtitles, and media shown
inside objects: a retro CRT TV, an XP-style window on green hills, stacked dark cards, navy
starbursts, scattered photos. Beats cut on spoken cue phrases, with pixel-block dissolves.

    python3 collage.py voice  --brief brief.json      # TTS the script + word timestamps (OpenAI)
    python3 collage.py assets --brief brief.json      # generate image slots with gpt-image-2
    python3 collage.py check|still|sheet|render --brief brief.json [times...]
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from framesmith import (Assets, Mosaic, Scene, Theme, Timeline, cover, ease_in_out, ease_out, generate_images, h,
                        hex2rgb, lerp, overflow_report, text)
from framesmith.media import fetch_icons, icon, is_light_mark
from framesmith import narration, ui
from framesmith.typography import F, OVERFLOWS, SHRINKS, fit

G = None


# ------------------------------------------------------------------ state
class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.bg = c("bg", (238, 241, 236))
        self.word = c("word", (122, 11, 11))            # big keywords + subtitles
        self.navy = c("navy", (19, 30, 95))
        self.cyan = c("cyan", (63, 227, 232))
        self.ink = c("ink", (10, 10, 10))
        self.paper = c("paper", (245, 245, 240))
        self.signal = c("signal", (255, 59, 31))
        self.card = c("card", (11, 11, 12))
        self.W, self.H = brief.get("size", [1080, 1080])
        self.assets = Assets(os.path.join(base, brief.get("assets_dir", "assets")), os.path.join(HERE, "..", "placeholders"))
        self._c = {}
        vo = brief["vo"]
        self.script = open(os.path.join(base, vo["script"])).read().strip()
        wpath = os.path.join(base, vo["words"])
        if os.path.exists(wpath):
            tr = json.load(open(wpath))
            self.toks = narration.align(self.script, tr["words"])
            self.vo_dur = tr["duration"]
        else:                                               # no voice yet: fake 2.6 words/s so layout can be reviewed
            words = self.script.split()
            fake = [{"word": w, "start": i / 2.6, "end": (i + 0.8) / 2.6} for i, w in enumerate(words)]
            self.toks = narration.align(self.script, fake)
            self.vo_dur = len(words) / 2.6
        self.subs = narration.chunks(self.toks, brief.get("subtitle_words", 3))
        self.audio = os.path.join(base, vo["audio"]) if os.path.exists(os.path.join(base, vo["audio"])) else None

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]

    def cue(self, phrase, after=0):
        i = narration.find(self.toks, phrase, after)
        return self.toks[i]["start"], i


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


# ------------------------------------------------------------------ media
def img(name):
    return G.assets.get(os.path.splitext(name)[0])


def gif_frames(name):
    def load():
        p = os.path.join(G.base, G.b.get("assets_dir", "assets"), name)
        g = Image.open(p)
        frames, durs = [], []
        for i in range(getattr(g, "n_frames", 1)):
            g.seek(i)
            frames.append(g.convert("RGB"))
            durs.append(g.info.get("duration", 70) / 1000)
        return frames, np.cumsum([0] + durs[:-1])
    return G.cache(("gif", name), load)


def static_noise(w, hgt, fi):
    rng = np.random.default_rng(fi)
    n = rng.integers(0, 255, (hgt // 3 + 1, w // 3 + 1), dtype=np.uint8)
    im = Image.fromarray(n).resize((w, hgt), Image.NEAREST).convert("RGB")
    return im


SCREEN_BG = (12, 15, 13)


def terminal_screen(spec, lt, fi, w, hgt):
    """Crisp native terminal text for a device screen. The font is sized so the longest line fits
    inside the safe area; anything still too long word-wraps, and tall transcripts scroll."""
    im = Image.new("RGB", (w, hgt), SCREEN_BG)
    pad_x, pad_y = int(w * 0.09), int(hgt * 0.11)             # tube corners and vignette eat the edges
    safe_w = w - 2 * pad_x
    lines = spec["lines"]
    longest = max(lines, key=lambda l: len(l["t"]))["t"]
    lh = spec.get("lh", 1.55)
    want = spec.get("size", 30)
    # grow to fill the safe area (width and height), capped at max_size; shrink only if a line is too long
    size = spec.get("max_size", 42)
    while size > 16 and (F("mono", size).getlength(longest) > safe_w or len(lines) * size * lh > hgt - 2 * pad_y):
        size -= 1
    if size < want * 0.8:                                    # surfaced by `check`: shorten the line
        SHRINKS.append((longest, size / want))
    rows = max(1, int((hgt - 2 * pad_y) / (size * lh)))
    paper, dim, good = (232, 238, 228), (130, 142, 132), (143, 227, 192)
    tl, t = [], spec.get("delay", 0.15)
    for ln in lines:
        tone, txt = ln.get("tone", "plain"), ln["t"]
        if tone == "cmd" and txt[:2] in ("$ ", "> ", "! "):
            spans, mark = [(txt[:2], good), (txt[2:], paper)], None
        elif tone == "bad":
            spans, mark = [(txt, SCREEN_BG, "mono_medium")], G.signal
        else:
            spans, mark = [(txt, {"dim": dim, "ok": good, "hi": (190, 170, 245)}.get(tone, paper),
                            "mono_medium" if tone in ("ok", "hi") else "mono")], None
        typ = 0.4 if tone == "cmd" else 0
        tl.append({"spans": spans, "t": t, "type": typ, "mark": mark, "mark_dur": 0.2})
        t += ln.get("hold", spec.get("step", 0.45)) + typ
    ui.terminal(im, (pad_x, pad_y), tl, lt, size, lh, paper, fi, max_lines=rows, max_width=safe_w)
    return im


def media(spec, lt, fi, w, hgt):
    """Render a media spec into a w×h RGB image at local time lt."""
    kind = spec.get("kind") or ("gif" if spec.get("src", "").endswith(".gif") else "image")
    if kind == "static":
        return static_noise(w, hgt, fi)
    if kind == "terminal":
        return terminal_screen(spec, lt, fi, w, hgt)
    if kind == "gif":
        frames, starts = gif_frames(spec["src"])
        f0, f1 = spec.get("frames", [0, len(frames) - 1])
        t0 = starts[f0] + lt * spec.get("speed", 1.0)
        k = int(np.searchsorted(starts, t0, side="right") - 1)
        im = frames[min(max(k, f0), f1)]
    else:
        im = img(spec["src"]).convert("RGB")
    if spec.get("crop"):
        x0, y0, x1, y1 = spec["crop"]
        im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
    z = lerp(1.0, spec.get("zoom", 1.06), min(1, lt / 4))           # slow Ken Burns
    return cover(im, w, hgt, z, *spec.get("focus", [0.5, 0.5]))


# ------------------------------------------------------------------ objects
def background(kind, lt):
    if kind == "hills":
        im = cover(img("hills").convert("RGB"), G.W, G.H, lerp(1.04, 1.0, min(1, lt / 3)), 0.5, 0.5)
        # lower third out of focus, like a shallow depth of field
        blur = im.filter(ImageFilter.GaussianBlur(10))
        m = Image.linear_gradient("L").resize((G.W, G.H)).point(lambda v: 0 if v < 170 else min(255, (v - 170) * 4))
        im.paste(blur, (0, 0), m)
        return im
    return Image.new("RGB", (G.W, G.H), G.bg)


def device_parts(name="crt"):
    """Key a device asset (CRT TV, retro computer…): green screen → transparent; returns (RGBA, screen box)."""
    def build():
        tv = img(name).convert("RGBA")
        a = np.asarray(tv).astype(np.int16)
        r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
        green = (g > 120) & (g > r + 40) & (g > b + 40)
        ys, xs = np.where(green)
        box = (xs.min(), ys.min(), xs.max(), ys.max())
        inside = np.zeros_like(green)
        inside[box[1]:box[3] + 1, box[0]:box[2] + 1] = True
        hole = inside & ((al < 200) | green)                        # green screen + any transparent hole in it
        out = a.copy()
        out[..., 3] = np.where(hole, 0, al)
        spill = (~hole) & (g > r + 25) & (g > b + 25) & inside      # despill the screen edge
        out[..., 1] = np.where(spill, (r + b) // 2, g)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8)), box
    return G.cache(("device", name), build)


def draw_tv(im, spec, lt, fi, cx, cy, width, pop=1.0, device="crt"):
    tv, (x0, y0, x1, y1) = device_parts(device)
    s = width / tv.width * lerp(0.92, 1.0, pop)
    tvs = tv.resize((int(tv.width * s), int(tv.height * s)), Image.LANCZOS)
    ox, oy = int(cx - tvs.width / 2), int(cy - tvs.height / 2)
    sx0, sy0, sx1, sy1 = [int(v * s) for v in (x0, y0, x1, y1)]
    scr = media(spec, lt, fi, sx1 - sx0 + 4, sy1 - sy0 + 4)
    a = np.asarray(scr, np.float32)
    a[::3] *= 0.82                                                  # scanlines
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    v = ((xx / a.shape[1] - 0.5) ** 2 + (yy / a.shape[0] - 0.5) ** 2) ** 0.5
    a *= np.clip(1.12 - v * 0.55, 0, 1)[..., None]                  # gentle tube vignette (edges stay readable)
    im.paste(Image.fromarray(a.clip(0, 255).astype(np.uint8)), (ox + sx0 - 2, oy + sy0 - 2))
    im.paste(tvs, (ox, oy), tvs)
    return (ox + sx0, oy + sy0, ox + sx1, oy + sy1)


def draw_window(im, spec, lt, fi, cx, cy, width, pop=1.0, title=""):
    """XP-style window: blue gradient title bar, square close button, content inset."""
    w = int(width * lerp(0.94, 1.0, pop))
    hgt = int(w * spec.get("aspect", 0.62))
    x0, y0 = int(cx - w / 2), int(cy - hgt / 2)
    d = ImageDraw.Draw(im)
    bar = 34
    top = Image.linear_gradient("L").rotate(90).resize((w, bar))
    grad = Image.merge("RGB", [top.point(lambda v: int(lerp(10, 70, v / 255))), top.point(lambda v: int(lerp(90, 150, v / 255))),
                               top.point(lambda v: int(lerp(215, 245, v / 255)))])
    d.rectangle((x0 - 3, y0 - 3, x0 + w + 3, y0 + hgt + 3), fill=(40, 105, 220))
    im.paste(grad, (x0, y0))
    d.rectangle((x0 + w - 30, y0 + 6, x0 + w - 8, y0 + 28), fill=(220, 70, 40), outline=(255, 255, 255))
    d.line((x0 + w - 25, y0 + 11, x0 + w - 13, y0 + 23), fill=(255, 255, 255), width=3)
    d.line((x0 + w - 13, y0 + 11, x0 + w - 25, y0 + 23), fill=(255, 255, 255), width=3)
    if title:
        text(d, (x0 + 12, y0 + bar / 2), title, F("sans_medium", 17), (255, 255, 255), 0, "lm", max_w=w - 60)
    im.paste(media(spec, lt, fi, w, hgt - bar), (x0, y0 + bar))
    return (x0, y0 + bar, x0 + w, y0 + hgt)


def starburst(im, cx, cy, r, col, rot, spikes=16, inner=0.52):
    pts = []
    for k in range(spikes * 2):
        a = rot + k * math.pi / spikes
        rr = r if k % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=col)


def card(spec, w):
    """Dark content card (file / terminal / repo). No pills: meta is typeset text."""
    pad, lh = 34, 44
    fb, fm = F("mono", 25), F("mono_medium", 25)
    lines = spec.get("lines", [])
    hgt = pad * 2 + 70 + lh * len(lines)
    im = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ui.rrect(d, (0, 0, w - 1, hgt - 1), 22, fill=G.card + (255,), outline=(44, 44, 48, 255))
    if spec.get("logo"):
        lg = img("logo").resize((40, 40), Image.LANCZOS)
        im.paste(lg, (pad, pad - 4), lg)
        tx = pad + 54
    else:
        tx = pad
    text(d, (tx, pad + 16), spec.get("title", ""), F("sans_medium", 30), G.paper, -0.5, "lm", max_w=w - tx - pad - 40)
    if spec.get("meta"):
        text(d, (w - pad, pad + 16), spec["meta"], F("pixel", 22), (150, 150, 156), 0, "rm", max_w=w * 0.4)
    y = pad + 70
    for ln in lines:
        t = ln["t"]
        f = fm if ln.get("mark") or ln.get("strong") else fb
        tw = fit(t, f, w - pad * 2).getlength(t)
        if ln.get("mark"):
            ui.marker(d, (pad - 8, y - 6, pad + tw + 8, y + 34), G.signal + (255,), 1.0)
            text(d, (pad, y), t, f, G.ink, 0, "la", max_w=w - pad * 2)
        else:
            col = {"good": (143, 227, 192), "dim": (150, 150, 156), "hi": (190, 170, 245)}.get(ln.get("tone"), G.paper)
            text(d, (pad, y), t, f, col, 0, "la", max_w=w - pad * 2)
        y += lh
    return im


def overlay_word(im, s, style, cy, pv):
    """Pixel-type word laid over media: 'inverse' = white on a black band, 'cyan' = bare cyan."""
    f = F("pixel", 132)
    if style == "inverse":
        m = Image.new("L", im.size, 0)
        text(ImageDraw.Draw(m), (G.W / 2, cy), s, f, 255, 0, "mm", max_w=G.W - 120)
        bb = m.getbbox()
        if bb and pv > 0:
            ImageDraw.Draw(im).rectangle((bb[0] - 18, bb[1] - 14, bb[0] + (bb[2] - bb[0] + 36) * min(1, pv * 1.4) - 18, bb[3] + 14), fill=G.ink)
        ui.rise(im, (G.W / 2, cy), s, f, G.paper, pv, 0, "mm", max_w=G.W - 120)
    else:
        ui.rise(im, (G.W / 2, cy), s, f, G.cyan, pv, 0, "mm", max_w=G.W - 120)


def big_word(im, s, lt, pv, photo=None, stars=False):
    f = F("pixel", G.b.get("word_size", 132))
    cy = G.H * 0.45
    if photo:
        ph = cover(img(photo).convert("RGB"), int(G.W * 0.24), int(G.W * 0.2))
        fw = fit(s, f, G.W * 0.62)
        tw = fw.getlength(s)
        total = tw + 30 + ph.width
        x = (G.W - total) / 2
        ui.rise(im, (x, cy), s, fw, G.word, pv, 0, "lm")
        if pv > 0.3:
            im.paste(ph, (int(x + tw + 30), int(cy - ph.height / 2)))
        return
    ui.rise(im, (G.W / 2, cy), s, f, G.word, pv, 0, "mm", max_w=G.W - 140)
    if stars and pv > 0.5:
        fw = fit(s, f, G.W - 140)
        tw = fw.getlength(s)
        rot = lt * 0.8
        starburst(im, G.W / 2 - tw / 2 - 6, cy - fw.size * 0.42, 22, G.navy, rot, 10, 0.45)
        starburst(im, G.W / 2 + tw / 2 + 4, cy + fw.size * 0.34, 24, G.navy, -rot, 10, 0.45)


def brand_icon(slug, size):
    path = os.path.join(G.base, G.b.get("assets_dir", "assets"), "icons", slug + ".svg")
    ic = icon(path, size)
    return icon(path, size, G.ink) if is_light_mark(ic) else ic


def draw_icons(im, beat, lt):
    """Named marks land large on their cues (with a pixel caption); the rest rain in as a grid behind."""
    lead = beat["lead"]
    n = len(lead)
    size = int(G.W * 0.17)
    gap = int(G.W * 0.07)
    total = n * size + (n - 1) * gap
    rest = beat.get("rest", [])
    tr = cue_time(beat, "rest_at", 1e9, beat) if rest else 1e9
    if lt >= tr:                                             # the rest: two rows across the top, faded behind
        per = -(-len(rest) // 2)
        rs = int(G.W * 0.075)
        pitch = min(G.W * 0.105, (G.W - 120) / per)
        x0 = (G.W - (per - 1) * pitch) / 2
        for k, slug in enumerate(rest):
            t0 = tr + k * 0.04
            if lt < t0:
                continue
            p = ease_out(min(1, (lt - t0) / 0.2))
            r, c = divmod(k, per)
            cx, cy = x0 + c * pitch + (pitch / 2 if r else 0), G.H * (0.09 + r * 0.11)
            ic = brand_icon(slug, rs)
            a = np.asarray(ic).copy()
            a[..., 3] = (a[..., 3] * 0.55 * p).astype(np.uint8)
            m = Image.fromarray(a)
            im.paste(m, (int(cx - rs / 2), int(cy - rs / 2 + (1 - p) * 16)), m)
    for k, it in enumerate(lead):
        t0 = cue_time(it, "at", k * 0.4, beat)
        if lt < t0:
            continue
        p = ease_out(min(1, (lt - t0) / 0.25))
        x = int((G.W - total) / 2 + k * (size + gap))
        y = int(G.H * 0.42 - size / 2 + (1 - p) * 40)
        ic = brand_icon(it["slug"], size)
        if p < 1:
            ic = ic.resize((max(1, int(size * lerp(0.7, 1, p))),) * 2, Image.LANCZOS)
        im.paste(ic, (x + (size - ic.width) // 2, y + (size - ic.height) // 2), ic)
        text(ImageDraw.Draw(im), (x + size / 2, y + size + 34), it.get("label", it["slug"]), F("pixel", 22), G.word, 0, "mm",
             max_w=size + gap - 10)


# ------------------------------------------------------------------ beats
def cue_time(spec, key="at", default=0.0, beat=None):
    """Local time (from the beat start) at which spec[key]'s cue phrase is spoken; searched from the beat's cue on."""
    beat = beat or spec
    if key not in spec:
        return default
    t, _ = G.cue(spec[key], beat["_tok"])
    return max(0.0, t - beat["_t0"])


def render_beat(beat, c):
    lt, fi = c.lt, c.fi
    im = background(beat.get("bg", "plain"), lt)
    kind = beat["type"]
    pop = ease_out(min(1, lt / 0.25))
    if kind == "tv":
        dev = beat.get("device", "crt")
        draw_tv(im, beat["media"], lt, fi, G.W / 2, G.H * beat.get("y", 0.4 if dev == "crt" else 0.42),
                G.W * beat.get("width", 0.64 if dev == "crt" else 0.56), pop, dev)
    elif kind == "window":
        draw_window(im, beat["media"], lt, fi, G.W / 2, G.H * beat.get("y", 0.42), G.W * beat.get("width", 0.74), pop,
                    beat.get("title", ""))
    elif kind == "cards":
        n = len(beat["cards"])
        for k, cs in enumerate(beat["cards"]):
            t0 = cue_time(cs, "at", 0.0, beat) if "at" in cs else k * 0.5
            if lt < t0:
                continue
            p = ease_out(min(1, (lt - t0) / 0.22))
            cw = int(G.W * beat.get("width", 0.72))
            cim = card(cs, cw)
            s = lerp(0.9, 1.0, p)
            cim = cim.resize((int(cim.width * s), int(cim.height * s)), Image.LANCZOS)
            dx = [0, -46, 40, -24, 30][k % 5]
            dy = [-60, -10, 40, 80, 120][k % 5] * beat.get("spread", 1.0)
            x = int(G.W / 2 - cim.width / 2 + dx)
            y = int(G.H * 0.42 - cim.height / 2 + dy - (n - 1) * 20)
            im.paste(cim, (x, y), cim)
    elif kind == "word":
        big_word(im, beat["text"], lt, ease_out(min(1, max(0, lt - cue_time(beat, "word_at")) / 0.3)),
                 beat.get("photo"), beat.get("stars"))
    elif kind == "burst":
        r = G.W * 0.2
        cx, cy = G.W * 0.3, G.H * 0.45
        rs = r * lerp(0.6, 1.0, pop)
        starburst(im, cx, cy, rs, G.navy, lt * 0.25)
        lg = img(beat.get("media", "logo")).resize((int(rs * 0.95), int(rs * 0.95)), Image.LANCZOS)
        im.paste(lg, (int(cx - lg.width / 2), int(cy - lg.height / 2)), lg)
        s = beat.get("text", "")
        tp = ease_out(min(1, max(0, lt - cue_time(beat, "word_at", 0.25)) / 0.3))
        ui.rise(im, (G.W * 0.56, cy), s, F("pixel", 99), G.word, tp, 0, "lm", max_w=G.W * 0.4)
    elif kind == "collage":
        items = beat["media"]
        slots = [(0.3, 0.36, 0.34), (0.64, 0.3, 0.3), (0.5, 0.52, 0.36), (0.22, 0.6, 0.28), (0.74, 0.58, 0.3)]
        for k, spec in enumerate(items):
            t0 = k * beat.get("step", 0.45)
            if lt < t0:
                continue
            p = ease_out(min(1, (lt - t0) / 0.2))
            x, y, sw = slots[k % len(slots)]
            w = int(G.W * sw * lerp(0.85, 1.0, p))
            ph = media(spec, lt - t0, fi, w, int(w * 0.78))
            im.paste(ph, (int(G.W * x - w / 2), int(G.H * y - w * 0.39)))
    elif kind == "icons":
        draw_icons(im, beat, lt)
    elif kind == "end":
        lg = img("logo").resize((220, 220), Image.LANCZOS)
        lp = ease_out(min(1, lt / 0.4))
        im.paste(lg, (int(G.W / 2 - 110), int(G.H * 0.3 - 110 + (1 - lp) * 30)), lg)
        ui.rise(im, (G.W / 2, G.H * 0.52), beat.get("text", ""), F("pixel", 110), G.word, ease_out(min(1, max(0, lt - 0.3) / 0.3)), 0, "mm",
                max_w=G.W - 160)
        ui.rise(im, (G.W / 2, G.H * 0.64), beat.get("sub", ""), F("pixel", 33), G.word, ease_out(min(1, max(0, lt - 0.7) / 0.3)), 0, "mm",
                max_w=G.W - 160)
    # overlays (keyword over the media)
    for ov in beat.get("overlays", []):
        t0 = cue_time(ov, "at", 0.0, beat) if "at" in ov else 0.0
        if lt >= t0:
            overlay_word(im, ov["text"], ov.get("style", "inverse"), G.H * ov.get("y", 0.42), ease_out(min(1, (lt - t0) / 0.25)))
    if kind == "end" and lt > c.dur - G.b.get("black_tail", 0.6):
        return np.zeros((G.H, G.W, 3), np.uint8)
    subtitles(im, c.t)
    return arr(im)


def subtitles(im, t):
    """Small pixel subtitle. Over busy footage it gets a soft halo in the paper colour (a glow, not a box)."""
    for s, e, txt in G.subs:
        if s <= t < e:
            f = F("pixel", G.b.get("subtitle_size", 33))
            xy = (G.W / 2, G.H * 0.87)
            m = Image.new("L", im.size, 0)
            text(ImageDraw.Draw(m), xy, txt, f, 255, 0, "mm", max_w=G.W - 160)
            halo = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(min(255, v * 1.6) * 0.8))
            im.paste(Image.new("RGB", im.size, G.bg), (0, 0), halo)
            text(ImageDraw.Draw(im), xy, txt, f, G.word, 0, "mm", max_w=G.W - 160)
            break


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    beats, tok = [], 0
    for k, b in enumerate(brief["beats"]):
        t0, tok = G.cue(b["at"], tok)
        b["_t0"], b["_tok"] = (0.0 if k == 0 else t0 - brief.get("lead", 0.08)), tok
        beats.append(b)
    end = G.vo_dur + brief.get("tail", 1.2)
    scenes = []
    for k, b in enumerate(beats):
        t1 = beats[k + 1]["_t0"] if k + 1 < len(beats) else end
        prev_bg = beats[k - 1].get("bg", "plain") if k else None
        tr = None
        if k and (b.get("tr") == "pixel" or (b.get("tr") != "cut" and prev_bg != b.get("bg", "plain"))):
            tr = Mosaic(0.32, 24, 24, 7 + k, (G.bg,))
        scenes.append(Scene(f"{k:02d}-{b['type']}", t1 - b["_t0"], (lambda bb: lambda c: render_beat(bb, c))(b), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["voice", "assets", "icons", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    brief = json.load(open(a.brief))
    if a.cmd == "voice":
        vo = brief["vo"]
        script = open(os.path.join(base, vo["script"])).read().strip()
        wav = narration.tts(script, os.path.join(base, vo["audio"]), voice=vo.get("voice", "ash"), instructions=vo.get("instructions"))
        json.dump(narration.transcribe_words(wav, prompt=script), open(os.path.join(base, vo["words"]), "w"), indent=1)
        print("voice ok:", wav)
        return
    if a.cmd == "icons":                                    # brand marks from thesvg.org, with licence metadata
        slugs = []
        for bt in brief["beats"]:
            if bt["type"] == "icons":
                slugs += [x["slug"] for x in bt["lead"]] + bt.get("rest", [])
        for m in fetch_icons(slugs, os.path.join(base, brief.get("assets_dir", "assets"), "icons")):
            print(m)
        return
    if a.cmd == "assets":
        specs = {k: v for k, v in brief.get("assets", {}).items() if "prompt" in v}
        for m in generate_images(specs, os.path.join(base, brief.get("assets_dir", "assets")), names=a.args or None, force=a.force):
            print(m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear()
        SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep:
            print("  ✗", r)
        for r in overflow_report(warn=True):
            print("  ! warning:", r)
        print(f"voice: {'yes' if G.audio else 'MISSING (run voice)'}; duration {tl.duration:.2f}s, {len(tl.scenes)} beats")
        for s, st in zip(tl.scenes, tl.starts):
            print(f"  {st:6.2f}s  {s.dur:5.2f}s  {s.name}")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["5"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 8, 6, 200))
    else:
        print(tl.render(a.out or os.path.join(out, "explainer.mp4"), G.audio))


if __name__ == "__main__":
    main()
