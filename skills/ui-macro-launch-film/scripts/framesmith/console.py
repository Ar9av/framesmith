"""Enterprise-console components, rebuilt natively from Prismor's admin console (prismor-web-preview).

Each component renders a panel as RGBA at a native width, animated by `lt` (seconds since it appeared):
numbers count up, rows stream in, stages light in order. Palette follows the console's `--pc-*` tokens
(green = allowed, amber = warned, red = blocked, violet = redacted). Status is typeset (dot + word),
never boxed in pills.

    from framesmith import console
    im = console.render("posture", data, lt)            # -> RGBA panel
    console.COMPONENTS                                   # names -> renderer
"""
import math, os, urllib.request

from PIL import Image, ImageDraw, ImageFilter

from .easing import ease_in_out, ease_out, lerp, h
from .typography import F, text, text_width
from .media import icon, rasterize_svg

# --pc-* tokens (oklch in globals.css, converted to sRGB)
PC = {
    "surface": (255, 255, 255), "inset": (247, 248, 249), "canvas": (242, 243, 245),
    "ink": (30, 33, 38), "ink2": (98, 102, 111), "ink3": (154, 158, 166),
    "line": (236, 238, 240), "line_strong": (225, 227, 230),
    "allow": (47, 158, 90), "warn": (224, 118, 31), "block": (220, 74, 74), "info": (47, 124, 240),
    "redact": (124, 92, 196),
}
VERDICT = {"allowed": "allow", "allow": "allow", "blocked": "block", "block": "block", "warned": "warn",
           "would block": "warn", "observe": "warn", "held": "warn", "redacted": "redact", "cloaked": "redact",
           "masked": "redact", "operating": "allow", "partial": "warn", "not configured": "ink3",
           "enforcing": "allow", "observing": "warn", "paused": "block", "online": "allow", "stale": "warn",
           "deny": "block", "strong": "allow", "fair": "warn", "at risk": "block"}
LUCIDE_URL = "https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{}.svg"
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "framesmith", "lucide")


def tint(c, k=0.9):
    return tuple(int(v + (255 - v) * k) for v in c)


def vcol(word):
    return PC[VERDICT.get(word.lower(), "ink2")]


def lucide(name, size, color):
    """A Lucide line icon (ISC), cached under ~/.cache/framesmith/lucide."""
    os.makedirs(CACHE, exist_ok=True)
    svg = os.path.join(CACHE, name + ".svg")
    if not os.path.exists(svg):
        with open(svg, "wb") as f:
            f.write(urllib.request.urlopen(LUCIDE_URL.format(name), timeout=60).read())
    if not os.path.exists(svg[:-4] + ".png"):
        rasterize_svg(svg, svg[:-4] + ".png")
    return icon(svg, int(size), tuple(color))


def _p(lt, t0, dur=0.4):
    return ease_out(min(1.0, max(0.0, (lt - t0) / dur)))


def _mix(a, b, p):
    return tuple(int(lerp(x, y, p)) for x, y in zip(a, b))


def card(w, hgt, r=16):
    """A console surface: white, hairline border, soft multi-stop lift (like --pc-lift)."""
    pad = 40
    im = Image.new("RGBA", (w + pad * 2, hgt + pad * 2), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + w, pad + hgt + 10), r, fill=40)
    im.paste((10, 14, 30, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + hgt), r, fill=PC["surface"] + (255,),
                                         outline=PC["line_strong"] + (255,), width=2)
    return im, pad


def header(d, x, y, w, title, sub=None, right=None):
    text(d, (x, y), title, F("sans_medium", 30), PC["ink"], -0.3, "lm", max_w=w * 0.6)
    if sub:
        text(d, (x, y + 36), sub, F("sans", 22), PC["ink2"], 0, "lm", max_w=w * 0.7)
    if right:
        text(d, (x + w, y), right, F("sans", 22), PC["ink3"], 0, "rm", max_w=w * 0.35)


def status(d, x, y, word, size=22, anchor="lm", strong=True):
    """Typeset status: coloured dot + coloured word (the console's pill, minus the pill)."""
    col = vcol(word)
    f = F("sans_medium" if strong else "sans", size)
    w = f.getlength(word) + size * 0.9
    if anchor[0] == "r":
        x -= w
    d.ellipse((x, y - size * 0.22, x + size * 0.44, y + size * 0.22), fill=col)
    d.text((x + size * 0.8, y), word, font=f, fill=col, anchor="lm")
    return w


