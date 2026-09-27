"""Assets: lookup with placeholder fallback, cover-fit, sprite sheets, and gpt-image-2 generation."""
import base64, json, os, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from PIL import Image, ImageOps


class Assets:
    """Resolves `name` → first existing <dir>/<name>.(png|jpg|webp) across search dirs."""

    def __init__(self, *dirs):
        self.dirs = [d for d in dirs if d]

    def path(self, name):
        for d in self.dirs:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = os.path.join(d, name + ext)
                if os.path.exists(p):
                    return p
        return None

    @lru_cache(None)
    def get(self, name):
        p = self.path(name)
        if not p:
            raise FileNotFoundError(f"asset '{name}' not found in {self.dirs}")
        return Image.open(p).convert("RGBA")

    def missing(self, names):
        return [n for n in names if not self.path(n)]


def cover(im, w, hgt, zoom=1.0, fx=0.5, fy=0.5):
    """Scale to cover w×h (× zoom) and crop around the focus point (fx, fy)."""
    s = max(w / im.width, hgt / im.height) * zoom
    r = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    x = int(min(max(fx * r.width - w / 2, 0), r.width - w))
    y = int(min(max(fy * r.height - hgt / 2, 0), r.height - hgt))
    return r.crop((x, y, x + w, y + hgt))


def cover_point(im, w, hgt, pt, zoom=1.0, fx=0.5, fy=0.5):
    """Where a source point (fractions of `im`) lands after cover(); returns px in the w×h crop."""
    s = max(w / im.width, hgt / im.height) * zoom
    rw, rh = im.width * s, im.height * s
    x = min(max(fx * rw - w / 2, 0), rw - w)
    y = min(max(fy * rh - hgt / 2, 0), rh - hgt)
    return pt[0] * rw - x, pt[1] * rh - y


def sprite_masks(sheet, cols, rows, dark_on_light=True, pad=8):
    """Split a line-art sprite sheet into alpha masks cropped to a shared bounding box."""
    g = sheet.convert("L")
    fw, fh = g.width // cols, g.height // rows
    frames = []
    for i in range(cols * rows):
        c = g.crop(((i % cols) * fw, (i // cols) * fh, (i % cols + 1) * fw, (i // cols + 1) * fh))
        if dark_on_light:
            c = ImageOps.invert(c)
        frames.append(c.point(lambda v: 255 if v > 90 else int(v * 2.5)))
    boxes = [f.getbbox() or (0, 0, fw, fh) for f in frames]
    box = (max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad),
           min(fw, max(b[2] for b in boxes) + pad), min(fh, max(b[3] for b in boxes) + pad))
    return [f.crop(box) for f in frames]


def pingpong(n):
    """Frame order 0..n-1..1 for a seamless loop."""
    return list(range(n)) + list(range(n - 2, 0, -1))


# ---------- gpt-image-2 ----------
def generate_images(specs, out_dir, key=None, names=None, force=False, workers=6, fmt=None):
    """Generate assets with OpenAI gpt-image-2.

    specs: {name: {"prompt": str, "size": "1024x1536", "quality": "low|medium|high",
                   "background": "transparent" (optional)}}
    Skips files that already exist unless force=True. Returns list of status strings.
    """
    key = key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    os.makedirs(out_dir, exist_ok=True)
    todo = names or [n for n in specs if force or not Assets(out_dir).path(n)]
    fmt = fmt or (lambda s: s)

    def one(name):
        spec = specs[name]
        body = {"model": spec.get("model", "gpt-image-2"), "prompt": fmt(spec["prompt"]),
                "size": spec.get("size", "1024x1024"), "quality": spec.get("quality", "medium"), "n": 1}
        if spec.get("background"):
            body["background"] = spec["background"]
        req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=600))
        except urllib.error.HTTPError as e:
            return f"{name}: HTTP {e.code} {e.read()[:300].decode(errors='replace')}"
        with open(os.path.join(out_dir, name + ".png"), "wb") as f:
            f.write(base64.b64decode(r["data"][0]["b64_json"]))
        return f"{name}: ok ({body['quality']}, {body['size']})"

    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(one, todo))


# ---------- brand icons (thesvg.org) ----------
THESVG_REGISTRY = "https://raw.githubusercontent.com/GLINCKER/thesvg/main/src/data/icons.json"


def thesvg_registry(max_age_h=24):
    """thesvg.org icon registry (list of {slug, title, aliases, categories, variants, license, hex, url}),
    cached in ~/.cache/framesmith for max_age_h hours."""
    import time
    cache = os.path.join(os.path.expanduser("~"), ".cache", "framesmith", "thesvg-icons.json")
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < max_age_h * 3600:
        return json.load(open(cache))
    data = json.load(urllib.request.urlopen(THESVG_REGISTRY, timeout=60))
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w") as f:
        json.dump(data, f)
    return data


def search_icons(query, limit=20):
    """Rank registry entries for a query: exact slug > title > alias > substring > category."""
    q = query.lower().strip()
    scored = []
    for i in thesvg_registry():
        slug, title = i["slug"], i.get("title", "").lower()
        aliases = [a.lower() for a in i.get("aliases", []) or []]
        cats = [c.lower() for c in i.get("categories", []) or []]
        score = (100 if slug == q else 90 if title == q else 80 if q in aliases else
                 60 if slug.startswith(q) or title.startswith(q) else 40 if q in slug or q in title else
                 20 if any(q in a for a in aliases) else 10 if q in cats else 0)
        if score:
            scored.append((score, -len(slug), i))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [i for _, _, i in scored[:limit]]


