#!/usr/bin/env python3
"""Scaffold a new framesmith template skill.

    python3 tools/new_skill.py kinetic-type-teaser ["One-line description"]

Creates skills/<name>/ with SKILL.md, a runnable starter CLI (scripts/main.py),
an example brief, references/, and a vendored copy of the engine.
"""
import os, re, shutil, sys, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_MD = '''---
name: {name}
description: {desc} Use when the user asks for TODO (list trigger phrases and the kinds of product/brand/content this fits).
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, video
---

# {title}

TODO: one paragraph describing the output (duration, aspect, scene count, look).

## Workflow

1. Copy `examples/demo/brief.json` next to the user's work, edit `copy` / `theme` / `assets`.
2. `python3 scripts/main.py check --brief brief.json`
3. `python3 scripts/main.py assets --brief brief.json` (optional, gpt-image-2)
4. `python3 scripts/main.py still --brief brief.json 1.0 2.5` → review
5. `python3 scripts/main.py render --brief brief.json`

See `references/storyboard.md` for the scene list.
'''

MAIN_PY = '''#!/usr/bin/env python3
"""{name}: framesmith template. Verbs: check | assets | still | sheet | render."""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from PIL import Image, ImageDraw

from framesmith import Assets, Scene, Theme, Timeline, ease_out, generate_images, scramble, text
from framesmith.typography import F

G = None


class State:
    def __init__(self, brief, base):
        self.b, self.c = brief, brief["copy"]
        self.th = Theme.from_dict(brief.get("theme"))
        self.W, self.H = brief.get("size", [720, 1280])
        self.assets = Assets(os.path.join(base, brief.get("assets_dir", "assets")),
                             os.path.join(HERE, "..", "placeholders"))


def s_title(c):
    im = Image.new("RGB", (c.W, c.H), G.th.ink)
    d = ImageDraw.Draw(im)
    text(d, (c.W / 2, c.H / 2), scramble(G.c["title"], ease_out(c.p(0, 0.5)), 1, c.fi), F("sans_medium", 72),
         G.th.paper, -2, "mm")
    return np.asarray(im)


def s_accent(c):
    im = Image.new("RGB", (c.W, c.H), G.th.accent)
    text(ImageDraw.Draw(im), (c.W / 2, c.H / 2), G.c["tagline"], F("mono", 24), G.th.on_accent, 1, "mm")
    return np.asarray(im)


SCENES = [("title", 1.5, s_title), ("accent", 1.0, s_accent)]


def build(path):
    global G
    brief = json.load(open(path))
    G = State(brief, os.path.dirname(os.path.abspath(path)))
    over = brief.get("scenes", {{}})
    sc = [Scene(n, over.get(n, d), f) for n, d, f in SCENES if over.get(n, d)]
    return Timeline(sc, G.W, G.H, brief.get("fps", 25), data=G, theme=G.th), brief


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "assets", "still", "sheet", "render"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--brief", default=os.path.join(HERE, "..", "examples", "demo", "brief.json"))
    ap.add_argument("--out")
    ap.add_argument("--audio")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_intermixed_args()
    tl, brief = build(a.brief)
    out = os.path.join(os.path.dirname(os.path.abspath(a.brief)), "out")
    os.makedirs(out, exist_ok=True)
    if a.cmd == "check":
        print(f"{{tl.duration:.2f}}s, {{tl.n_frames}} frames, {{len(tl.scenes)}} scenes")
    elif a.cmd == "assets":
        for m in generate_images(brief.get("assets", {{}}), G.assets.dirs[0], names=a.args or None, force=a.force):
            print(m)
    elif a.cmd == "still":
        for s in a.args or ["1.0"]:
            print(tl.still(float(s), os.path.join(out, f"still_{{float(s):05.2f}}.png")))
    elif a.cmd == "sheet":
        print(tl.contact_sheet(a.out or os.path.join(out, "contact_sheet.png")))
    else:
        print(tl.render(a.out or os.path.join(out, "{name}.mp4"), a.audio))


if __name__ == "__main__":
    main()
'''

BRIEF = '''{{
  "size": [720, 1280],
  "fps": 25,
  "theme": {{"accent": "#F2561D", "ink": "#000000", "paper": "#FFFFFF"}},
  "copy": {{"title": "{title}", "tagline": "MADE WITH FRAMESMITH"}},
  "scenes": {{}},
  "assets": {{}}
}}
'''


def main():
    if len(sys.argv) < 2 or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", sys.argv[1]):
        sys.exit("usage: new_skill.py <kebab-case-name> [description]")
    name = sys.argv[1]
    desc = sys.argv[2] if len(sys.argv) > 2 else "TODO: what this template renders."
    title = name.replace("-", " ").title()
    d = os.path.join(ROOT, "skills", name)
    if os.path.exists(d):
        sys.exit(f"{d} already exists")
    for sub in ("scripts", "references", "examples/demo", "placeholders"):
        os.makedirs(os.path.join(d, sub))
    open(os.path.join(d, "SKILL.md"), "w").write(SKILL_MD.format(name=name, desc=desc, title=title))
    open(os.path.join(d, "scripts", "main.py"), "w").write(MAIN_PY.format(name=name))
    open(os.path.join(d, "examples", "demo", "brief.json"), "w").write(BRIEF.format(title=title))
    open(os.path.join(d, "references", "storyboard.md"), "w").write(
        f"# Storyboard: {name}\n\n| # | Scene | Start | Dur | What happens | Brief keys |\n|---|---|---|---|---|---|\n")
    open(os.path.join(d, "placeholders", ".gitkeep"), "w").close()
    shutil.copytree(os.path.join(ROOT, "core", "framesmith"), os.path.join(d, "scripts", "framesmith"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(textwrap.dedent(f"""\
        created skills/{name}/
        next:
          python3 skills/{name}/scripts/main.py still 0.5 2.0
          edit SKILL.md (description = triggers!), scripts/main.py, examples/demo/brief.json
          python3 tools/catalog.py && python3 tools/validate.py"""))


if __name__ == "__main__":
    main()
