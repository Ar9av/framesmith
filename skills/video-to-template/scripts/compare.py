#!/usr/bin/env python3
"""Compare a render against its reference.

    python3 compare.py ref.mp4 ours.mp4 [--out compare] [--every 1.0] [--audio ref|ours|none]

Writes compare/side_by_side.mp4 (reference left, ours right, same height, chosen audio) and
compare/pairs_NN.png (reference over ours at the same timestamps, labelled) for frame-by-frame review.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw

from framesmith.typography import F


def duration(p):
    return float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", p],
                                           capture_output=True, text=True).stdout)["format"]["duration"])


def frame(p, t, h):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", p, "-frames:v", "1", "-vf", f"scale=-2:{h}",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(out)).convert("RGB") if out else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("ours")
    ap.add_argument("--out", default="compare")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between paired frames")
    ap.add_argument("--audio", choices=["ref", "ours", "none"], default="ref")
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    h = a.height - a.height % 2
    amap = {"ref": ["-map", "0:a?"], "ours": ["-map", "1:a?"], "none": []}[a.audio]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.ref, "-i", a.ours, "-filter_complex",
                    f"[0:v]scale=-2:{h},setsar=1[l];[1:v]scale=-2:{h},setsar=1[r];[l][r]hstack=inputs=2[v]",
                    "-map", "[v]", *amap, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", os.path.join(a.out, "side_by_side.mp4")], check=True)
    T = min(duration(a.ref), duration(a.ours))
    times = [t * a.every for t in range(int(T / a.every) + 1)]
    th = 240
    f = F("mono", 14)
    per = 8
    for si in range(0, len(times), per):
        chunk = times[si:si + per]
        pairs = [(t, frame(a.ref, t, th), frame(a.ours, t, th)) for t in chunk]
        w = max((max(r.width if r else 0, o.width if o else 0) for _, r, o in pairs), default=th)
        sheet = Image.new("RGB", (len(pairs) * (w + 6), th * 2 + 30), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for k, (t, r, o) in enumerate(pairs):
            x = k * (w + 6)
            if r:
                sheet.paste(r, (x, 22))
            if o:
                sheet.paste(o, (x, 22 + th + 6))
            d.text((x + 4, 4), f"{t:5.1f}s  ref ↑ / ours ↓", font=f, fill=(0, 255, 0))
        sheet.save(os.path.join(a.out, f"pairs_{si // per:02d}.png"))
    print(os.path.join(a.out, "side_by_side.mp4"), f"· {(len(times) + per - 1) // per} pair sheets")


if __name__ == "__main__":
    main()
