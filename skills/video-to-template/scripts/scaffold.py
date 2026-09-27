#!/usr/bin/env python3
"""Scaffold a new framesmith template from a reference analysis, as a timed animatic.

    python3 scaffold.py <kebab-name> --analysis analysis/<ref>/analysis.json [--skills-dir ../..] [--description "…"]

Creates <skills-dir>/<name>/ with:
  SKILL.md                      frontmatter to finish (validate fails while TODOs remain)
  scripts/main.py               CLI (check | still | sheet | render) + scene library + one scene per shot
  scripts/framesmith/           vendored engine (copied from this skill)
  examples/demo/brief.json      size, fps, palette-derived theme, shots with reference timing
  examples/demo/reference/      keyframes used by the animatic (gitignored: reference material stays local)
  references/storyboard.md      the analysis storyboard skeleton
Every shot starts as `animatic` (its reference keyframe, dimmed and labelled), so the cut already
matches the reference's timing; replace shots with real scene types one at a time.
"""
import argparse, colorsys, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))

MAIN_PY = r'''#!/usr/bin/env python3
"""{name}: framesmith template scaffolded from a reference (see references/storyboard.md).

    python3 main.py check|still|sheet|render --brief brief.json [times...] [--audio track.m4a]

Shots live in brief.json → "shots": [{{"name", "dur", "type", ...}}]. Start from `animatic` (the
reference keyframe) and replace each with a real scene type. Add new types to SCENE_TYPES.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from framesmith import Mosaic, Scene, Theme, Timeline, cover, ease_out, lerp, overflow_report, scramble, text
from framesmith import ui
from framesmith.typography import F, OVERFLOWS, SHRINKS

G = None


class State:
    def __init__(self, brief, base):
        self.b, self.base = brief, base
        self.th = Theme.from_dict(brief.get("theme"))
        self.W, self.H = brief["size"]
        self._c = {{}}

    def path(self, p):
        return os.path.join(self.base, p)


def arr(im):
    return np.asarray(im.convert("RGB")).copy()


# ---------------------------------------------------------------- scene library
def s_animatic(c, shot):
    """Placeholder: the reference keyframe, dimmed, with the shot label. Replace me."""
    im = Image.new("RGB", (c.W, c.H), G.th.ink)
    kf = shot.get("keyframe")
    if kf and os.path.exists(G.path(kf)):
        ref = cover(Image.open(G.path(kf)).convert("RGB"), c.W, c.H, lerp(1.0, 1.04, c.p(0, c.dur)))
        im = ImageEnhance.Brightness(ref).enhance(0.45)
    d = ImageDraw.Draw(im)
    text(d, (40, 40), f"{{shot['name']}}  ·  {{c.lt:4.2f}} / {{c.dur:4.2f}} s", F("mono", 26), G.th.paper, 0, max_w=c.W - 80)
    text(d, (40, 80), shot.get("note", "animatic: replace with a real scene"), F("pixel", 22), G.th.paper, 0, max_w=c.W - 80)
    return arr(im)


def s_word(c, shot):
    """One big word, rising in. Keys: text, color (accent|ink|paper), bg (paper|ink|accent), size."""
    th = G.th
    bg = {{"paper": th.paper, "ink": th.ink, "accent": th.accent}}[shot.get("bg", "paper")]
    fg = {{"paper": th.paper, "ink": th.ink, "accent": th.accent}}[shot.get("color", "accent")]
    im = Image.new("RGB", (c.W, c.H), bg)
    ui.rise(im, (c.W / 2, c.H / 2), shot["text"], F(shot.get("font", "pixel"), shot.get("size", 132)), fg,
            ease_out(c.p(0, 0.3)), 0, "mm", max_w=c.W - 140)
    return arr(im)


def s_image(c, shot):
    """A full-bleed image with a slow push. Keys: src, zoom, focus."""
    im = cover(Image.open(G.path(shot["src"])).convert("RGB"), c.W, c.H, lerp(1.0, shot.get("zoom", 1.08), c.p(0, c.dur)),
               *shot.get("focus", [0.5, 0.5]))
    return arr(im)


SCENE_TYPES = {{"animatic": s_animatic, "word": s_word, "image": s_image}}


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    scenes = []
    for shot in brief["shots"]:
        fn = SCENE_TYPES[shot.get("type", "animatic")]
        tr = Mosaic(shot["mosaic"], 18, 18, len(scenes) + 3) if shot.get("mosaic") else None
        scenes.append(Scene(shot["name"], shot["dur"], (lambda f, s: lambda c: f(c, s))(fn, shot), tr))
    return Timeline(scenes, G.W, G.H, brief.get("fps", 30), data=G, theme=G.th), brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "demo", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        OVERFLOWS.clear(); SHRINKS.clear()
        for fi in range(0, tl.n_frames, max(1, tl.fps // 4)):
            tl.frame(fi)
        rep = overflow_report()
        print("text overflow:", "none" if not rep else "")
        for r in rep + ["! " + w for w in overflow_report(warn=True)]:
            print("  ", r)
        todo = sum(1 for s in brief["shots"] if s.get("type", "animatic") == "animatic")
        print(f"{{tl.duration:.2f}} s, {{len(tl.scenes)}} shots, {{todo}} still animatic")
        sys.exit(1 if rep else 0)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{{float(s):05.2f}}.png")), "·", tl.scene_at(float(s)))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png")))
    else:
        print(tl.render(a.out or os.path.join(out, "{name}.mp4"), a.audio))


if __name__ == "__main__":
    main()
'''

