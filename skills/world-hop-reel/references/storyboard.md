# Storyboard: world-hop-reel

Timings are for the example (120 BPM, 4 beats per world, 6 worlds, 6.5 s end hold = 18.5 s).

| # | Scene | Start | Dur | What happens | Brief keys |
|---|---|---|---|---|---|
| 1 | cave | 0.00 | 2.0 | Runner in ochre (strokes boil on 3s, multiplied into rock), hand stencils, finger dots, torch flicker; label in dry-brush Anton | `worlds[0]` |
| 2 | egypt | 2.00 | 2.0 | Whip on the downbeat; flat skin-tone runner with kilt, wig and broad collar over ruled hieroglyph columns; label in lapis between gold rules | `worlds[1]` |
| 3 | greek | 4.00 | 2.0 | Black-figure runner with incised lines on terracotta, meander and tongue bands; tracked serif label | `worlds[2]` |
| 4 | glass | 6.00 | 2.0 | Voronoi lead cells breathing with light; runner in jewel segments with a halo; serif on a lead band | `worlds[3]` |
| 5 | crt | 8.00 | 2.0 | 1/6-resolution phosphor runner, vector mountains, scanlines, roll bar, bezel; Departure Mono label | `worlds[4]` |
| 6 | holo | 10.00 | 2.0 | Wireframe runner with glow and emitter cone over a perspective grid; mono label, HUD arcs, note line | `worlds[5]` |
| 7 | gallery | 12.00 | 6.5 | Paper ground; one tile per world wipes up every half beat (same figure, same moment of its cycle); years under tiles; title, details, URL rise in at +3.0, +3.5, +4.0 | `copy.title`, `copy.details`, `copy.url` |

The reel wrapper puts `copy.hook` above the film for the whole duration and `copy.footer` below it.

## Reference reel notes (what was studied)

- 44 s 9:16, a 16:9 film in the middle band, blurred zoomed cover behind, a yellow hook line fixed on top for all 44 s.
- A narrated story; nearly every spoken phrase switches art style: 3D diorama, rubber-hose B&W, anime, chalkboard, flat vector, sitcom couch, 3D product render, HUD hologram, pop-art comic, terminal, isometric pixel room, theatre stage, pixel CTA.
- A small companion creature recurs and "evolves" across the worlds; one keyword per beat in that world's typography; "×2" counters as beat accents.
- Ends on "comment SKILL" as the call to action.
