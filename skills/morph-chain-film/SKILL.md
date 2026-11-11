---
name: morph-chain-film
description: Render a square morph-chain film (about 17 s, 1:1, 120 BPM, synthesised plucky arpeggio) where one solid hero shape becomes a chain of icons on the beat, from a drop to a cloud, sun, leaf, pin and bell, ending on the app icon. Every change passes through a circle with a turn and 10–15 % squash and stretch. Outlines are resampled by arc length from the top so morphs never knot (`check` tests every midpoint). The ground changes with a clean colour-block wipe on each morph, one caption per icon states a concrete feature, and the last shape becomes the app icon with the first shape cut into it and the wordmark beside it. Use for app launches, feature tours, icon-led product explainers, logo reveals, or when the user asks for "shape morphing", "icon morph", "morph transitions", "Apple-style morph", "flat icon animation" or "one shape that keeps changing".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: morph, icons, app-launch, flat, color-blocks, music-driven, square
---

# Morph chain film

A 1080×1080 film at 120 BPM. Each icon lands on its own bar (beat 2, 6, 10 …), and each morph takes 1.6 beats with 3-frame cushions at both ends. Captions rise once an icon has landed and sink as the next morph begins. The colour palette is a list of `[ground, ink]` pairs, one per icon, cycled.

From the morph study in [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15/blob/main/prompts/08-morph.md):
- one hero shape becomes six to eight meaningful icons
- every A → B passes through a simple intermediate with rotation and squash and stretch
- clean colour-block wipes per morph
- `cubic-bezier(0.7, 0, 0.3, 1)`-like easing
- every morph midpoint checked for knots

Example: `examples/kestrel/` is a fictional hyperlocal rain-alert app.

## Workflow

1. Copy `examples/kestrel/brief.json`.
   - `chain` lists 4–9 shapes from `drop, cloud, sun, leaf, pin, bell, squircle, circle`, each with a caption stating one concrete feature (numbers help).
   - End the chain on `squircle`, the app icon.
   - Set the `palette` pairs and the `copy` end card.
2. To add a shape, write a function in `scripts/main.py` that returns a closed outline about 2 units across, centred and star-shaped from its centroid, and register it in `SHAPES`. `check` fails if any morph knots.
3. Run captions through `no-ai-slop`. `check` → `still 0.5 2.6 3.4 7 11 13.5 17` → `render`.

## Rules

- Solid fills only: no outlines, gradients or shadows. Captions are Inter Display Black in the current ink, balanced over two lines at most.
- Never put the brand logo in the chain. The end shape is the app's own icon silhouette.
