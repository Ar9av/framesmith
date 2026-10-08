"""Soundtrack for cartoon-launch-film: 120 BPM, F major, everything synthesised.
Plucked bass (Karplus-Strong), marimba lead, glockenspiel, kick/clap/shaker, plus cartoon SFX on the film's beats.
Writes OUT_DIR/mix.wav and OUT_DIR/mix.m4a. Cues follow the timings in main.py."""
import math, os, subprocess, sys, wave
import numpy as np

if __name__ == "__main__" and (len(sys.argv) < 3 or sys.argv[1] != "score"):
    print("usage: audio.py score OUT_DIR   (main.py render runs this)")
    sys.exit(0)
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
from scipy.signal import lfilter

SR = 48000
SH = 12.5                                       # new browser + answer beats inserted at B(32)
T_END = 32.4 + SH
B0 = 4.2
N = int((T_END + 1) * SR)
L = np.zeros(N)       # left
R = np.zeros(N)       # right
rng = np.random.default_rng(3)


def B(k):
    return B0 + 0.5 * k


def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def m(s):                                     # "F4" -> midi
    return 12 * (int(s[-1]) + 1) + NOTE[s[:-1]]


def add(sig, t, gain=1.0, pan=0.0):
    s0 = int(t * SR)
    if s0 >= N or s0 + len(sig) <= 0:
        return
    a, b = max(0, s0), min(N, s0 + len(sig))
    seg = sig[a - s0:b - s0] * gain
    L[a:b] += seg * math.cos((pan + 1) * math.pi / 4)
    R[a:b] += seg * math.sin((pan + 1) * math.pi / 4)


def env(n, a=0.002, d=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def lp(x, fc):
    k = math.exp(-2 * math.pi * fc / SR)
    return lfilter([1 - k], [1, -k], x)


def hp(x, fc):
    return x - lp(x, fc)


# ---------------------------------------------------------------- instruments
def marimba(note, dur=0.5):
    n = int(dur * 1.6 * SR)
    t = np.arange(n) / SR
    f = mtof(note)
    s = np.sin(2 * np.pi * f * t) * env(n, 0.001, 0.32) + 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * env(n, 0.001, 0.05)
    s += 0.12 * np.sin(2 * np.pi * f * 9.2 * t) * env(n, 0.0005, 0.012)
    return s * 0.5


def glock(note):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = mtof(note)
    return (np.sin(2 * np.pi * f * t) * env(n, 0.001, 0.6) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * env(n, 0.001, 0.15)) * 0.28


def pluck(note, dur=0.45, bright=0.5):
    f = mtof(note)
    p = int(SR / f)
    n = int(dur * SR)
    buf = rng.uniform(-1, 1, p)
    buf = lp(buf, 1200 + 3000 * bright)
    out = np.zeros(n)
    for i in range(n):                         # Karplus-Strong
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out * env(n, 0.003, dur * 0.6) * 0.9


_pl = {}


def bass(note, dur=0.45):
    k = (note, dur)
    if k not in _pl:
        _pl[k] = lp(pluck(note, dur, 0.2), 900) + 0.5 * np.sin(2 * np.pi * mtof(note) * np.arange(int(dur * SR)) / SR) * env(int(dur * SR), 0.004, dur * 0.4)
    return _pl[k]


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.12) * 0.9


def clap():
    n = int(0.25 * SR)
    x = hp(lp(rng.standard_normal(n), 3500), 900)
    e = np.zeros(n)
    for d in (0, 0.011, 0.022):
        e += env(n, 0.0005, 0.012) * (np.arange(n) >= d * SR)
    e += env(n, 0.001, 0.09) * 0.6
    return x * e * 0.45


def shaker():
    n = int(0.08 * SR)
    return hp(rng.standard_normal(n), 6000) * env(n, 0.006, 0.025) * 0.18


def crash(dur=1.6):
    n = int(dur * SR)
    return hp(rng.standard_normal(n), 4000) * env(n, 0.002, dur * 0.35) * 0.35


# ---------------------------------------------------------------- sfx
def sweep(f0, f1, dur, shape="sin", decay=None, vib=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur) * (1 + vib * np.sin(2 * np.pi * 7 * t))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    e = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.03)
    if decay:
        e *= np.exp(-t / decay)
    return s * e


def pop():
    return sweep(500, 1400, 0.07) * 0.35


def gulp():
    return (sweep(520, 160, 0.16) + 0.4 * sweep(1040, 320, 0.16)) * 0.4


