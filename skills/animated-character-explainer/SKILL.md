---
name: animated-character-explainer
description: Render a narrated explainer video (about 45–90 s, 16:9) animated from layers. It uses a consistent cast of characters generated with gpt-image-2 on transparent backgrounds, with every pose kept on-model by reference-guided edits, plus transparent props, empty room backdrops, and Lucide or brand icon tiles, all composited in code. Characters slide in, breathe and swap poses on spoken cues, icons pop with a spring, whiteboards draw flows, connectors link devices, map pins drop, and a parallax camera drifts, all timed to an OpenAI TTS voiceover. Use when the user wants an animated explainer with characters, a corporate or SaaS story with a recurring cast, "make PNG characters and animate them", or a flat-illustration explainer where people and icons move rather than static images.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: explainer, characters, animation, transparent-png, gpt-image-2, voiceover, icons
---

# Animated character explainer

Every scene is a `stage` of layers: a backdrop, props, characters and icons. The voiceover drives the timing. There are two examples:
- `examples/prismor-enterprise/` is a 62.8 s film with a cast of four (Maya, Leo, an agent bot, an auditor) in 14 poses. See `cast_sheet.png`.
- `examples/starter/` is the same 11-beat arc with every line as a `[placeholder]` and a stand-in cast.

## Workflow

1. **Start:** `python3 scripts/main.py init my-film` copies the starter.
2. **Script** (`vo.txt`): follow the arc of pain questions → reassurance → "Here comes [Product]" → how it works → setup → reach → benefits → trust → CTA. Run it through the `no-ai-slop` skill, and take every claim from the product's own docs.
3. **Cast** (`cast.json`): one shared `style` block (character, prop and backdrop prefixes) and a palette. Each character has a `desc` and named `poses`. List props and empty backdrops as well.
   - Run `python3 scripts/main.py cast --brief my-film/brief.json`.
   - It generates bases on transparent backgrounds first, then every pose via gpt-image-2 edits with the base image as reference, so faces, hair and clothes stay on-model. Existing files are kept, and `cast <name>` regenerates one.
   - Put the real logo at `assets/logo.png`.
4. **Voice:** `python3 scripts/main.py voice` (TTS plus Whisper word timings). Before this step, `check` and `still` preview with estimated timings.
5. **Beats** (`brief.json`): each beat starts on a cue phrase from the script (`at`). Layers and pose swaps can have their own cues.
6. **Check** (overflow, unfilled placeholders, trailing periods) → **still** → **render**. The voiceover is muxed automatically.

## Stage layers

Every beat has `"type": "stage"`, a `bg` backdrop, `cam: [z0, z1, fx0, fx1]` (a parallax drift, where each layer moves according to its depth `z`), an optional `veil` (`left` or `right`, to keep text readable) and a `caption`.

| layer | keys |
|---|---|
| sprite | `img`, `x`, `y` (the bottom anchor, as a fraction of the frame), `h` (fraction of frame height), `anchor: bottom\|center`, `enter: left\|right\|up\|pop\|fade`, `at` (cue) or `t`, `idle: breathe\|bob\|float`, `flip`, `swap: [{at, img}]` (pose change on a cue), `exit_at` |
| icon tile | `icon: lucide:<name>\|brand:<thesvg slug>`, `size`, `color`, `label`, `x`, `y`, `enter: pop`, `at` |
| label | `label`, `size`, `font`, `color`, `anchor` |
| flow | `flow: [{icon, label, at}]`, `box: [x0, y0, x1, y1]` (icons joined by arrows, e.g. drawn on a whiteboard prop) |
| list | `list: [{icon, color, text, at}]`, `x`, `y`, `gap` (an icon bullet list) |
| lines | `lines: [[x, y], …]`, `from: [x, y]` (connectors from a hub, e.g. a cloud to laptops) |
| pins | `pins: [city keys]` (map pins over a world-map backdrop) |

Other beat types: `logo` (hub ring plus the real logo, best with `"tr": "whoosh"`), `scene`, `bullets`, `split`, `map`, `cards` and `cta`. Transitions are a crossfade by default, or `"tr": "whoosh"`.

## Tips

- Ask for full body, a transparent background, no floor and no shadow for characters and props. Describe backdrops as empty rooms with an open floor.
- Keep one palette in the style block; it's what makes separately generated images look like one set.
- Pose prompts describe the change only. The reference image carries the identity.
- `flip` mirrors a sprite. Check that pointing poses still point at the thing they refer to.

## Rules

Captions are plain small caps between thin rules, with no boxes, pills or italics. There are no trailing periods on screen. Use the real logo only. Never invent testimonials. AI voices should be disclosed.