def label(d, x, y, s, w=None, color=None):
    text(d, (x, y), s.upper(), F("sans_medium", 17), color or PC["ink3"], 1.4, "lm", max_w=w)


def count(value, p):
    """'1,482' / '0.4%' / '38 ms' counted up to p."""
    import re
    m = re.search(r"[\d,.]+", str(value))
    if not m:
        return str(value)
    raw = m.group()
    v = float(raw.replace(",", "")) * p
    body = f"{v:,.0f}" if "," in raw else (f"{v:.1f}" if "." in raw else f"{v:.0f}")
    return str(value)[:m.start()] + body + str(value)[m.end():]


# ------------------------------------------------------------------ components
def posture(data, lt, w=1400):
    """PostureBar: score ring + three pillars + coverage-gaps note."""
    hgt = 210
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    score = data.get("score", 92)
    p = ease_out(min(1, max(0, (lt - 0.2) / 1.2)))
    s_now = score * p
    tone = "Strong" if score >= 85 else "Fair" if score >= 60 else "At risk"
    cx, cy, r = x0 + 110, y0 + hgt / 2, 62
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=PC["line"], width=12)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * s_now / 100, fill=vcol(tone), width=12)
    text(d, (cx, cy + 4), f"{s_now:.0f}", F("sans_medium", 50), PC["ink"], -1, "mm")
    tx = cx + r + 40
    text(d, (tx, cy - 34), data.get("title", "Security posture"), F("sans_medium", 32), PC["ink"], -0.3, "lm", max_w=300)
    status(d, tx, cy + 6, tone, 24)
    text(d, (tx, cy + 40), "across code, fixes & runtime", F("sans", 20), PC["ink2"], 0, "lm", max_w=290)
    sx0 = x0 + 540
    gx = x0 + w - 270
    pills = data.get("pillars", [])
    pw = (gx - 40 - sx0) / max(1, len(pills))
    for k, pl in enumerate(pills):
        pp = _p(lt, 0.5 + k * 0.15)
        x = sx0 + k * pw
        d.line((x - 20, y0 + 40, x - 20, y0 + hgt - 40), fill=PC["line"], width=2)
        ic = lucide(pl.get("icon", "shield-check"), 34, _mix(PC["surface"], PC["ink2"], pp))
        im.alpha_composite(ic, (int(x), int(cy - 52)))
        label(d, x + 48, cy - 36, pl["label"], pw - 60, _mix(PC["surface"], PC["ink3"], pp))
        text(d, (x, cy + 12), count(pl["value"], pp), F("sans_medium", 38), _mix(PC["surface"], PC["ink"], pp), -0.5, "lm", max_w=pw - 20)
        if pl.get("sub"):
            text(d, (x, cy + 52), pl["sub"], F("sans", 20), _mix(PC["surface"], PC["ink3"], pp), 0, "lm", max_w=pw - 20)
    d.line((gx - 20, y0 + 40, gx - 20, y0 + hgt - 40), fill=PC["line"], width=2)
    gp = _p(lt, 1.2)
    gaps = data.get("gaps", 0)
    col = PC["warn"] if gaps else PC["allow"]
    ic = lucide("triangle-alert" if gaps else "circle-check", 30, _mix(PC["surface"], col, gp))
    im.alpha_composite(ic, (int(gx), int(cy - 16)))
    text(d, (gx + 44, cy), f"{gaps} coverage gap{'s' if gaps != 1 else ''}" if gaps else "No coverage gaps", F("sans_medium", 24),
         _mix(PC["surface"], col, gp), 0, "lm", max_w=250)
    return im


