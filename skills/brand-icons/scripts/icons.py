#!/usr/bin/env python3
"""brand-icons: find, fetch, preview and credit brand SVG icons from thesvg.org (7,400+ marks).

    python3 icons.py search stripe                      # ranked matches with variants + licence
    python3 icons.py info github-copilot                # everything the registry knows about one icon
    python3 icons.py fetch claude openai cursor --out assets/icons [--theme light|dark] [--png 512]
    python3 icons.py sheet claude openai cursor --out icons.png [--bg "#EEF1EC"] [--size 128]
    python3 icons.py credits assets/icons [--md]        # attribution table from icons.json

Fetch writes <slug>.svg, a transparent <slug>.png rendered by headless Chromium, and icons.json
(title, variant, source URL, licence, brand URL) so attribution travels with the files.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw

from framesmith.media import fetch_icons, icon, is_light_mark, rasterize_svg, search_icons, thesvg_registry
from framesmith.theme import hex2rgb, luminance
from framesmith.typography import F, text

OPEN = {"CC0-1.0", "MIT", "Apache-2.0", "ISC", "BSD-2-Clause", "BSD-3-Clause", "0BSD", "Unlicense", "OFL-1.1"}


def licence_note(lic):
    """Plain-language usage note for a licence string from the registry."""
    lic = lic or "Unknown"
    if lic in OPEN:
        return "open"
    if lic.startswith("CC-BY") and "ND" in lic:
        return "attribution required; no modification (don't recolour or alter)"
    if lic.startswith("CC-BY"):
        return "attribution required"
    if lic in ("brand-use", "Trademark"):
        return "trademark: follow the brand's guidelines; nominative use only (e.g. 'works with')"
    if lic == "Unknown":
        return "unknown licence: avoid unless you have the brand's permission"
    return f"check terms ({lic})"


def variant_for(info, theme):
    order = {"light": ("light", "default", "mono"), "dark": ("dark", "default", "mono")}.get(theme, ("default", "mono"))
    return next((v for v in order if v in info.get("variants", {})), "default")


def cmd_search(a):
    rows = search_icons(" ".join(a.query), a.limit)
    if not rows:
        print("no matches")
        return
    for i in rows:
        print(f"{i['slug']:<34} {i.get('title', ''):<28} {i.get('license') or 'Unknown':<14} {','.join(i.get('variants', {}))}")


def cmd_info(a):
    reg = {i["slug"]: i for i in thesvg_registry()}
    for s in a.slugs:
        i = reg.get(s)
        if not i:
            print(f"{s}: not found (try `search`)")
            continue
        print(json.dumps({**i, "usage": licence_note(i.get("license"))}, indent=1))


def cmd_fetch(a):
    reg = {i["slug"]: i for i in thesvg_registry()}
    ok = []
    for s in a.slugs:
        i = reg.get(s)
        if not i:
            print(f"✗ {s}: not on thesvg (try `search {s}`)")
            continue
        lic = i.get("license") or "Unknown"
        if lic == "Unknown" and not a.allow_unknown:
            print(f"✗ {s}: licence unknown, skipped (pass --allow-unknown if you have permission)")
            continue
        ok.append(s)
    if not ok:
        return
    prefer = {"light": ("light", "default", "mono"), "dark": ("dark", "default", "mono")}.get(a.theme, ("default", "mono"))
    for line in fetch_icons(ok, a.out, prefer):
        s = line.split(":")[0]
        print(f"✓ {line}  · {licence_note(reg[s].get('license'))}")
    if a.png and a.png != 512:                              # fetch_icons renders 512 px; re-render at the requested size
        for s in ok:
            rasterize_svg(os.path.join(a.out, s + ".svg"), os.path.join(a.out, s + ".png"), a.png)


def cmd_sheet(a):
    tmp = a.cache or os.path.join(os.path.dirname(os.path.abspath(a.out)), "icons-cache")
    bg = hex2rgb(a.bg)
    theme = "light" if luminance(bg) > 0.4 else "dark"
    reg = {i["slug"]: i for i in thesvg_registry()}
    have = [s for s in a.slugs if s in reg]
    missing = [s for s in have if not os.path.exists(os.path.join(tmp, s + ".png"))]
    if missing:
        fetch_icons(missing, tmp, {"light": ("light", "default", "mono"), "dark": ("dark", "default", "mono")}[theme])
    n, cols, cell = len(have), min(a.cols, max(1, len(have))), int(a.size * 1.6)
    rows = -(-n // cols)
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + 30)), bg + (255,))
    d = ImageDraw.Draw(sheet)
    ink = (10, 10, 10) if theme == "light" else (245, 245, 240)
    for k, s in enumerate(have):
        ic = icon(os.path.join(tmp, s + ".svg"), a.size)
        nd = "ND" in (reg[s].get("license") or "")
        if not nd and ((theme == "light" and is_light_mark(ic)) or (theme == "dark" and not is_light_mark(ic, 60) and _is_dark_mark(ic))):
            ic = icon(os.path.join(tmp, s + ".svg"), a.size, ink)   # keep single-colour marks visible on this ground
        x, y = (k % cols) * cell, (k // cols) * (cell + 30)
        sheet.alpha_composite(ic, (x + (cell - a.size) // 2, y + (cell - a.size) // 2))
        text(d, (x + cell / 2, y + cell + 8), s, F("mono", 14), ink, 0, "mm", max_w=cell - 8)
    sheet.convert("RGB").save(a.out)
    print(a.out)


def _is_dark_mark(im):
    import numpy as np
    arr = np.asarray(im)
    vis = arr[..., 3] > 64
    return bool(vis.any() and arr[..., :3][vis].mean() < 60)


def cmd_credits(a):
    meta = json.load(open(os.path.join(a.dir, "icons.json")))
    if a.md:
        print("| Icon | Licence | Source | Brand |\n|---|---|---|---|")
        for s, m in sorted(meta.items()):
            print(f"| {m['title']} | {m.get('license') or 'Unknown'} | {m['source']} | {m.get('brand_url') or ''} |")
        print("\nIcons via [thesvg.org](https://thesvg.org). Brand names and logos are trademarks of their owners.")
    else:
        for s, m in sorted(meta.items()):
            print(f"{m['title']:<28} {m.get('license') or 'Unknown':<14} {licence_note(m.get('license'))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("search"); p.add_argument("query", nargs="+"); p.add_argument("--limit", type=int, default=15)
    p = sub.add_parser("info"); p.add_argument("slugs", nargs="+")
    p = sub.add_parser("fetch"); p.add_argument("slugs", nargs="+"); p.add_argument("--out", default="icons")
    p.add_argument("--theme", choices=["light", "dark", "any"], default="light", help="background the icons will sit on")
    p.add_argument("--png", type=int, default=512); p.add_argument("--allow-unknown", action="store_true")
    p = sub.add_parser("sheet"); p.add_argument("slugs", nargs="+"); p.add_argument("--out", default="icons.png")
    p.add_argument("--bg", default="#EEF1EC"); p.add_argument("--size", type=int, default=128)
    p.add_argument("--cols", type=int, default=8); p.add_argument("--cache")
    p = sub.add_parser("credits"); p.add_argument("dir"); p.add_argument("--md", action="store_true")
    a = ap.parse_args()
    {"search": cmd_search, "info": cmd_info, "fetch": cmd_fetch, "sheet": cmd_sheet, "credits": cmd_credits}[a.cmd](a)


if __name__ == "__main__":
    main()
