"""Easing, interpolation and deterministic randomness.

Curves follow Emil Kowalski's motion tokens: strong ease-out for entrances,
strong ease-in-out for on-screen moves, linear only for constant motion.
Never use ease-in for something entering the frame.
"""
import zlib


def bezier(x1, y1, x2, y2):
    """CSS-style cubic-bezier(x1, y1, x2, y2) as a function of t in [0, 1]."""
    def f(t):
        t = min(max(t, 0.0), 1.0)
        u = t
        for _ in range(8):
            x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u ** 2 * x2 + u ** 3 - t
            dx = 3 * (1 - u) ** 2 * x1 + 6 * (1 - u) * u * (x2 - x1) + 3 * u ** 2 * (1 - x2)
            if abs(dx) < 1e-6:
                break
            u = min(max(u - x / dx, 0.0), 1.0)
        return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u ** 2 * y2 + u ** 3
    return f


ease_out = bezier(0.23, 1, 0.32, 1)        # entrances, reveals
ease_in_out = bezier(0.77, 0, 0.175, 1)    # zooms / moves of things already on screen
ease_drawer = bezier(0.32, 0.72, 0, 1)     # panel / sheet slides
linear = lambda t: min(max(t, 0.0), 1.0)   # marquees, counters, scrolls


def prog(t, a, b):
    """Normalised progress of t through [a, b], clamped to [0, 1]."""
    if b == a:
        return 1.0 if t >= b else 0.0
    return min(max((t - a) / (b - a), 0.0), 1.0)


def lerp(a, b, p):
    return a + (b - a) * p


def h(*key):
    """Deterministic hash of any key → float in [0, 1). Same key, same value, every render."""
    return (zlib.crc32(repr(key).encode()) & 0xFFFFFF) / 0x1000000
