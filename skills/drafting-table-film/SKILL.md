---
name: drafting-table-film
description: Render a 16:9 drafting-table product film (24 s, 120 BPM, synthesised score) where one mechanism is drawn in three inks on a locked camera. Act 1 is graphite on cream paper, with boiling double-stroked pencil lines, construction circles, section hatching drawn one line at a time, the product name in hatching cut to its letters, and a dimension. Act 2 is a hard-edged blueprint flood from the pencil tip, with white lines, dashed pitch circles, a planetary gear train that runs with true ratios, and callouts drawing their leaders. Act 3 is a single scan line into a hologram (cyan line with a white core, scan-line fills, no glow) where the stack explodes along its axis and specs count in. Use for hardware, mechanical, robotics, industrial, engineering or maker products, "how it's built" or "inside the product" films, spec reveals, or when the user asks for "blueprint", "technical drawing", "engineering drawing", "pencil sketch to render", "exploded view", "hologram" or "drafting" motion graphics.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, blueprint, technical-drawing, hardware, exploded-view, hologram, mechanical, music-driven
---

# Drafting table film

A 24 s, 1920×1080 film in one continuous shot: the same drawing changes ink twice. The mechanism is a procedural planetary gearbox (sun, three planets, fixed ring, bolted housing) whose tooth counts come from the brief.
- **Ratios are true:** the carrier turns at `sun / (sun + ring)` of the sun's speed, and the planets turn at `−(ring / planet − 1)` of the carrier's.
- **The meshing holds:** with even tooth counts the teeth stay in mesh while it runs.

The look comes from the three-ink prompt in the Opus 5.5 motion-design lists ([heyiamnick's drafting table](https://x.com/heyiamnick/status/2109174851412119558), collected in [motionvideohq/awesome-opus-5-5-motion-design](https://github.com/motionvideohq/awesome-opus-5-5-motion-design)):
- 60 px grid at 13 %, with every fifth line at 26 %
- pencil lines pushed off true by sine waves that re-roll 8× a second, stroked twice (full width at 90 %, half width at 40 %)
- big type as hatching cut to the letters
- the paper → blueprint change as a hard-edged flood, and blueprint → hologram as one scan line
- hologram lines with a white core at 30 % of their width, and scan-line fills whose thickness follows how lit each face is
- a locked camera, with moves starting 0.05 s early so they land on the beat

Its corner chrome ("FIG. 07", "BEAT 27 / 60") is left out on purpose.

Example: `examples/brannock/` is a fictional 6:1 planetary gearbox.

## Workflow

1. Copy `examples/brannock/brief.json`. Set `gear` (`sun`, `planet` and `module` in px; the ring is `sun + 2·planet`) and `copy`.
2. Every spec must match the geometry and the real product. `check` prints the ratio implied by the tooth counts; make sure it matches your `specs`.
3. Run the copy through `no-ai-slop`, with no trailing periods.
4. `check` → `still 0.8 4 6.5 8.2 12 16.3 18 23.5` → `render`.

## Brief

| key | meaning |
|---|---|
| `theme` | `paper`, `graphite`, `blueprint`, `line` (blueprint ink), `void` and `holo` (hologram) |
| `gear` | `sun`, `planet` tooth counts and `module` (px at 1080p). Even counts keep the mesh exact |
| `copy.parts` | 4 callouts keyed `sun`, `planet`, `ring`, `housing`: `[name, detail]` |
| `copy.specs` | up to 4 `[value, label]`, counted in during the hologram act |
| `copy.brand`, `product`, `kind`, `dimension`, `url` | title block, hatched title, dimension label, end lines |

## Rules

- Sans for every label (Inter Display Bold/Medium, Black for the hatched title). No mono and no italics. Labels sit on the drawing's own ground, never in boxes.
- To draw a different mechanism, replace `parts()` with your own outlines (closed polylines in px), and keep the three ink functions as they are. They only need outlines, an explode order and callout anchors.
- `references/storyboard.md` has the beat sheet.
