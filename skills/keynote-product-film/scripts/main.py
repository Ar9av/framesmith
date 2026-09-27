#!/usr/bin/env python3
"""keynote-product-film: a 16:9 keynote-style product film (music-driven, no voiceover).

Text carries the story: centred sentences whose words blur in one by one, with inline line icons
and app tiles; charcoal and white grounds alternate; real product UI (prompt bar, agent session,
permission prompts, step lists, a benchmark chart, a masked field) does the proving.

    python3 main.py check|still|sheet|render --brief brief.json [times...] [--audio music.m4a]
    python3 main.py icons --brief brief.json      # fetch brand icons (thesvg) + line icons (lucide)
"""
import argparse, json, math, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import (Dissolve, Mosaic, Scene, Timeline, cover, ease_in_out, ease_out, hex2rgb, lerp,
                        overflow_report, scramble, text, typed)
from framesmith.media import fetch_icons, generate_images, icon, rasterize_svg
from framesmith.typography import F, OVERFLOWS, SHRINKS
from framesmith import ui

G = None
LUCIDE = "https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{}.svg"


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.dark = c("dark", (38, 38, 38))
        self.light = c("light", (255, 255, 255))
        self.ink = c("ink", (18, 18, 19))
        self.muted_d = c("muted_dark", (120, 120, 126))
        self.muted_l = c("muted_light", (161, 161, 170))
        self.accent = c("accent", (168, 213, 186))
        self.wash = [hex2rgb(x) for x in brief.get("wash", ["#FDFBF7", "#FEEEDC", "#DCF5FC", "#FEE3DF"])]
        self.W, self.H = brief.get("size", [1920, 1080])
        self.assets = os.path.join(base, brief.get("assets_dir", "assets"))
        self._c = {}

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def ground(kind):
    return {"dark": G.dark, "light": G.light, "black": (0, 0, 0)}.get(kind, G.light)


def is_dark(kind):
    return kind in ("dark", "black")


def fg(kind):
    return G.light if is_dark(kind) else G.ink


# ------------------------------------------------------------------ icons
def icon_img(ref, size, color=None):
    """'lucide:globe' (line icon, tinted) or 'brand:slug' (thesvg mark; tinted only if a colour is given)."""
    kind, name = ref.split(":", 1)
    size = int(size)
    if kind == "lucide":
        return icon(os.path.join(G.assets, "lucide", name + ".svg"), size, tuple(color) if color else G.ink)
    path = os.path.join(G.assets, "icons", name + ".svg")
    return icon(path, size, tuple(color)) if color is not None else icon(path, size)


def logo(size):
    size = int(size)
    return G.cache(("logo", size), lambda: Image.open(os.path.join(G.assets, "logo.png")).convert("RGBA").resize((size, size), Image.LANCZOS))


def tile(ref, s, bg=(255, 255, 255)):
    """App-icon tile: rounded square with a soft shadow and the mark inside."""
    def build():
        pad = int(s * 0.25)
        im = Image.new("RGBA", (s + pad * 2, s + pad * 2), (0, 0, 0, 0))
        sh = Image.new("L", im.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + s * 0.06, pad + s, pad + s * 1.06), s * 0.23, fill=120)
        im.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(s * 0.08)))
        body = Image.new("L", im.size, 0)
        ImageDraw.Draw(body).rounded_rectangle((pad, pad, pad + s, pad + s), s * 0.23, fill=255)
        im.paste(bg + (255,), (0, 0), body)
        mark = logo(s * 0.8) if ref == "logo" else icon_img(ref, s * 0.6)
        im.alpha_composite(mark, (pad + (s - mark.width) // 2, pad + (s - mark.height) // 2))
        return im
    return G.cache(("tile", ref, s), build)


# ------------------------------------------------------------------ kinetic sentence
TOK = re.compile(r"\{[^}]+\}|\S+")


def tokens_of(line):
    return TOK.findall(line)


def token_size(tok, f):
    if tok.startswith("{icon:"):
        s = int(f.size * 0.82)
        return s, s
    if tok.startswith("{tiles:"):
        n = len(tok[7:-1].split(","))
        s = int(f.size * 1.35)
        return n * s + (n - 1) * int(s * 0.18), s
    t = tok[1:] if tok.startswith("_") else tok
    return f.getlength(t), f.size


def draw_token(img, tok, x, baseline, f, color, muted, p):
    """Blur-in: alpha, blur and a small rise all driven by p."""
    if p <= 0:
        return
    w, hgt = token_size(tok, f)
    pad = int(f.size * 0.6)
    layer = Image.new("RGBA", (int(w) + pad * 2, int(f.size * 1.6) + pad * 2), (0, 0, 0, 0))
    top = pad + int(f.size * 0.25)
    if tok.startswith("{icon:"):
        name = tok[6:-1]
        ic = icon_img(name if ":" in name else "lucide:" + name, hgt, color)
        layer.alpha_composite(ic, (pad, top + int(f.size * 0.13)))
    elif tok.startswith("{tiles:"):
        s = int(f.size * 1.35)
        tx = pad
        for r in tok[7:-1].split(","):
            tl = tile(r if r == "logo" or ":" in r else "brand:" + r, s)
            layer.alpha_composite(tl, (max(0, int(tx - s * 0.25)), max(0, int(top - s * 0.34))))
            tx += s + int(s * 0.18)
    else:
        t = tok[1:] if tok.startswith("_") else tok
        ImageDraw.Draw(layer).text((pad, top + f.size * 0.95), t, font=f, fill=(muted if tok.startswith("_") else color) + (255,),
                                   anchor="ls")
    if p < 1:
        a = np.asarray(layer).copy()
        a[..., 3] = (a[..., 3] * p).astype(np.uint8)
        layer = Image.fromarray(a).filter(ImageFilter.GaussianBlur((1 - p) * 14))
    img.alpha_composite(layer, (int(x - pad), int(baseline - top - f.size * 0.95 + (1 - p) * 22)))


def line_width(line, f):
    toks = tokens_of(line)
    return sum(token_size(t, f)[0] for t in toks) + f.getlength(" ") * (len(toks) - 1)


def sentence(img, lines, cx, cy, f, color, muted, lt, start=0.1, stagger=0.09, layout="center", line_gap=1.12,
             align=None, max_w=None):
    """Lay out lines of tokens (words, {icon:…}, {tiles:…}, _muted) and blur them in word by word."""
    max_w = max_w or G.W - 220
    widths = [line_width(l, f) for l in lines]
    if max(widths) > max_w:                          # shrink the block uniformly rather than overflow
        k = max_w / max(widths)
        if k < 0.8:
            SHRINKS.append((" / ".join(lines), k))
        f = F("sans_medium", max(24, int(f.size * k)))
        widths = [line_width(l, f) for l in lines]
    lh = f.size * line_gap
    y0 = cy - lh * (len(lines) - 1) / 2
    k = 0
    for li, line in enumerate(lines):
        if layout == "stairs":
            span = G.W - 2 * 240 - max(widths)
            x = 240 + (span * li / max(1, len(lines) - 1) if align is None else align[li] * span)
        else:
            x = cx - widths[li] / 2
        for tk in tokens_of(line):
            p = ease_out(min(1, max(0, (lt - start - k * stagger) / 0.38)))
            draw_token(img, tk, x, y0 + li * lh + f.size * 0.35, f, color, muted, p)
            x += token_size(tk, f)[0] + f.getlength(" ")
            k += 1
    return k


# ------------------------------------------------------------------ UI pieces
def shadowed_box(img, box, r, fill, border=None, shadow=70, blur=26, dy=14):
    x0, y0, x1, y1 = [int(v) for v in box]
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + dy, x1, y1 + dy), r, fill=shadow)
    img.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).rounded_rectangle((x0, y0, x1, y1), r, fill=fill, outline=border, width=2 if border else 0)


