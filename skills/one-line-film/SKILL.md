---
name: one-line-film
description: Render a 16:9 one-line film (20 s, felt-piano score) where the whole film is one continuous line of constant width with round caps, led by a pen tip. Each figure's tail is the next one's start, from seed to sapling to a house drawn out of the branch, then a skyline and a horizon that lifts and loops into a monogram ring and letter. The camera follows the tip with older segments dimmed to 35 %. At the hero moment the ring fills from the letter's anchor point (line to fill), and the camera dollies out to reveal the whole drawing as a poster while the wordmark sets in letter-spaced serif caps. Use for architecture, interiors, real estate, luxury, jewellery, wine, hotels, studios, "brand story in one line", logo reveals, or when the user asks for "line art animation", "one continuous line", "single-line drawing", "draw-on logo", "monoline" or "stroke animation".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: line-art, draw-on, logo-reveal, monogram, luxury, architecture, minimal
---

# One-line film

A 20 s, 1920×1080 film drawn by one line of about 11 000 world units:
- The draw eases into and out of each figure, using `cubic-bezier(0.65, 0, 0.35, 1)`-like timing on its own cue.
- The camera follows the pen tip with a lag and opens tight on the seed.
- At the end it zooms out in log space to frame the whole drawing as a poster.
- The ring then fills from the monogram's anchor point, and the letter stays as a cut line.

From the line-art study in [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15/blob/main/prompts/02-line-art.md): a midnight ground #0B1320, a single champagne line #E9D7A5 at a constant ~3 px with round caps, a story where each figure's tail starts the next, older segments dimmed to about 35 %, and the line-to-fill moment. The pen tip is a solid point with a thin ring, with no glow.

Example: `examples/vrana/` is a fictional architecture studio with a "V" monogram.

## Workflow

1. Copy `examples/vrana/brief.json`. Set `copy` (brand, one line saying what the studio or brand does, URL) and `monogram`, a single-stroke letter: `V W M N A Z L U`.
2. To draw something else, edit `build_path()` in `scripts/main.py`. It's a list of beziers, segments and arcs appended end to end, and `CUES` maps each figure to its time window. Keep one continuous path.
3. `check` → `still 0.6 2.5 5 8.5 11.5 13.6 15.5 19` → `render`.

## Rules

- One line, one colour, constant width. Nothing else draws except the fill and the wordmark.
- Wordmark in `serif` caps tracked wide; the second line in `sans_medium`. No italics.
- Add letters to `LETTERS` as single-stroke polylines in a unit box. Start at a box corner so the stroke leaves the ring cleanly.
