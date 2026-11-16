---
name: ui-macro-launch-film
description: Render a white, type-led SaaS launch film (about 58 s, 16:9, music only) built from the product's own UI at macro zoom. A caret types the brand huge, then small with a trail of dots that swell into shapes. Three "<Brand> is not a …" rows end in a button, a card and a field that get struck out. The logo grows into the app window, and the camera pushes through native-drawn UI fragments - an AI composer being typed, a "thinking" beat, an activity table with a detail panel, a checklist writing itself, search with marker-highlighted matches, a team thread with a ticking counter, an integrations grid, a timeline row going to Done. It closes on "<Brand> does" beside a cascading checklist, one box the cursor ticks, and the box turning into the logo. Use for SaaS, productivity, collaboration, dev-tool or AI-agent launches, "product tour" or "feature walkthrough" films, or when the user says "clean white UI video", "Apple-style UI close-ups", "macro UI zoom", "zoom into the interface" or "what <product> is and isn't".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: saas, product-tour, ui-zoom, kinetic-type, launch-film, white, minimal, checklist, music-only
---

# UI macro launch film

A 57.5 s film at 1920×1080 and 30 fps, made of 14 scenes on a pure white ground. It has a synthesised score with keys, plucked bass, typing ticks and clicks.

It was back-engineered from an 87 s Instagram reel for a workspace app (shot list in `references/storyboard.md`). The reference's grammar:
- Every scene is one UI fragment, drawn huge and sharp: a prompt box, a table, a checklist, a search box, a chat thread.
- One type family throughout (Inter Display), with ink on white and colour only in the UI's own states.
- A caret and typing carry the story. The camera pushes in on the part that matters.
- Hard cuts on the beat, with object handoffs between scenes: dots become shapes, the logo becomes the window, a checkbox becomes the logo.

What changed from the reference, on purpose:
- Monogram tiles instead of illustrated faces.
- Agent icons (thesvg) instead of mascots.
- Status as typeset coloured words, not badges.
- The reaction count as a drawn check plus a number, with no container.

Every UI element is drawn natively in design units through a camera (`P` in `scripts/main.py`), so text stays crisp at 2.6× zoom. No screenshots or generated images are used.

Example: `examples/prismor/`, the Prismor console (agent tool-call checks, policies, cloaked keys) for a fictional robotics team.

## Workflow

1. Copy `examples/prismor/` and put the brand's **real** logo at `assets/logo.png`. Fetch integration icons with the `brand-icons` skill into `assets/icons/<slug>.png` (`--theme light`).
2. Edit `brief.json`. Every string on screen comes from it:
   - `copy`: brand, url, cta
   - `hook`: the giant letters and the small line
   - `not_a`: three rows, each with a kind (`button`, `card` or `field`), a label and an icon
   - `console`, `composer`, `table`, `checklist`, `search`, `thread`, `agents`, `timeline`, `team` and `outro`
3. Run the copy through `no-ai-slop`. Every line should state a product fact or show a concrete moment. Leave off trailing periods, and use uncommon demo names.
4. `python3 scripts/main.py check --brief brief.json`. It fails on a missing logo or icon, trailing periods, or any overflow.
5. Run `still --brief brief.json 1.3 9.6 14 18 24 26.5 30 33.5 39 43.9 45.5 52.5 57.2` and look at every frame.
6. `FRAMESMITH_PRESET=medium python3 scripts/main.py render --brief brief.json`. This takes about 10 min on 2 cores.

## Rules

- Ink on white. Colour appears only as UI state: the verdict words, the strike, the marker, the accent on AI actions, and the three "thinking" dots in the brand's light.
- No pills or badges. Dates and verdicts are coloured mono words. The only rounded containers are real UI (cards, inputs, buttons, chat bubbles).
- Code is mono (Geist), and reasons are in `pixel`. Everything else is Inter Display. No italics.
- Keep `not_a` labels short (≤ 14 characters), keep `checklist` and `outro` items to one line each, and keep the `search.query` substring present in each result so the marker has something to hit.
