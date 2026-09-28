#!/usr/bin/env python3
"""illustrated-explainer: a narrated, flat-vector corporate explainer.

Wide gpt-image-2 illustrations in one house style, slow camera pans across them, a small-caps caption at
the top of each scene, bullet lists, a split screen, a zoom-blur whoosh into the logo on a hub ring,
a world map with pins, floating product cards, and a spoken CTA. Every beat starts on a spoken cue.

    python3 main.py voice|assets|check|still|sheet|render --brief brief.json [times...]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from framesmith import Dissolve, Scene, Timeline, cover, ease_in_out, ease_out, generate_images, h, hex2rgb, lerp, overflow_report, text
from framesmith import narration
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width
from framesmith import ui

G = None


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        th = brief.get("theme", {})
        c = lambda k, d: hex2rgb(th[k]) if k in th else d
        self.bg = c("bg", (222, 232, 248))
        self.ink = c("ink", (31, 58, 95))
        self.mid = c("mid", (92, 128, 163))
        self.accent = c("accent", (57, 184, 176))
        self.warm = c("warm", (244, 197, 66))
        self.W, self.H = brief.get("size", [1920, 1080])
        self.assets = os.path.join(base, brief.get("assets_dir", "assets"))
        self._c = {}
        vo = brief["vo"]
        self.script = open(os.path.join(base, vo["script"])).read().strip()
        tr = json.load(open(os.path.join(base, vo["words"])))
        self.toks = narration.align(self.script, tr["words"])
        self.vo_dur = tr["duration"]
        self.audio = os.path.join(base, vo["audio"])

    def cache(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]

    def cue(self, phrase, after=0):
        i = narration.find(self.toks, phrase, after)
        return self.toks[i]["start"], i


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


def img(name):
    return G.cache(("img", name), lambda: Image.open(os.path.join(G.assets, name + ".png")).convert("RGBA"))


def fade(im, p):
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * max(0.0, min(1.0, p))).astype(np.uint8)
    return Image.fromarray(a)


def canvas():
    return Image.new("RGBA", (G.W, G.H), G.bg + (255,))


def pan(name, lt, dur, move, w=None, hgt=None):
    """Ken Burns across a wide illustration: move = [zoom0, zoom1, fx0, fx1, fy0, fy1]."""
    z0, z1, fx0, fx1, fy0, fy1 = move
    p = ease_in_out(min(1, lt / max(0.1, dur)))
    return cover(img(name).convert("RGB"), w or G.W, hgt or G.H, lerp(z0, z1, p), lerp(fx0, fx1, p), lerp(fy0, fy1, p)).convert("RGBA")


def caption(im, s, lt, y=64, max_w=None):
    """Small-caps caption at the top of the scene: plain text between two thin rules, no box."""
    if not s:
        return
    p = ease_out(min(1, max(0, (lt - 0.15) / 0.4)))
    f = F("sans_medium", 30)
    lines = s.upper().split("\n")
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    widths = [text_width(l, f, 2) for l in lines]
    wmax = min(max(widths), (max_w or G.W - 300))
    lh = 44
    top = y
    for k, l in enumerate(lines):
        text(d, (G.W / 2, top + k * lh), l, f, G.ink + (255,), 2, "ma", max_w=max_w or G.W - 300)
    ry = top + lh * len(lines) + 10
    half = wmax / 2 * p
    d.line((G.W / 2 - half, top - 16, G.W / 2 + half, top - 16), fill=G.mid + (255,), width=2)
    d.line((G.W / 2 - half, ry, G.W / 2 + half, ry), fill=G.mid + (255,), width=2)
    # a soft pale wash behind the caption so it stays readable over the illustration
    wash = Image.new("L", im.size, 0)
    ImageDraw.Draw(wash).rectangle((G.W / 2 - wmax / 2 - 60, top - 40, G.W / 2 + wmax / 2 + 60, ry + 24), fill=int(200 * p))
    im.paste(Image.new("RGB", im.size, (245, 249, 255)), (0, 0), wash.filter(ImageFilter.GaussianBlur(30)))
    im.alpha_composite(fade(lay, p))


def cue_t(spec, key, beat, default=0.0):
    if key not in spec:
        return default
    t, _ = G.cue(spec[key], beat["_tok"])
    return max(0.0, t - beat["_t0"])


# ------------------------------------------------------------------ beats
def b_scene(c, s):
    im = pan(s["image"], c.lt, c.dur, s.get("move", [1.06, 1.16, 0.45, 0.55, 0.55, 0.5]))
    caption(im, s.get("caption"), c.lt)
    return arr(im)


def b_bullets(c, s):
    """Faded illustration on the right, bullet list on the left, one item per spoken cue."""
    base = pan(s["image"], c.lt, c.dur, s.get("move", [1.1, 1.14, 0.6, 0.62, 0.5, 0.5]))
    veil = Image.new("RGBA", base.size, (245, 249, 255, 175))
    base.alpha_composite(veil)
    caption(base, s.get("caption"), c.lt)
    d = ImageDraw.Draw(base)
    f = F("sans_medium", 44)
    y0 = G.H * 0.36
    for k, it in enumerate(s["items"]):
        t0 = cue_t(it, "at", s, 0.5 + k * 0.6)
        p = ease_out(min(1, max(0, (c.lt - t0) / 0.35)))
        if p <= 0:
            continue
        y = y0 + k * 92
        x = G.W * 0.12 + (1 - p) * 30
        col = tuple(int(lerp(v, w, p)) for v, w in zip((245, 249, 255), G.ink))
        dot = tuple(int(lerp(v, w, p)) for v, w in zip((245, 249, 255), hex2rgb(s.get("dot", "#E0525A"))))
        d.ellipse((x, y - 11, x + 22, y + 11), fill=dot)
        text(d, (x + 48, y), it["text"].upper(), f, col, 2, "lm", max_w=G.W * 0.72)
    return arr(base)


def b_split(c, s):
    """Two illustrations side by side; a divider slides in from the right."""
    im = canvas()
    p = ease_in_out(min(1, c.lt / 0.6))
    xdiv = int(lerp(G.W, G.W / 2, p))
    left = pan(s["left"], c.lt, c.dur, s.get("move_l", [1.1, 1.18, 0.5, 0.52, 0.5, 0.5]), G.W // 2, G.H)
    right = pan(s["right"], c.lt, c.dur, s.get("move_r", [1.1, 1.18, 0.5, 0.48, 0.5, 0.5]), G.W // 2, G.H)
    im.alpha_composite(left, (int(lerp(G.W / 4, 0, p)), 0))
    im.alpha_composite(right, (xdiv, 0))
    ImageDraw.Draw(im).rectangle((xdiv - 3, 0, xdiv + 3, G.H), fill=G.ink)
    caption(im, s.get("caption"), c.lt)
    return arr(im)


def b_logo(c, s):
    """Hub ring spinning in with the real logo at its centre, then the product name rises beneath."""
    im = canvas()
    glow = Image.new("L", im.size, 0)
    ImageDraw.Draw(glow).ellipse((G.W / 2 - 520, G.H * 0.47 - 420, G.W / 2 + 520, G.H * 0.47 + 420), fill=160)
    im.paste(Image.new("RGB", im.size, (245, 249, 255)), (0, 0), glow.filter(ImageFilter.GaussianBlur(90)))
    p = ease_out(min(1, c.lt / 0.9))
    size = int(lerp(300, 640, p))
    ring = img(s.get("ring", "network_ring")).resize((size, size), Image.LANCZOS).rotate(lerp(-90, 0, p) + c.lt * 3, resample=Image.BICUBIC)
    cy = G.H * 0.47
    im.alpha_composite(fade(ring, p), (int(G.W / 2 - size / 2), int(cy - size / 2)))
    lp = ease_out(min(1, max(0, (c.lt - 0.5) / 0.5)))
    ls = int(size * 0.27)
    tile = Image.new("RGBA", (ls, ls), (0, 0, 0, 0))
    ImageDraw.Draw(tile).ellipse((0, 0, ls - 1, ls - 1), fill=(255, 255, 255, 255))
    lg = img("logo").resize((int(ls * 0.62),) * 2, Image.LANCZOS)
    tile.alpha_composite(lg, ((ls - lg.width) // 2, (ls - lg.height) // 2))
    im.alpha_composite(fade(tile, lp), (int(G.W / 2 - ls / 2), int(cy - ls / 2)))
    caption(im, s.get("caption"), c.lt - 0.6, y=48)
    np_ = ease_out(min(1, max(0, (c.lt - cue_t(s, "name_at", s, 1.2)) / 0.45)))
    ui.rise(im, (G.W / 2, G.H * 0.94), s.get("name", ""), F("sans_medium", 64), G.ink, np_, 6, "ms", max_w=G.W - 300)
    return arr(im)


CITIES = {"sf": (0.155, 0.37), "ny": (0.285, 0.35), "sp": (0.345, 0.72), "ldn": (0.49, 0.28), "ber": (0.525, 0.28), "lag": (0.505, 0.55),
          "dxb": (0.64, 0.43), "blr": (0.705, 0.52), "sgp": (0.775, 0.58), "tok": (0.87, 0.36), "syd": (0.9, 0.8), "nbo": (0.595, 0.6)}


def b_map(c, s):
    """World map with pins dropping in one by one; optional name fades in over the top."""
    im = pan(s.get("image", "world_map"), c.lt, c.dur, s.get("move", [1.02, 1.08, 0.5, 0.5, 0.5, 0.5]))
    d = ImageDraw.Draw(im)
    for k, key in enumerate(s.get("pins", list(CITIES))):
        fx, fy = CITIES[key]
        t0 = 0.4 + k * s.get("every", 0.18)
        p = ease_out(min(1, max(0, (c.lt - t0) / 0.35)))
        if p <= 0:
            continue
        x, y = fx * G.W, fy * G.H - (1 - p) * 40
        r = 16
        col = G.accent if k % 3 else G.ink
        d.ellipse((x - r * 1.8, fy * G.H - 6, x + r * 1.8, fy * G.H + 6), fill=(190, 208, 232))
        d.polygon([(x - r, y - r * 1.6), (x + r, y - r * 1.6), (x, y + 2)], fill=col)
        d.ellipse((x - r, y - r * 2.6, x + r, y - r * 0.6), fill=col)
        d.ellipse((x - r * 0.4, y - r * 2.0, x + r * 0.4, y - r * 1.2), fill=(255, 255, 255))
        if s.get("links") and k:
            px, py = CITIES[s["pins"][0]] if s.get("pins") else CITIES["ldn"]
            lp = ease_out(min(1, max(0, (c.lt - t0 - 0.2) / 0.5)))
            d.line((px * G.W, py * G.H, lerp(px * G.W, x, lp), lerp(py * G.H, fy * G.H, lp)), fill=G.mid, width=2)
    caption(im, s.get("caption"), c.lt)
    return arr(im)


def b_cards(c, s):
    """Product decision cards floating upward over a softened backdrop (the product's own events, not testimonials)."""
    base = pan(s.get("image", "world_map"), c.lt, c.dur, [1.1, 1.12, 0.5, 0.5, 0.5, 0.5])
    base = base.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(Image.new("RGBA", base.size, (230, 240, 252, 120)))
    f1, f2 = F("sans_medium", 30), F("mono", 24)
    for k, cd in enumerate(s["cards"]):
        t0 = cue_t(cd, "at", s, 0.3 + k * 0.5)
        age = c.lt - t0
        if age < 0:
            continue
        p = ease_out(min(1, age / 0.5))
        w, hh = 620, 132
        col_x = [0.08, 0.55, 0.3, 0.62, 0.12, 0.4][k % 6]
        x = G.W * col_x
        y = G.H * (0.28 + (k % 3) * 0.22) + 40 - age * 18
        card = Image.new("RGBA", (w + 60, hh + 60), (0, 0, 0, 0))
        sh = Image.new("L", card.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle((30, 40, 30 + w, 40 + hh), 18, fill=60)
        card.paste(G.ink + (255,), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
        cdr = ImageDraw.Draw(card)
        cdr.rounded_rectangle((30, 30, 30 + w, 30 + hh), 18, fill=(255, 255, 255, 240))
        vc = {"blocked": (220, 74, 74), "allowed": (47, 158, 90), "held": (224, 118, 31), "redacted": (124, 92, 196)}.get(cd["verdict"], G.ink)
        cdr.ellipse((58, 62, 74, 78), fill=vc)
        text(cdr, (88, 70), cd["verdict"].upper() + "  ·  " + cd["title"], f1, G.ink, 0.5, "lm", max_w=w - 90)
        text(cdr, (58, 122), cd["detail"], f2, G.mid, 0, "lm", max_w=w - 60)
        base.alpha_composite(fade(card, p), (int(x), int(y)))
    caption(base, s.get("caption"), c.lt)
    return arr(base)


def b_cta(c, s):
    im = pan(s["image"], c.lt, c.dur, s.get("move", [1.04, 1.1, 0.6, 0.62, 0.5, 0.5]))
    veil = Image.new("L", im.size, 0)
    ImageDraw.Draw(veil).rectangle((0, 0, G.W * 0.55, G.H), fill=225)
    im.paste(Image.new("RGB", im.size, (245, 249, 255)), (0, 0), veil.filter(ImageFilter.GaussianBlur(120)))
    lp = ease_out(min(1, c.lt / 0.5))
    lg = img("logo").resize((110, 110), Image.LANCZOS)
    im.alpha_composite(fade(lg, lp), (int(G.W * 0.08), int(G.H * 0.3)))
    ui.rise(im, (G.W * 0.08 + 140, G.H * 0.3 + 78), s.get("name", ""), F("sans_medium", 72), G.ink, ease_out(min(1, max(0, (c.lt - 0.2) / 0.4))), -1, "ls",
            max_w=G.W * 0.45)
    ui.rise(im, (G.W * 0.08, G.H * 0.52), s.get("line", ""), F("sans", 44), G.mid, ease_out(min(1, max(0, (c.lt - 0.6) / 0.4))), 0, "ls", max_w=G.W * 0.5)
    ui.rise(im, (G.W * 0.08, G.H * 0.63), s.get("url", ""), F("sans_medium", 44), G.ink, ease_out(min(1, max(0, (c.lt - cue_t(s, "url_at", s, 1.2)) / 0.4))), 1,
            "ls", max_w=G.W * 0.5)
    return arr(im)


BEATS = {"scene": b_scene, "bullets": b_bullets, "split": b_split, "logo": b_logo, "map": b_map, "cards": b_cards, "cta": b_cta}


class ZoomBlur:
    """Whoosh: the outgoing frame zooms and radially blurs into a white flash, then the new beat resolves."""
    def __init__(self, dur=0.5):
        self.dur = dur

    def blend(self, a, b, p, theme=None):
        src = a if p < 0.5 else b
        q = p / 0.5 if p < 0.5 else (1 - p) / 0.5
        im = Image.fromarray(src)
        w, hgt = im.size
        acc = np.zeros((hgt, w, 3), np.float32)
        n = 6
        for i in range(n):
            z = 1 + q * 0.35 * (i + 1) / n
            zi = im.resize((int(w * z), int(hgt * z)), Image.BILINEAR)
            x0, y0 = (zi.width - w) // 2, (zi.height - hgt) // 2
            acc += np.asarray(zi.crop((x0, y0, x0 + w, y0 + hgt)), np.float32)
        acc /= n
        flash = q ** 2 * 0.8
        return (acc * (1 - flash) + 255 * flash).astype(np.uint8)


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    beats, tok = [], 0
    for k, b in enumerate(brief["beats"]):
        t0, tok = G.cue(b["at"], tok)
        b["_t0"], b["_tok"] = (0.0 if k == 0 else t0 - brief.get("lead", 0.1)), tok
        beats.append(b)
    end = G.vo_dur + brief.get("tail", 1.5)
    scenes = []
    for k, b in enumerate(beats):
        t1 = beats[k + 1]["_t0"] if k + 1 < len(beats) else end
        tr = {"whoosh": ZoomBlur(0.5), "fade": Dissolve(0.45, 8)}.get(b.get("tr", "fade" if k else None))
        scenes.append(Scene(f"{k:02d}-{b['type']}", t1 - b["_t0"], (lambda bb: lambda c: BEATS[bb["type"]](c, bb))(b), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["voice", "assets", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor-enterprise", "brief.json"))
    ap.add_argument("--out")
    a = ap.parse_intermixed_args()
    base = os.path.dirname(os.path.abspath(a.brief))
    brief = json.load(open(a.brief))
    if a.cmd == "voice":
        vo = brief["vo"]
        script = open(os.path.join(base, vo["script"])).read().strip()
        wav = narration.tts(script, os.path.join(base, "vo.wav"), voice=vo.get("voice", "onyx"), instructions=vo.get("instructions"))
        json.dump(narration.transcribe_words(wav, prompt=script), open(os.path.join(base, vo["words"]), "w"), indent=1)
        os.system(f"ffmpeg -v error -y -i {wav} -c:a aac -b:a 128k {os.path.join(base, vo['audio'])}")
        print("voice ok")
        return
    if a.cmd == "assets":
        specs = brief.get("assets") or json.load(open(os.path.join(base, "assets.json")))
        style = brief.get("style", "")
        specs = {k: dict(v, prompt=v["prompt"].replace("STYLE", style)) for k, v in specs.items()}
        for m in generate_images(specs, os.path.join(base, brief.get("assets_dir", "assets")), names=a.args or None):
            print(m)
        return
    tl, brief = build(a.brief)
    out = os.path.join(base, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 3)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep + ["! " + w for w in overflow_report(warn=True)]:
            print("  ", r)
        for s, st in zip(tl.scenes, tl.starts):
            print(f"  {st:6.2f}s  {s.dur:5.2f}s  {s.name}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} beats")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["2"]:
            print(tl.still(float(s), os.path.join(out, f"still_{float(s):05.2f}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 4, 320))
    else:
        print(tl.render(a.out or os.path.join(out, "explainer.mp4"), G.audio))


if __name__ == "__main__":
    main()
