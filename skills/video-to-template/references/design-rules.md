# Design rules (hard requirements)

These came from direct feedback on real deliverables. Treat each as a failing test.

1. **No pills, chips or badges.** Rounded coloured status labels read as generic AI-UI slop. Status is typeset: a coloured word, a leader line, a rule, or inverse video. Captions sit on a scrim, never inside a rounded box.
2. **The brand's real logo only.** Never generate, trace or "reinterpret" a logo, and never substitute a literal visual pun for the name (a stock prism for "Prismor" was rejected). Fetch the actual file from the brand's site or repo.
3. **No text overflow, ever.** Every `text()` call gets a `max_w` (use `fit_to=` during scramble or typing). Terminals word-wrap at `max_width`, and device screens auto-size to their safe area. `check` fails on overflow and warns below 80%; the fix is shorter copy, not smaller type.
4. **No default-terminal look.** No typewriter or slab mono, and no salmon/amber/grey "syntax theme". Use a tight palette: ink, paper, one signal colour used as solid fields (inverse video), and brand light for positive states.
5. **No italics.** Emphasis comes from inverse video, the pixel face, scale, or brand light.
6. **Type roles:** Inter Display for statements, Geist Mono for literal code only (ligatures off), Departure Mono (`pixel`) for accents, voice and labels, snapped to its 11 px grid.
7. **Make it move.** Text enters with masked rises (40–60 ms staggers), highlights sweep, and cameras drift and punch on beats. Hold a static frame longer than ~0.5 s only on purpose.
8. **Honest content.** Claims come from the product's docs. No invented testimonials, quotes, tweets or metrics. AI voices should be disclosed to viewers.
9. **Licensed assets.** Fonts are OFL/MIT and bundled. Icons are licence-checked (brand-icons). Reference frames stay out of the repo (the scaffold gitignores them).
