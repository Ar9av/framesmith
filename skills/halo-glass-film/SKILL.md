---
name: halo-glass-film
description: Render a pale-grey, iridescent "labs launch" film (about 33 s, 16:9, music only, plus a 4:5 letterboxed feed cut) in frosted glass and soft holographic light. A white ring with an orbiting dot lands as the "o" of the brand's huge white wordmark, then turns into a glass prompt card that gets typed and applied. A big light heading sits over glass metric cards with gradient charts and a live activity column. A severity list zooms into one finding, whose fix row lights up and opens a code card. A capsule line chart falls, and a tall gradient card fills with agent tiles. One dot draws two rings carrying the product's four-step loop, the rings merge back into the wordmark, and the real logo closes on the CTA. Use for AI agents, dev tools, security, "experimental" or labs-style product launches, or when the user says "Google Labs style", "glassy iridescent launch video", "frosted glass UI film", "soft gradient product reveal", "like the Stitch Loop video", or shares a pale, holographic UI launch reel and wants one for their brand.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: launch-film, glassmorphism, iridescent, labs, ai-agent, security, wordmark, product-reveal, music-only
---

# Halo glass film

A 32.9 s film at 1920×1080 and 30 fps, in 9 scenes. The ground is pale grey, with soft iridescent light pools behind frosted glass cards. The score is synthesised: an airy pad, plucks, glass blips and typing ticks. `render --ig` also writes a 1080×1350 cut with the 16:9 film letterboxed on black, the way the reference was posted.

It was back-engineered with `video-to-template` from a 32.7 s Instagram post of a Google Labs agent launch (shot list in `references/storyboard.md`). The reference's grammar:
- One world: a pale grey ground (#E0E0E2) with lavender, cyan and mint light. White strokes, frosted cards, ink type.
- Huge light sans headings over small, precise UI.
- Hairline rails with tiny mono marks, and grids of white discs, as quiet structure.
- One object carries each cut: ring → wordmark "o" → glass card; findings row → heading; row → code card; dot grid → agent card → dot → loop rings → wordmark → logo.
- Light comes through the UI: gradient area charts, a glow spilling through the focused row, a gradient progress fill.

What changed from the reference, on purpose:
- No pill buttons or "+ REPOSITORY" chips. Status is typeset as coloured mono words, and the source buttons became agent tiles with real thesvg icons.
- The real logo closes the film. The wordmark is solid white with the light behind it, never a gradient fill.
- Every UI string is a concrete product fact (the commands, the verdicts, the counts).

Everything is drawn natively in design units through a camera painter (`P` in `scripts/main.py`): glass is the frame under the card, blurred and lifted to white; rings and discs are analytic anti-aliased fields. No screenshots and no generated images.

Example: `examples/prismor/`, Prismor's runtime checks on agent tool calls (cloaked keys, blocked `.env` reads, policies across 14 agents).

## Workflow

1. Copy `examples/prismor/` and put the brand's **real** logo at `assets/logo.png`. Fetch the agent or integration icons with the `brand-icons` skill into `assets/icons/<slug>.png` (`--theme light`).
2. Edit `brief.json`. Every string on screen comes from it:
   - `copy`: brand, kicker, two lines under the wordmark, independent/open-source line, cta
   - `policy`: label, placeholder, prompt, button, rail marks
   - `stats`: heading, three cards (`area`, `bars`, `segments`), live feed rows `[time, agent, command, verdict, colour]`
   - `findings`: severity groups with rows `[text, agent · device]`
   - `detail`: two-line heading, three fix rows, which one to focus, the code card lines (`muted`, `accent`)
   - `trend`: two-line heading, 7 points, note
   - `agents`: heading, up to 8 icon tiles
   - `loop`: four node labels
   - `theme.aura`: five light colours. Take them from the brand's own palette (Prismor's come from its holographic logo).
3. The wordmark's ring replaces the first "o" in `copy.brand`. If the brand has no "o", the ring floats beside the word; consider a different opener.
4. Run the copy through `no-ai-slop`. No trailing periods, uncommon demo names, real commands.
5. `python3 scripts/main.py check --brief brief.json`. It fails on a missing logo or icon, trailing periods, or overflow.
6. `still --brief brief.json 1.2 4 7.1 9.3 12 14 15.4 17 18.6 20.6 22 23.8 26 27 29.3 31 32.5` and look at every frame.
7. `FRAMESMITH_PRESET=medium python3 scripts/main.py render --brief brief.json --ig`. This takes about 15 min on 2 cores (about 1 s per frame).

## Rules

- One colour world. Ink and white on pale grey. Colour appears only as light: the aura, chart fills, the focused-row glow, the progress fill and the tall card. Verdict words take the state colours (red, amber, green, accent).
- No pills or badges. The only rounded containers are real UI: cards, an input, a button, icon tiles.
- `sans` (Inter Display) for headings and UI, `mono` (Geist) for commands, labels and marks. No italics.
- Keep `detail.heading` lines under about 34 characters, the feed commands under 24, and the agent names under 12.
