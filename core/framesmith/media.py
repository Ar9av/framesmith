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
