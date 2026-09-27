"""Blocky techno wordmark for any brand name (A–Z, 0–9, space, '-', '.').

Glyphs sit on a 5×5 grid. '#' is a full cell, '.' empty, and q/p/b/d are
cells with a 45° chamfer cut from the top-left / top-right / bottom-left /
bottom-right corner. Cells are wider than tall for a squat, industrial look.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

GLYPHS = {
    "A": "q###p #...# ##### #...# #...#", "B": "####p #...# ####. #...# ####d",
    "C": "q#### #.... #.... #.... b####", "D": "####p #...# #...# #...# ####d",
    "E": "q#### #.... ####. #.... b####", "F": "q#### #.... ####. #.... #....",
    "G": "q#### #.... #.### #...# b####", "H": "#...# #...# ##### #...# #...#",
    "I": "##### ..#.. ..#.. ..#.. #####", "J": "....# ....# ....# #...# b###d",
    "K": "#...# #..#. ###.. #..#. #...#", "L": "#.... #.... #.... #.... b####",
    "M": "q###p #.#.# #.#.# #.#.# #.#.#", "N": "q###p #...# #...# #...# #...#",
    "O": "q###p #...# #...# #...# b###d", "P": "q###p #...# ####d #.... #....",
    "Q": "q###p #...# #...# #..#. b##.#", "R": "q###p #...# ####d #..#. #...#",
    "S": "q#### #.... b###p ....# ####d", "T": "##### ..#.. ..#.. ..#.. ..#..",
    "U": "#...# #...# #...# #...# b###d", "V": "#...# #...# #...# .#.#. ..#..",
    "W": "#...# #...# #.#.# #.#.# b###d", "X": "#...# .#.#. ..#.. .#.#. #...#",
    "Y": "#...# #...# b###d ..#.. ..#..", "Z": "##### ...#. ..#.. .#... #####",
    "0": "q###p #..## #.#.# ##..# b###d", "1": ".q#.. ..#.. ..#.. ..#.. #####",
    "2": "q###p ....# q###d #.... #####", "3": "####p ....# .###. ....# ####d",
    "4": "#...# #...# ##### ....# ....#", "5": "##### #.... ####p ....# ####d",
    "6": "q#### #.... ####p #...# b###d", "7": "##### ....# ...#. ..#.. ..#..",
    "8": "q###p #...# ##### #...# b###d", "9": "q###p #...# b#### ....# ####d",
    "-": "..... ..... .###. ..... .....", ".": "..... ..... ..... ..... ..#..",
    " ": "... ... ... ... ...",
}
ASPECT = 1.3   # cell width / height


def _cell(d, x, y, cw, ch, k):
    x2, y2 = x + cw, y + ch
    shape = {
        "#": [(x, y), (x2, y), (x2, y2), (x, y2)],
        "q": [(x2, y), (x2, y2), (x, y2)],
        "p": [(x, y), (x2, y2), (x, y2)],
        "b": [(x, y), (x2, y), (x2, y2)],
        "d": [(x, y), (x2, y), (x, y2)],
    }.get(k)
    if shape:
        d.polygon(shape, fill=255)


def layout(word, unit):
    """Per-letter (x_offset, width) in px for a given cell height `unit`."""
    cw = unit * ASPECT
    x, out = 0.0, []
    for c in word.upper():
        rows = GLYPHS.get(c, GLYPHS[" "]).split()
        w = len(rows[0]) * cw
        out.append((x, w))
        x += w + cw
    return out, x - cw


def wordmark_mask(word, size, unit, letters_dx=None, outline=0, y_offset=0):
    """L-mode mask of `word` centred in `size`. Returns (mask, letter_boxes)."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    cw = unit * ASPECT
    lay, total = layout(word, unit)
    x0 = (size[0] - total) / 2
    y0 = (size[1] - 5 * unit) / 2 + y_offset
    boxes = []
    for i, c in enumerate(word.upper()):
        rows = GLYPHS.get(c, GLYPHS[" "]).split()
        ox = x0 + lay[i][0] + (letters_dx[i] if letters_dx else 0)
        for r, row in enumerate(rows):
            for k, ch in enumerate(row):
                _cell(d, ox + k * cw, y0 + r * unit, cw + 0.6, unit + 0.6, ch)
        boxes.append((ox, y0, ox + lay[i][1], y0 + 5 * unit))
    if outline:
        inner = m.filter(ImageFilter.MinFilter(outline * 2 + 1))
        m = Image.fromarray(((np.asarray(m) > 0) & (np.asarray(inner) == 0)).astype(np.uint8) * 255)
    return m, boxes


def fit_unit(word, max_width, max_unit):
    """Largest cell height (≤ max_unit) at which `word` fits in max_width px."""
    _, total = layout(word, 1.0)
    return min(max_unit, max_width / max(total, 1e-6))


def spread(n, amount):
    """Symmetric per-letter x offsets pushing letters away from the centre."""
    c = (n - 1) / 2
    return [(i - c) / max(c, 1) * amount for i in range(n)]