def boing():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 220 * (1 + 0.35 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 6)) * (1 + 0.6 * np.exp(-t * 12))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.18) * 0.35


def whoosh(dur=0.45, f0=400, f1=2500):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    # time-varying band via chunked filtering
    ch = 512
    for i in range(0, n, ch):
        fc = f0 * (f1 / f0) ** (i / n)
        out[i:i + ch] = hp(lp(x[i:i + ch], fc * 1.6), fc * 0.5)
    t = np.arange(n) / SR
    return out * np.sin(np.pi * t / dur) ** 2 * 0.35


def key():
    n = int(0.03 * SR)
    return hp(rng.standard_normal(n), 2500) * env(n, 0.0003, 0.006) * 0.25 + np.pad(sweep(1800, 1200, 0.02) * 0.05, (0, n - int(0.02 * SR)))


def scribble(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = hp(lp(rng.standard_normal(n), 5000), 1500)
    return x * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t)) * np.sin(np.pi * t / dur) * 0.16


def boom(dur=1.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-t * 6)) / SR) * env(n, 0.002, 0.5)
    s += lp(rng.standard_normal(n), 500) * env(n, 0.002, 0.45) * 1.2
    s += hp(rng.standard_normal(n), 2500) * env(n, 0.001, 0.15) * 0.4
    return s * 0.8


def thud():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-t * 25)) / SR) * env(n, 0.001, 0.14)
            + lp(rng.standard_normal(n), 900) * env(n, 0.001, 0.06)) * 0.9


def slide_whistle(f0, f1, dur):
    return sweep(f0, f1, dur, vib=0.012) * 0.3 + sweep(f0 * 2, f1 * 2, dur, vib=0.012) * 0.06


def ding(note=m("C7")):
    return glock(note) * 1.6


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (whoosh(dur, 300, 6000) * 0.9 + sweep(200, 900, dur) * 0.08) * (t / dur) ** 2


def tick():
    return sweep(2400, 2200, 0.025) * 0.18


# ---------------------------------------------------------------- music
CHORDS = [("F", [m("F2")], [m("A4"), m("C5"), m("F5")]), ("Dm", [m("D2")], [m("A4"), m("D5"), m("F5")]),
          ("Bb", [m("A#1")], [m("A#4"), m("D5"), m("F5")]), ("C", [m("C2")], [m("G4"), m("C5"), m("E5")])]
MEL = [["C5", None, "A4", "C5", "F5", None, "E5", "C5"], ["D5", None, "A4", "D5", "F5", "E5", "D5", None],
       ["D5", None, "A#4", "D5", "F5", None, "G5", "F5"], ["E5", None, "C5", "E5", "G5", "F5", "E5", "C5"]]
MEL2 = [["F5", "G5", "A5", None, "C6", None, "A5", "F5"], ["D5", "F5", "A5", None, "G5", "F5", "D5", None],
        ["A#5", None, "A5", "G5", "F5", None, "D5", "F5"], ["G5", None, "E5", "C5", "E5", "F5", "G5", None]]


def section(tb):
    """What plays at a beat time: returns dict of layers."""
    if tb < B(1):
        return None
    if B(32) <= tb < B(35) + SH:                   # the new Chrome-extension and answer beats
        return dict(bass=True, stab=True, mel=True, drums="full", sad=False, hi=False)
    if tb >= B(35) + SH:
        tb -= SH
    if B(5) <= tb < B(9):                          # the sad, forgetful bit: sparse, minor colour
        return dict(bass=True, stab=False, mel=False, drums="light", sad=True)
    if B(38.5) <= tb < B(41):                      # explosion and smoke: silence
        return None
    if tb >= B(54.5):
        return None
    hi = tb >= B(41)
    return dict(bass=True, stab=True, mel=True, drums="full", sad=False, hi=hi)