def kpis(data, lt, w=1400):
    """KpiStrip: four metric cards counting up, each with a tiny sparkline."""
    items = data["items"]
    gap = 24
    cw = (w - gap * (len(items) - 1)) / len(items)
    hgt = 190
    out = Image.new("RGBA", (w + 80, hgt + 80), (0, 0, 0, 0))
    for k, it in enumerate(items):
        c, pad = card(int(cw), hgt, 14)
        d = ImageDraw.Draw(c)
        pp = _p(lt, 0.15 + k * 0.12, 0.9)
        ic = lucide(it.get("icon", "activity"), 28, PC["ink3"])
        c.alpha_composite(ic, (pad + 26, pad + 26))
        label(d, pad + 66, pad + 40, it["label"], cw - 90)
        text(d, (pad + 26, pad + 108), count(it["value"], pp), F("sans_medium", 56), PC["ink"], -1, "lm", max_w=cw - 52)
        if it.get("sub"):
            text(d, (pad + 26, pad + 160), it["sub"], F("sans", 20), vcol(it.get("tone", "")) if it.get("tone") else PC["ink3"], 0, "lm",
                 max_w=cw - 170)
        pts = [(pad + cw - 146 + i * 10.5, pad + 172 - 26 * (0.3 + 0.7 * h(k, i))) for i in range(12)]
        n = max(2, int(len(pts) * min(1, max(0, (lt - 0.3 - k * 0.12) / 0.8))))
        d.line(pts[:n], fill=tint(PC["info"], 0.35), width=3, joint="curve")
        out.alpha_composite(c, (int(k * (cw + gap)), 0))
    return out


def guard(data, lt, w=1300):
    """GuardPipeline: one event walks POLICY -> IAM -> SCOPED; the deciding stage trips."""
    hgt = 330
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 96), 16, fill=PC["inset"])
    d.rectangle((x0, y0 + 80, x0 + w, y0 + 96), fill=PC["inset"])
    d.line((x0, y0 + 96, x0 + w, y0 + 96), fill=PC["line"], width=2)
    label(d, x0 + 30, y0 + 32, data.get("kind", "Bash · tool call"), w * 0.5)
    text(d, (x0 + 30, y0 + 66), data["call"], F("mono", 26), PC["ink"], 0, "lm", max_w=w - 320)
    stages = data.get("stages", ["POLICY", "IAM", "SCOPED"])
    trip = data.get("trip", 1)
    verdict = data.get("verdict", "Blocked")
    done_t = 0.5 + len(stages) * 0.5
    if lt > min(done_t, 0.5 + (trip + 1) * 0.5):
        status(d, x0 + w - 30, y0 + 50, verdict, 26, "rm")
    sw = (w - 60 - 60 * (len(stages) - 1)) / len(stages)
    icons = data.get("icons", ["scale", "user-round", "zap"])
    for k, st in enumerate(stages):
        t0 = 0.5 + k * 0.5
        on = lt >= t0
        tripped = k == trip and on
        passed = on and k < trip
        after = k > trip
        x = x0 + 30 + k * (sw + 60)
        y = y0 + 140
        col = PC["block"] if tripped else PC["allow"] if passed else PC["ink3"]
        fill = tint(PC["block"], 0.92) if tripped else tint(PC["allow"], 0.93) if passed else PC["surface"]
        pp = _p(lt, t0, 0.3)
        d.rounded_rectangle((x, y, x + sw, y + 96), 14, fill=_mix(PC["surface"], fill, pp),
                            outline=_mix(PC["line_strong"], tint(col, 0.5), pp), width=2)
        im.alpha_composite(lucide(icons[k % len(icons)], 32, _mix(PC["ink3"], col, pp)), (int(x + 22), int(y + 32)))
        text(d, (x + 72, y + 36), st, F("sans_medium", 24), PC["ink"], 1.5, "lm", max_w=sw - 90)
        sub = "tripped" if tripped else "passed" if passed else ("skipped" if after and lt > done_t else "waiting")
        text(d, (x + 72, y + 66), sub.upper(), F("sans_medium", 16), _mix(PC["ink3"], col, pp), 1.2, "lm", max_w=sw - 90)
        if k:
            ax = x - 44
            d.line((ax, y + 48, ax + 28, y + 48), fill=PC["ink3"], width=3)
            d.polygon([(ax + 28, y + 40), (ax + 38, y + 48), (ax + 28, y + 56)], fill=PC["ink3"])
    if lt > 0.5 + (trip + 1) * 0.5:
        fp = _p(lt, 0.5 + (trip + 1) * 0.5)
        msg = data.get("why", f"{verdict} at the {stages[trip]} stage")
        text(d, (x0 + 30, y0 + 282), msg, F("sans", 24), _mix(PC["surface"], PC["ink2"], fp), 0, "lm", max_w=w - 60)
    return im


