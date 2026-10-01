---
name: abstract-journey-film
description: Render a music-only abstract title film (about 80 s, 16:9, 24 fps) in which a small glowing orb travels through a chain of worlds and lands on the logo. The worlds are a dark glitch data field, a UI card in a lit chamber, wireframes that fill into a web page, a flythrough of 3D app panels, a bubble-sky horizon, a spiral vortex of gradient cards, neon diamonds, a construction grid that builds a sphere and bursts it into glossy spheres, a sphere room, isometric glass objects, pastel light pillars, ribbons and glass, a frosted sphere, nested frames, a pastel world, a portal of rings, an illustrated sunset landscape and space with planets. Image assets come from gpt-image-2.5 (transparent spheres, planets, clouds, ribbon, isometric objects and four backdrops); the rest is procedural, and the score is synthesised in code. Use for a conference opener, brand title sequence, product "sizzle" intro, event teaser, or to recreate a dreamy no-text motion-design journey (the Webflow No Code Conf opener style) for a brand.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: title-sequence, abstract, motion-design, gpt-image-2.5, transparent-png, procedural, music, opener
---

# Abstract journey film

There's no voiceover and no text until the logo: a glowing orb is the thread through 22 worlds, from dark and digital to bright and dreamy, ending on the brand. Example: `examples/prismor/` is an 83 s Prismor title film.

## Workflow

1. **Start:** `python3 scripts/main.py init my-film`.
2. **Brand:** put the real logo in `assets/logo.png` and set `name` in `brief.json` (the wordmark beside it). Never generate the logo.
3. **Assets:** restyle the prompts in `assets.json` to your palette, then run `python3 scripts/main.py assets`. `assets <name>` regenerates one.
   - The default model is `gpt-image-2.5-sunburst`. Use `FRAMESMITH_IMAGE_MODEL=gpt-image-2.5-flare` for faster drafts.
   - Transparent assets use native alpha. If a model refuses alpha, the engine falls back to a chroma key and a cutout automatically. Use `"key": "#FF00FF"` for green subjects.
4. **Review:** run `sheet` (30 frames across the film) and `still 3 22 48`.
5. **Render:** run `render`. The score (pad chords, shimmer notes on cuts, whooshes, a pulse in the bright half and a logo hit) is synthesised and muxed. Pass your own track by muxing afterwards if you have a licensed one.

## Worlds

`scenes` in the brief overrides any duration (`0` drops a world). In order:
- `data` · `chamber` · `wire` · `room`
- `flight` · `horizon` · `vortex` · `neon`
- `icons` · `geometry` · `sroom` · `iso`
- `flash` · `pillars` · `ribbons` · `frost`
- `frames` · `pworld` · `portal` · `land`
- `space` · `logo`

The dark half uses indigo, signal red, green and cyan accents. From `flash` onwards the film turns pastel. Each world is one function in `scripts/main.py`.

| asset | used in | framing |
|---|---|---|
| `orb` | everywhere | small luminous glass orb, transparent |
| `sphere_*` (pink, cyan, lime, violet, peach, frost) | burst, sphere room, pillars, ribbons, frost | single glossy sphere, centred, transparent |
| `planet_*` | space | single planet, transparent |
| `clouds`, `ribbon` | landscape, ribbons, frames | separate shapes, transparent |
| `iso_house`, `iso_stairs`, `iso_shield` | isometric panels | isometric glass object, transparent; swap the shield for your product's symbol |
| `bubbles_sky`, `pastel_world`, `landscape`, `space` | horizon, flash, pastel world, landscape, space | wide 1536×1024 backdrops |

## Notes

- Scene canvases are RGB on purpose: Pillow blends translucent draws only on RGB images, and RGBA sprites paste with themselves as the mask.
- Dense particle fields use a seeded `numpy` table, not the `h()` hash, to avoid streaks.
- About 2000 frames: budget roughly 1–1.5 h on 2 throttled cores with `FRAMESMITH_PRESET=veryfast`.
