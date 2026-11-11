---
name: riso-poster-promo
description: Render a vertical risograph street-poster promo (20 s, 9:16, 120 BPM, synthesised score) printed in two inks, fluorescent pink and riso blue by default, multiplied onto paper with riso grain re-rolled every other frame. Ultra-condensed headlines slam in glyph by glyph on 1/16-note staggers. A ghost plate misregisters only on impact frames, and a halftone ramp rises on the opening beat. A word repeats down the page like delay taps, then the camera flies through the counter of its O into a duotone halftone of the product photo. Spec numbers land on the beat, facts arrive as inverse-video bands with letters that scramble and snap, the product name runs the full height filled with halftone, and the end card closes on price, availability and URL. Use for product drops, music gear, records, merch, events, indie hardware, zines, or any launch that should feel printed, or when the user asks for "risograph", "riso", "duotone", "halftone poster", "street poster", "screen-print look" or "gig-poster motion".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, risograph, halftone, duotone, kinetic-typography, product-drop, vertical-video, music-driven
---

# Riso poster promo

A 20 s, 1080×1920 promo in six scenes at 120 BPM. Every frame is two coverage masks, one per plate, composited by `framesmith.press`. Overlaps multiply like real ink, so pink over blue goes deep violet.

The grammar follows the riso and street-poster prompts collected in the Opus 5.5 motion-design lists ([motionvideohq/awesome-opus-5-5-motion-design](https://github.com/motionvideohq/awesome-opus-5-5-motion-design), the techhalla prompt), and the grain recipe follows makevoid's p5 `riso.js`:
- misregistration only on impact frames (a 40 % duplicate offset 2–4 px)
- per-glyph springs staggered by a 1/16 note
- seeded Fisher–Yates letter scrambles that snap on the beat
- punch-ins of up to 1.045× instead of camera moves
- the outgoing word's shape is the mask that reveals the next scene

The banned list applies too: no soft gradients, no glows, no bouncy cartoon easing, no particles, no HUD chrome.

Example: `examples/ferrum/` is a fictional tape-echo guitar pedal. Its product photo was generated with gpt-image, then halftoned.

## Workflow

1. Copy `examples/ferrum/brief.json`. Edit `copy` and `assets.hero.prompt`, and optionally the two plate colours in `theme`.
2. `python3 scripts/main.py assets --brief brief.json` generates `hero` with gpt-image (medium quality). It needs `OPENAI_API_KEY`.
   - Without a key, the bundled placeholder is used and `check` warns.
   - A real product photo works better than a generated one. Ask for a top-down shot on a plain light background with hard shadows.
3. Run all copy through `no-ai-slop`. Facts are product facts, and there are no trailing periods.
4. `check` → `still 0.6 3 4.3 6 9.5 13 17 19.5` → `render`.

## Brief

| key | meaning |
|---|---|
| `theme` | `paper`, `ink`, `plate_a` (headlines, default fluorescent pink #FF48B0), `plate_b` (photo shadows and crumbs, default riso blue #0078BF) |
| `copy.slam` | the opening one-word headline (4–6 letters slam best) |
| `copy.echo` | the word that repeats like delay taps. Give it an O for the counter fly-through; without one, `check` warns and the fly-through uses the glyph |
| `copy.specs` | up to 3 `[number, label]` pairs |
| `copy.facts` | up to 4 short lines for the inverse bands (≈ 28 characters keeps them big) |
| `copy.brand`, `product`, `kicker`, `price`, `ships`, `url` | the end card and crumbs |
| `assets.hero` | the product photo slot. Framing: top-down or front, centred, filling ~70 %, plain light ground, high contrast. Format `{product}`-style fields from `copy` |

## Rules

- Headlines use `condensed` (Anton, OFL); crumbs use `pixel` (Departure Mono). No italics, and no boxes or chips behind labels. Readable type sits on bare paper or knocks out of a solid band.
- Only two inks. A third colour breaks the print logic; to get a darker tone, overprint the two plates.
- `references/storyboard.md` has the beat sheet.