def cursor(img, x, y, s=2.4, click=0.0):
    """macOS-style arrow pointer; click in (0,1) draws a fading ring."""
    d = ImageDraw.Draw(img)
    if 0 < click < 1:
        r = 14 + 26 * click
        d.ellipse((x - r, y - r, x + r, y + r), outline=(150, 150, 150), width=max(1, int(4 * (1 - click))))
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.6), (9.6, 18.6), (6.8, 12.2), (12.4, 12.2)]
    P = [(x + px * s, y + py * s) for px, py in pts]
    d.polygon(P, fill=(255, 255, 255))
    d.line(P + [P[0]], fill=(0, 0, 0), width=2)


def ibeam(img, x, y, hgt, col=(20, 20, 20)):
    d = ImageDraw.Draw(img)
    d.line((x, y, x, y + hgt), fill=col, width=3)
    d.line((x - 7, y, x + 7, y), fill=col, width=3)
    d.line((x - 7, y + hgt, x + 7, y + hgt), fill=col, width=3)


def elbow(d, x, y, col, s):
    """⎿ drawn as vectors (not in the bundled fonts)."""
    w = max(2, int(s * 0.09))
    d.line((x, y - s * 0.55, x, y), fill=col, width=w)
    d.line((x, y, x + s * 0.55, y), fill=col, width=w)


def chevron(d, x, y, col, s):
    """❯ drawn as vectors."""
    d.line((x, y - s * 0.3, x + s * 0.3, y, x, y + s * 0.3), fill=col, width=max(2, int(s * 0.1)), joint="curve")


def prompt_bar(img, box, textv, placeholder, dark, caret_on, extras=True):
    x0, y0, x1, y1 = box
    fill = (46, 46, 48) if dark else (255, 255, 255)
    border = (64, 64, 68) if dark else (228, 228, 231)
    shadowed_box(img, box, 22, fill, border, 90 if dark else 45)
    d = ImageDraw.Draw(img)
    f = F("sans", 34)
    mid = y0 + (y1 - y0) * (0.4 if extras else 0.5)
    tcol = (240, 240, 240) if dark else (24, 24, 27)
    budget = x1 - x0 - 330
    if textv:
        text(d, (x0 + 34, mid), textv, f, tcol, 0, "lm", max_w=budget)
        cx = x0 + 34 + min(f.getlength(textv), budget)
    else:
        text(d, (x0 + 34, mid), placeholder, f, (140, 140, 146), 0, "lm", max_w=budget)
        cx = x0 + 34
    if caret_on:
        d.rectangle((cx + 3, mid - 20, cx + 5, mid + 20), fill=tcol)
    if extras:
        sf, sc = F("sans", 22), (130, 130, 136)
        text(d, (x1 - 30, mid), "Enter to run", sf, sc, 0, "rm")
        text(d, (x0 + 34, y1 - 30), "claude-code  ·  " + G.b.get("model", "Opus 5.5"), sf, sc, 0, "lm")
        text(d, (x1 - 30, y1 - 30), "protected by Prismor", sf, sc, 0, "rm")
    return cx, mid


CC = {"agent": (217, 119, 87), "command": (161, 161, 170), "warden": (168, 106, 30), "blocked": (107, 79, 160),
      "success": (46, 125, 79), "reason": (113, 113, 122), "user": (24, 24, 27), "text": (39, 39, 42)}


def wrap(spans, max_w):
    """[(text, font, colour)] → rows, word-wrapped at max_w (ligatures off for code)."""
    rows, row, w = [], [], 0.0
    for txt, f, col in spans:
        for word in re.split(r"(\s+)", txt):
            if not word:
                continue
            ww = f.getlength(word, features=ui.CODE_FEATURES)
            if w + ww > max_w and row and not word.isspace():
                rows.append(row)
                row, w = [], 0.0
            if word.isspace() and not row:
                continue
            row.append((word, f, col))
            w += ww
    if row:
        rows.append(row)
    return rows


