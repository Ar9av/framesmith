---
name: brutalist-product-promo
description: Render a 22-second brutalist / industrial product promo video (spec-sheet motion graphics) for any hardware, device, robot, drone, vehicle or tech product. The video is 9:16 with a signal-colour accent on black and white, and includes ASCII glitch fields, animated engineering blueprints with counting dimensions, text-scramble kinetic typography, pixel-mosaic transitions, a gpt-image-2 product render and sprite, and a wordmark outro. Use when the user asks for a product launch video, spec sheet video, hardware teaser, "tech brutalism" / Swiss industrial motion graphic, Instagram/TikTok/Reels/Shorts product promo, or wants to recreate this ARC Robotics style for their own brand. Pure Python + ffmpeg, deterministic, no browser.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, video, product-promo, brutalism, kinetic-typography, gpt-image-2, ascii, blueprint
---

# Brutalist product promo

This template produces a 22.64 s, 25 fps, 720×1280 promo made of 21 hard-cut scenes. It is driven entirely by a JSON **brief**: copy, colours, image prompts and scene timing. Every frame is a pure function of time, so you can review any single frame before rendering the full video.

Preview: `examples/arc/contact_sheet.png`. A second example, `examples/prismor/`, applies the style to software (Prismor, electric violet, a key, a padlock sprite and a server rack instead of a robot) and shows the brand's real logo beside the wordmark via `meta.logo`. The storyboard with per-scene timing and purpose is in `references/storyboard.md`.

## Requirements

- Python 3.9+ with `numpy` and `Pillow`, plus `ffmpeg` on PATH. Fonts are bundled.
- Optional: `OPENAI_API_KEY` for generating the six product images with gpt-image-2. Without it, placeholders are used so the pipeline still runs.

## Workflow

1. **Brief.** Copy `examples/arc/brief.json` to a new working folder as `brief.json`, then rewrite the `copy`, `theme` and `assets` prompts for the user's product. Keep copy short: these are labels, not sentences. Field rules are in `references/brief.md`. Ask the user only for things you can't infer (brand name, product, accent colour). Invent plausible spec lines if none are given, and say that you did.
2. **Validate.** Run `python3 scripts/promo.py check --brief path/to/brief.json`. It reports missing copy keys, missing assets and weak contrast.
3. **Images.** Run `python3 scripts/promo.py assets --brief path/to/brief.json`. This generates any missing slots into `<brief dir>/assets/` with gpt-image-2. Keep `quality` at `low` or `medium`: frames are 720 px and heavily processed, so `high` is wasted spend. Regenerate one slot with `assets <name> --force`.
4. **Review stills.** Run `python3 scripts/promo.py still --brief … 3.4 7.9 11.3 16.9` and look at the PNGs in `<brief dir>/out/`. For the whole cut, use `sheet`. Check the hero targeting box: adjust `meta.hero_target` (fractions of the hero image) so it sits on the product's key detail.
5. **Render.** Run `python3 scripts/promo.py render --brief … [--audio track.mp3]` to produce `<brief dir>/out/promo.mp4`. A render takes about 1 min on 2 cores.

## Image slots (assets)

Each image slot is used by particular scenes and needs a particular framing. State the background explicitly in every prompt.

| Slot | Used in | Framing that works |
|---|---|---|
| `hero` | product-name scene (top 64%) | studio render, 3/4 view, flat mid-grey background, subject centred |
| `closeup` | glitch scene + thresholded "connected" scene | macro detail entering from the left, **pure black** background, bright subject |
| `cutout` | checkerboard scene | side view, `"background": "transparent"`, subject spans the full width |
| `environment` | stripe + ASCII scenes | top-down B/W photo of where the product lives, strong vertical lines; `low` quality is fine |
| `lineart` | overview page + tinted-grid scene | **white outlines on pure black**, no fill, subject fills the frame |
| `sprite` | "[model]" and specs scenes, loops | sprite sheet, `grid: [cols, rows]`, black line art on white, same framing in every cell, only one part moving |

Prompt craft: write full sentences and name the materials, lighting, lens and background. Wrap any in-image text in quotes (`"{brand}"` is substituted from the copy). Don't rely on the model for typography; the engine renders all text.

## Customising

- **Timing:** `"scenes": {"hero": 1.4, "smear": 0}` sets per-scene seconds (0 drops the scene). `"speed": 1.2` scales the whole cut.
- **Theme:** `accent`, `ink`, `paper`, `tint` (hex). Text on the accent automatically switches between ink and paper for contrast.
- **Format:** `"size": [720, 1280]` is the designed layout. Other sizes are not supported by this template.
- **Audio:** pass `--audio`. Cuts land on a ~0.25 s grid, so a 120–130 BPM track sits well.

## Guardrails

- Don't put a real company's trademarks in the copy or prompts unless the user owns them or has asked for them.
- Never have gpt-image-2 draw the brand's logo. Set `meta.logo` to the real logo file, and the engine places it beside the wordmark on the logo, cross and outro scenes (with a hairline on dark grounds so a dark mark stays visible).
- Report honestly which slots are placeholders versus generated.
- To change motion itself, edit `scripts/promo.py` (one function per scene). Never edit `scripts/framesmith/`: it is vendored from the repo's `core/` and gets overwritten.