bar = 2.0
for k in range(0, 200):
    tb = B(0) + k * 0.25                            # eighth notes
    if tb >= T_END:
        break
    sec = section(tb)
    if not sec:
        continue
    bi = int((tb - B0) // bar) % 4
    e = int(round((tb - B0) / 0.25)) % 8
    name, bnotes, chord = CHORDS[bi]
    if sec.get("sad"):
        name, bnotes, chord = (CHORDS[1] if bi % 2 == 0 else CHORDS[2])
    if sec["bass"] and e in (0, 4):
        add(bass(bnotes[0] if e == 0 else bnotes[0] + 7, 0.45), tb, 0.55)
    if sec["bass"] and e == 6 and not sec.get("sad"):
        add(bass(bnotes[0] + 12, 0.25), tb, 0.35)
    if sec["stab"] and e in (2, 6):
        for j, cn in enumerate(chord):
            add(marimba(cn - 12, 0.25), tb, 0.16, pan=-0.3 + 0.3 * j)
    if sec["mel"]:
        mel = MEL2 if sec.get("hi") else MEL
        nn = mel[bi][e]
        if nn:
            add(marimba(m(nn), 0.3), tb, 0.42, pan=0.15)
            if sec.get("hi") and e in (0, 4):
                add(glock(m(nn) + 12), tb, 0.35, pan=-0.2)
    if sec.get("sad") and e == 0:
        add(marimba(m("D5") if bi % 2 == 0 else m("C#5"), 0.5), tb, 0.3)
    dr = sec["drums"]
    if e in (0, 4):
        add(kick(), tb, 0.7 if dr == "full" else 0.35)
    if dr == "full" and e in (2, 6):
        add(clap(), tb, 0.6, pan=0.1)
    if dr == "full":
        add(shaker(), tb, 1.0 if e % 2 else 0.6, pan=0.4)

# ---------------------------------------------------------------- terminal cold open
for k in range(9):                                 # soft clock pulse
    add(tick() * 1.4, 0.2 + k * 0.5, 0.8)
for i in range(41):
    add(key(), 0.25 + i * (1.2 / 41) + rng.uniform(0, 0.01), 0.9, pan=0.1)
for i in range(5):
    add(key(), 2.6 + i * 0.05, 0.9, pan=0.1)
for i in range(7):
    add(key(), 3.65 + i * 0.045, 0.9, pan=0.1)
add(key() * 2.2, 4.0, 1.0)
add(scribble(0.4), 2.05, 1.0, pan=-0.2)
add(scribble(0.22), 3.32, 1.0, pan=-0.2)
for tm in (2.9, 3.12, 3.3):
    add(sweep(900, 1300, 0.05) * 0.2, tm, 1.0)
add(riser(1.0), 3.2, 0.9)

# ---------------------------------------------------------------- the cartoon
add(boom(1.4), B(0) - 0.05, 0.9)
add(crash(2.0), B(0), 0.8)
add(whoosh(0.5, 300, 3000), 4.7, 0.6)
add(thud(), 5.2, 1.0)
add(crash(1.0), 5.2, 0.3)
add(boing(), 5.45, 0.8)
add(boing(), 6.0, 0.6)
add(whoosh(0.35, 600, 4000), 6.45, 0.7)
for i in range(10):
    add(pop(), 6.75 + i * 0.09, 0.5, pan=(i % 3 - 1) * 0.5)
add(slide_whistle(700, 380, 0.6), 7.6, 0.6)            # the sad droop
for i in range(10):
    add(gulp(), B(9) + 0.25 + i * 0.22, 0.8, pan=-0.1)
add(sweep(300, 1600, 0.25) * 0.4, B(14), 1.0)          # cheeks fill
add(pop() * 2, B(15), 1.0)
add(ding(m("F6")), B(15), 0.8)
add(boing(), B(15) + 0.05, 0.6)
for i in range(6):
    add(pop(), B(16.5) + i * 0.25, 0.6, pan=(i % 2) * 0.6 - 0.3)
for i in range(6):
    add(whoosh(0.18, 1500, 5000) * 0.6, B(19) + i * 0.12, 0.6)
for i in range(7):
    add(whoosh(0.18, 1200, 4000) * 0.5, B(21) + i * 0.12, 0.6)
add(whoosh(0.35, 400, 6000), B(24) - 0.32, 0.9)       # whip
for n in range(9):
    add(pop(), B(24) + n * 0.05, 0.35)
for n in range(8):
    add(ding(m("C6") + [0, 2, 4, 5, 7, 9, 11, 12][n]) * 0.6, B(26.5) + n * 0.25, 0.7, pan=(n % 3 - 1) * 0.4)
add(whoosh(0.4, 500, 4000), B(31.5), 0.8)

# ---------------------------------------------------------------- Chrome: capture, then fill a form
TB = B(32)


def O(k):
    return B(k) + SH


def click():
    return key() * 1.6 + np.pad(sweep(1400, 900, 0.03) * 0.25, (0, 0))


add(whoosh(0.4, 400, 3000), TB, 0.6)
add(thud() * 0.7, TB + 0.35, 0.9)
add(scribble(0.7), TB + 1.25, 0.8, pan=-0.2)                      # drag-select
for c in (2.4, 3.05, 5.6, 6.0, 6.5):
    add(click(), TB + c, 1.0, pan=0.3)
add(pop(), TB + 2.42, 0.7)
add(whoosh(0.6, 2500, 400), TB + 3.1, 0.8)                        # page sucked into the brain
add(gulp(), TB + 3.65, 0.9)
add(ding(m("F6")), TB + 3.72, 0.8)
for i in range(10):
    add(key(), TB + 3.75 + i * 0.03, 0.6)
add(pop() * 0.7, TB + 4.45, 0.6)
add(whoosh(0.5, 300, 2500), TB + 4.85, 0.7)                       # page swaps to the form
for i in range(8):
    add(key(), TB + 4.85 + i * 0.04, 0.6)
add(pop(), TB + 5.62, 0.7)
for i in range(10):
    add(key(), TB + 6.55 + i * 0.03, 0.5)
add(pop() * 0.7, TB + 7.0, 0.6)
for i in range(3):
    tf = TB + 7.35 + i * 0.5
    for j in range(9):
        add(key(), tf + j * 0.038, 0.8, pan=0.1)
    add(ding(m("C6") + [0, 4, 7][i]), tf + 0.36, 0.7, pan=(i - 1) * 0.3)
add(sweep(330, 220, 0.25) * 0.35, TB + 8.85, 1.0)                 # the blank field
add(whoosh(0.35, 400, 6000), TB + 10.7, 0.9)
TA = TB + 11.0
add(pop() * 1.5, TA + 0.05, 0.8)
add(boing(), TA + 0.25, 0.6)
add(pop() * 1.5, TA + 0.5, 0.8)
add(scribble(0.3), TA + 1.4, 0.9)
add(whoosh(0.4, 500, 4000), TA + 2.7, 0.8)
add(thud() * 0.6, O(35), 0.8)
n = int(1.0 * SR)                                      # needle rattling at the limit
add(hp(rng.standard_normal(n), 3000) * 0.05 * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 20 * np.arange(n) / SR))), O(35) + 0.05, 1.0)
add(slide_whistle(1600, 420, 0.5), O(36), 0.8)
add(crash(1.2), O(37), 0.7)
add(ding(m("A6")), O(37), 0.9)
add(riser(0.5), O(37.5), 0.8)
add(boom(2.2), O(38.4), 1.2)
n = int(1.2 * SR)
add(lp(rng.standard_normal(n), 300) * env(n, 0.05, 0.6) * 0.6, O(39), 1.0)        # smoke rumble
for i in range(36):
    add(tick(), O(41) + 0.2 + 2.0 * (1 - (1 - i / 36) ** 0.5), 1.4, pan=0.2)
