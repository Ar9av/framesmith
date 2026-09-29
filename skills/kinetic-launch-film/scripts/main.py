"""Kinetic UI launch film: voice-synced masked word rises on a light gridded ground with one accent, words on
dashed paths, letter stretch and scatter, a logo reveal, logo cards, a tilted 3D product window with detection
boxes, live UI driven by a cursor, a log that structures itself into a table, a hub with travelling beams, and
code-synthesised sound effects under the narration.

    python3 main.py init my-film                       copy the Prismor example to start from
    python3 main.py voice | check | still 3 12 | sheet | render   [--brief path/brief.json]
"""
import argparse, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "stage_engine"))   # shared compositor (same as archive-launch-film)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import stage as base
from stage import (INK, WHITE, arr, back_out, card, cl, console, cursor, cursor_path, fade, icon_img, logo_lockup,
                  mesh, mono, paste_scaled, pr)
from framesmith import Dissolve, ease_in_out, ease_out, lerp, h, text, ui, narration, overflow_report
from framesmith.typography import F, OVERFLOWS, SHRINKS, text_width
from framesmith import motion as M

PC = console.PC
PAPER = (247, 247, 245)


def G():
    return base.G


# ------------------------------------------------------------------ ground
def _grid():
    im = Image.new("RGBA", (G().W, G().H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(0, G().W, 72):
        d.line((x, 0, x, G().H), fill=(0, 0, 0, 12))
    for y in range(0, G().H, 72):
        d.line((0, y, G().W, y), fill=(0, 0, 0, 12))
    return im


def ground(t, side=1.0):
    """Warm off-white, a faint grid, and one soft Prismor-pastel glow drifting along an edge."""
    W, H = G().W, G().H
    im = Image.new("RGBA", (W, H), PAPER + (255,))
    glow = mesh(t)
    cx = W * (0.5 + 0.42 * side) + 80 * math.sin(t * 0.3)
    cy = H * 0.35 + 60 * math.cos(t * 0.25)
    m = G().cache(("glowmask", side), lambda: None)
    yy, xx = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32)
    r = np.hypot(xx * 8 - cx, (yy * 8 - cy) * 1.2) / (W * 0.55)
    a = (np.clip(1 - r, 0, 1) ** 1.6 * 235).astype(np.uint8)
    mask = Image.fromarray(a).resize((W, H), Image.BICUBIC)
    im.paste(glow, (0, 0), mask)
    im.alpha_composite(G().cache("grid", _grid))
    return im


# ------------------------------------------------------------------ timing
def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def word_times(s, phrase, words):
    """Beat-local time for each on-screen word: its spoken time when it matches the voice, else a 55 ms stagger."""
    t0, i0 = G().cue(phrase["at"], s["_tok"])
    toks = G().toks
    out, j, last = [], i0, t0 - s["_t0"]
    for w, _ in words:
        found = None
        for k in range(j, min(j + 6, len(toks))):
            if norm(toks[k]["w"]) == norm(w):
                found = k
                break
        if found is not None:
            last = toks[found]["start"] - s["_t0"]
            j = found + 1
        else:
            last += 0.055
        out.append(max(0.0, last - 0.04))
    return out


def phrase_lines(ph):
    lines = ph["text"] if isinstance(ph["text"], list) else ph["text"].split("\n")
    return [M.parse(l) for l in lines]


def draw_phrases(im, c, s):
    """Every phrase of a beat, each shown until the next begins (then blurred out)."""
    phs = s["phrases"]
    starts = [G().cue(p["at"], s["_tok"])[0] - s["_t0"] for p in phs]
    for k, ph in enumerate(phs):
        a = starts[k] - 0.06
        b = starts[k + 1] - 0.06 if k + 1 < len(phs) else c.dur + 1
        if not (a <= c.lt < b + 0.3):
            continue
        out_p = cl((c.lt - b) / 0.3) if c.lt >= b else 0.0
        lines = phrase_lines(ph)
        flat = [w for ln in lines for w in ln]
        times = word_times(s, ph, flat)
        st = ph.get("stretch")
        stretch = None
        if st:
            wi = [norm(w) for w, _ in flat].index(norm(st["word"]))
            stretch = (wi, st["letter"], st.get("extra", 3), st.get("t0", 0.25), st.get("dur", 0.9))
        fall = None
        if ph.get("fall"):
            fall = ([norm(w) for w, _ in flat].index(norm(ph["fall"])), 0.35)
        sc = None
        if ph.get("scatter_at"):
            sc = G().cue(ph["scatter_at"], s["_tok"])[0] - s["_t0"] if isinstance(ph["scatter_at"], str) else ph["scatter_at"]
        size = ph.get("size", 72)
        M.kinetic(im, lines, size, times, c.lt, c.t, ph.get("x", 0.5) * G().W, ph.get("y", 0.5) * G().H,
                  align=ph.get("align", "center"), stretch=stretch, fall=fall, scatter=sc, out_p=out_p)


def cam(im, c, s):
    """Slow push plus a small punch on every phrase start (log-space zoom, exponential decay)."""
    z = math.exp(lerp(0, math.log(s.get("push", 1.03)), ease_in_out(cl(c.lt / c.dur))))
    for p in s.get("phrases", []):
        t0 = G().cue(p["at"], s["_tok"])[0] - s["_t0"]
        if c.lt >= t0:
            z *= 1 + 0.012 * math.exp(-(c.lt - t0) * 5)
    return base.zoom_about(im, z, G().W / 2, G().H / 2)


# ------------------------------------------------------------------ beats
def b_kin(c, s):
    im = ground(c.t, s.get("side", 1.0))
    if s.get("backdrop") == "ui":
        panel = G().cache("bd_feed", lambda: console.render("feed", s["feed"], 9.0, 1250))
        p2 = panel.filter(ImageFilter.GaussianBlur(2.5))
        im.alpha_composite(fade(p2, 0.55), (int(G().W - 820 - 60 * ease_in_out(cl(c.lt / c.dur))), int(G().H / 2 - p2.height / 2 + 40)))
        wash = Image.new("L", im.size, 0)
        ImageDraw.Draw(wash).rectangle((0, 0, int(G().W * 0.62), G().H), fill=200)
        im.paste(PAPER + (255,), (0, 0), wash.filter(ImageFilter.GaussianBlur(120)))
    draw_phrases(im, c, s)
    return arr(cam(im, c, s))


def window(kind, w=1100, hgt=640):
    """Generic app windows for the 'agents are everywhere' montage (no brand UI invented)."""
    def mk():
        im = card(w, hgt, 18)
        d = ImageDraw.Draw(im)
        dark = kind == "terminal"
        if dark:
            d.rounded_rectangle((0, 0, w - 1, hgt - 1), 18, fill=(22, 23, 30, 255))
        for k, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            d.ellipse((24 + k * 26, 22, 38 + k * 26, 36), fill=col)
        g1, g2 = ((70, 72, 86), (52, 54, 66)) if dark else ((226, 228, 234), (238, 240, 244))
        if kind == "browser":
            d.rounded_rectangle((140, 16, w - 40, 44), 10, fill=(242, 243, 246))
            for i in range(3):
                d.rounded_rectangle((60 + i * 330, 90, 360 + i * 330, 300), 12, fill=g2)
            for i in range(6):
                d.rounded_rectangle((60, 340 + i * 40, 60 + (w - 200) * (0.5 + 0.5 * h(i, 2)), 358 + i * 40), 6, fill=g1)
        elif kind == "editor":
            d.rectangle((0, 58, 220, hgt - 1), fill=(244, 245, 248))
            for i in range(12):
                d.rounded_rectangle((24, 84 + i * 36, 24 + 150 * (0.4 + 0.6 * h(i, 4)), 98 + i * 36), 5, fill=g1)
                ind = 250 + 40 * int(h(i, 6) * 3)
                d.rounded_rectangle((ind, 84 + i * 40, ind + 520 * (0.3 + 0.7 * h(i, 8)), 100 + i * 40), 5,
                                    fill=[(180, 150, 230), (150, 200, 190), g1][i % 3])
        elif kind == "terminal":
            for i in range(11):
                d.rounded_rectangle((40, 80 + i * 46, 40 + (w - 160) * (0.25 + 0.7 * h(i, 3)), 98 + i * 46), 5,
                                    fill=[(90, 190, 130), g1, g1, (200, 170, 90)][i % 4])
        elif kind == "cloud":
            for i in range(3):
                for j in range(2):
                    x0, y0 = 70 + i * 330, 90 + j * 260
                    d.rounded_rectangle((x0, y0, x0 + 290, y0 + 220), 16, fill=g2)
                    im.alpha_composite(console.lucide(["server", "database", "cloud"][(i + j) % 3], 64, PC["ink3"]), (x0 + 30, y0 + 30))
                    d.rounded_rectangle((x0 + 30, y0 + 130, x0 + 230, y0 + 146), 6, fill=g1)
        return im
    return G().cache(("win", kind, w, hgt), mk)


def b_windows(c, s):
    """Label montage: each cue swaps a big white label over a tinted app window (blur swap)."""
    im = ground(c.t, -1)
    items = s["items"]
    starts = [G().cue(it["at"], s["_tok"])[0] - s["_t0"] for it in items]
    tint = tuple(s.get("tint", (118, 96, 206)))
    for k, it in enumerate(items):
        a = starts[k] - 0.05
        b = starts[k + 1] - 0.05 if k + 1 < len(items) else c.dur + 1
        if not (a <= c.lt < b + 0.25):
            continue
        q = M.spring(c.lt - a, *M.DEFAULT)
        outp = cl((c.lt - b) / 0.25) if c.lt >= b else 0
        wv = window(it["kind"])
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        cx = G().W / 2 + [0, -120, 140, -60][k % 4]
        cy = G().H / 2 + 30 + (1 - q) * 80
        paste_scaled(lay, wv, cx, cy, lerp(0.92, 1.0, q), min(1, q * 2))
        # tint the window so a white label reads on it
        tl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(tl).rounded_rectangle((cx - 550 * q, cy - 320 * q, cx + 550 * q, cy + 320 * q), 18, fill=tint + (int(150 * min(1, q)),))
        lay.alpha_composite(tl)
        f = F("sans_medium", 96)
        M.kinetic(lay, [[(w, False) for w in it["label"].split()]], 96, [a + 0.08 + i * 0.07 for i in range(5)], c.lt, c.t,
                  cx, cy, ink=(255, 255, 255))
        for j, ic in enumerate(it.get("icons", [])):
            qq = M.spring(c.lt - a - 0.2 - j * 0.1, *M.PLAYFUL)
            if qq > 0:
                tile = G().cache(("wtile", ic), lambda: _tile(ic, 120))
                ox, oy = [(-640, -250), (620, 210), (560, -280), (-600, 260)][j % 4]
                paste_scaled(lay, tile, cx + ox, cy + oy + math.sin(c.t * 1.5 + j) * 8, qq, min(1, qq * 2))
        if outp > 0:
            lay = fade(lay.filter(ImageFilter.GaussianBlur(12 * outp)), 1 - outp)
        im.alpha_composite(lay)
    return arr(im)


def _tile(ref, sz):
    t = card(sz, sz, int(sz * 0.24))
    ico = icon_img(ref, int(sz * 0.52))
    t.alpha_composite(ico, ((sz - ico.width) // 2, (sz - ico.height) // 2))
    return t


def b_paths(c, s):
    """Words appear riding dashed curves, each drawn as it is spoken."""
    im = ground(c.t, 1)
    d = ImageDraw.Draw(im)
    for it in s["items"]:
        t0 = G().cue(it["at"], s["_tok"])[0] - s["_t0"] - 0.05
        p = ease_out(cl((c.lt - t0) / 0.7))
        if p <= 0:
            continue
        pts = M.bezier([(x * G().W, y * G().H) for x, y in it["curve"]])
        M.dashed_path(d, pts, p, (70, 72, 84, 255), 3)
        f = F("sans_medium", it.get("size", 64))
        M.text_on_path(im, pts, it["word"], f, INK, it.get("start", 60), cl((c.lt - t0 - 0.1) / 0.35), lift=16)
    return arr(cam(im, c, s))


def b_meet(c, s):
    """'Meet' + logo mark pop; on the brand cue 'Meet' lifts away and the wordmark rises beside the mark."""
    im = ground(c.t, 1)
    lt = c.lt
    t_name = G().cue(s["name_at"], s["_tok"])[0] - s["_t0"]
    f = F("sans_medium", 150)
    lg = logo_lockup(150)
    sw = M.spring(lt - t_name, *M.DEFAULT)
    meet_w = text_width("Meet", f, -3)
    name_w = text_width(s.get("name", "Prismor"), f, -3)
    gap = 40
    w_a = meet_w + gap + lg.width
    w_b = lg.width + gap + name_w
    total = lerp(w_a, w_b, sw)
    x0 = G().W / 2 - total / 2
    lx = lerp(x0 + meet_w + gap, x0, sw)
    q = M.spring(lt - 0.25, *M.PLAYFUL)
    paste_scaled(im, lg, lx + lg.width / 2, G().H / 2, q, min(1, q * 2), shadow=False)
    if sw < 1:
        M.kinetic(im, [[("Meet", True)]], 150, [0.0], lt, c.t, x0 + meet_w / 2, G().H / 2, out_p=cl(sw * 1.6))
    if lt >= t_name:
        M.kinetic(im, [[(s.get("name", "Prismor"), False)]], 150, [t_name + 0.05], lt, c.t, lx + lg.width + gap + name_w / 2, G().H / 2,
                  spring_kd=M.DEFAULT)
    return arr(cam(im, c, s))


def b_logos(c, s):
    """A headline, then bordered logo cards spring in as each name is spoken."""
    im = ground(c.t, -1)
    draw_phrases(im, c, s)
    items = s["items"]
    cols = s.get("cols", 3)
    cw, ch, gx, gy = 400, 128, 34, 30
    rows = (len(items) + cols - 1) // cols
    top = G().H * s.get("grid_y", 0.52)
    for k, it in enumerate(items):
        t0 = G().cue(it["at"], s["_tok"])[0] - s["_t0"] - 0.05
        q = M.spring(c.lt - t0, *M.PLAYFUL)
        if q <= 0:
            continue
        r, col = divmod(k, cols)
        n_in_row = min(cols, len(items) - r * cols)
        cx = G().W / 2 + (col - (n_in_row - 1) / 2) * (cw + gx)
        cy = top + r * (ch + gy)
        cd = G().cache(("lcard", it["name"]), lambda: _logo_card(it, cw, ch))
        paste_scaled(im, cd, cx, cy, lerp(0.6, 1.0, q), min(1, q * 2.5))
    return arr(cam(im, c, s))


def _logo_card(it, cw, ch):
    cd = card(cw, ch, 22, WHITE, (220, 222, 230))
    ico = icon_img(it["icon"], 60)
    f = F("sans_medium", 34)
    tw = min(cw - 130, text_width(it["name"], f, -0.4))
    x0 = (cw - (60 + 20 + tw)) / 2
    cd.alpha_composite(ico, (int(x0), (ch - 60) // 2))
    text(ImageDraw.Draw(cd), (x0 + 80, ch / 2), it["name"], f, INK, -0.4, "lm", max_w=cw - 130)
    return cd


def secrets_window(w=1500, hgt=820):
    """The secrets demo from prismor.dev's hero, rebuilt: a Claude Code session with Prismor cloaking keys."""
    im = card(w, hgt, 22)
    d = ImageDraw.Draw(im)
    for k, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse((30 + k * 30, 30, 46 + k * 30, 46), fill=col)
    tabs = ["Secrets", "Least privilege", "Lethal trifecta", "Malicious skill", "Supply chain"]
    x = 170
    for i, tb in enumerate(tabs):
        f = F("sans", 26)
        tw = f.getlength(tb)
        if i == 0:
            d.rounded_rectangle((x - 22, 18, x + tw + 22, 60), 10, fill=(244, 245, 248))
        d.text((x, 39), tb, font=f, fill=INK if i == 0 else PC["ink3"], anchor="lm")
        x += tw + 70
    d.line((0, 78, w, 78), fill=PC["line"], width=2)
    d.rounded_rectangle((34, 104, 640, 260), 14, outline=(226, 150, 120), width=2)
    d.rectangle((52, 92, 250, 116), fill=WHITE)
    mono(d, (60, 104), "Claude Code", 26, (205, 110, 80), "lm")
    im.alpha_composite(icon_img("claude-code", 40), (58, 130))
    mono(d, (58, 200), "Opus 5.5", 26, INK, "lm")
    mono(d, (58, 236), "~/prismor-web", 26, PC["ink2"], "lm")
    return im


SECRET_LINES = [
    ("● ", "PRISMOR secrets loaded from disk", (200, 150, 60)),
    ("  ", "Real values substituted at execution", PC["ink2"]),
    ("  ", "DATABASE_URL · API_KEY · STRIPE_SECRET → cloaked", PC["ink2"]),
    ("● ", "PRISMOR output filter active, scrubbing secrets from logs", (200, 130, 40)),
    ("● ", "Connected to the database and built the page. I never saw a real credential", INK),
    ("✓ ", "3 secrets cloaked · 0 exposed to the model", (40, 150, 90)),
]


def b_tilt(c, s):
    """A tilted 3D product window: lines type in, detection boxes land on each secret, the card settles flat."""
    lt = c.lt
    im = ground(c.t, -1)
    win = G().cache("secwin", secrets_window).copy()
    d = ImageDraw.Draw(win)
    f = F("mono", 27)
    y0 = 310
    boxes = []
    for i, (lead, txt, col) in enumerate(SECRET_LINES):
        tt = 0.35 + i * 0.32
        if lt < tt:
            continue
        n = int(cl((lt - tt) / 0.35) * len(txt))
        y = y0 + i * 62
        if lead.startswith("✓"):                          # Geist Mono has no check glyph: draw it
            d.line([(44, y), (52, y + 9), (68, y - 10)], fill=col, width=4, joint="curve")
            lead = "  "
        mono(d, (40, y), lead + txt[:n], 27, col, "lm", 1420)
        if i == 2:
            for name in ("DATABASE_URL", "API_KEY", "STRIPE_SECRET"):
                a = f.getlength(lead + txt[:txt.index(name)], features=ui.CODE_FEATURES)
                b = a + f.getlength(name, features=ui.CODE_FEATURES)
                boxes.append((40 + a - 8, y - 24, 40 + b + 8, y + 24))
    t_box = G().cue(s["box_at"], s["_tok"])[0] - s["_t0"] if s.get("box_at") else 1.4
    ov = Image.new("RGBA", win.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for k, bx in enumerate(boxes):
        M.detect_box(od, bx, (124, 92, 196), M.spring(lt - t_box - k * 0.22, *M.PLAYFUL))
    win.alpha_composite(ov)
    q = ease_in_out(cl(lt / c.dur))
    ry, rx = lerp(-20, -7, q), lerp(12, 5, q)
    lay, quad = M.tilt(win, im.size, G().W / 2 - 40, G().H / 2 + 120, ry, rx, lerp(-2, 0, q), lerp(0.8, 0.86, q))
    sh = lay.getchannel("A").filter(ImageFilter.GaussianBlur(30)).point(lambda v: v * 50 // 255)
    shl = Image.new("RGBA", im.size, (30, 30, 70, 0))
    shl.putalpha(sh)
    im.alpha_composite(shl, (0, 24))
    im.alpha_composite(lay)
    draw_phrases(im, c, s)
    if s.get("curve_label"):
        lp = cl((lt - t_box - 0.6) / 0.5)
        if lp > 0:
            pts = M.bezier([(1380, 300), (1520, 236), (1690, 236), (1840, 290)])
            M.text_on_path(im, pts, s["curve_label"], F("sans_medium", 52), (124, 92, 196), 10, lp, lift=0)
    return arr(im)


def b_activity(c, s):
    """Live activity with an agent cursor; the destructive call lands, gets outlined red, and the verdict pops."""
    lt = c.lt
    im = ground(c.t, 1)
    feed = console.render("feed", s["feed"], lt, 1300)
    q = M.spring(lt, *M.DEFAULT)
    px, py = G().W / 2 - feed.width / 2, G().H / 2 - feed.height / 2 + 60
    paste_scaled(im, feed, G().W / 2, G().H / 2 + 60 + (1 - q) * 80, 1.0, min(1, q * 2))
    d = ImageDraw.Draw(im)
    M.spinner(d, G().W / 2 - 250, 150, 18, c.t, (124, 92, 196), 5)
    text(d, (G().W / 2 - 215, 150), s.get("status", "Inspecting every tool call"), F("sans_medium", 34), INK, -0.4, "lm", max_w=800)
    n = len(s["feed"]["items"])
    t_last = 0.3 + (n - 1) * s["feed"].get("every", 0.55)
    bp = M.spring(lt - t_last - 0.45, *M.SNAPPY)
    if bp > 0:
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        M.detect_box(ImageDraw.Draw(ov), (px + 52, py + 40 + 96 + 2, px + 40 + 1300 - 12, py + 40 + 96 + 82), PC["block"], bp, 30, 12, 4)
        im.alpha_composite(ov)
    kx, ky = cursor_path(lt, [(0, G().W - 200, G().H - 120), (1.2, G().W / 2 + 120, py + 400), (t_last + 0.3, G().W / 2 + 380, py + 190),
                              (c.dur, G().W / 2 + 420, py + 200)])
    cursor(im, kx, ky)
    lab = s.get("agent", "claude-code")
    halo = Image.new("L", im.size, 0)
    fw = F("sans_medium", 24)
    ImageDraw.Draw(halo).text((kx + 34, ky + 50), lab, font=fw, fill=255)
    halo = halo.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
    im.paste((255, 255, 255, 255), (0, 0), halo)
    ImageDraw.Draw(im).text((kx + 34, ky + 50), lab, font=fw, fill=PC["ink2"])
    return arr(im)


def b_approve2(c, s):
    """Approval card, cursor click, then a toast with a border beam confirming the decision."""
    lt = c.lt
    t_click = G().cue(s["click_at"], s["_tok"])[0] - s["_t0"] if isinstance(s.get("click_at"), str) else s.get("click_at", 1.6)
    s2 = dict(s, click_at=t_click)
    fr = base.b_approve(c, s2)
    im = Image.fromarray(fr).convert("RGBA")
    tp = M.spring(lt - t_click - 0.35, *M.SNAPPY)
    if tp > 0:
        w, hh = 760, 96
        toast = card(w, hh, 18)
        td = ImageDraw.Draw(toast)
        toast.alpha_composite(console.lucide("circle-check", 36, PC["allow"]), (28, 30))
        text(td, (80, hh / 2), s.get("toast", "Approved by Priya · this push only"), F("sans_medium", 30), INK, -0.3, "lm", max_w=w - 110)
        toast.alpha_composite(M.border_beam(toast.size, (1, 1, w - 2, hh - 2), 18, lt * 0.6, width=4))
        paste_scaled(im, toast, G().W / 2, 120 + (1 - tp) * -120, 1.0, min(1, tp * 2))
    return arr(im)


def b_structure(c, s):
    """A raw log card; tokens light up, then fly into a clean audit table."""
    lt = c.lt
    im = ground(c.t, -1)
    draw_phrases(im, c, s)
    rows = s["rows"]
    logw, logh = 720, 470
    lx, ly = 150, 330
    log = card(logw, logh, 20)
    ld = ImageDraw.Draw(log)
    mono(ld, (30, 40), "audit.log", 24, PC["ink3"], "lm")
    raw = s["raw"]
    fm = F("mono", 22)
    tok_pos = []
    for i, ln in enumerate(raw):
        y = 90 + i * 34
        mono(ld, (30, y), ln, 22, PC["ink2"], "lm", logw - 60)
        tok_pos.append(y)
    t_fly = G().cue(s["fly_at"], s["_tok"])[0] - s["_t0"] if s.get("fly_at") else 1.6
    q = M.spring(lt, *M.DEFAULT)
    paste_scaled(im, log, lx + logw / 2, ly + logh / 2 + (1 - q) * 60, 1.0, min(1, q * 2))
    tx, ty, tw = 980, 330, 800
    tq = M.spring(lt - t_fly + 0.3, *M.DEFAULT)
    cols = s["columns"]
    if tq > 0:
        tb = card(tw, 90 + 80 * len(rows), 20)
        td = ImageDraw.Draw(tb)
        x = 30
        for cn, cwf in cols:
            text(td, (x, 45), cn.upper(), F("sans_medium", 18), PC["ink3"], 1.4, "lm", max_w=cwf * tw)
            x += cwf * tw
        td.line((20, 80, tw - 20, 80), fill=PC["line"], width=2)
        paste_scaled(im, tb, tx + tw / 2, ty + tb.height / 2 + (1 - tq) * 60, 1.0, min(1, tq * 2))
    hl_col = [(255, 226, 120), (200, 190, 250), (170, 225, 245), (190, 235, 200)]
    d = ImageDraw.Draw(im)
    for r, row in enumerate(rows):
        for k, (val, src_line) in enumerate(row):
            src_x = fm.getlength(raw[src_line][:max(0, raw[src_line].find(val))], features=ui.CODE_FEATURES)
            tt = t_fly + r * 0.25 + k * 0.06
            hp = M.spring(lt - (t_fly - 0.9) - r * 0.2 - k * 0.05, *M.SNAPPY)
            sx = lx + 30 + src_x
            sy = ly + tok_pos[src_line]
            dx = tx + 30 + sum(cw for _, cw in cols[:k]) * tw
            dy = ty + 80 + 40 + r * 80
            fp = ease_in_out(cl((lt - tt) / 0.6))
            x, y = lerp(sx, dx, fp), lerp(sy, dy, fp) - math.sin(math.pi * fp) * 60
            fsz = int(lerp(22, 26, fp))
            f = F("mono", fsz) if k != 3 else F("sans_medium", fsz)
            wv = f.getlength(val, features=ui.CODE_FEATURES)
            if hp > 0 and fp < 1:
                d.rounded_rectangle((x - 6, y - 17, x + wv + 6, y + 17), 6, fill=hl_col[k % 4] + (int(220 * min(1, hp)),))
            col = console.vcol(val) if k == 3 and fp > 0.5 else INK
            if k == 3 and fp >= 1:
                d.ellipse((x - 2, y - 7, x + 12, y + 7), fill=col)
                d.text((x + 22, y), val, font=f, fill=col, anchor="lm")
            else:
                d.text((x, y), val, font=f, fill=col, anchor="lm", features=ui.CODE_FEATURES)
    return arr(im)


def b_hub(c, s):
    """Agents on the left, Prismor in the middle, tools on the right; beams draw in and pulses travel."""
    lt = c.lt
    im = ground(c.t, 1)
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    cxm, cym = G().W / 2, G().H / 2 + 40
    L, R = s["left"], s["right"]
    cw, ch = 330, 84
    xl, xr = 380, G().W - 380
    def ys(n):
        return [cym + (i - (n - 1) / 2) * (ch + 22) for i in range(n)]
    for side, items, xx, hdr in ((-1, L, xl, s.get("left_title", "Agents")), (1, R, xr, s.get("right_title", "Tools"))):
        hq = pr(lt, 0.1, 0.4)
        M.kinetic(lay, [[(hdr, True)]], 44, [0.1 if side < 0 else 0.3], lt, c.t, xx, ys(len(items))[0] - 100)
        for i, (it, y) in enumerate(zip(items, ys(len(items)))):
            t0 = 0.3 + i * 0.12 + (0.5 if side > 0 else 0)
            q = M.spring(lt - t0, *M.SNAPPY)
            if q <= 0:
                continue
            a = (xx - side * -cw / 2, y) if False else (xx + (cw / 2 if side < 0 else -cw / 2), y)
            b = (cxm + side * 110, cym)
            pts = M.bezier([a, (a[0] + (b[0] - a[0]) * 0.5, a[1]), (a[0] + (b[0] - a[0]) * 0.5, b[1]), b], 60)
            M.beam(ld, pts, cl((lt - t0 - 0.2) / 0.6), c.t, (160, 164, 190, 200), (124, 92, 196), 3, 0.7, i * 0.17)
            cd = G().cache(("hcard", it["name"]), lambda: _hub_card(it, cw, ch))
            paste_scaled(lay, cd, xx, y + (1 - q) * 30, 1.0, min(1, q * 2))
    im.alpha_composite(lay)
    q = M.spring(lt - 0.15, *M.PLAYFUL)
    disc = G().cache("hubdisc", lambda: _disc(210))
    paste_scaled(im, disc, cxm, cym, q, min(1, q * 2))
    return arr(cam(im, c, s))


def _hub_card(it, cw, ch):
    cd = card(cw, ch, 18, WHITE, (220, 222, 230))
    ico = icon_img(it["icon"], 44)
    cd.alpha_composite(ico, (26, (ch - 44) // 2))
    text(ImageDraw.Draw(cd), (88, ch / 2), it["name"], F("sans_medium", 30), INK, -0.3, "lm", max_w=cw - 110)
    return cd


def _disc(sz):
    d = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    ImageDraw.Draw(d).ellipse((0, 0, sz - 1, sz - 1), fill=WHITE + (255,), outline=(220, 222, 230, 255), width=3)
    lg = logo_lockup(int(sz * 0.5))
    d.alpha_composite(lg, ((sz - lg.width) // 2, (sz - lg.height) // 2))
    return d


def b_end(c, s):
    lt = c.lt
    im = ground(c.t, 1)
    f = F("sans_medium", 130)
    lg = logo_lockup(130)
    name = s.get("name", "Prismor")
    nw = text_width(name, f, -2.6)
    x0 = G().W / 2 - (lg.width + 36 + nw) / 2
    y = G().H / 2 - 90
    q = M.spring(lt - 0.05, *M.PLAYFUL)
    paste_scaled(im, lg, x0 + lg.width / 2, y, q, min(1, q * 2), shadow=False)
    M.kinetic(im, [[(name, False)]], 130, [0.15], lt, c.t, x0 + lg.width + 36 + nw / 2, y, spring_kd=M.DEFAULT)
    t_tag = G().cue(s["tag_at"], s["_tok"])[0] - s["_t0"]
    tl = M.parse(s["tagline"])
    M.kinetic(im, [tl], 52, [t_tag + i * 0.07 for i in range(len(tl))], lt, c.t, G().W / 2, y + 130)
    up = M.spring(lt - t_tag - 0.8, *M.SNAPPY)
    if up > 0:
        d = ImageDraw.Draw(im)
        fu = F("sans_medium", 44)
        url = s.get("url", "prismor.dev")
        uw = text_width(url, fu, -0.5)
        ux, uy = G().W / 2 - uw / 2, y + 250 + (1 - up) * 30
        text(d, (ux, uy), url, fu, INK, -0.5, "lm", max_w=800)
        t_click = t_tag + 1.9
        ul = ease_out(cl((lt - t_click) / 0.35))
        d.line((ux, uy + 34, ux + uw * max(ul, 0.0), uy + 34), fill=INK, width=3)
        kx, ky = cursor_path(lt, [(t_tag + 0.8, G().W / 2 + 420, G().H + 40), (t_click - 0.1, ux + uw * 0.7, uy + 6), (c.dur, ux + uw * 0.75, uy + 14)])
        cursor(im, kx, ky, cl(1 - abs(lt - t_click) / 0.16))
    bk = pr(lt, c.dur - 0.5, 0.45)
    a = arr(im)
    return (a * (1 - bk)).astype(np.uint8) if bk > 0 else a


BEATS = {"kin": b_kin, "windows": b_windows, "paths": b_paths, "meet": b_meet, "logos": b_logos, "tilt": b_tilt,
         "activity": b_activity, "approve2": b_approve2, "structure": b_structure, "hub": b_hub, "end": b_end}


# ------------------------------------------------------------------ sound design
def sfx_events(tl, brief):
    ev = []
    for sc, st, b in zip(tl.scenes, tl.starts, brief["beats"]):
        ev.append((max(0, st - 0.12), "whoosh", 0.10))
        cue = lambda k: G().cue(k, b["_tok"])[0]
        ty = b["type"]
        if ty == "meet":
            ev += [(st + 0.25, "pop", 0.25), (cue(b["name_at"]), "thump", 0.3)]
        if ty in ("logos",):
            ev += [(cue(it["at"]), "pop", 0.18) for it in b["items"]]
        if ty == "paths":
            ev += [(cue(it["at"]), "tick", 0.15) for it in b["items"]]
        if ty == "windows":
            ev += [(cue(it["at"]), "tick", 0.12) for it in b["items"]]
        if ty == "tilt":
            t_box = cue(b["box_at"])
            ev += [(t_box + k * 0.22, "tick", 0.2) for k in range(3)]
        if ty == "approve2":
            t_click = cue(b["click_at"])
            ev += [(t_click, "click", 0.35), (t_click + 0.35, "pop", 0.2)]
        if ty == "activity":
            n = len(b["feed"]["items"])
            ev += [(st + 0.3 + k * b["feed"].get("every", 0.55), "tick", 0.07) for k in range(n)]
        if ty == "hub":
            ev += [(st + 0.15, "pop", 0.2)]
        if ty == "end":
            t_tag = cue(b["tag_at"])
            ev += [(st + 0.05, "thump", 0.3), (t_tag + 1.9, "click", 0.35)]
    return ev


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "voice", "check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "prismor", "brief.json"))
    ap.add_argument("--out")
    a = ap.parse_intermixed_args()
    if a.cmd == "init":
        import shutil
        dst = os.path.abspath(a.args[0] if a.args else "film")
        if os.path.exists(dst):
            sys.exit(f"{dst} already exists")
        shutil.copytree(os.path.join(HERE, "..", "examples", "prismor"), dst, ignore=shutil.ignore_patterns("out", ".vo_*", "mix.wav"))
        print(f"created {dst}: rewrite vo.txt (no-ai-slop), swap assets/logo.png and icons, then voice → check → still → render")
        return
    if a.cmd == "voice":
        import subprocess
        bdir = os.path.dirname(os.path.abspath(a.brief))
        brief = json.load(open(a.brief))
        vo = brief["vo"]
        script = open(os.path.join(bdir, vo["script"])).read().strip()
        wav = narration.tts(script, os.path.join(bdir, "vo.wav"), model=vo.get("model", "gpt-4o-mini-tts-2025-12-15"),
                            voice=vo.get("voice", "marin"), instructions=vo.get("instructions"))
        json.dump(narration.transcribe_windows(wav), open(os.path.join(bdir, vo["words"]), "w"), indent=1)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "aac", "-b:a", "128k", os.path.join(bdir, vo["audio"])], check=True)
        print("voice ok")
        return
    base.BEATS.update(BEATS)
    tl, brief = base.build(a.brief)
    for sc in tl.scenes:                                  # blur swaps between beats, like the reference
        if sc.transition is None and sc is not tl.scenes[0]:
            sc.transition = Dissolve(0.28, 14)
    bdir = os.path.dirname(os.path.abspath(a.brief))
    out = os.path.join(bdir, "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 3)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep + ["! " + w for w in overflow_report(warn=True)]:
            print("  ", r)
        for sc, st in zip(tl.scenes, tl.starts):
            print(f"  {st:6.2f}s  {sc.dur:5.2f}s  {sc.name}")
        print(f"{tl.duration:.2f} s, {len(tl.scenes)} beats")
    elif a.cmd == "still":
        for x in a.args or ["2"]:
            print(tl.still(float(x), os.path.join(out, f"still_{float(x):05.2f}.png")), "·", tl.scene_at(float(x)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png"), 6, 4, 320))
    else:
        audio = None
        if G().audio:
            audio = M.mix(G().audio, sfx_events(tl, brief), os.path.join(bdir, "mix.wav"))
        print(tl.render(a.out or os.path.join(out, "film.mp4"), audio))


if __name__ == "__main__":
    main()
