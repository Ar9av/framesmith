---
name: framesmith
description: Start here for any framesmith request. framesmith is a library of motion-graphics, video and visual-design skills for AI agents; each template is driven by a brief and renders deterministically with Python and ffmpeg. Use this skill to pick the right template for a request (product promo, launch video, kinetic typography, spec-sheet motion graphic, brutalist or glitch visuals, gpt-image-2 asset pipelines) or to build a new template on the framesmith engine. Triggers include "make a promo video", "motion graphics for my product", "animated spec sheet", "turn this style/video into a template", and "which framesmith skill should I use".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
---

# framesmith: start here

framesmith templates are **skills**: a `SKILL.md`, a brief schema, an example brief with assets, and a `scripts/` CLI that renders frames with the shared engine (numpy + Pillow → ffmpeg). It needs no browser, GPU or account. Image generation (gpt-image-2) is optional and uses placeholders when there is no key.

## 1. Route the request

<!-- catalog:start -->
| Skill | Output | Pick it when |
|---|---|---|
| [`brutalist-product-promo`](../brutalist-product-promo/SKILL.md) | 22.6 s 9:16 MP4, 21 scenes | Hardware/tech product promo, spec-sheet motion graphic, industrial/brutalist look, one accent colour on black and white |
| [`devtool-launch-video`](../devtool-launch-video/SKILL.md) | 33.8 s 16:9 MP4, 11 scenes | Launch or "what is X" film for a CLI, dev tool, AI-agent or security product: rogue-terminal problem, brand reveal, verdict-chip proof, features, dashboard, install, CTA |
| [`narrated-collage-explainer`](../narrated-collage-explainer/SKILL.md) | ~50 s 1:1 MP4 with voiceover, beats on spoken cues | Narrated explainer or founder story in a paper-white collage style (big pixel keywords, synced subtitles, CRT TV / XP window / cards / starbursts), built from a script plus real screenshots and GIFs |
<!-- catalog:end -->

If nothing fits, say so and offer to build a new template (section 3) rather than forcing the wrong one.

## 2. Use a template

Each template exposes the same CLI verbs:

```
python3 skills/<name>/scripts/<entry>.py check  --brief brief.json   # validate
python3 skills/<name>/scripts/<entry>.py assets --brief brief.json   # gpt-image-2, low/medium quality
python3 skills/<name>/scripts/<entry>.py still  --brief brief.json 3.4 9.1
python3 skills/<name>/scripts/<entry>.py sheet  --brief brief.json   # contact sheet
python3 skills/<name>/scripts/<entry>.py render --brief brief.json [--audio a.mp3]
```

Always review stills or the contact sheet before a full render, and report which assets are placeholders.

## 3. Build a new template (e.g. recreating a reference video)

1. **Deconstruct the reference.** Extract frames at 4 fps with ffmpeg, tile them into timestamped contact sheets, and write a storyboard table (scene, start, duration, what moves, the text it carries). Note the palette, type roles (display / mono), the transition types and the beat grid.
2. **Scaffold.** Run `python3 tools/new_skill.py <kebab-name>` from the repo root. This creates the skill folder, vendors the engine, and writes a starter CLI and brief.
3. **Build scenes.** Write one function per scene, `fn(ctx) -> HxWx3 uint8`. Use `ctx.lt` (local seconds) and `ctx.p(a, b)` for progress, and keep all copy in the brief. Engine API: `references/engine.md`.
4. **Assets.** Define image slots with explicit framing and background in the brief. Generate at `low`/`medium`. Use sprite sheets (a grid of the same subject with one part changing) for looping motion.
5. **Iterate with stills.** Compare against the reference side by side (`ffmpeg hstack`). Then test a second brief with a different brand, a light accent and a long name to prove it generalises.
6. **Ship.** Add a README catalog entry by running `python3 tools/catalog.py`, then run `python3 tools/sync_core.py --check` and `python3 tools/validate.py`.
