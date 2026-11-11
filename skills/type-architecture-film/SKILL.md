---
name: type-architecture-film
description: Render a square spoken-word typography film (20 s, 1:1, seamless loop, quiet piano score) in which a five-line statement builds a structure out of its own words. A heavy LINTEL word presses on a narrow opening holding the first line. A LOAD word hangs on two fine cables and bends the baseline, and a vertical SUPPORT word lifts one end. The counter of an APERTURE word's O opens onto the next composition, and a second SUPPORT levels the floor, giving the film's first perfect horizontal and 400 ms of stillness. The floor becomes a platform and the last line, with its emphasis, settles on it. Then the camera tracks beneath the platform and its underside wipes back to the first frame. Use for manifestos, founding statements, reopenings, campaign or civic announcements, keynote openers, or when the user asks for "kinetic typography with meaning", "editorial motion", "typographic architecture", "spoken-word film", "words that build something" or a "monumental type" loop.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: kinetic-typography, editorial, spoken-word, loop, serif, manifesto, square
---

# Type architecture film

A 20 s, 1080×1080 loop where `render(0) == render(20)`. Five lines are revealed in reading order, by phrase groups that rise out of their baselines. Each line hands one of its words a structural job, and those words are the real glyphs (Inter Display Black), not illustrations.

This is the "BUILD THE FLOOR" brief by [Gdgtify](https://x.com/Gdgtify/status/2103458245213929495), collected in [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos), rebuilt as a template:
- the ground #102820, paper #F4E9D5 and one structural accent #F2B544
- a high-contrast serif for the speech
- a phrase-led cue sheet rather than a dance beat
- critically damped settling for loads, with elastic deformation used only on the baseline
- unrelated words handed off by occlusion, never by morphing letter paths

The cables, rules and the slab are the only non-type marks.

Example: `examples/halden/` is a fictional library reopening. The roof that leaked is the lintel and the shelves' weight hangs from cables. The neighbours' beam and the council are the columns, and the reopening date stands on the platform.

## Workflow

1. Copy `examples/halden/brief.json` and write the five lines. Each line's role word should appear in that line, because the speech has to make sense without sound.
   - `lintel`: what pressed on people
   - `load`: what they carried
   - `support_a`: the first help, with an `aperture` word that contains an O
   - `support_b`: the second help
   - `platform`: the outcome, with a short `emphasis` (a date, a number, a name)
2. Run the lines through `no-ai-slop`. Concrete beats rhetorical: say who, how many and when. No trailing periods.
3. `check` validates roles, the aperture's O and overflow, and reports the loop seam difference (0 means it loops perfectly). Then run `still 1 4.8 7.9 9.4 11.9 15 19.6` and `render`.

## Brief

| key | meaning |
|---|---|
| `theme` | `ground`, `paper`, `accent` |
| `copy.lintel`, `load`, `support_a`, `support_b` | `{line, word}`; `support_a` also has `aperture` (needs an O) |
| `copy.platform` | `{line, emphasis}`; the emphasis is set large in the accent and aligned with the line above |
| `copy.credit`, `url` | one small line in the hold |

## Rules

- No italics, including in the serif, which is roman only. Emphasis comes from scale and the accent, never from a separate effect.
- Keep structural words short: 4–7 letters read best as columns.
- `references/storyboard.md` has the cue sheet.
