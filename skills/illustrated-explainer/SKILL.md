---
name: illustrated-explainer
description: Render a narrated, flat-vector corporate explainer video (about 60–100 s, 16:9). It uses a soft pastel office illustration style generated with gpt-image-2 in one consistent house style, and every beat is cut on a spoken cue from an OpenAI TTS voiceover. Scene types are slow camera pans across wide illustrations with a small-caps caption at the top, bullet lists over a faded scene, a split screen, a zoom-blur whoosh into the logo on a hub ring, a world map with pins and links, floating product cards, and a CTA. Use when the user wants an animated explainer, a "problem, meet X, benefits, CTA" narrated video, a B2B services or SaaS explainer in the flat illustration style, or shares a reference like a corporate animated explainer.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
---

# Illustrated explainer

Built with `video-to-template` from a narrated flat-illustration explainer. There are two examples, both Prismor Enterprise with the same voiceover:

- `examples/prismor-layered/` (**recommended**): composited from a transparent-PNG cast, props and icons that animate independently.
- `examples/prismor-enterprise/`: full-frame illustrations with camera pans.

## Workflow

1. **Script** (`vo.txt`): follow the classic arc: the reader's pain as questions, then "you are not alone", then "Here comes <product>", what it does, how it works, benefits, and a CTA. Run it through the `no-ai-slop` skill, and keep every claim sourced from the product's docs.
2. **Voice:** `python3 scripts/main.py voice` (OpenAI TTS plus Whisper word timings).
3. **Illustrations:** list scenes in `assets.json`. Each prompt starts with `STYLE` and describes one scene; the brief's `style` string (or the example's) replaces it, which keeps every image in one house style. Then run `python3 scripts/main.py assets` (1536×1024, medium quality; the hub ring on a transparent background). Leave the top edge calm for captions, and ask for no text in images: all words are typeset.
4. **Beats:** in `brief.json`, each beat starts on a cue phrase (`at`). Cards and bullets can have their own cues. The real logo goes in `assets/logo.png`.
5. **Check, stills, render:** the voiceover is muxed automatically.

## Layered production (characters, props, icons)

1. **Cast:** generate one base image per character on a transparent background (`background: transparent`, full body, no floor or shadow), e.g. `maya`, `leo`, `bot`.
2. **Poses:** add `"ref": "<base name>"` to a pose's spec. The engine then calls gpt-image-2's edits endpoint with the base image, so the face, hair, clothes and colours stay on-model. Example: `maya_worried`, `maya_point`, `maya_confident`. See `examples/prismor-layered/assets2.json`.
3. **Props and backdrops:** props go on transparent backgrounds (desk, whiteboard, laptop, server, cloud-shield, plant). Backdrops are empty rooms with an open floor and no people.
4. **Icons:** `lucide:<name>` line icons (tinted) and `brand:<slug>` marks from thesvg, drawn as white app-icon tiles that pop in with a spring overshoot.
5. **Stage beats:** each scene is a `stage` with `bg`, `cam: [z0, z1, fx0, fx1]` (parallax by layer depth `z`), optional `veil` (`left` or `right`), and `layers`:

| layer | keys |
|---|---|
| sprite | `img`, `x`, `y` (the bottom anchor, as a fraction of the frame), `h` (fraction of frame height), `anchor: bottom\|center`, `enter: left\|right\|up\|pop\|fade`, `at` (cue) or `t`, `idle: breathe\|bob\|float`, `flip`, `swap: [{at, img}]` (pose change on a cue), `exit_at` |
| icon tile | `icon: lucide:…\|brand:…`, `size`, `color`, `label`, `x`, `y`, `enter: pop`, `at` |
| label | `label`, `size`, `font`, `color`, `anchor` |
| flow | `flow: [{icon, label, at}]`, `box: [x0, y0, x1, y1]` (icons joined by arrows, e.g. on a whiteboard) |
| list | `list: [{icon, color, text, at}]`, `x`, `y`, `gap` |
| lines | `lines: [[x, y]…]`, `from: [x, y]` (connectors drawn from a hub) |
| pins | `pins: [city keys]` (map pins) |

## Beat types

| type | shows | keys |
|---|---|---|
| `scene` | a Ken Burns pan across one illustration plus a caption | `image`, `caption` (`\n` for two lines), `move: [z0, z1, fx0, fx1, fy0, fy1]` |
| `bullets` | faded illustration, bullet items on cues | `image`, `caption`, `items: [{text, at}]` |
| `split` | two illustrations with a sliding divider | `left`, `right`, `caption` |
| `logo` | hub ring spins in, real logo in the centre, name rises | `ring`, `caption`, `name`, `name_at` (use `"tr": "whoosh"`) |
| `map` | world map, pins drop, optional links from the first pin | `pins` (city keys), `links`, `caption` |
| `cards` | product decision cards float up over a soft backdrop | `cards: [{verdict, title, detail, at}]` |
| `cta` | logo, name, line, URL over a calm illustration | `image`, `name`, `line`, `url`, `url_at` |

Transitions: a crossfade by default, or `"tr": "whoosh"` for a zoom-blur flash.

## Rules

- Captions are plain small caps between thin rules, never boxed. There are no trailing periods on screen.
- Use the product's own events for cards. Never invent testimonials or quote made-up customers.
- The logo is always the real file. AI voices should be disclosed.