def session_panel(img, box, lines, lt, cwd="~/acme-web", model="Opus 5.5", s=1.0):
    """Claude Code session, after Prismor's site hero component: notched badge, then timed lines."""
    x0, y0, x1, y1 = [int(v) for v in box]
    shadowed_box(img, box, 18, (255, 255, 255), (231, 231, 234), 60)
    d = ImageDraw.Draw(img)
    fs, fm, fb = F("sans", 27 * s), F("mono", 25 * s), F("sans_medium", 27 * s)
    lh = 40 * s
    bx0, by0 = x0 + 36 * s, y0 + 40 * s
    bx1, by1 = bx0 + 470 * s, by0 + 118 * s
    d.rounded_rectangle((bx0, by0, bx1, by1), 14 * s, outline=(236, 180, 160), width=2)
    lab, lf = "Claude Code", F("sans", 22 * s)
    d.rectangle((bx0 + 14 * s, by0 - 14 * s, bx0 + 28 * s + lf.getlength(lab), by0 + 12 * s), fill=(255, 255, 255))
    d.text((bx0 + 20 * s, by0), lab, font=lf, fill=CC["agent"], anchor="lm")
    ps = 9 * s
    for r, row in enumerate([[0, 1, 1, 1, 0], [1, 1, 1, 1, 1], [0, 1, 0, 1, 0]]):
        for c, v in enumerate(row):
            if v:
                d.rectangle((bx0 + 24 * s + c * ps, by0 + 26 * s + r * ps, bx0 + 24 * s + (c + 1) * ps - 1,
                             by0 + 26 * s + (r + 1) * ps - 1), fill=CC["agent"])
    d.text((bx0 + 24 * s, by0 + 88 * s), f"{model}  ·  {cwd}", font=F("sans", 21 * s), fill=(113, 113, 122), anchor="lm")
    tx0, ty0 = x0 + 44 * s, by1 + 36 * s
    maxw = x1 - x0 - 150 * s
    rendered = []
    for ln in lines:
        if lt < ln["t"]:
            break
        typ, txt = ln["type"], ln["text"]
        if typ == "user":
            spans, lead = [(typed(txt, (lt - ln["t"]) / max(0.01, ln.get("type_s", 0.9))), fb, CC["user"])], "chev"
        elif typ == "command":
            cmd = txt[2:] if txt.startswith("$ ") else txt
            spans, lead = [("Bash(", fs, CC["text"]), (cmd, fm, (113, 113, 122)), (")", fs, CC["text"])], "dotc"
        elif typ in ("reason", "blocked"):
            spans, lead = [(txt, fb if typ == "blocked" else fs, CC[typ])], "elbow"
        elif typ == "success":
            spans, lead = [(txt, fb, CC["success"])], "check"
        elif typ == "warden":
            spans, lead = [(txt, fb, CC["warden"])], "dotw"
        else:
            spans, lead = [(txt, fs, CC["text"])], "dota"
        indent = 40 * s if lead == "elbow" else 0
        rendered.append((ln, lead, indent, wrap(spans, maxw - indent)))
    total = sum(len(r[3]) * lh + 10 * s for r in rendered)
    avail = y1 - ty0 - 30 * s
    y = ty0 - max(0, total - avail)                      # scroll so the newest line stays in view
    for ln, lead, indent, rows in rendered:
        p = ease_out(min(1, (lt - ln["t"]) / 0.25))
        yy = y + (1 - p) * 14
        ly = yy + lh * 0.5
        lc = {"chev": (161, 161, 170), "dotc": CC["command"], "elbow": CC.get(ln["type"], CC["reason"]),
              "check": CC["success"], "dotw": CC["warden"], "dota": CC["agent"]}[lead]
        if ly >= ty0:
            if lead == "chev":
                chevron(d, tx0, ly, lc, 26 * s)
            elif lead == "elbow":
                elbow(d, tx0 + 12 * s, ly, lc, 26 * s)
            elif lead == "check":
                d.text((tx0, ly), "✓", font=fb, fill=lc, anchor="lm")
            else:
                d.text((tx0, ly), "●", font=F("sans", 20 * s), fill=lc, anchor="lm")
        for ri, row in enumerate(rows):
            ry = yy + ri * lh + lh * 0.5
            if ry < ty0:
                continue
            x = tx0 + 36 * s + indent
            for word, f, col in row:
                d.text((x, ry), word, font=f, fill=tuple(int(lerp(255, v, p)) for v in col), anchor="lm", features=ui.CODE_FEATURES)
                x += f.getlength(word, features=ui.CODE_FEATURES)
        y += len(rows) * lh + 10 * s


def permission_box(img, box, command, desc, sel, alpha=255, back=False):
    """Claude Code's permission prompt: text UI, options chosen with a chevron (no buttons).
    back=True draws an opaque card with dimmed content, so stacked copies never show text through each other."""
    x0, y0, x1, y1 = [int(v) for v in box]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x1, y1), 14, fill=(30, 30, 31, 255 if back else alpha), outline=(110, 110, 116, alpha), width=2)
    if back:                                                  # stacked copy: card edge only, no text
        img.alpha_composite(layer)
        return
    fb, fs, fm = F("sans_medium", 30), F("sans", 28), F("mono", 26)
    d.text((x0 + 36, y0 + 44), "Bash command", font=fb, fill=(217, 119, 87, alpha), anchor="lm")
    text(d, (x0 + 60, y0 + 100), command, fm, (235, 235, 235, alpha), 0, "lm", max_w=x1 - x0 - 110)
    text(d, (x0 + 60, y0 + 142), desc, fs, (150, 150, 156, alpha), 0, "lm", max_w=x1 - x0 - 110)
    d.text((x0 + 36, y0 + 205), "Do you want to proceed?", font=fs, fill=(235, 235, 235, alpha), anchor="lm")
    for i, o in enumerate(["Yes", "Yes, and don't ask again for this command", "No, and tell Claude what to do differently"]):
        y = y0 + 258 + i * 46
        col = (217, 119, 87, alpha) if i == sel else (200, 200, 204, alpha)
        if i == sel:
            chevron(d, x0 + 42, y, col, 26)
        d.text((x0 + 76, y), str(i + 1), font=fs, fill=col if i == sel else (130, 130, 136, alpha), anchor="lm")
        text(d, (x0 + 110, y), o, fs, col, 0, "lm", max_w=x1 - x0 - 150)
    img.alpha_composite(layer)


def wash_bg(lt):
    """Prismor's hero wash: peach, ice and dusty rose drifting over the off-white field."""
    w, h = G.W // 8, G.H // 8
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.zeros((h, w, 3), np.float32) + np.array(G.wash[0], np.float32)
    for bx, by, r, col in [(0.78 + 0.05 * math.sin(lt * 0.6), 0.3, 0.55, G.wash[1]),
                           (0.2, 0.72 + 0.04 * math.cos(lt * 0.5), 0.5, G.wash[2]),
                           (0.55 + 0.06 * math.cos(lt * 0.4), 0.5, 0.35, G.wash[3])]:
        dd = np.sqrt(((xx / w - bx) / r) ** 2 + ((yy / h - by) / (r * 0.8)) ** 2)
        a = np.clip(1 - dd, 0, 1)[..., None] ** 1.5
        base = base * (1 - a) + np.array(col, np.float32) * a
    return Image.fromarray(base.astype(np.uint8)).resize((G.W, G.H), Image.BICUBIC).convert("RGBA")


def asset_png(name):
    return G.cache(("png", name), lambda: Image.open(os.path.join(G.assets, name + ".png")).convert("RGBA"))


