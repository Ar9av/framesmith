"""framesmith — a tiny deterministic motion-graphics engine for AI agent skills.

Pure Python (numpy + Pillow) → frames → ffmpeg. No browser, no GPU.
Templates live in skills/<name>/ and vendor this package into their scripts/.
"""
__version__ = "0.14.0"

from .easing import bezier, ease_out, ease_in_out, ease_drawer, linear, prog, lerp, h
from .theme import Theme, hex2rgb, mix, luminance
from .typography import F, text, text_width, fit, scramble, typed, decay, rot_text, overflow_report
from .timeline import Timeline, Scene, Ctx, Mosaic, Dissolve, Cut
from .media import Assets, cover, cover_point, sprite_masks, pingpong, generate_images
from .wordmark import wordmark_mask, spread, fit_unit
from . import fx, blueprint, ui, narration, console