def trust(data, lt, w=1400):
    """Agent trust card: name + state, then four facts (policy boundary, least privilege, evidence, outcomes)."""
    hgt = 300
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 110), 16, fill=PC["inset"])
    d.rectangle((x0, y0 + 94, x0 + w, y0 + 110), fill=PC["inset"])
    d.line((x0, y0 + 110, x0 + w, y0 + 110), fill=PC["line"], width=2)
    im.alpha_composite(lucide("bot", 40, PC["ink"]), (x0 + 30, y0 + 34))
    text(d, (x0 + 88, y0 + 42), data["agent"], F("sans_medium", 32), PC["ink"], -0.3, "lm", max_w=500)
    text(d, (x0 + 88, y0 + 78), data.get("sub", "Agent trust card"), F("sans", 22), PC["ink2"], 0, "lm", max_w=600)
    if lt > 0.3:
        status(d, x0 + w - 30, y0 + 55, data.get("state", "Enforcing"), 26, "rm")
    facts = data["facts"]
    fw = w / len(facts)
    for k, fct in enumerate(facts):
        pp = _p(lt, 0.4 + k * 0.15)
        x = x0 + k * fw + 30
        if k:
            d.line((x0 + k * fw, y0 + 130, x0 + k * fw, y0 + hgt - 20), fill=PC["line"], width=2)
        col = PC["block"] if fct.get("danger") else PC["ink3"]
        im.alpha_composite(lucide(fct.get("icon", "lock"), 24, _mix(PC["surface"], col, pp)), (int(x), int(y0 + 150)))
        label(d, x + 36, y0 + 162, fct["label"], fw - 80, _mix(PC["surface"], col, pp))
        text(d, (x, y0 + 214), fct["value"], F("sans_medium", 30), _mix(PC["surface"], PC["block"] if fct.get("danger") else PC["ink"], pp), -0.3,
             "lm", max_w=fw - 60)
        text(d, (x, y0 + 256), fct.get("detail", ""), F("sans", 20), _mix(PC["surface"], PC["ink3"], pp), 0, "lm", max_w=fw - 60)
    return im


def table(data, lt, w=1400):
    """Console table (coverage, shadow AI findings, devices): header row, rows streaming in; cells may be
    'status:<word>', 'mono:<text>', 'muted:<text>' or 'icon:<lucide>|<text>'."""
    rows = data["rows"]
    cols = data["columns"]
    rh = 74
    top = 110 if data.get("title") else 20
    hgt = top + 56 + rh * len(rows) + 16
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    if data.get("title"):
        header(d, x0 + 30, y0 + 40, w - 60, data["title"], None, data.get("right"))
        if data.get("sub"):
            text(d, (x0 + 30, y0 + 78), data["sub"], F("sans", 22), PC["ink2"], 0, "lm", max_w=w - 60)
    xs, x = [], x0 + 30
    for cdef in cols:
        xs.append(x)
        x += cdef["w"] * (w - 60)
    hy = y0 + top + 26
    d.rectangle((x0, hy - 26, x0 + w, hy + 28), fill=PC["inset"])
    for k, cdef in enumerate(cols):
        label(d, xs[k], hy, cdef["title"], cdef["w"] * (w - 60) - 16)
    d.line((x0, hy + 28, x0 + w, hy + 28), fill=PC["line"], width=2)
    for r, row in enumerate(rows):
        t0 = row.get("t", 0.3 + r * data.get("every", 0.16))
        if lt < t0:
            continue
        pp = _p(lt, t0, 0.3)
        y = hy + 28 + rh * r + rh / 2
        if row.get("hl") and lt > row.get("hl_at", 0):
            d.rectangle((x0 + 2, y - rh / 2 + 1, x0 + w - 2, y + rh / 2 - 1), fill=tint(PC[row.get("hl_tone", "warn")], 0.94))
        for k, cell in enumerate(row["cells"]):
            cw = cols[k]["w"] * (w - 60) - 20
            xx = xs[k] + (1 - pp) * 18
            cell = str(cell)
            if cell.startswith("status:"):
                status(d, xx, y, cell[7:], 22)
            elif cell.startswith("icon:"):
                nm, _, tx = cell[5:].partition("|")
                im.alpha_composite(lucide(nm, 26, _mix(PC["surface"], PC["ink2"], pp)), (int(xx), int(y - 13)))
                text(d, (xx + 38, y), tx, F("sans", 24), _mix(PC["surface"], PC["ink"], pp), 0, "lm", max_w=cw - 38)
            elif cell.startswith("mono:"):
                text(d, (xx, y), cell[5:], F("mono", 22), _mix(PC["surface"], PC["ink2"], pp), 0, "lm", max_w=cw)
            elif cell.startswith("muted:"):
                text(d, (xx, y), cell[6:], F("sans", 22), _mix(PC["surface"], PC["ink3"], pp), 0, "lm", max_w=cw)
            else:
                text(d, (xx, y), cell, F("sans_medium" if k == 0 else "sans", 24), _mix(PC["surface"], PC["ink"], pp), 0, "lm", max_w=cw)
        if r < len(rows) - 1:
            d.line((x0 + 30, y + rh / 2, x0 + w - 30, y + rh / 2), fill=PC["line"], width=1)
    return im


