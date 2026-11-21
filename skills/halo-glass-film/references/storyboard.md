# Storyboard: halo-glass-film

Reference: a 32.7 s Instagram post (1080×1350, a 16:9 film letterboxed on black) launching a Google Labs product agent. It's music only, cuts on in-scene morphs rather than hard cuts, and the average shot is 4.7 s.

| # | Ref time | Reference shot | Our scene | Start | Dur | What happens | Brief keys |
|---|---|---|---|---|---|---|---|
| 1 | 0.0–7.4 | Two white rings with orbiting dots over lavender/cyan light; letters slide in and the rings become the "oo" of "Loop"; logo + "Experiment" above | `halo` | 0.0 | 7.0 | One ring with an ink dot on it shrinks into the brand's "o" as the letters slide in from both sides; logo row above; two lines rise under the word; letters fly out and the ring returns to centre | `copy` |
| 2 | 7.4–10.0 | The rings fold into a "Goal" glass card; placeholder, typed goal, "Create Loop" button with gradient fill; hairline rails | `policy` | 7.0 | 3.6 | The ring morphs into the glass card; placeholder clears; the prompt types with a caret; the button fills with light and gets a check; the camera pushes in | `policy` |
| 3 | 10.0–14.3 | Huge "Security" over a glass metric card with a gradient area chart; two more cards stack in | `stats` | 10.6 | 4.0 | Heading rises; area chart draws and counter ticks; the camera pulls back; bar and segment cards stack in; a live activity column scrolls on the right | `stats` |
| 4 | 14.3–15.2 | Findings by severity (HIGH / MEDIUM / LOW), a dot column | `findings` | 14.6 | 1.3 | Severity groups with ring marks and typeset level words; the camera dives into the first HIGH row | `findings` |
| 5 | 15.2–19.4 | Dot-matrix mark + 3-line finding; three fix rows; one lights up with a gradient glow and opens a code card | `detail` | 15.9 | 3.8 | Same, with real fix rows; the focused row glows, the others dim, a code card grows from the row and types the before/after | `detail` |
| 6 | 19.4–21.9 | "Critical Vulnerabilities" over a capsule glass chart; white disc grid | `trend` | 19.7 | 2.6 | Two-line heading; the line falls across 7 days with labelled points; the disc grid pops; the camera pans to the discs | `trend` |
| 7 | 21.9–24.6 | Tall lavender→cyan card with "+ REPOSITORY / + FILE / + INTEGRATIONS" pills; discs on the left | `agents` | 22.3 | 2.6 | Same card; heading plus agent tiles (real icons, mono names) pop in; the card collapses into one dot | `agents` |
| 8 | 24.6–28.3 | One dot "DECIDE WHAT TO BUILD"; a blue arc draws two rings with four step labels; the rings become "Loop" again | `loop` | 24.9 | 3.6 | The dot draws two rings, step labels pop as the arc passes, a thin comet runs the figure-eight; the rings merge and land as the wordmark's "o" | `loop` |
| 9 | 28.3–32.7 | Stitch logo "built with …", then Google Labs lockup + waitlist URL, flask grows | `end` | 28.5 | 4.4 | The letters fold away, the ring shrinks into the real logo; name + "Independent and open source"; then the logo grows over the CTA | `copy.cta` |

## Style spec

- Palette: ground #E2E2E4, ink #17171A, muted #86868E, hairline #C6C6CC; aura lavender #B3A6F6, cyan #86E3F2, mint #A9F2D6, pink #F5B3DA, periwinkle #8FA8F0.
- Type: `sans` for the wordmark (300 px, white) and headings (96–140 px, ink); `sans_medium` for UI labels; `mono` for commands and marks.
- Motion: ease-out rises and masked line rises; ease-in-out camera; a small overshoot on pop-ins only (discs, tiles, loop nodes).
- Audio: 96 BPM pad in D, plucks under the chart, blips on reveals, typing ticks, risers into the findings dive and the ring merge.
