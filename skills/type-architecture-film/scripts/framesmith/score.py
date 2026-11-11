"""A beat-grid score synthesised in numpy: one cue sheet drives both picture and sound.

    sc = Score(bpm=120, dur=20.0)
    sc.pattern("kick", every=1)                       # every beat
    sc.hit("clack", sc.beat(8), pitch=1.4)            # one hit at beat 8
    sc.bass([("A1", 0, 2), ("C2", 2, 2)], start=sc.bar(4))
    sc.write("score.wav")

Instruments are short, dry and percussive on purpose (clicks, clacks, blips, a sub kick, a
plucked bass, a felt-piano tone and a soft pad), which is what kinetic posters and print films
want. No scipy needed; randomness is seeded.
"""
import math, subprocess, wave

import numpy as np

SR = 48000
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def midi(s):
    """'A1' → 33, 'C#4' → 61, or an int passes through."""
    if isinstance(s, (int, float)):
        return s
    return 12 * (int(s[-1]) + 1) + NOTE[s[:-1]]


def hz(note):
    return 440 * 2 ** ((midi(note) - 69) / 12)


def _t(n):
    return np.arange(n, dtype=np.float32) / SR


def _env(n, a=0.002, d=0.2):
    t = _t(n)
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def _lp(x, k):
    """Cheap low-pass: moving average of k samples."""
    if k <= 1:
        return x
    c = np.cumsum(np.concatenate([[0], x]))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([y, np.zeros(k - 1)])


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n).astype(np.float32)


def kick(pitch=1.0):
    n = int(0.42 * SR)
    t = _t(n)
    f = (52 + 110 * np.exp(-t * 28)) * pitch
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 0.16)
    click = _lp(_noise(n, 1), 3) * _env(n, 0.0005, 0.004) * 0.35
    return (body + click) * 0.95


def clack(pitch=1.0, seed=2):
    """Wood/metal clack: two inharmonic partials + a noise transient (a module landing)."""
    n = int(0.12 * SR)
    t = _t(n)
    f = 1150 * pitch
    s = np.sin(2 * np.pi * f * t) * _env(n, 0.0005, 0.03) + 0.5 * np.sin(2 * np.pi * f * 2.71 * t) * _env(n, 0.0005, 0.012)
    s += _lp(_noise(n, seed), 2) * _env(n, 0.0003, 0.003) * 0.6
    return s * 0.45


def tick(pitch=1.0):
    n = int(0.04 * SR)
    t = _t(n)
    return np.sin(2 * np.pi * 3200 * pitch * t) * _env(n, 0.0003, 0.008) * 0.35


def hat(open_=False, seed=5):
    n = int((0.22 if open_ else 0.05) * SR)
    x = _noise(n, seed)
    x = x - _lp(x, 6)                                  # high-pass by subtracting the low band
    return x * _env(n, 0.0005, 0.07 if open_ else 0.012) * 0.28


def snare(seed=7):
    n = int(0.25 * SR)
    t = _t(n)
    tone = np.sin(2 * np.pi * 190 * t) * _env(n, 0.001, 0.05)
    x = _noise(n, seed)
    x = x - _lp(x, 4)
    return (tone * 0.6 + x * _env(n, 0.001, 0.07) * 0.7) * 0.5


def blip(note="A5", dur=0.09):
    n = int(dur * 2 * SR)
    t = _t(n)
    f = hz(note)
    sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.25 + np.sin(2 * np.pi * f * t) * 0.75
    return _lp(sq, 3) * _env(n, 0.001, dur * 0.5) * 0.3


def pluck(note="A2", dur=0.4):
    """Karplus-Strong plucked bass."""
    f = hz(note)
    p = max(2, int(SR / f))
    n = int(dur * 1.5 * SR)
    buf = _noise(p, int(f))
    out = np.zeros(n, np.float32)
    for i in range(0, n, p):                           # vectorised per period: average with the shifted buffer
        k = min(p, n - i)
        out[i:i + k] = buf[:k]
        buf = 0.5 * (buf + np.roll(buf, -1)) * 0.996
    sub = np.sin(2 * np.pi * f * _t(n)) * _env(n, 0.004, dur * 0.6)
    return (out * 0.5 + sub * 0.7) * _env(n, 0.001, dur) * 0.6


def piano(note="E4", dur=1.2):
    """Felt-piano tone: decaying partials with a soft hammer."""
    n = int(dur * 2.0 * SR)
    t = _t(n)
    f = hz(note)
    s = sum(a * np.sin(2 * np.pi * f * k * t) * _env(n, 0.004, dur / (1 + 0.6 * k)) for k, a in ((1, 1), (2, 0.35), (3, 0.12), (4, 0.05)))
    return _lp(s, 2) * 0.32