def shadow(data, lt, w=1400):
    """Shadow AI: fleet-coverage ring + three finding counters, over a findings table."""
    stats_h = 200
    im, pad = card(w, stats_h)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    cov = data.get("coverage", 86)
    p = ease_out(min(1, max(0, (lt - 0.2) / 1.2)))
    cx, cy, r = x0 + 100, y0 + stats_h / 2, 58
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=PC["line"], width=12)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * cov / 100 * p, fill=PC["info"], width=12)
    text(d, (cx, cy + 3), f"{cov * p:.0f}%", F("sans_medium", 34), PC["ink"], -0.5, "mm")
    label(d, cx + r + 34, cy - 20, "Fleet coverage", 300)
    text(d, (cx + r + 34, cy + 20), data.get("coverage_sub", "devices running Prismor hooks"), F("sans", 22), PC["ink2"], 0, "lm", max_w=330)
    stats = data["stats"]
    sx = x0 + 600
    sw = (w - 620) / len(stats)
    for k, st in enumerate(stats):
        pp = _p(lt, 0.5 + k * 0.15, 0.8)
        x = sx + k * sw
        d.line((x - 20, y0 + 36, x - 20, y0 + stats_h - 36), fill=PC["line"], width=2)
        im.alpha_composite(lucide(st.get("icon", "radar"), 28, PC["warn"] if st.get("warn") else PC["ink3"]), (int(x), int(cy - 58)))
        label(d, x + 40, cy - 44, st["label"], sw - 60)
        text(d, (x, cy + 10), count(st["value"], pp), F("sans_medium", 50), PC["warn"] if st.get("warn") else PC["ink"], -1, "lm", max_w=sw - 30)
        text(d, (x, cy + 56), st.get("hint", ""), F("sans", 18), PC["ink3"], 0, "lm", max_w=sw - 30)
    if data.get("rows"):
        tb = table({"columns": data["columns"], "rows": data["rows"], "every": 0.2}, lt - 0.9, w)
        out = Image.new("RGBA", (im.width, im.height + tb.height - 50), (0, 0, 0, 0))
        out.alpha_composite(im, (0, 0))
        out.alpha_composite(tb, (0, im.height - 50))
        return out
    return im


def egress(data, lt, w=1400):
    """Network egress: mode selector (typeset, chevron on the active one) + allowed / denied destinations."""
    lists = data["lists"]
    rows = max(len(l["hosts"]) for l in lists)
    hgt = 220 + rows * 64 + 30
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    header(d, x0 + 30, y0 + 44, w - 60, data.get("title", "Network egress"), data.get("sub"))
    mx = x0 + 30
    for k, m in enumerate(data.get("modes", ["Disabled", "Observe", "Enforce"])):
        on = k == data.get("active", 2) and lt > data.get("switch_at", 0.6)
        f = F("sans_medium", 26)
        col = PC["ink"] if on else PC["ink3"]
        if on:
            d.line((mx - 4, y0 + 172, mx + f.getlength(m) + 4, y0 + 172), fill=PC["ink"], width=3)
        d.text((mx, y0 + 146), m, font=f, fill=col, anchor="lm")
        mx += f.getlength(m) + 50
    colw = (w - 90) / len(lists)
    for li, lst in enumerate(lists):
        x = x0 + 30 + li * (colw + 30)
        tone = "allow" if lst.get("tone", "allow") == "allow" else "block"
        label(d, x, y0 + 212, lst["title"], colw, PC[tone])
        for r, host in enumerate(lst["hosts"]):
            t0 = 0.8 + r * 0.15 + li * 0.3
            if lt < t0:
                continue
            pp = _p(lt, t0, 0.3)
            y = y0 + 262 + r * 64
            d.rounded_rectangle((x, y - 24, x + colw, y + 24), 10, fill=_mix(PC["surface"], PC["inset"], pp), outline=PC["line"])
            im.alpha_composite(lucide("globe" if tone == "allow" else "ban", 22, _mix(PC["surface"], PC[tone], pp)), (int(x + 16), int(y - 11)))
            text(d, (x + 52, y), host, F("mono", 22), _mix(PC["surface"], PC["ink"], pp), 0, "lm", max_w=colw - 70)
    return im


