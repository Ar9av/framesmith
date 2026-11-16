---
name: world-hop-reel
description: Render a beat-cut "style hop" reel (about 18 s, 9:16 Instagram/TikTok wrapper or 16:9) where ONE rigged character runs through a chain of art-style worlds without changing. The worlds are cave wall, Egyptian wall painting, Greek black-figure vase, stained glass, old green CRT and hologram. A whip-pan lands on every downbeat, and the seam crosses the runner so it renders half in one style and half in the next. Each world sets one keyword and a year in its own type. It ends on a gallery card with the same figure in every style side by side, then title, details and URL. The 9:16 wrapper puts a blurred cover behind the film and a fixed hook line on top. Use for museum or exhibition promos, "through the ages" or history-of-X reels, brand or mascot launches that need one character across many looks, style showcases, "same character, every art style" trends, and requests for a reel that "hops between art styles on the beat" or shows "one character, many worlds".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: reel, style-hop, character-consistency, beat-sync, art-history, vertical-video, kinetic-typography
---

# World hop reel

Built from a creator reel (Gennaro, "This took me 10 minutes", 44 s). Its pitch was the lesson: *"One character, the same rules, every world … zero re-prompts, all on the beat."* What carries over:

1. **Keep the character separate from the world.** The runner is one skeleton: 12 bones whose joints come from a run cycle locked to the beat, with one stride pair per beat so the feet land on the 8ths. A world is only a renderer: a plate, a *brush* that draws the same bones its own way, a type rule for its keyword, and a post pass. Adding a world never touches the rig, so the character can't drift off-model. This is the procedural version of "same character sheet, re-styled": regenerating the character per style is exactly what breaks consistency.
2. **Cut on the beat, and let the character carry the cut.** The camera holds each world for `beats_per_world` beats with a slow drift. It whips to the next world in ±0.16 s around the downbeat. The whip blur hits the world layer only, so the runner stays sharp, and the seam crosses the runner on the beat. The figure is the object that hands one shot to the next.
3. **Each world speaks in its own type.** Cave: dry-brush Anton, multiplied into the rock. Egypt: Inter Black in lapis between gold rules. Greece: tracked roman serif. Glass: serif on a lead band. CRT: Departure Mono. Hologram: Geist Mono with a glow and HUD arcs. One keyword and one year per world, rising in on beats 1 and 2.
4. **The payoff shows the rule.** The gallery end card lines up the same figure, at the same moment of its cycle, in every world.
5. **The vertical wrapper from the reference.** A 16:9 film in the middle band of a 9:16 frame, a blurred and darkened cover of the same film behind it, and a fixed hook line above it that is readable with the sound off. It's set in yellow on a soft shadow, never in a box.

Example: `examples/walk-cycle/` promotes a fictional exhibition about how artists drew a running figure, from Chauvet to a headset (Halvard Gallery).

## Workflow

1. Copy `examples/walk-cycle/brief.json` and edit:
   - `worlds`: 3–8 entries of `{style, label, year}`. Pick each `style` from `cave`, `egypt`, `greek`, `glass`, `crt`, `holo`; order them as a journey. `holo` also takes a `note` line.
   - `copy.hook`: two lines at most, about 26 characters. Make it a concrete claim rather than a slogan.
   - `copy.title`, `copy.details`, `copy.url`, and optionally `copy.footer` (shown under the film in the reel wrapper).
   - `bpm`, `beats_per_world` (4 = one bar per world), `end_hold`, `format` (`reel` or `wide`).
2. Run every on-screen line through the `no-ai-slop` skill. On-screen text never ends in a period, and `check` fails if it does.
3. `python3 scripts/main.py check --brief brief.json`. This validates styles, label widths per world typeface, hook wrapping and end-card widths.
4. `python3 scripts/main.py still --brief brief.json --format wide 1 3 5 7 9 11 2.02 14 17`. Review each world, one seam crossing (just after a downbeat), and the end card.
5. `FRAMESMITH_PRESET=medium python3 scripts/main.py render --brief brief.json` renders 9:16 by default; pass `--format wide` for the 16:9 film. The score is synthesised: kick, hat and snare under the worlds, a riser and thud on every cut, a blip per gallery tile and a pad under the title. `--audio` replaces it.

## Adding a world

Write three functions in `scripts/main.py` and register them:
- `plate_<style>(rng)`: an `H × L` RGB array, built once (texture, borders, ground line at about `0.84 H`; keep the right half above `0.5 H` clear for the keyword).
- A brush `b(d, part, a, c, w, depth)` that draws one bone (`part` is thigh, shin, foot, upper, fore, torso or head; `depth` is far, mid or near). Far limbs go darker or thinner.
- A `TYPE` entry (font role, size, colour, year role, tracking) and a `YEAR_COL` colour, plus any post pass in `world_frame`.

Never add per-world poses or a second character drawing. If a world needs a prop (a halo, a kilt, a collar), the brush hangs it on the existing bones.

## Rules

- One rig, one cycle, one screen position for the runner through the whole film. Only the world changes.
- Cuts land on downbeats. Keywords land on beats 1 and 2 of their world.
- The whip blurs the world, never the runner.
- No pills or rounded label boxes. The glass world's lead band is square and is part of the window.
- No faces. The runner is a figure, not a portrait.
