---
name: kinetic-launch-film
description: Render a narrated kinetic-typography product launch film (about 60–90 s, 16:9) on a light gridded ground with one drifting brand glow. Every on-screen word rises out of a mask with a spring exactly when the voice says it. Other beats include a rubber-band letter ("everrrywhere"), words riding dashed curves, a word tipping off its line, sentences that scatter, and a "Meet" + logo reveal. The product UI appears as bordered logo cards, a tilted 3D window with detection boxes, a live activity feed driven by an agent cursor, an approval with a border-beam toast, a raw log whose tokens fly into an audit table, and a hub with travelling connector beams. Sound effects are synthesised in code and mixed under an OpenAI TTS voiceover. Use when the user wants a modern SaaS or AI-agent launch video in the kinetic-type style, a "text-led product film with UI", or to recreate a launch video that is mostly animated words plus product screens.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: launch-video, kinetic-typography, product-ui, voiceover, springs, sfx, saas, ai-agents
---

# Kinetic launch film

A text-led launch film: the voiceover drives everything. Words rise on the beat they are spoken, UI scenes carry the product story, and a closing logo card lands on a cursor click. Motion follows the ideas in [howseen-ai/claude-motion-design](https://github.com/howseen-ai/claude-motion-design) (MIT), ported to framesmith's pure-Python `seek(t)` model in `framesmith.motion`:
- closed-form springs (snappy 320/30, default 170/26, playful 180/12)
- log-space camera push with a small punch on every phrase
- masked word rises with a slight rotation
- border beams and travelling connector beams
- code-synthesised click, tick, pop, thump and whoosh effects

Example: `examples/prismor/` is a 67 s Prismor launch film with a marin voiceover.

## Workflow

1. **Start:** `python3 scripts/main.py init my-film` copies the Prismor example.
2. **Script** (`vo.txt`): the arc is:
   - a problem hook with a stretched word
   - where the pain lives (label montage)
   - three words on curves
   - the question, and the flat answer with a falling word
   - "Meet [Product]"
   - what it does (big two-line headline over blurred UI)
   - compatibility (logo cards)
   - the stakes (a sentence that scatters)
   - "[Product] can help"
   - three or four UI proofs
   - the hub
   - the positioning lines
   - the logo, tagline and URL

   Run the script through the `no-ai-slop` skill, and take every claim from the product's docs or site.
3. **Voice:** `python3 scripts/main.py voice --brief my-film/brief.json`. This uses the latest TTS snapshot (default voice `marin`) and transcribes it in overlapping windows (`narration.transcribe_windows`), because Whisper drops stretches of long takes.
4. **Brief** (`brief.json`): every beat starts on a cue phrase (`at`), and so does every phrase, card and item inside it. `holds` insert silence after a phrase so a UI beat can breathe.
5. **Check** → **still** → **render**. The render mixes the voice with the synthesised effects automatically.

## Beats

| type | what it does | keys |
|---|---|---|
| `kin` | voice-synced masked word rises; `*accent*` words get a scrolling holographic fill; phrases swap with a blur | `phrases[{at, text, size, x, y, align, stretch, fall, scatter_at}]`, `backdrop: "ui"` + `feed` |
| `windows` | label montage: big white word over a tinted app window, with brand icon tiles floating | `items[{at, label, kind: terminal/editor/browser/cloud, icons}]` |
| `paths` | each word drawn along a dashed Bézier as it is spoken | `items[{at, word, curve: 4 points (0–1), start}]` |
| `meet` | "Meet" + mark pop; on the brand cue "Meet" lifts away and the wordmark rises | `name_at`, `name` |
| `logos` | headline + bordered logo cards on a playful spring, one per spoken name | `phrases`, `items[{at, icon, name}]`, `grid_y` |
| `tilt` | a product window tilted in 3D settles flat while lines type and detection boxes land | `box_at`, `curve_label`, `phrases` |
| `activity` | live activity feed, spinner status, agent cursor with a label, the last call outlined | `feed`, `status`, `agent` |
| `approve2` | approval card, cursor click on Approve, a toast with a border beam | `click_at`, `action`, `cmd`, `who`, `toast` |
| `structure` | a raw log's tokens highlight, then arc into a clean table | `raw`, `columns`, `rows[[value, raw_line]]`, `fly_at` |
| `hub` | left list → product disc → right list, beams draw in and pulses travel | `left`, `right`, `left_title`, `right_title` |
| `end` | logo + wordmark, tagline, URL underlined by a cursor click, fade to black | `tag_at`, `tagline`, `url` |

Icons come from `assets/icons/<slug>.svg` (thesvg, via `brand-icons`) or `lucide:<name>`. Put the real logo in `assets/logo.png`.

## Rules

- Design rules from `video-to-template/references/design-rules.md` apply:
  - no pills or chips (status is a dot plus a word, and the cursor label is plain text on a halo)
  - the real logo
  - no overflow
  - no italics
  - no trailing periods on on-screen text
- UI content must be the product's real UI or clearly generic. The `tilt` example rebuilds prismor.dev's own hero demo. Org, device and people names are sample data.
- The shared compositor lives in `scripts/stage_engine/stage.py` (the same file as `archive-launch-film`), which provides the backgrounds, cards, cursor, console panels and holds.
