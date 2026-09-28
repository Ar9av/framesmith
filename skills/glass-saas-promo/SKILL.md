---
name: glass-saas-promo
description: Render a bright, music-driven SaaS promo (about 30–40 s, 16:9) in the frosted-glass style: a lavender-white field, blue-to-violet gradients, gpt-image-2 glass 3D objects (shield, folder, check, sparkle, laptop), real product UI in 3D perspective (tilts, a tunnel of screens, a card scatter, a carousel), kinetic word swaps, a gradient stream that sweeps a screen away and settles into a counting progress bar, and a confetti check. Use for product launch or feature promos in the clean glassy SaaS look, especially when the user shares a reference like LangEase-style or Apple-style bright promos.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
---

# Glass Saas Promo

Built with `video-to-template` from a reference film. Example: `examples/prismor-enterprise/` (Prismor Enterprise).

## Workflow

1. Write the copy through the `no-ai-slop` skill. On-screen text has no trailing periods, and claims come from the product's own docs.
2. Generate backdrops and objects with gpt-image-2: put prompts in `brief.json` under `assets` and run `python3 scripts/main.py assets --brief brief.json` (medium quality, explicit backgrounds). The logo is always the real file.
3. UI panels come from the real product: screenshots, or panels rendered by `keynote-product-film` and cropped (see `examples/prismor-enterprise/assets/ui/`).
4. Run `check` (it fails on overflow and warns on trailing periods), then `still … t1 t2` to review, then `render --audio music.m4a`. These films are music-driven, so cut shot lengths to the beat.

Shot types and their keys are documented at the top of each function in `scripts/main.py`.

## Platform and icon shots

- `pillars`: a row of icon tiles with a label and one-line detail each (governance pillars).
- `flow`: a pipeline of icon tiles on a line, with a glowing pulse lighting each step.
- `orbit`: the logo at the centre, with brand icons from thesvg on two counter-rotating rings.

Fetch every icon a brief uses with `python3 scripts/main.py icons --brief brief.json` (Lucide line icons plus thesvg brand marks, with licences).

## Real product UI

Prefer the product's real frontend over recreations. `skills/video-to-template/scripts/grab.mjs` drives headless Chromium over CDP: it scrolls the live site so scroll-triggered sections render, then clips components by selector or rectangle. It can also isolate a single layer of a pinned or crossfading section. The `web/*.png` panels in the example came from prismor.dev this way.