def pad(notes, dur):
    """Soft detuned pad chord, swelling in and out over dur."""
    n = int(dur * SR)
    t = _t(n)
    sw = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    s = np.zeros(n, np.float32)
    for note in notes:
        f = hz(note)
        for det in (-0.12, 0.0, 0.11):
            s += np.sin(2 * np.pi * f * (1 + det / 100) * t + det * 9)
    return _lp(s / (3 * len(notes)), 8) * sw * 0.22


def riser(dur=1.0, seed=9):
    n = int(dur * SR)
    t = _t(n)
    x = _noise(n, seed)
    x = x - _lp(x, 3)
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 1800 * (t / dur) ** 2) / SR) * 0.15
    return (x * 0.18 + sweep) * (t / dur) ** 2


def thud():
    n = int(0.3 * SR)
    t = _t(n)
    f = 90 * np.exp(-t * 10) + 38
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.09) * 0.9


def paper_slap(seed=11):
    """A sheet landing on a table: filtered noise burst with a low body."""
    n = int(0.18 * SR)
    x = _lp(_noise(n, seed), 5) * _env(n, 0.001, 0.035)
    return (x * 0.9 + thud()[:n] * 0.4) * 0.6


def scratch(dur=0.3, seed=13):
    """Pencil on paper."""
    n = int(dur * SR)
    x = _noise(n, seed)
    x = x - _lp(x, 3)
    am = 0.6 + 0.4 * np.sin(2 * np.pi * 23 * _t(n))
    return x * am * np.sin(np.pi * np.linspace(0, 1, n)) * 0.12


INSTRUMENTS = {"kick": kick, "clack": clack, "tick": tick, "hat": hat, "snare": snare, "blip": blip,
               "thud": thud, "riser": riser, "slap": paper_slap, "scratch": scratch}


class Score:
    def __init__(self, bpm=120, dur=20.0, offset=0.0):
        self.bpm, self.dur, self.offset = bpm, dur, offset
        self.L = np.zeros(int((dur + 2) * SR), np.float32)
        self.R = np.zeros_like(self.L)
        self._cache = {}

    # beat grid ------------------------------------------------------
    @property
    def spb(self):
        return 60.0 / self.bpm

    def beat(self, k):
        return self.offset + k * self.spb

    def bar(self, k):
        return self.beat(4 * k)

    # placing sound --------------------------------------------------
    def add(self, sig, t, gain=1.0, pan=0.0):
        s0 = int(t * SR)
        n = len(self.L)
        if s0 >= n or s0 + len(sig) <= 0:
            return
        a, b = max(0, s0), min(n, s0 + len(sig))
        seg = sig[a - s0:b - s0] * gain
        self.L[a:b] += seg * math.cos((pan + 1) * math.pi / 4)
        self.R[a:b] += seg * math.sin((pan + 1) * math.pi / 4)

    def hit(self, kind, t, gain=1.0, pan=0.0, **kw):
        key = (kind, tuple(sorted(kw.items())))
        if key not in self._cache:
            self._cache[key] = INSTRUMENTS[kind](**kw)
        self.add(self._cache[key], t, gain, pan)

    def pattern(self, kind, every=1.0, start=0.0, end=None, gain=1.0, skip=(), pan=0.0, **kw):
        """Repeat an instrument every `every` beats from beat `start` to beat `end` (exclusive)."""
        end = end if end is not None else (self.dur - self.offset) / self.spb
        k = start
        while k < end - 1e-9:
            if round(k, 3) not in skip:
                self.hit(kind, self.beat(k), gain, pan, **kw)
            k += every

    def bass(self, notes, start=0.0, gain=1.0):
        """notes = [(note, beat_offset, length_beats)] placed from time `start` (s)."""
        for note, b, ln in notes:
            self.add(pluck(note, ln * self.spb), start + b * self.spb, gain)

    def keys(self, notes, start=0.0, gain=1.0, pan=0.0):
        for note, b, ln in notes:
            self.add(piano(note, ln * self.spb), start + b * self.spb, gain, pan)

    def chord(self, notes, t, dur, gain=1.0):
        s = pad(notes, dur)
        self.add(s, t, gain * 0.9, -0.3)
        self.add(s, t + 0.011, gain * 0.9, 0.3)

    # output ---------------------------------------------------------
    def write(self, path, peak_db=-1.0):
        n = int(self.dur * SR)
        st = np.stack([self.L[:n], self.R[:n]], 1)
        fade = int(0.25 * SR)
        st[-fade:] *= np.linspace(1, 0, fade)[:, None]
        peak = np.abs(st).max() or 1
        st *= 10 ** (peak_db / 20) / peak
        wav = path if path.endswith(".wav") else path.rsplit(".", 1)[0] + ".wav"
        with wave.open(wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((st * 32767).astype(np.int16).tobytes())
        if not path.endswith(".wav"):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "aac", "-b:a", "192k", path], check=True)
        return path
