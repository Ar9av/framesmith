"""Colour theme: a strict few-colour system derived from one accent."""
from dataclasses import dataclass, field


def hex2rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mix(a, b, p):
    return tuple(int(round(x + (y - x) * p)) for x, y in zip(a, b))


@dataclass
class Theme:
    accent: tuple = (242, 86, 29)   # signal colour
    ink: tuple = (0, 0, 0)          # dark
    paper: tuple = (255, 255, 255)  # light
    tint: tuple = None              # deep accent used for mosaics / smears
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.tint is None:
            self.tint = mix(self.accent, self.ink, 0.43)

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        kw = {k: hex2rgb(d.pop(k)) for k in ("accent", "ink", "paper", "tint") if k in d}
        return cls(**kw, extra={k: hex2rgb(v) if isinstance(v, str) and v.startswith("#") else v for k, v in d.items()})

    # derived tones
    @property
    def accent_grid(self):
        return mix(self.accent, self.ink, 0.08)

    @property
    def paper_grid(self):
        return mix(self.paper, self.ink, 0.075)

    @property
    def on_accent(self):
        """Ink or paper, whichever reads better on the accent (WCAG relative luminance)."""
        return self.ink if luminance(self.accent) > 0.4 else self.paper

    @property
    def mid(self):
        return mix(self.paper, self.ink, 0.5)
