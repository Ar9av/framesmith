# Storyboard: canvas-story-reel

Reference: a 19.7 s, 1276x720, 30 fps Instagram reel ("storytelling is the moat"). It has no hard cuts. Every beat is continuous motion, so map it with a 3 fps contact sheet, because scene detection finds nothing. Shots sit on a 1/3 s grid.

| # | Shot | Start | Dur | Reference | Prismor example |
|---|---|---|---|---|---|
| 1 | `words` (black, lead arrow, tags) | 0.00 | 1.67 | "Somewhere right now" with an arrow cursor and code fragments | same line; agent commands as tags |
| 2 | `ring` | 1.67 | 0.33 | a ring with an up arrow and a dot stream | same |
| 3 | `wave` | 2.00 | 0.33 | a blue dot-matrix wave with a glowing arrow | same |
| 4 | `plate` | 2.33 | 1.34 | a map UI card over clouds, zooming | an agent terminal window over clouds |
| 5 | `frame` | 3.67 | 2.33 | blue garage plate, "Someone is changing everything" frame, punch into "everything", close to a card | "An agent is touching everything" |
| 6 | `grid` | 6.00 | 0.67 | a pixel-grid icon on white | same |
| 7 | `scatter` | 6.67 | 0.67 | "AND NOBODY KNOWS IT" converging | "AND NOBODY SEES IT" |
| 8 | `column` | 7.33 | 1.33 | "The ones [photo column] who won" | "The teams … who win" |
| 9 | `words` (black, tags) | 8.67 | 1.33 | "who won didn't just build" | "who win didn't just ship agents" |
| 10 | `flip` | 10.00 | 1.00 | three tilted archival photos | same, generated plates |
| 11 | `stack` | 11.00 | 2.33 | THEY / MADE / THE / WORLD over full-bleed founder photos | THEY / GOVERNED / THE / AGENTS |
| 12 | `words` (glow) | 13.33 | 3.67 | "Believe" then "Sell your story to the world" | "Govern" then "Ship agents the world can trust" |
| 13 | `logo` | 17.00 | 3.00 | the mark, then the wordmark | the Prismor logo and name |

## Style spec

- **Palette:** black and white grounds. Accent blue `#5A6BFF` for the newest word, the wave and the grid. Red `#E2264D` handles and code brackets. Yellow `#F4E409` anchor dots. Lavender `#A3ADFF` particles. Pink `#F08AA8` diamonds. Warm `#FF9B3D` path line. Plates are tinted onto `#2A4FA8`.
- **Type:** `sans` (Inter Display) regular for lines, medium for the stack and scatter. Tracking is −6 px at 150 px for the stack. `mono` is used only for code tags.
- **Grammar:** selection handles on everything, a hopping anchor cluster (moves every 4 frames), diamonds, code tags, newest-word accent flash (0.25 s), blue luminance tint on plates, drifting pixel particles.
- **Transitions:** hard cuts only. Motion carries the continuity.
- **Audio:** music only, no voiceover.
