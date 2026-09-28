---
name: blue-story-film
description: Render a music-driven SaaS story film (about 60–90 s, 16:9) in the blue-light style. It opens with typewriter captions, a caret and a selection highlight over ghosted UI, then a huge 'Meet' word that collapses into the brand line. The body shows product UI in perspective over gpt-image-2 blue light backdrops, a split screen where a UI row wires into a dark terminal, bracket words, a wide streaking word, and a camera flying over oversized form fields. It closes on a black typewriter CTA. Use for launch films and 'meet X' product stories for B2B software, especially when the user shares a Numtera-style reference.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
---

# Blue Story Film

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