add(ding(m("C7")), O(41) + 2.2, 1.1)
add(crash(1.2), O(41) + 2.2, 0.5)
for i in range(12):
    add(sweep(1800 + 90 * i, 2600 + 90 * i, 0.05) * 0.12, O(41) + 0.1 + i * 0.2, 1.0, pan=rng.uniform(-0.6, 0.6))
add(pop(), O(48) + 0.2, 0.6)
add(pop(), O(48) + 0.7, 0.6)
add(scribble(0.35), O(48) + 1.3, 0.9)
add(whoosh(0.3, 400, 3000), O(54) - 0.3, 0.8)
add(thud(), O(54), 1.3)
add(crash(1.0), O(54), 0.5)
for j, cn in enumerate([m("F3"), m("A3"), m("C4"), m("F4")]):    # final chord
    add(marimba(cn, 0.9), O(54), 0.4, pan=-0.3 + 0.2 * j)
add(bass(m("F1"), 1.0), O(54), 0.7)

# ---------------------------------------------------------------- master
mix = np.stack([L, R], 1)[:int(T_END * SR)]
t = np.arange(len(mix)) / SR
mix[t >= T_END - 0.25] *= 0.0
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix *= 0.9 / np.abs(mix).max()
out = (mix * 32767).astype(np.int16)
w = wave.open(os.path.join(OUT, "mix.wav"), "wb")
w.setnchannels(2)
w.setsampwidth(2)
w.setframerate(SR)
w.writeframes(out.tobytes())
w.close()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(OUT, "mix.wav"), "-af", "loudnorm=I=-14:TP=-1.0:LRA=11", "-ar", "48000",
                "-c:a", "aac", "-b:a", "192k", os.path.join(OUT, "mix.m4a")], check=True)
print("ok", len(mix) / SR)