def proof(data, lt, w=1400):
    """Security proof pack: headline metrics, then control-assurance rows (Operating / Partial / Not configured)."""
    ctr = data["controls"]
    hgt = 330 + len(ctr) * 64
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    header(d, x0 + 30, y0 + 44, w - 60, data.get("title", "Security proof pack"), data.get("sub", "Evidence-based report"), data.get("period", "Last 30 days"))
    mets = data["metrics"]
    mw = (w - 60) / len(mets)
    for k, m in enumerate(mets):
        pp = _p(lt, 0.3 + k * 0.12, 1.0)
        x = x0 + 30 + k * mw
        label(d, x, y0 + 140, m["label"], mw - 20)
        text(d, (x, y0 + 194), count(m["value"], pp), F("sans_medium", 50), PC["ink"], -1, "lm", max_w=mw - 20)
    d.line((x0 + 30, y0 + 250, x0 + w - 30, y0 + 250), fill=PC["line"], width=2)
    label(d, x0 + 30, y0 + 282, "Control assurance", 400)
    for r, cc in enumerate(ctr):
        t0 = 0.9 + r * 0.18
        if lt < t0:
            continue
        pp = _p(lt, t0, 0.3)
        y = y0 + 330 + r * 64
        text(d, (x0 + 30 + (1 - pp) * 16, y), cc["name"], F("sans", 26), _mix(PC["surface"], PC["ink"], pp), 0, "lm", max_w=w * 0.45)
        text(d, (x0 + w * 0.5, y), cc.get("ref", ""), F("mono", 20), _mix(PC["surface"], PC["ink3"], pp), 0, "lm", max_w=w * 0.25)
        status(d, x0 + w - 30, y, cc["state"], 22, "rm")
        if r < len(ctr) - 1:
            d.line((x0 + 30, y + 32, x0 + w - 30, y + 32), fill=PC["line"], width=1)
    return im


def feed(data, lt, w=1400):
    """Live activity: newest decision slides in at the top; verdict typeset on the right."""
    items = data["items"]
    rh, n = 84, data.get("visible", 6)
    hgt = 110 + rh * n
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    header(d, x0 + 30, y0 + 44, w - 60, data.get("title", "Live activity"), None, None)
    if (int(lt * 2) % 2) == 0:
        d.ellipse((x0 + w - 150, y0 + 36, x0 + w - 136, y0 + 50), fill=PC["allow"])
    text(d, (x0 + w - 30, y0 + 44), "Streaming", F("sans", 22), PC["ink2"], 0, "rm")
    every = data.get("every", 0.55)
    shown = [k for k in range(len(items)) if lt >= 0.3 + k * every]
    area = Image.new("RGBA", (w, rh * n), (0, 0, 0, 0))
    ad = ImageDraw.Draw(area)
    for j, k in enumerate(reversed(shown)):
        it = items[k]
        age = lt - (0.3 + k * every)
        pp = ease_out(min(1, age / 0.35))
        y = (j - 1 + pp) * rh + rh / 2
        if y > rh * n:
            continue
        a = pp if j == 0 else 1
        if j == 0 and pp < 1:
            ad.rectangle((0, y - rh / 2, w, y + rh / 2), fill=tint(PC["info"], 0.95))
        area.alpha_composite(lucide(it.get("icon", "terminal"), 28, _mix(PC["surface"], PC["ink2"], a)), (30, int(y - 14)))
        text(ad, (80, y - 14), it["title"], F("sans_medium", 25), _mix(PC["surface"], PC["ink"], a), 0, "lm", max_w=w * 0.5)
        text(ad, (80, y + 18), it.get("detail", ""), F("mono", 19), _mix(PC["surface"], PC["ink3"], a), 0, "lm", max_w=w * 0.5)
        text(ad, (w * 0.6, y), it.get("who", ""), F("sans", 22), _mix(PC["surface"], PC["ink2"], a), 0, "lm", max_w=w * 0.22)
        status(ad, w - 30, y, it["verdict"], 22, "rm")
        ad.line((30, y + rh / 2, w - 30, y + rh / 2), fill=PC["line"], width=1)
    im.alpha_composite(area, (x0, y0 + 96))
    return im