def fetch_icons(slugs, out_dir, prefer=("light", "default", "mono")):
    """Download brand SVGs from thesvg.org into out_dir/<slug>.svg and write out_dir/icons.json
    (slug, variant, source URL, licence) so attribution travels with the assets."""
    os.makedirs(out_dir, exist_ok=True)
    reg = {i["slug"]: i for i in thesvg_registry()}
    meta_path = os.path.join(out_dir, "icons.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    out = []
    for s in slugs:
        info = reg.get(s)
        if not info:
            out.append(f"{s}: not on thesvg")
            continue
        variant = next((v for v in prefer if v in info.get("variants", {})), "default")
        url = "https://thesvg.org" + info["variants"][variant]
        svg_file = os.path.join(out_dir, s + ".svg")
        with open(svg_file, "wb") as f:
            f.write(urllib.request.urlopen(url, timeout=60).read())
        rasterize_svg(svg_file, os.path.join(out_dir, s + ".png"))
        meta[s] = {"title": info.get("title", s), "variant": variant, "source": url, "license": info.get("license"),
                   "brand_url": info.get("url")}
        out.append(f"{s}: {variant} ({info.get('license')})")
    json.dump(meta, open(meta_path, "w"), indent=1)
    return out


def _chromium():
    import shutil
    for b in ("chromium-browser", "chromium", "google-chrome", "google-chrome-stable"):
        if shutil.which(b):
            return shutil.which(b)
    return None


def rasterize_svg(svg_path, png_path, size=512):
    """Render an SVG with headless Chromium (a real SVG engine) to a transparent size×size PNG.

    Work happens in a staging folder under $HOME (not hidden, not /tmp): snap-confined Chromium can
    only see those, and has a private /tmp. The PNG is then moved to png_path.
    """
    import shutil, subprocess, uuid
    exe = _chromium()
    if not exe:
        return False
    stage = os.path.join(os.path.expanduser("~"), "framesmith-svg-stage", uuid.uuid4().hex[:8])
    os.makedirs(stage, exist_ok=True)
    try:
        shutil.copy(svg_path, os.path.join(stage, "icon.svg"))
        page, out = os.path.join(stage, "page.html"), os.path.join(stage, "out.png")
        with open(page, "w") as f:
            f.write(f'<html><body style="margin:0;background:transparent"><img src="icon.svg" '
                    f'style="width:{size}px;height:{size}px;object-fit:contain;display:block"></body></html>')
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        "--default-background-color=00000000", f"--window-size={size},{size}",
                        f"--screenshot={out}", "file://" + page], capture_output=True, timeout=90)
        if not os.path.exists(out):
            return False
        shutil.move(out, png_path)
        return True
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try:
            os.rmdir(os.path.dirname(stage))
        except OSError:
            pass


@lru_cache(None)
def icon(svg_path, size, tint=None):
    """Rasterise an SVG to a size×size RGBA image (ImageMagick, or cairosvg if installed).
    tint: RGB to recolour a single-colour mark (e.g. white-on-transparent marks on a light ground)."""
    png_cache = os.path.splitext(svg_path)[0] + ".png"          # pre-rasterised by fetch_icons (Chromium)
    if os.path.exists(png_cache):
        im = Image.open(png_cache).convert("RGBA")
        bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        side = max(im.size)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
        im = sq.resize((size, size), Image.LANCZOS)
        if tint is not None:
            a = im.getchannel("A")
            im = Image.new("RGBA", im.size, tuple(tint) + (255,))
            im.putalpha(a)
        return im
    import re, subprocess, tempfile
    svg = open(svg_path, encoding="utf-8").read()
    # normalise web-only values rasterisers choke on: em sizes, currentColor
    vb = re.search(r'viewBox="([\d.\s-]+)"', svg)
    if vb:
        _, _, vw, vh = [float(v) for v in vb.group(1).split()]
        svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)
        svg = svg.replace("<svg", f'<svg width="{vw}" height="{vh}"', 1)
    svg = svg.replace("currentColor", "#000000")
    src = tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w", encoding="utf-8")
    src.write(svg)
    src.close()
    png = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        try:
            import cairosvg
            cairosvg.svg2png(url=src.name, write_to=png, output_width=size, output_height=size)
        except ImportError:
            subprocess.run(["convert", "-background", "none", "-density", "1200", src.name, "-resize", f"{size}x{size}",
                            "-gravity", "center", "-extent", f"{size}x{size}", png], check=True, capture_output=True)
        im = Image.open(png).convert("RGBA")
    finally:
        os.unlink(src.name)
        if os.path.exists(png):
            os.unlink(png)
    if tint is not None:
        a = im.getchannel("A")
        im = Image.new("RGBA", im.size, tuple(tint) + (255,))
        im.putalpha(a)
    return im


def is_light_mark(im, thresh=200):
    """True if the visible pixels of a mark are near-white (it would vanish on a light background)."""
    import numpy as np
    a = np.asarray(im)
    vis = a[..., 3] > 64
    return bool(vis.any() and a[..., :3][vis].mean() > thresh)
