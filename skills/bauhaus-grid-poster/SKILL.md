---
name: bauhaus-grid-poster
description: Render a kinetic Bauhaus / Swiss poster film (20 s, 4:5, 120 BPM, synthesised score) that assembles itself on a module grid. Circles, quarter discs, semicircles, wedges and slabs in red, yellow, blue and black land one per beat, every move a whole number of modules with in-out easing and no overshoot. A block of the poster turns 90° about its centre in 7.5° escapement teeth, a phase-shifted wave of quarter discs sweeps the grid on the drop, then the ink plates snap into register on the "press lock" beat and the facts set themselves flush-left in Inter Display. Four ink plates are multiplied onto paper tooth with drifting misregistration. Use for event and festival posters, exhibition or design-week promos, studio and type-foundry identities, album or release announcements, or when the user asks for "Bauhaus", "Swiss style", "constructivist", "kinetic poster", "geometric motion design", "grid-based motion poster" or "print-like motion graphics".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, kinetic-poster, bauhaus, swiss-design, print, misregistration, music-driven
---

# Bauhaus grid poster

A 20 s, 1080×1350 poster film on an 8 × 10 module grid at 120 BPM. One cue sheet in `scripts/main.py` drives both the picture and the synthesised score: every landing is a clack, the escapement turn ticks, the wave plays a blip per diagonal, and the press lock lands on a thud.

The style comes from the Bauhaus entry in [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15/blob/main/prompts/09-bauhaus.md), one of the Opus 5.5 motion-design studies. Its rules are kept as hard constraints:
- integer-module moves landing on grid lines, one element acting per beat
- in-out easing only, never overshoot
- rotation pivots that alternate between an element's own centre, a corner, and the block centre
- a cascade wave on the drop and the hero moment at about 60–75 % of the runtime
- a composed end frame with living micro-motion (one quarter disc keeps turning every bar)
- paper tooth and print misregistration that lock into register

Example: `examples/vesna/` is a fictional print festival in Ljubljana.

## Workflow

1. Copy `examples/vesna/brief.json` and edit `copy`, `theme` and, if you like, `seed`. The copy is a masthead (`brand`, `edition`), a vertical `title` of up to 7 letters, a small-caps `sub` line, up to four `facts` and a `url`.
2. Run every line through the `no-ai-slop` skill. State facts (dates, places, counts, hours), not slogans. No trailing periods.
3. `python3 scripts/main.py check --brief brief.json` validates the copy and samples the cut for overflow.
4. `python3 scripts/main.py still --brief brief.json 1 5 9 13 16 19.5`, then look at the frames.
5. `python3 scripts/main.py render --brief brief.json` synthesises the score and encodes. Pass `--audio` to use your own 120 BPM track instead.

## Brief

| key | meaning |
|---|---|
| `size`, `grid` | 1080×1350 with an 8 × 10 grid by default; the module is `width / cols` |
| `bpm`, `beats`, `press_lock_beat` | 120, 40, 30; the hero wave runs on beats 24–30 |
| `theme` | `paper`, `ink`, `red`, `yellow`, `blue`; keep the primaries, or swap in a brand's three inks |
| `copy` | `brand`, `edition`, `title`, `sub`, `facts[≤4]`, `url` |
| `meta.logo` | optional path to the brand's real logo (it sits beside the URL after the lock). Never generate one |

## Rules

- Type is Inter Display Black/Bold/Medium (`sans_black`, `sans_bold`, `sans_medium`), set flush-left on grid lines. No italics and no pills.
- To re-choreograph, edit `elements()` in `scripts/main.py`. Each action is `(land_beat, kind, params, dur_beats)` with kind `in`, `rot`, `slide` or `flip`. Keep moves to whole modules and keep one element acting per beat.
- See `references/storyboard.md` for the beat sheet.