def keyed(name):
    """A gpt-image-2 device PNG with a flat #00FF00 screen: returns (RGBA with the screen cut out, screen box)."""
    def build():
        im = asset_png(name)
        a = np.asarray(im).astype(np.int16)
        r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
        green = (g > 110) & (g > r + 40) & (g > b + 40) & (al > 0)
        ys, xs = np.where(green)
        box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        out = a.copy()
        out[..., 3] = np.where(green, 0, al)
        edge = (~green) & (g > r + 20) & (g > b + 20)            # despill the bezel edge
        out[..., 1] = np.where(edge, (r + b) // 2, g)
        return Image.fromarray(out.clip(0, 255).astype(np.uint8)), box
    return G.cache(("keyed", name), build)


def fade(ic, p):
    a = np.asarray(ic).copy()
    a[..., 3] = (a[..., 3] * p).astype(np.uint8)
    return Image.fromarray(a)


# ------------------------------------------------------------------ shots
def shot_sentence(c, s):
    bg = s.get("bg", "dark")
    im = wash_bg(c.lt) if bg == "wash" else Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    f = F("sans_medium", s.get("size", 96))
    cy = c.H * s.get("y", 0.5)
    if s.get("bar"):                                     # a dark input bar that contains the whole text block
        p = ease_out(min(1, c.lt / 0.35))
        bw = max(line_width(l, f) for l in s["lines"]) + 160
        tall = max(token_size(t, f)[1] for l in s["lines"] for t in tokens_of(l))   # tiles are taller than text
        bh = f.size * 1.12 * (len(s["lines"]) - 1) + max(f.size, tall) + 120
        bw = min(bw, c.W - 120) * lerp(0.9, 1, p)
        prompt_bar(im, (c.W / 2 - bw / 2, cy - bh / 2 + f.size * 0.02, c.W / 2 + bw / 2, cy + bh / 2 + f.size * 0.02), "", "", True,
                   False, False)
    if s.get("logo"):
        lp = ease_out(min(1, c.lt / 0.4))
        ls = s.get("logo_size", 180)
        lg = logo(ls)
        if bg == "black":                                  # logo's black half needs a tile to read on pure black
            t = int(ls * 1.08)
            tl = Image.new("RGBA", (t, t), (0, 0, 0, 0))
            ImageDraw.Draw(tl).rounded_rectangle((0, 0, t - 1, t - 1), int(t * 0.23), fill=(26, 26, 28, 255), outline=(62, 62, 66, 255), width=2)
            tl.alpha_composite(lg, ((t - ls) // 2, (t - ls) // 2))
            lg = tl
        lg = fade(lg, lp)
        im.alpha_composite(lg, (int(c.W / 2 - lg.width / 2), int(cy - lg.height - 80 + (1 - lp) * 30)))
    sentence(im, s["lines"], c.W / 2, cy, f, G.ink if bg in ("light", "wash") else G.light,
             G.muted_d if is_dark(bg) else G.muted_l, c.lt, s.get("start", 0.1), s.get("stagger", 0.09),
             s.get("layout", "center"), align=s.get("align"))
    return arr(im)


def shot_permission(c, s):
    im = Image.new("RGBA", (c.W, c.H), G.dark + (255,))
    sentence(im, s["caption"], c.W / 2, 170, F("sans_medium", 80), G.light, G.muted_d, c.lt, 0.05, 0.08)
    n, every = s.get("copies", 1), s.get("every", 0.55)
    w, h = 1080, 400
    for k in range(n):
        t0 = 0.5 + k * every
        if c.lt < t0:
            break
        p = ease_out(min(1, (c.lt - t0) / 0.3))
        x0 = c.W / 2 - w / 2 - (n - 1) * 23 + k * 46
        y0 = 330 - (n - 1) * 19 + k * 38
        last = k == n - 1 or c.lt < t0 + every
        alpha = int(255 * p)
        age = c.lt - t0
        sel = s.get("select", 0) if (k == n - 1 and age > s.get("select_at", 1.0)) else 0
        permission_box(im, (x0, y0 + (1 - p) * 30, x0 + w, y0 + h + (1 - p) * 30), s["command"], s.get("desc", ""), sel, alpha,
                       back=not last)
        if last:
            click_t = s.get("select_at", 1.0) if k == n - 1 else every * 0.7
            clk = (age - click_t) / 0.35 if age > click_t else 0
            opt_y = y0 + 258 + (s.get("select", 0) if k == n - 1 else 0) * 46
            cursor(im, x0 + 330 + (1 - p) * 120, opt_y + 8 + (1 - p) * 90, 2.4, clk)
    return arr(im)


def shot_prompt(c, s):
    dark = s.get("bg") == "dark"
    im = Image.new("RGBA", (c.W, c.H), ground(s.get("bg", "light")) + (255,))
    if s.get("logo_above"):
        im.alpha_composite(fade(logo(90), 0.35), (int(c.W / 2 - 45), int(c.H / 2 - 250)))
    p = ease_out(min(1, c.lt / 0.3))
    w = 1240 * lerp(0.92, 1, p)
    box = (c.W / 2 - w / 2, c.H / 2 - 90, c.W / 2 + w / 2, c.H / 2 + 90)
    t0 = s.get("type_at", 0.5)
    txt = typed(s["typed"], (c.lt - t0) / s.get("type_s", 1.8)) if c.lt > t0 else ""
    cx, mid = prompt_bar(im, box, txt, s.get("placeholder", "Ask your agent anything"), dark, (c.fi // 8) % 2 == 0)
    if c.lt < t0 + 0.4:
        ibeam(im, box[0] + 330 + (1 - p) * 60, mid + 40, 44, (220, 220, 220) if dark else (30, 30, 30))
    return arr(im)


def shot_session(c, s):
    bg = s.get("bg", "light")
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, 118, F("sans_medium", 64), fg(bg), G.muted_d if bg == "dark" else G.muted_l,
                 c.lt, 0.05, 0.07)
    top = 220 if s.get("caption") else 110
    p = ease_out(min(1, c.lt / 0.35))
    w = s.get("width", 1560)
    box = (c.W / 2 - w / 2, top + (1 - p) * 40, c.W / 2 + w / 2, c.H - 70 + (1 - p) * 40)
    session_panel(im, box, s["lines"], c.lt, s.get("cwd", "~/acme-web"), s.get("model", "Opus 5.5"), s.get("scale", 1.35))
    out = im.convert("RGB")
    z = s.get("zoom")
    if z:                                                # slow camera push toward a focus point
        out = cover(out, c.W, c.H, lerp(1.0, z[0], ease_in_out(c.p(0, c.dur))), z[1], z[2])
    return np.asarray(out).copy()


def shot_steps(c, s):
    im = Image.new("RGBA", (c.W, c.H), G.light + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, 150, F("sans_medium", 64), G.ink, G.muted_l, c.lt, 0.05, 0.07)
    d = ImageDraw.Draw(im)
    y0, x0 = 320, 300
    for k, r in enumerate(s["rows"]):
        t0 = r.get("t", 0.4 + k * 0.8)
        if c.lt < t0:
            continue
        p = ease_out(min(1, (c.lt - t0) / 0.35))
        y = y0 + k * 132
        col = {"blocked": CC["blocked"], "success": CC["success"]}.get(r.get("tone"), G.ink)
        d.line((x0 - 90, y - 66, x0 - 90, y), fill=(226, 226, 229), width=3)
        d.line((x0 - 90, y, x0 - 40, y), fill=(226, 226, 229), width=3)
        ic = icon_img(r["icon"], 52, None if r["icon"].startswith("brand:") else col)
        im.alpha_composite(fade(ic, p), (int(x0 - 20), int(y - 26)))
        d = ImageDraw.Draw(im)
        c2 = tuple(int(lerp(255, v, p)) for v in col)
        text(d, (x0 + 60 + (1 - p) * 20, y), r["text"], F("sans_medium", 42), c2, -0.5, "lm", max_w=c.W - x0 - 300)
        if r.get("sub"):
            text(d, (x0 + 60 + (1 - p) * 20, y + 44), r["sub"], F("sans", 28), tuple(int(lerp(255, v, p)) for v in (140, 140, 146)),
                 0, "lm", max_w=c.W - x0 - 300)
    return arr(im)


def shot_chart(c, s):
    im = Image.new("RGBA", (c.W, c.H), G.dark + (255,))
    phases = s["phases"]
    seg = c.dur / len(phases)
    ph = min(len(phases) - 1, int(c.lt / seg))
    lt_ph = c.lt - ph * seg
    cur, prev = phases[ph], phases[max(0, ph - 1)]
    lab_w, bw, rh, gap = 470, 900, 84, 26
    n = len(s["rows"])
    x0 = (c.W - (lab_w + bw + 170)) / 2 + lab_w                  # bars start after the label column
    y0 = (c.H - (n * rh + (n - 1) * gap)) / 2 + 60
    d = ImageDraw.Draw(im)
    text(d, (x0 - lab_w, y0 - 150), cur["title"], F("sans_medium", 54), G.light, -1, "lm", max_w=lab_w + bw + 160)
    text(d, (x0 - lab_w, y0 - 86), s["sub"], F("sans", 30), G.muted_d, 0, "lm", max_w=lab_w + bw + 160)
    for k, row in enumerate(s["rows"]):
        v1 = cur["values"][k]
        v0 = prev["values"][k] if ph else 0
        v = lerp(v0, v1, ease_out(min(1, max(0, (lt_ph - 0.15 - k * 0.08) / 0.6))))
        y = y0 + k * (rh + gap)
        hi = row.get("highlight")
        text(d, (x0 - lab_w, y + rh * 0.36), row["label"], F("sans_medium", 36), G.accent if hi else G.light, 0, "lm", max_w=lab_w - 30)
        if row.get("note"):
            text(d, (x0 - lab_w, y + rh * 0.8), row["note"], F("sans", 24), G.muted_d, 0, "lm", max_w=lab_w - 30)
        d.rounded_rectangle((x0, y, x0 + bw, y + rh), 12, fill=(48, 48, 50))
        wv = max(16, bw * v / 100)
        if hi:
            glow = Image.new("L", im.size, 0)
            ImageDraw.Draw(glow).rounded_rectangle((x0, y, x0 + max(90, wv), y + rh), 12, fill=150)
            im.paste(G.accent, (0, 0), glow.filter(ImageFilter.GaussianBlur(20)))
            d = ImageDraw.Draw(im)
        d.rounded_rectangle((x0, y, x0 + wv, y + rh), 12, fill=G.accent if hi else (86, 86, 90))
        text(d, (x0 + bw + 44, y + rh / 2), f"{v:.0f}%", F("sans_medium", 42), G.accent if hi else G.light, 0, "lm")
    return arr(im)


def shot_ticker(c, s):
    im = Image.new("RGBA", (c.W, c.H), G.dark + (255,))
    d = ImageDraw.Draw(im)
    f = F("sans_medium", 80)
    items, step = s["items"], s.get("every", 0.75)
    pos = max(0.0, (c.lt - 0.35) / step)                 # continuous index of the item in focus
    k = int(pos)
    frac = ease_in_out(min(1, (pos - k) / 0.4))
    focus = min(len(items) - 1, k + frac)
    px = c.W * 0.5 - 30
    pp = ease_out(min(1, c.lt / 0.35))
    text(d, (px, c.H / 2), s["prefix"], f, tuple(int(lerp(v, 255, pp)) for v in G.dark), -1.5, "rm", max_w=c.W * 0.42)
    for j, it in enumerate(items):
        rel = j - focus
        if rel < -0.8 or rel > 3.2:
            continue
        y = c.H / 2 + rel * 100
        on = abs(rel) < 0.5
        dim = max(0.28, 1 - abs(rel) * 0.28)
        col = G.light if on else tuple(int(v * dim) for v in (200, 200, 205))
        x = px + 40
        im.alpha_composite(icon_img("lucide:" + it["icon"], 66, col), (int(x), int(y - 33)))
        text(d, (x + 92, y), it["text"], f, col, -1.5, "lm", max_w=c.W - x - 190)
    return arr(im)


def shot_mask(c, s):
    im = Image.new("RGBA", (c.W, c.H), G.light + (255,))
    sentence(im, s["caption"], c.W / 2, 250, F("sans_medium", 72), G.ink, G.muted_l, c.lt, 0.05, 0.08)
    p = ease_out(min(1, c.lt / 0.35))
    w, h = 1180, 150
    cx = c.W / 2 + (170 if s.get("object") else 0)            # make room for the object on the left
    box = (cx - w / 2, 520 + (1 - p) * 30, cx + w / 2, 520 + h + (1 - p) * 30)
    shadowed_box(im, box, 26, (255, 255, 255), (232, 232, 235), 55)
    d = ImageDraw.Draw(im)
    click = s.get("click_at", 2.2)
    if c.lt < click:
        val, col = typed(s["value"], (c.lt - 0.5) / 1.1), (24, 24, 27)
    else:
        val, col = scramble(s["masked"], ease_out(min(1, (c.lt - click) / 0.6)), 7, c.fi, 5), CC["blocked"]
    ref = max((s["value"], s["masked"]), key=len)
    text(d, (box[0] + 44, (box[1] + box[3]) / 2), val, F("mono", 54), col, 0, "lm", max_w=w - 170, fit_to=ref)
    eye = icon_img("lucide:" + ("eye-off" if c.lt >= click else "eye"), 58, (90, 90, 96))
    ex, ey = box[2] - 100, (box[1] + box[3]) / 2 - 29
    im.alpha_composite(eye, (int(ex), int(ey)))
    mv = ease_in_out(min(1, max(0, (c.lt - 1.2) / (click - 1.2))))
    if c.lt > 1.0:
        cursor(im, lerp(c.W / 2 + 200, ex + 30, mv), lerp(c.H - 200, ey + 36, mv), 2.6,
               (c.lt - click) / 0.4 if c.lt > click else 0)
    if s.get("object"):                                      # gpt-image-2 object: floats, then dissolves at the click
        ob = asset_png(s["object"])
        size = s.get("object_size", 300)
        obj = ob.resize((size, int(ob.height * size / ob.width)), Image.LANCZOS)
        appear = ease_out(min(1, c.lt / 0.5))
        gone = ease_out(min(1, max(0, (c.lt - click) / 0.5)))
        vis = appear * (1 - gone)
        if vis > 0.01:
            obj = obj.rotate(math.sin(c.lt * 1.4) * 5 - 8, expand=True, resample=Image.BICUBIC)
            if gone > 0:
                obj = obj.filter(ImageFilter.GaussianBlur(gone * 16))
            ox, oy = box[0] - obj.width - 30, (box[1] + box[3]) / 2 - obj.height / 2 + math.sin(c.lt * 2) * 10 - gone * 40
            im.alpha_composite(fade(obj, vis), (int(ox), int(oy)))
    if s.get("footnote"):
        text(ImageDraw.Draw(im), (c.W / 2, 850), s["footnote"], F("sans", 30), (140, 140, 146), 0, "mm", max_w=c.W - 300)
    return arr(im)


def shot_icons_row(c, s):
    im = Image.new("RGBA", (c.W, c.H), ground(s.get("bg", "dark")) + (255,))
    sentence(im, s["caption"], c.W / 2, 330, F("sans_medium", 76), G.light, G.muted_d, c.lt, 0.05, 0.08)
    refs, size, gap = s["icons"], 110, 70
    x = c.W / 2 - (len(refs) * size + (len(refs) - 1) * gap) / 2
    for k, r in enumerate(refs):
        p = ease_out(min(1, max(0, (c.lt - 0.6 - k * 0.1) / 0.35)))
        if p > 0:
            if r == "logo":
                ic = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                ImageDraw.Draw(ic).rounded_rectangle((0, 0, size - 1, size - 1), 26, fill=(26, 26, 28, 255), outline=(62, 62, 66, 255), width=2)
                lg = logo(size * 0.7)
                ic.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
            else:
                ic = icon_img("brand:" + r, size * 0.74, G.light)
            im.alpha_composite(fade(ic, p), (int(x + (size - ic.width) / 2), int(620 - ic.height / 2 + (1 - p) * 24)))
        x += size + gap
    return arr(im)


def shot_laptop(c, s):
    """Caption above, a laptop rising in with real product media on its keyed screen."""
    bg = s.get("bg", "light")
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    sentence(im, s["caption"], c.W / 2, s.get("caption_y", 190), F("sans_medium", s.get("size", 80)), fg(bg),
             G.muted_d if bg == "dark" else G.muted_l, c.lt, 0.05, 0.08)
    dev, (x0, y0, x1, y1) = keyed(s.get("device", "laptop"))
    p = ease_out(min(1, max(0, (c.lt - 0.35) / 0.6)))
    w = c.W * s.get("width", 0.56)
    k = w / dev.width
    devs = dev.resize((int(dev.width * k), int(dev.height * k)), Image.LANCZOS)
    ox = int(c.W / 2 - devs.width / 2)
    oy = int(c.H - devs.height - 30 + (1 - p) * 160)
    sx0, sy0, sx1, sy1 = [int(v * k) for v in (x0, y0, x1, y1)]
    scr = Image.open(os.path.join(G.assets, s["media"])).convert("RGB")
    if s.get("crop"):                                    # trim screenshot frames / browser chrome
        x0c, y0c, x1c, y1c = s["crop"]
        scr = scr.crop((int(x0c * scr.width), int(y0c * scr.height), int(x1c * scr.width), int(y1c * scr.height)))
    sw, sh = sx1 - sx0 + 2, sy1 - sy0 + 2
    zz = lerp(1.0, s.get("zoom", 1.06), ease_in_out(c.p(0, c.dur)))
    if s.get("fit") == "contain":                        # show the whole UI; fill the rest with its own background
        fillc = hex2rgb(s["fill"]) if s.get("fill") else scr.getpixel((scr.width // 2, scr.height // 2))
        k2 = min(sw / scr.width, sh / scr.height) * zz
        fitted = scr.resize((int(scr.width * k2), int(scr.height * k2)), Image.LANCZOS)
        canvas = Image.new("RGB", (sw, sh), fillc)
        ax = (sw - fitted.width) // 2
        ay = 0 if s.get("anchor") == "top" else (sh - fitted.height) // 2
        canvas.paste(fitted, (ax, ay))
        scr = canvas
    else:
        scr = cover(scr, sw, sh, zz, *s.get("focus", [0.5, 0.4]))
    im.paste(scr, (ox + sx0 - 1, oy + sy0 - 1))
    im.alpha_composite(devs, (ox, oy))
    return arr(im)


STATUS = {"online": (46, 160, 90), "idle": (161, 161, 170), "stale": (200, 140, 40), "paused": (107, 79, 160),
          "blocked": (107, 79, 160), "allowed": (46, 125, 79), "warned": (168, 106, 30), "held": (168, 106, 30),
          "revoked": (190, 60, 60), "signed": (46, 125, 79), "granted": (46, 125, 79), "verified": (46, 125, 79)}


def shot_fleet_grid(c, s):
    """A fleet of devices: icons light up (enrolled), some get flagged, and a policy push ripples across."""
    bg = s.get("bg", "dark")
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, s.get("caption_y", 150), F("sans_medium", s.get("size", 72)), fg(bg),
                 G.muted_d if bg == "dark" else G.muted_l, c.lt, 0.05, 0.08)
    cols, rows = s.get("cols", 14), s.get("rows", 5)
    cell = s.get("cell", 104)
    gx0 = (c.W - cols * cell) / 2
    gy0 = s.get("grid_y", 330)
    base = (78, 78, 84) if bg == "dark" else (212, 212, 216)
    on_col = G.light if bg == "dark" else G.ink
    push_t = s.get("push_at")
    flagged = set(s.get("flag", []))
    for r in range(rows):
        for q in range(cols):
            k = r * cols + q
            ap = ease_out(min(1, max(0, (c.lt - 0.3 - (q + r) * s.get("appear", 0.025)) / 0.3)))
            if ap <= 0:
                continue
            col = base
            if c.lt > s.get("online_at", 0.9) + ((k * 7919) % 97) / 97 * 0.8:
                col = on_col
            if k in flagged and c.lt > s.get("flag_at", 99):
                col = STATUS[s.get("flag_color", "blocked")]
            if push_t is not None:                               # wave from the left: policy applied
                wave = push_t + q * s.get("wave", 0.06) + r * 0.02
                if c.lt > wave:
                    col = G.accent
                    if c.lt < wave + 0.25:
                        col = tuple(int(lerp(255, v, (c.lt - wave) / 0.25)) for v in G.accent)
            ic = icon_img("lucide:" + s.get("icon", "laptop"), cell * 0.52, col)
            im.alpha_composite(fade(ic, ap), (int(gx0 + q * cell + cell * 0.24), int(gy0 + r * cell + cell * 0.24 + (1 - ap) * 12)))
    if s.get("note") and c.lt > s.get("note_at", 1.5):
        p = ease_out(min(1, (c.lt - s.get("note_at", 1.5)) / 0.35))
        ui.rise(im, (c.W / 2, gy0 + rows * cell + 70), s["note"], F("sans", 34), G.muted_d if bg == "dark" else G.muted_l, p, 0,
                "mm", max_w=c.W - 300)
    return arr(im)


def cell_draw(im, d, x, y, w, kind, val, fsz, col, bg_dark):
    """One table cell. kinds: text, mono, strong, status (● word, typeset), icons (brand marks), muted."""
    if kind == "status":
        sc = STATUS.get(val.split(" ")[0], (150, 150, 156))
        d.text((x, y), "●", font=F("sans", fsz * 0.7), fill=sc, anchor="lm")
        text(d, (x + fsz * 0.9, y), val, F("sans_medium", fsz), sc, 0, "lm", max_w=w - fsz)
    elif kind == "icons":
        ix = x
        for slug in val.split(","):
            ic = icon_img("brand:" + slug, fsz * 1.15, G.light if bg_dark else None)
            im.alpha_composite(ic, (int(ix), int(y - ic.height / 2)))
            ix += ic.width + 12
    else:
        f = {"mono": F("mono", fsz * 0.92), "strong": F("sans_medium", fsz)}.get(kind, F("sans", fsz))
        text(d, (x, y), val, f, col, 0, "lm", max_w=w - 20)


def shot_table(c, s):
    """A console table (devices, members…): header, then rows sliding in; optional row updates at a time."""
    bg = s.get("bg", "light")
    dark = bg == "dark"
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, 130, F("sans_medium", 64), fg(bg), G.muted_d if dark else G.muted_l, c.lt, 0.05, 0.07)
    cols = s["columns"]                                   # [{title, w (fraction), kind}]
    x0, x1 = 170, c.W - 170
    top = s.get("top", 270)
    rh = s.get("row_h", 86)
    fsz = s.get("font", 28)
    card = (x0 - 30, top - 30, x1 + 30, top + 70 + rh * len(s["rows"]) + 20)
    p0 = ease_out(min(1, c.lt / 0.35))
    shadowed_box(im, (card[0], card[1] + (1 - p0) * 30, card[2], card[3] + (1 - p0) * 30), 18,
                 (34, 34, 36) if dark else (255, 255, 255), (60, 60, 64) if dark else (232, 232, 235), 50)
    d = ImageDraw.Draw(im)
    txt = G.light if dark else G.ink
    mut = G.muted_d if dark else (113, 113, 122)
    xs, x = [], x0
    for col in cols:
        xs.append(x)
        x += col["w"] * (x1 - x0)
    for k, col in enumerate(cols):
        text(d, (xs[k], top + 20), col["title"].upper(), F("sans_medium", 18), mut, 1.5, "lm", max_w=cols[k]["w"] * (x1 - x0) - 20)
    d.line((x0, top + 48, x1, top + 48), fill=(56, 56, 60) if dark else (236, 236, 239), width=2)
    for r, row in enumerate(s["rows"]):
        t0 = row.get("t", 0.5 + r * 0.18)
        if c.lt < t0:
            continue
        p = ease_out(min(1, (c.lt - t0) / 0.3))
        vals = row["cells"]
        for u in row.get("updates", []):                   # a cell changes at time u.t (e.g. status flips)
            if c.lt >= u["t"]:
                vals = list(vals)
                vals[u["col"]] = u["value"]
        y = top + 70 + r * rh + rh / 2 + (1 - p) * 16
        if row.get("highlight") and c.lt >= row.get("highlight_at", 0):
            hp = ease_out(min(1, (c.lt - row.get("highlight_at", 0)) / 0.3))
            d.rectangle((x0 - 30, y - rh / 2 + 4, x1 + 30, y + rh / 2 - 4), fill=tuple(int(lerp(v, w, hp * 0.12)) for v, w in
                        zip((34, 34, 36) if dark else (255, 255, 255), G.accent)))
        for k, col in enumerate(cols):
            ccol = tuple(int(lerp(v, w, p)) for v, w in zip((34, 34, 36) if dark else (255, 255, 255), txt if col.get("kind") != "muted" else mut))
            cell_draw(im, d, xs[k] + (1 - p) * 20, y, col["w"] * (x1 - x0), col.get("kind", "text"), vals[k], fsz, ccol, dark)
            d = ImageDraw.Draw(im)
        if r < len(s["rows"]) - 1:
            d.line((x0, y + rh / 2, x1, y + rh / 2), fill=(48, 48, 52) if dark else (242, 242, 244), width=1)
    return arr(im)


def shot_feed(c, s):
    """Live receipts streaming in at the top of a list; older rows slide down and fade."""
    bg = s.get("bg", "dark")
    dark = bg == "dark"
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, 130, F("sans_medium", 64), fg(bg), G.muted_d if dark else G.muted_l, c.lt, 0.05, 0.07)
    d = ImageDraw.Draw(im)
    items = s["items"]
    every = s.get("every", 0.45)
    shown = [it for k, it in enumerate(items) if c.lt >= 0.4 + k * every]
    x0, x1, top, rh = 260, c.W - 260, s.get("top", 290), 96
    for j, it in enumerate(reversed(shown)):
        k = len(shown) - 1 - j
        age = c.lt - (0.4 + k * every)
        p = ease_out(min(1, age / 0.3))
        y = top + (j - 1 + p) * rh + rh / 2
        if y > c.H - 80:
            continue
        a = max(0.25, 1 - j * 0.14) * p
        base = (38, 38, 38) if dark else (255, 255, 255)
        mix = lambda col: tuple(int(lerp(bv, cv, a)) for bv, cv in zip(base, col))
        vc = STATUS.get(it["verdict"], (150, 150, 156))
        text(d, (x0, y), it["verdict"].upper(), F("sans_medium", 26), mix(vc), 2, "lm", max_w=170)
        text(d, (x0 + 190, y - 14), it["rule"], F("mono", 26), mix(G.light if dark else G.ink), 0, "lm", max_w=520)
        text(d, (x0 + 190, y + 20), it.get("detail", ""), F("sans", 22), mix(G.muted_d if dark else G.muted_l), 0, "lm", max_w=560)
        ix = x0 + 760
        if it.get("agent"):
            ic = icon_img("brand:" + it["agent"], 34, mix(G.light) if dark else None)
            im.alpha_composite(fade(ic, a), (int(ix), int(y - 17)))
        text(d, (ix + 50, y), it.get("who", ""), F("sans", 26), mix(G.light if dark else G.ink), 0, "lm", max_w=420)
        text(d, (x1, y), it.get("hash", ""), F("mono", 22), mix(G.muted_d), 0, "rm", max_w=300)
        d.line((x0, y + rh / 2, x1, y + rh / 2), fill=mix((56, 56, 60) if dark else (236, 236, 239)), width=1)
    if s.get("note"):
        text(d, (c.W / 2, c.H - 70), s["note"], F("sans", 28), G.muted_d if dark else G.muted_l, 0, "mm", max_w=c.W - 300)
    return arr(im)


def shot_card(c, s):
    """A console detail card (approval, exemption…): title, key/value rows, optional code, typeset actions."""
    bg = s.get("bg", "light")
    dark = bg == "dark"
    im = Image.new("RGBA", (c.W, c.H), ground(bg) + (255,))
    if s.get("caption"):
        sentence(im, s["caption"], c.W / 2, 150, F("sans_medium", 70), fg(bg), G.muted_d if dark else G.muted_l, c.lt, 0.05, 0.08)
    w = s.get("width", 1180)
    rows = s.get("rows", [])
    code = s.get("code", [])
    hgt = 150 + len(rows) * 62 + (len(code) * 44 + 50 if code else 0) + (110 if s.get("actions") else 30)
    p = ease_out(min(1, max(0, (c.lt - 0.2) / 0.4)))
    x0, y0 = c.W / 2 - w / 2, s.get("top", 300) + (1 - p) * 40
    shadowed_box(im, (x0, y0, x0 + w, y0 + hgt), 20, (34, 34, 36) if dark else (255, 255, 255), (60, 60, 64) if dark else (232, 232, 235), 55)
    d = ImageDraw.Draw(im)
    txt, mut = (G.light, G.muted_d) if dark else (G.ink, (113, 113, 122))
    sc = STATUS.get(s.get("state", ""), mut)
    if s.get("state"):
        text(d, (x0 + 50, y0 + 58), s["state"].upper(), F("sans_medium", 22), sc, 2, "lm", max_w=300)
    text(d, (x0 + 50, y0 + 104), s["title"], F("sans_medium", 40), txt, -0.5, "lm", max_w=w - 100)
    y = y0 + 170
    for k, (lab, val) in enumerate(rows):
        rp = ease_out(min(1, max(0, (c.lt - 0.5 - k * 0.12) / 0.3)))
        text(d, (x0 + 50, y), lab, F("sans", 26), tuple(int(lerp(255 if not dark else 34, v, rp)) for v in mut), 0, "lm", max_w=260)
        mono = lab.lower() in s.get("mono_keys", ["rule", "what runs", "repo", "rules"])
        text(d, (x0 + 330, y), val, F("mono", 26) if mono else F("sans_medium", 28), tuple(int(lerp(255 if not dark else 34, v, rp)) for v in txt),
             0, "lm", max_w=w - 390)
        y += 62
    if code:
        cy0 = y - 10
        d.rounded_rectangle((x0 + 40, cy0, x0 + w - 40, cy0 + len(code) * 44 + 30), 12, fill=(24, 24, 26) if dark else (246, 246, 248))
        for k, ln in enumerate(code):
            text(d, (x0 + 70, cy0 + 36 + k * 44), ln, F("mono", 26), (190, 190, 196) if dark else (63, 63, 70), 0, "lm", max_w=w - 140)
        y = cy0 + len(code) * 44 + 70
    if s.get("actions"):
        ax = x0 + 50
        chosen = s.get("choose")
        for k, act in enumerate(s["actions"]):
            on = chosen is not None and k == chosen and c.lt >= s.get("choose_at", 99)
            f = F("sans_medium", 30)
            col = sc if on else txt
            if on:
                chevron(d, ax, y + 10, col, 28)
            text(d, (ax + 30, y + 10), act, f, col, 0, "lm", max_w=400)
            ax += f.getlength(act) + 90
    if s.get("footnote"):
        text(d, (c.W / 2, min(c.H - 60, y0 + hgt + 70)), s["footnote"], F("sans", 28), G.muted_d if dark else G.muted_l, 0, "mm",
             max_w=c.W - 300)
    return arr(im)


def shot_black(c, s):
    return np.zeros((c.H, c.W, 3), np.uint8)


SHOTS = {"sentence": shot_sentence, "permission": shot_permission, "prompt": shot_prompt, "session": shot_session,
         "steps": shot_steps, "chart": shot_chart, "ticker": shot_ticker, "mask": shot_mask, "icons_row": shot_icons_row,
         "laptop": shot_laptop, "fleet_grid": shot_fleet_grid, "table": shot_table, "feed": shot_feed,
         "card": shot_card, "black": shot_black}


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    scenes = []
    for k, s in enumerate(brief["shots"]):
        tr = {"dissolve": Dissolve(0.35, 10), "pixel": Mosaic(0.35, 24, 14, k + 3, (G.dark,))}.get(s.get("tr"))
        scenes.append(Scene(f"{k:02d}-{s['type']}", s["dur"], (lambda f, sh: lambda c: f(c, sh))(SHOTS[s["type"]], s), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def fetch_line_icons(names, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for n in names:
        p = os.path.join(out_dir, n + ".svg")
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(urllib.request.urlopen(LUCIDE.format(n), timeout=60).read())
        if not os.path.exists(p[:-4] + ".png"):
            rasterize_svg(p, p[:-4] + ".png")
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "icons", "assets", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    if a.cmd == "init":                                  # copy the starter template into a new project folder
        import shutil
        dst = os.path.abspath(a.args[0] if a.args else "keynote-film")
        if os.path.exists(dst):
            sys.exit(f"{dst} already exists")
        shutil.copytree(os.path.join(HERE, "..", "examples", "starter"), dst, ignore=shutil.ignore_patterns("out"))
        print(f"created {dst}\n  1. replace every [placeholder] in brief.json (run the copy through the no-ai-slop skill)"
              f"\n  2. assets/logo.png = your real logo, assets/dashboard.png = a real screenshot"
              f"\n  3. python3 {os.path.join(HERE, 'main.py')} icons|assets|check|render --brief {os.path.join(dst, 'brief.json')}")
        return
    if a.cmd == "assets":                                # gpt-image-2 PNGs declared in brief["assets"]
        brief = json.load(open(a.brief))
        for m in generate_images(brief.get("assets", {}), os.path.join(base, brief.get("assets_dir", "assets")),
                                 names=a.args or None):
            print(m)
        return
    if a.cmd == "icons":
        brief = json.load(open(a.brief))
        blob = json.dumps(brief["shots"])
        lucide = sorted(set(re.findall(r"lucide:([a-z0-9-]+)", blob)) | set(re.findall(r"\{icon:([a-z0-9-]+)\}", blob))
                        | set(re.findall(r'"icon": "([a-z0-9-]+)"', blob)) | {"eye", "eye-off"})
        brands = sorted(set(re.findall(r"brand:([a-z0-9-]+)", blob)) | set(brief.get("brand_icons", [])) |
                        {x for s in brief["shots"] for x in s.get("icons", []) if x != "logo"} |
                        {x for m in re.findall(r"\{tiles:([^}]+)\}", blob) for x in m.split(",") if x != "logo"})
        assets = os.path.join(base, brief.get("assets_dir", "assets"))
        print("lucide:", fetch_line_icons(lucide, os.path.join(assets, "lucide")))
        for m in fetch_icons(brands, os.path.join(assets, "icons")):
            print("brand:", m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep:
            print("  ✗", r)
        for r in overflow_report(warn=True):
            print("  ! warning:", r)
        blob = json.dumps(brief["shots"])
        todo = sorted(set(re.findall(r"\[[A-Za-z][^\]\[\"]{1,60}\]", blob)))
        if todo:
            print(f"  ! {len(todo)} unfilled placeholders, e.g. " + ", ".join(todo[:4]))
        trailing = [t for t in re.findall(r'"(?:text|caption|footnote|note|sub)"?: ?"([^"]+\.)"', blob)
                    if not re.search(r"\.(com|dev|io|md|json|env|csv|sh|py)$", t)]
        if trailing:
            print(f"  ! {len(trailing)} on-screen lines end with a period, e.g. {trailing[0]!r}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} shots")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 5, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "film.mp4"), a.audio))


if __name__ == "__main__":
    main()
