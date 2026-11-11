---
name: halftone-dot-film
description: Render a square one-dot film (20 s, 1:1, 120 BPM, synthesised score) in ink, paper and a single accent, where one dot carries every scene. It drops and draws its own spring curve, then hops onto the brand and becomes the tittle of its i (the word is set with dotless i's). Next it becomes day one of a month of habit or activity dots that fill in on eighth notes, floods the frame for three features, and turns into a halftone year of 364 dots whose sizes swell around it. The field grows past the frame until the page flips to ink, and the dot lands on the i again. No gradients, glows or particles. Use for app launches (habit, fitness, finance, calendar, productivity, data products), streaks, "year in review" posts, brands with an i in a short lowercase name, or when the user asks for "halftone", "dot motion", "minimal Swiss motion", "one-element animation", "dot grid", "data-driven motion graphic" or a "Dieter Rams / Braun"-calm product clip.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: motion-graphics, halftone, minimal, app-launch, data-viz, one-element, square, music-driven
---

# Halftone dot film

A 20 s, 1080×1080 film. The dot is the only character, and every transition is the dot changing role:
- curve → tittle
- tittle → day one
- last kept day → flood
- flood ground → halftone field
- field → ink page
- falling dot → tittle again

The structure follows the "one-dot system" and halftone-field films collected in the Opus 5.5 motion-design lists. In particular, [ultimaxbt's dot film](https://x.com/ultimaxbt/status/2107486052550062398) (warm off-white, near-black, one orange accent; gradients, glows and particles banned) is in [motionvideohq/awesome-opus-5-5-motion-design](https://github.com/motionvideohq/awesome-opus-5-5-motion-design). The spring curve the dot draws is sampled from the same `framesmith.motion.spring` that moves it, and the score places a blip on every bounce peak of that curve.

Example: `examples/tiri/` is a fictional habit tracker.

## Workflow

1. Copy `examples/tiri/brief.json`. The brand must contain a lowercase `i`, because each i's tittle is a dot.
2. Fill the month with real or representative data: `days`, the `kept` day numbers, and a `count` line that agrees with them.
3. Run the copy through `no-ai-slop`. Features say what the product does; there are no slogans and no trailing periods.
4. `check` → `still 0.8 2.6 5.5 8.6 13 15.6 18.5` → `render`.

## Brief

| key | meaning |
|---|---|
| `theme` | `paper`, `ink`, `accent`; one accent only |
| `copy.brand` | short lowercase name with at least one `i` (set in Inter Display Black) |
| `copy.kind` | one line under the word |
| `copy.habit`, `month`, `days`, `kept`, `count` | the month grid: kept days are accent dots, missed days are hairline rings |
| `copy.features` | up to 3, each wraps to at most two lines |
| `copy.year` | the label over the 364-dot year |
| `copy.offer`, `url` | end card |

## Rules

- Every mark is a solid dot, a hairline or type: no boxes, pills or shadows.
- Keep the accent for the dot and the kept days. Text is ink on paper, ink on accent, or paper on ink.
- `references/storyboard.md` has the beat sheet.
