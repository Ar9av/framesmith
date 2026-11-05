---
name: canvas-story-reel
description: Render a 20-second, music-only story reel (16:9, 30 fps) in the design-canvas style. Kinetic type lands word by word with the newest word flashing the accent, and every element wears design-editor overlays (red selection handles, a hopping yellow anchor cluster, pink diamonds, code tags in red brackets). Between the type beats it runs a ring and arrow, a blue dot-matrix wave, a photo card zooming to full bleed, a blue-tinted plate behind a text frame that punches into its last word, a pixel grid, scattered words converging, a scrolling photo column, tilted photo flips, a huge stacked headline over full-bleed archival plates, a glow-lit closing line and the real logo. Use for founder-story or manifesto reels, 'storytelling is the moat' style Instagram or X posts, brand teasers and short hype cuts, or when the user shares a reel with editor handles and stacked headlines and says "make one like this for <brand>".
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: kinetic-typography, story-reel, editor-overlays, manifesto, instagram, music-driven
---

# Canvas Story Reel

A 20 s, 13-shot story reel that reads like a design canvas being edited live. It was built with `video-to-template` from a 19.7 s Instagram reel. Example: `examples/prismor/` (Prismor, "They governed the agents").

The arc is fixed and works for most manifesto copy:
1. A hook line on black, with code tags typing in around it.
2. An abstract transition: a ring with an arrow, then a dot wave.
3. A place: a photo card zooming in.
4. The tension: a text frame over a blue plate, punching into its last word.
5. A reveal: a pixel grid, then scattered words converging.
6. "The ones who…": a scrolling photo column.
7. The turn: a line on black.
8. Proof: tilted photo flips.
9. The anthem: a 4-word stacked headline over full-bleed plates.
10. The call: a glow line.
11. The logo.

## Workflow

1. Write the copy with the `no-ai-slop` skill. Use short beats: 3 words for the hook, 5 for the frame line, 4 for the scatter and the stack. Leave off trailing periods.
2. Supply the real logo as `assets/logo.png` (square, with a transparent or dark background).
3. Put plate prompts in `brief.json` under `assets` and run `python3 scripts/main.py assets --brief brief.json`. Plates are 1536x1024, documentary or 35 mm photographs of anonymous people seen from behind. Do not use real public figures, even though the reference does.
4. `python3 scripts/main.py check --brief brief.json` fails on overflow and warns on shrunk copy and trailing periods.
5. Review with `still … 1.2 4.6 7.9 11.2 16.5 19` or `sheet`, then `render --audio music.m4a`. Shot lengths sit on a 1/3 s grid, so cut the music to it.

## Shots (brief `shots[]`, each with `type` and `dur`)

| type | What it draws | Keys |
|---|---|---|
| `words` | A centred line landing word by word under handles. Each new line replaces the last at its `at` time. | `bg` black/white/glow, `lines` [str or {text, at, chars}], `every`, `size`, `lead_arrow`, `tags` [{t, x, y, at}], `particles` |
| `ring` | A ring scaling up around an up arrow, with dots streaming in | — |
| `wave` | A blue dot-matrix wave under a glowing arrow | — |
| `plate` | A photo card on a blue field zooming past full bleed while its tint drains out | `media`, `from`, `to` |
| `frame` | A blue-tinted plate with a white text frame that slides in typing, then punches into the last word with rings. It can close into a card on white. | `media`, `text`, `every`, `size`, `punch_at`, `close` |
| `grid` | A pixel-grid icon filling in on white | — |
| `scatter` | Uppercase words converging from scattered positions | `words` [{t, from, to, green}], `converge`, `size` |
| `column` | Left and right words around a scrolling photo column | `left`, `right`, `right_at`, `media` [], `every` |
| `flip` | Tilted photos flipping on white | `media` [], `tilts` [] |
| `stack` | A stacked headline over plates. Each beat swaps the plate and lights the next word. | `words` [4], `plates` [{media, look color/bw}], `size` |
| `logo` | The logo pops in, then the name slides out | `name`, `size` |

Theme keys (hex): `accent`, `handle`, `anchor`, `lavender`, `pink`, `warm`, `tint`, `green`. See `references/storyboard.md` for timings against the reference.

## Notes

- The white text frame in `frame` is the reference's own caption treatment, kept on purpose for this style. It deviates from the repo's no-pills rule.
- Code tags are literal code, so they use mono. Keep them harmless-looking: agent security hooks flag strings that look like exfiltration.
