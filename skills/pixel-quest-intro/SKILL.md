---
name: pixel-quest-intro
description: Render a 16:9 retro side-scroller attract sequence (20 s, chiptune) drawn at a true 320×180 in a 16-colour palette and scaled ×6 nearest-neighbour. It has a dithered sky, parallax ridge, trees and cottages, and ground tiles that all move by whole pixels. A hand-authored courier sprite runs on a stepped 12 fps cycle, collects spinning coins with sparkles, and bops a slime. The palette shifts from day to sunset in four steps and the cottage windows light up. Then a chest opens with a stepped light burst, a bordered dialogue box types two pages of facts, and the chunky two-tone logo drops in with a shine sweep, release line and blinking URL. Pulse lead, triangle bass, noise drums and jump/coin/chest effects are synthesised in code. Use for indie game trailers and announcements, Steam or Switch launches, dev tools or apps with a retro identity, game-jam reels, or when the user asks for "pixel art", "8-bit", "16-bit", "retro game intro", "attract mode", "platformer", "PICO-8 style" or "chiptune".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: pixel-art, retro, game, chiptune, 8-bit, parallax, trailer
---

# Pixel quest intro

Every frame is a 320×180 array of palette indices, PICO-8's 16 colours by default. It's turned into RGB once and scaled by an integer factor (`scale`, default 6, giving 1920×1080), with a light scanline on the last row of each pixel so pixels stay square and never blur.
- **Strictly integer:** all positions are whole pixels. Sprites animate on stepped timing with no easing. The sky gradient is ordered (Bayer) dither between two palette colours.
- **Text:** Departure Mono at its native 11 px grid (22 px for the logo), thresholded to solid pixels.

From the pixel-art study in [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15/blob/main/prompts/20-pixel.md):
- 320×180 ×6 nearest-neighbour
- a limited palette with a dithered sky
- 3–4 parallax layers moving by whole pixels
- a hand-authored run cycle at about 12 fps
- coins, a slime bop, a day → sunset palette shift
- a chest with a light burst
- a typing dialogue box
- a dropping logo with a shine sweep

Example: `examples/moss-courier/` is a fictional delivery platformer.

## Workflow

1. Copy `examples/moss-courier/brief.json` and set `copy`:
   - `title`: up to about 13 characters
   - `dialogue`: two pages of up to 80 characters each, with concrete facts about the game or product
   - `release`: one line
   - `url`
2. To change the hero, edit the string sprites (`BODY`, `LEGS`, `JUMP`) in `scripts/main.py`: one hex digit is one palette index, and `.` is transparent. To change the level, move `COINS`, `SLIME_X` and `JUMPS`.
3. `check` validates widths on the 320 px screen. Then run `still 1 2.7 7.1 10.4 13.8 15 18.8` and `render`.

## Rules

- No smooth easing, rotation or scaling on sprites, and no anti-aliasing. If something has to move smoothly, step it.
- Keep the 16 colours. A sunset is a palette step, not a gradient.