SKILL_MD = '''---
name: {name}
description: {desc}
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  reference: "{source}"
---

# {title}

TODO: one paragraph describing the output: duration, aspect, shot count, and the look in concrete terms (palette, type, motion, transitions).

## Workflow

1. Copy `examples/demo/brief.json`, then edit `theme` and `shots`.
2. `python3 scripts/main.py check --brief brief.json` (fails on text overflow; reports how many shots are still animatic).
3. `python3 scripts/main.py still --brief brief.json 1.0 4.2` to review.
4. `python3 scripts/main.py render --brief brief.json [--audio track.m4a]`.

Storyboard: `references/storyboard.md`.
'''


def hexs(rgb):
    return "#%02X%02X%02X" % rgb


def theme_from_palette(pal):
    """paper = most covered light colour, ink = darkest, accent = most saturated mid-tone."""
    cols = [tuple(int(p["hex"][i:i + 2], 16) for i in (1, 3, 5)) for p in pal]
    lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    sat = lambda c: colorsys.rgb_to_hsv(*[v / 255 for v in c])[1]
    paper = next((c for c in cols if lum(c) > 170), (245, 245, 240))
    ink = min(cols, key=lum) if cols else (10, 10, 10)
    mids = [c for c in cols if 40 < lum(c) < 220] or cols
    accent = max(mids, key=sat) if mids else (242, 86, 29)
    return {"paper": hexs(paper), "ink": hexs(ink if lum(ink) < 80 else (10, 10, 10)), "accent": hexs(accent)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--skills-dir", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--description", default="TODO: what it renders, then when to use it (the phrases users say).")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name):
        sys.exit("name must be kebab-case")
    an = json.load(open(a.analysis))
    adir = os.path.dirname(os.path.abspath(a.analysis))
    d = os.path.join(a.skills_dir, a.name)
    if os.path.exists(d):
        sys.exit(f"{d} exists")
    for sub in ("scripts", "references", "examples/demo/reference"):
        os.makedirs(os.path.join(d, sub))
    shutil.copytree(os.path.join(HERE, "framesmith"), os.path.join(d, "scripts", "framesmith"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    open(os.path.join(d, "scripts", "main.py"), "w").write(MAIN_PY.format(name=a.name))
    open(os.path.join(d, "SKILL.md"), "w").write(SKILL_MD.format(name=a.name, desc=a.description,
                                                                 title=a.name.replace("-", " ").title(), source=an.get("source", "")))
    open(os.path.join(d, ".gitignore"), "w").write("examples/*/reference/\nexamples/*/out/\n")
    # scale to an even, render-friendly size with the reference's aspect (long side 1080–1920)
    w, h = an["width"], an["height"]
    k = (1080 if max(w, h) <= 1080 else 1920) / max(w, h) if max(w, h) < 1080 else 1.0
    size = [int(w * k) // 2 * 2, int(h * k) // 2 * 2]
    shots = []
    for i, s in enumerate(an["shots"]):
        kf = s.get("keyframe")
        rel = None
        if kf and os.path.exists(os.path.join(adir, kf)):
            rel = f"reference/shot_{i + 1:02d}.png"
            shutil.copy(os.path.join(adir, kf), os.path.join(d, "examples", "demo", rel))
        shots.append({"name": f"shot{i + 1:02d}", "dur": round(s["dur"], 3), "type": "animatic", "keyframe": rel})
    brief = {"size": size, "fps": round(an.get("fps", 30)) if an.get("fps", 30) <= 60 else 30,
             "theme": theme_from_palette(an.get("palette", [])), "shots": shots}
    json.dump(brief, open(os.path.join(d, "examples", "demo", "brief.json"), "w"), indent=1)
    report = os.path.join(adir, "report.md")
    sb = open(report).read() if os.path.exists(report) else "# Storyboard\n"
    open(os.path.join(d, "references", "storyboard.md"), "w").write(sb.replace(
        "# Reference analysis", "# Storyboard (from reference analysis)"))
    print(f"created {d}\n  animatic: python3 {os.path.join(d, 'scripts/main.py')} render"
          f"\n  compare:  python3 {os.path.join(HERE, 'compare.py')} {os.path.join(adir, an['file'])} <render.mp4>")


if __name__ == "__main__":
    main()
