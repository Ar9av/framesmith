#!/usr/bin/env python3
"""Break a reference video down into what you need to rebuild its style.

    python3 analyze.py <url-or-path> [--out analysis/<name>] [--fps 4] [--scene 0.3] [--transcribe]

Writes into --out:
  ref.<ext>            the downloaded reference
  analysis.json        format, cuts (start, dur), shot stats, palette, audio profile, transcript (optional)
  report.md            human summary + a storyboard skeleton to fill in
  sheets/sheet_NN.png  timestamped contact sheets (fps frames, 30 per sheet)
  keyframes/cut_NN.png one full-res frame from the middle of every shot
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw

from framesmith.typography import F


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fetch(src, out_dir):
    if os.path.exists(src):
        dst = os.path.join(out_dir, "ref" + os.path.splitext(src)[1])
        shutil.copy(src, dst)
        return dst
    ext = os.path.splitext(src.split("?")[0])[1] or ".mp4"
    dst = os.path.join(out_dir, "ref" + ext)
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
    with open(dst, "wb") as f:
        f.write(urllib.request.urlopen(req, timeout=300).read())
    return dst


def probe(path):
    r = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]).stdout)
    v = next(s for s in r["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "25/1").split("/")
    return {"duration": float(r["format"]["duration"]), "width": v["width"], "height": v["height"],
            "fps": round(float(num) / float(den or 1), 3), "has_audio": any(s["codec_type"] == "audio" for s in r["streams"])}


def diff_cuts(path, sens=0.22, fps=10, side=96):
    """Cuts from the fraction of pixels that change between sampled frames. This catches cuts on a constant
    background (collage / minimal styles) that ffmpeg's global scene score misses."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={side}:{side},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, side, side).astype(np.int16)
    if len(fr) < 3:
        return []
    ch = (np.abs(np.diff(fr, axis=0)) > 28).mean(axis=(1, 2))           # changed-pixel fraction per step
    # adaptive: a cut is a local peak well above this video's own baseline motion (minimal styles change
    # only a few % of pixels per cut; busy footage needs the absolute `sens` floor)
    th = min(sens, max(0.035, float(np.median(ch)) * 6))
    out = []
    for i in range(len(ch)):
        lo, hi = max(0, i - 3), min(len(ch), i + 4)
        if ch[i] >= th and ch[i] == ch[lo:hi].max() and (not out or (i + 1) / fps - out[-1] >= 0.4):
            out.append((i + 1) / fps)
    return out


def cuts(path, thresh, duration):
    """Shot boundaries: ffmpeg scene score (metadata printed to a file) ∪ changed-pixel peaks."""
    tmp = os.path.join(os.path.dirname(path), "_scores.txt")
    sh(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf",
        f"select='gt(scene,{thresh})',metadata=print:file={tmp}", "-f", "null", "-"])
    times = []
    if os.path.exists(tmp):
        times = [float(m) for m in re.findall(r"pts_time:([\d.]+)", open(tmp).read())]
        os.remove(tmp)
    times = sorted(set(times) | set(diff_cuts(path)))
    starts = [0.0] + [t for t in times if t > 0.15]
    dedup = []
    for t in starts:                                     # merge boundaries closer than 0.2 s (flashes, dissolves)
        if not dedup or t - dedup[-1] >= 0.2:
            dedup.append(t)
    return [{"start": round(s, 3), "dur": round((dedup[k + 1] if k + 1 < len(dedup) else duration) - s, 3)}
            for k, s in enumerate(dedup)]


