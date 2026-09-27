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
| [`video-to-template`](../video-to-template/SKILL.md) | a new template skill + the finished video | The user shares a **reference video** ("make one like this", "copy this style"). Runs the whole pipeline: analyse → storyboard → animatic → assets → build → compare → ship |
| [`brutalist-product-promo`](../brutalist-product-promo/SKILL.md) | 22.6 s 9:16 MP4, 21 scenes | Hardware/tech product promo, spec-sheet motion graphic, industrial/brutalist look, one accent colour on black and white |
| [`devtool-launch-video`](../devtool-launch-video/SKILL.md) | 33.8 s 16:9 MP4, 11 scenes | Launch or "what is X" film for a CLI, dev tool, AI-agent or security product: rogue-terminal problem, brand reveal, verdict-chip proof, features, dashboard, install, CTA |
| [`narrated-collage-explainer`](../narrated-collage-explainer/SKILL.md) | ~50 s 1:1 MP4 with voiceover, beats on spoken cues | Narrated explainer or founder story in a paper-white collage style (big pixel keywords, synced subtitles, CRT TV / XP window / cards / starbursts), built from a script plus real screenshots and GIFs |
| [`brand-icons`](../brand-icons/SKILL.md) | SVG + PNG brand marks with a licence and attribution table | Any design needs real company/tool logos ("works with" rows, stack grids, partner walls); fetched from thesvg.org with the right variant for the background |
| [`keynote-product-film`](../keynote-product-film/SKILL.md) | ~60–90 s 16:9 MP4, music-driven, no VO | Apple-event-style launch or "introducing" film: kinetic sentences with inline icons, real product UI (prompt, agent session, permission prompts, steps, benchmark chart, ticker, masked field), logo reveal on a gradient wash |
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

## 3. Build a new template

Use [`video-to-template`](../video-to-template/SKILL.md). It holds the full process: reference analysis (`analyze.py`), a timed animatic scaffold (`scaffold.py`), side-by-side review (`compare.py`), the design rules, and a list of pitfalls that each cost a re-render. With no reference video, scaffold a blank template with `python3 tools/new_skill.py <name>` and follow the same phases from Phase 2.
