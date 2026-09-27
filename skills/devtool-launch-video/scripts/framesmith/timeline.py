"""Seekable timeline: scenes with durations, optional transitions, deterministic rendering.

Every frame is a pure function of its index, so any frame can be rendered alone
(stills for review) and full renders parallelise across processes.

    tl = Timeline([Scene("intro", 0.45, intro), Scene("title", 1.0, title, Mosaic(0.3))],
                  width=720, height=1280, fps=25)
    tl.render("out.mp4")          # or tl.still(3.2, "frame.png")

A scene function is fn(ctx) -> HxWx3 uint8 array, where ctx is a Ctx with
lt (local seconds), dur, t (global seconds), fi (frame index), W, H, and
whatever you passed as `data` (brief, theme, assets...).
"""
import multiprocessing as mp
import os, subprocess, sys
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

import numpy as np
from PIL import Image

from .easing import ease_in_out, prog
from .fx import mosaic


@dataclass
class Ctx:
    lt: float
    dur: float
    t: float
    fi: int
    W: int
    H: int
    data: object = None

    def p(self, a, b):
        """Local progress between a and b seconds (negative = relative to scene end)."""
        a = a if a >= 0 else self.dur + a
        b = b if b >= 0 else self.dur + b
        return prog(self.lt, a, b)

    def at(self, lt):
        """Same scene context at another local time (for freeze frames / smears)."""
        return replace(self, lt=lt, t=self.t - self.lt + lt)


@dataclass
class Mosaic:
    """Pixel-block wipe from the previous scene (which keeps running) into this one."""
    dur: float = 0.3
    cols: int = 6
    rows: int = 10
    seed: int = 1
    flashes: Optional[tuple] = None     # colours flashed mid-flip; default = theme colours
    ease: Callable = ease_in_out

    def blend(self, a, b, p, theme=None):
        fl = self.flashes or ((theme.ink, theme.paper, theme.accent) if theme else ((0, 0, 0), (255,) * 3))
        return mosaic(a, b, self.ease(p), self.cols, self.rows, self.seed, fl)


@dataclass
class Cut:
    """Hard cut (the default)."""
    dur: float = 0.0


@dataclass
class Scene:
    name: str
    dur: float
    fn: Callable
    transition: object = None


@dataclass
class Timeline:
    scenes: list
    width: int = 720
    height: int = 1280
    fps: int = 25
    data: object = None
    theme: object = None
    starts: list = field(init=False)

    def __post_init__(self):
        self.starts, t = [], 0.0
        for s in self.scenes:
            self.starts.append(t)
            t += s.dur
        self.duration = t

    @property
    def n_frames(self):
        return int(round(self.duration * self.fps))

    def _ctx(self, i, t, fi):
        return Ctx(t - self.starts[i], self.scenes[i].dur, t, fi, self.width, self.height, self.data)

    def _run(self, i, t, fi):
        out = self.scenes[i].fn(self._ctx(i, t, fi))
        out = np.asarray(out)
        if out.shape != (self.height, self.width, 3):
            raise ValueError(f"scene '{self.scenes[i].name}' returned {out.shape}")
        return out.astype(np.uint8, copy=False)

    def frame(self, fi):
        t = fi / self.fps
        i = max(k for k, s in enumerate(self.starts) if s <= t + 1e-9)
        i = min(i, len(self.scenes) - 1)
        cur = self._run(i, t, fi)
        tr = self.scenes[i].transition
        if i > 0 and isinstance(tr, Mosaic) and t - self.starts[i] < tr.dur:
            prev = self._run(i - 1, t, fi)      # previous scene keeps running under the wipe
            cur = tr.blend(prev, cur, (t - self.starts[i]) / tr.dur, self.theme)
        return np.ascontiguousarray(cur)

    def scene_at(self, t):
        i = max(k for k, s in enumerate(self.starts) if s <= t + 1e-9)
        return self.scenes[min(i, len(self.scenes) - 1)].name

    def still(self, t, path):
        Image.fromarray(self.frame(int(round(t * self.fps)))).save(path)
        return path

    def contact_sheet(self, path, cols=8, rows=4, thumb_w=180):
        n = cols * rows
        th = int(thumb_w * self.height / self.width)
        sheet = Image.new("RGB", (cols * thumb_w, rows * th))
        for k in range(n):
            fi = int((k + 0.5) / n * self.n_frames)
            im = Image.fromarray(self.frame(fi)).resize((thumb_w, th))
            sheet.paste(im, ((k % cols) * thumb_w, (k // cols) * th))
        sheet.save(path)
        return path

    def render(self, out, audio=None, workers=None, crf=16, log=True):
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.width}x{self.height}", "-r", str(self.fps), "-i", "-"]
        if audio:
            # pad the audio with silence so the video's own length (tails, black ends) is kept
            cmd += ["-i", audio, "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:a", "aac", "-b:a", "160k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", out]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        n = self.n_frames
        global _TL
        _TL = self
        try:
            ctx = mp.get_context("fork")
        except ValueError:                  # no fork (Windows): render in-process
            ctx = None
        if ctx and (workers or os.cpu_count() or 1) > 1:
            with ctx.Pool(workers or os.cpu_count()) as pool:
                it = pool.imap(_frame_bytes, range(n), chunksize=4)
                self._pipe(it, ff, n, log)
        else:
            self._pipe(map(_frame_bytes, range(n)), ff, n, log)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg failed")
        return out

    @staticmethod
    def _pipe(frames, ff, n, log):
        for i, b in enumerate(frames):
            ff.stdin.write(b)
            if log and i % 50 == 0:
                print(f"  frame {i}/{n}", file=sys.stderr)


_TL = None


def _frame_bytes(fi):
    return _TL.frame(fi).tobytes()