def sheets(path, out_dir, fps, font):
    fdir = os.path.join(out_dir, "_frames")
    os.makedirs(fdir, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps}", os.path.join(fdir, "f_%04d.jpg")])
    frames = sorted(os.listdir(fdir))
    sdir = os.path.join(out_dir, "sheets")
    os.makedirs(sdir, exist_ok=True)
    out = []
    per, cols = 30, 10
    for si in range(0, len(frames), per):
        chunk = frames[si:si + per]
        ims = [Image.open(os.path.join(fdir, f)).convert("RGB") for f in chunk]
        tw = 240
        th = int(tw * ims[0].height / ims[0].width)
        sheet = Image.new("RGB", (cols * tw, -(-len(ims) // cols) * th), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for k, im in enumerate(ims):
            x, y = (k % cols) * tw, (k // cols) * th
            sheet.paste(im.resize((tw, th)), (x, y))
            t = (si + k) / fps
            d.rectangle((x, y, x + 64, y + 20), fill=(0, 0, 0))
            d.text((x + 4, y + 3), f"{t:5.2f}s", font=font, fill=(0, 255, 0))
        p = os.path.join(sdir, f"sheet_{si // per:02d}.png")
        sheet.save(p)
        out.append(os.path.relpath(p, out_dir))
    shutil.rmtree(fdir)
    return out


def keyframes(path, out_dir, shots):
    kdir = os.path.join(out_dir, "keyframes")
    os.makedirs(kdir, exist_ok=True)
    for k, c in enumerate(shots):
        t = c["start"] + c["dur"] / 2
        p = os.path.join(kdir, f"cut_{k:02d}.png")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", p])
        c["keyframe"] = os.path.relpath(p, out_dir)
    return shots


def palette(out_dir, shots, n=6):
    """Global palette: quantize every keyframe, pool colours, merge near-duplicates, rank by coverage."""
    pool = {}
    for c in shots:
        p = os.path.join(out_dir, c.get("keyframe", ""))
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB").resize((160, 160)).quantize(n, method=Image.Quantize.MEDIANCUT)
        pal = im.getpalette()[: n * 3]
        counts = sorted(im.getcolors(), reverse=True)
        c["palette"] = []
        for cnt, idx in counts:
            rgb = tuple(pal[idx * 3: idx * 3 + 3])
            key = tuple(v // 24 for v in rgb)
            pool.setdefault(key, [0, rgb])
            pool[key][0] += cnt
            c["palette"].append("#%02X%02X%02X" % rgb)
    ranked = sorted(pool.values(), key=lambda x: -x[0])
    total = sum(x[0] for x in ranked) or 1
    return [{"hex": "#%02X%02X%02X" % rgb, "share": round(cnt / total, 3)} for cnt, rgb in ranked[:10]]


def audio_profile(path, duration):
    vol = sh(["ffmpeg", "-v", "info", "-i", path, "-af", "volumedetect", "-f", "null", "-"]).stderr
    mean = re.search(r"mean_volume: ([-\d.]+)", vol)
    sil = sh(["ffmpeg", "-v", "info", "-i", path, "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"]).stderr
    gaps = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sil)]
    per_min = len(gaps) / max(duration / 60, 1e-6)
    kind = ("narration (frequent short pauses)" if per_min > 6 and gaps and sum(gaps) / len(gaps) < 1.2
            else "music / continuous bed" if per_min < 2 else "mixed")
    return {"mean_db": float(mean.group(1)) if mean else None, "pauses_per_min": round(per_min, 1), "guess": kind}


def transcribe(path, out_dir):
    wav = os.path.join(out_dir, "_audio.wav")
    sh(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav])
    from framesmith.narration import transcribe_words
    r = transcribe_words(wav)
    os.remove(wav)
    return {"text": " ".join(w["word"] for w in r["words"]), "words": r["words"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--out")
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--scene", type=float, default=0.3, help="scene-cut sensitivity (lower = more cuts)")
    ap.add_argument("--transcribe", action="store_true", help="Whisper transcript with word times (needs OPENAI_API_KEY)")
    a = ap.parse_args()
    name = re.sub(r"[^a-zA-Z0-9_-]", "", os.path.splitext(os.path.basename(a.src.split("?")[0]))[0]) or "ref"
    out = a.out or os.path.join("analysis", name)
    os.makedirs(out, exist_ok=True)
    ref = fetch(a.src, out)
    info = probe(ref)
    shots = keyframes(ref, out, cuts(ref, a.scene, info["duration"]))
    font = F("mono", 13)
    result = {
        "source": a.src, "file": os.path.basename(ref), **info,
        "aspect": f"{info['width']}:{info['height']}",
        "shots": shots, "shot_count": len(shots),
        "avg_shot_s": round(info["duration"] / max(1, len(shots)), 2),
        "palette": palette(out, shots),
        "audio": audio_profile(ref, info["duration"]) if info["has_audio"] else None,
        "sheets": sheets(ref, out, a.fps, font),
    }
    if a.transcribe and info["has_audio"] and not os.environ.get("OPENAI_API_KEY"):
        print("warning: --transcribe needs OPENAI_API_KEY; skipping transcript", file=sys.stderr)
    elif a.transcribe and info["has_audio"]:
        result["transcript"] = transcribe(ref, out)
        wps = len(result["transcript"]["words"]) / info["duration"]
        result["audio"]["words_per_s"] = round(wps, 2)
        if wps > 1.2:
            result["audio"]["guess"] = f"narration ({wps:.1f} words/s)"
    json.dump(result, open(os.path.join(out, "analysis.json"), "w"), indent=1)
    lines = [f"# Reference analysis: {name}", "",
             f"- **Format:** {info['width']}×{info['height']} ({result['aspect']}), {info['fps']} fps, {info['duration']:.2f} s",
             f"- **Shots:** {len(shots)} detected, avg {result['avg_shot_s']} s (scene threshold {a.scene}; dissolves and fast flashes may merge or split)",
             f"- **Audio:** {result['audio']['guess'] if result['audio'] else 'none'}"
             + ("" if result.get("transcript") or not result["audio"] else " (heuristic; run with --transcribe to confirm narration)")
             + (f", mean {result['audio']['mean_db']} dB" if result["audio"] else ""),
             "- **Palette (by coverage):** " + " ".join(f"`{p['hex']}` {p['share']:.0%}" for p in result["palette"][:8]),
             "", "## Look at these first", ""] + [f"- `{s}`" for s in result["sheets"]] + [
             "", "## Storyboard skeleton (fill in; merge or split shots where the detector was wrong)", "",
             "| # | Start | Dur | Keyframe | Layout / subject | Type (face, size, colour) | Motion in / out | Transition | Copy |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {k + 1} | {c['start']:.2f} | {c['dur']:.2f} | `{c['keyframe']}` |  |  |  |  |  |" for k, c in enumerate(shots)]
    if result.get("transcript"):
        lines += ["", "## Transcript", "", result["transcript"]["text"]]
    open(os.path.join(out, "report.md"), "w").write("\n".join(lines) + "\n")
    print(f"{out}/report.md  ·  {len(shots)} shots  ·  {len(result['sheets'])} sheets  ·  audio: "
          f"{result['audio']['guess'] if result['audio'] else 'none'}")


if __name__ == "__main__":
    main()