def mcp(data, lt, w=1400):
    """MCP gateway: agents on the left, the gateway in the middle, servers on the right; calls travel through."""
    hgt = 520
    im, pad = card(w, hgt)
    d = ImageDraw.Draw(im)
    x0, y0 = pad, pad
    header(d, x0 + 30, y0 + 44, w - 60, data.get("title", "MCP gateway"), data.get("sub", "One connector in front of every MCP server"))
    gx, gy = x0 + w / 2, y0 + 300
    agents, servers = data["agents"], data["servers"]
    def col_pts(n, x):
        return [(x, y0 + 150 + (hgt - 190) * (i + 0.5) / n) for i in range(n)]
    ap, sp = col_pts(len(agents), x0 + 200), col_pts(len(servers), x0 + w - 230)
    for i, (x, y) in enumerate(ap + sp):
        d.line((x, y, gx, gy), fill=PC["line_strong"], width=2)
    period = data.get("period", 1.4)
    for i in range(len(agents)):                             # a call pulse from each agent through the gateway
        ph = ((lt - 0.4 - i * 0.35) % period) / period if lt > 0.4 + i * 0.35 else -1
        if ph < 0:
            continue
        (ax, ay) = ap[i]
        tx, ty = sp[i % len(sp)]
        if ph < 0.5:
            q = ph / 0.5
            x, y = lerp(ax, gx, q), lerp(ay, gy, q)
        else:
            q = (ph - 0.5) / 0.5
            x, y = lerp(gx, tx, q), lerp(gy, ty, q)
        blocked = data.get("block_agent") == i and ph >= 0.5
        if not blocked:
            d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=PC["info"] if data.get("block_agent") != i else PC["warn"])
        elif ph < 0.75:
            q = (ph - 0.5) / 0.25
            rr = 80 + 60 * q
            d.rounded_rectangle((gx - rr * 1.4, gy - rr, gx + rr * 1.4, gy + rr), 26, outline=tint(PC["block"], 0.3 + 0.7 * q), width=4)
    for i, (nm, (x, y)) in enumerate(zip(agents, ap)):
        d.rounded_rectangle((x - 170, y - 30, x + 20, y + 30), 12, fill=PC["surface"], outline=PC["line_strong"], width=2)
        text(d, (x - 150, y), nm, F("sans", 24), PC["ink"], 0, "lm", max_w=160)
    for i, (nm, (x, y)) in enumerate(zip(servers, sp)):
        d.rounded_rectangle((x - 20, y - 30, x + 200, y + 30), 12, fill=PC["surface"], outline=PC["line_strong"], width=2)
        im.alpha_composite(lucide("server", 22, PC["ink3"]), (int(x), int(y - 11)))
        text(d, (x + 36, y), nm, F("mono", 22), PC["ink"], 0, "lm", max_w=150)
    d.rounded_rectangle((gx - 110, gy - 70, gx + 110, gy + 70), 20, fill=PC["ink"])
    im.alpha_composite(lucide("shield-check", 40, (255, 255, 255)), (int(gx - 20), int(gy - 44)))
    text(d, (gx, gy + 30), "Prismor gateway", F("sans_medium", 20), (255, 255, 255), 0, "mm", max_w=200)
    if data.get("note"):
        text(d, (x0 + w / 2, y0 + hgt - 24), data["note"], F("sans", 22), PC["ink2"], 0, "mm", max_w=w - 80)
    return im


COMPONENTS = {"posture": posture, "kpis": kpis, "guard": guard, "trust": trust, "table": table, "shadow": shadow,
              "egress": egress, "proof": proof, "feed": feed, "mcp": mcp}


def render(name, data, lt, w=None):
    fn = COMPONENTS[name]
    return fn(data, lt, w) if w else fn(data, lt)
