# Changelog

## 0.6.1 (2026-09-27)
- keynote-product-film: container-overflow fixes (the bar sizes to the whole text block, stacked permission cards are opaque edges only, chart labels in their own column); `assets` verb for gpt-image-2 PNGs; `laptop` shot (keyed green-screen device showing a real screenshot); a floating generated object in `mask`.

## 0.6.0 (2026-09-27)
- Skill `keynote-product-film` (built with `video-to-template` from a keynote-style reference): kinetic blur-in sentences with Lucide line icons and app tiles, prompt bar, Claude Code-style session panel, permission prompts, brand-icon step list, morphing benchmark chart, ticker, masked-secret field, icon row, hero-wash logo reveal. Example: Prismor, using its site components, scenarios and OWASP benchmark.
- Engine: `Dissolve` transition (crossfade with blur peak); transitions are duck-typed (`blend`).

## 0.5.0 (2026-09-27)
- Skill `video-to-template`: the end-to-end reference → template process. `analyze.py` (download, cuts via scene score ∪ adaptive changed-pixel peaks, pacing, palette, audio type, Whisper transcript, contact sheets, keyframes, storyboard skeleton), `scaffold.py` (new template as a timed animatic from the analysis, reference frames gitignored), `compare.py` (side-by-side + paired frames). References: design rules, lessons, engine map.

## 0.4.0 (2026-09-27)
- Skill `brand-icons`: search / info / fetch / sheet / credits for thesvg.org brand icons, licence-aware (unknown refused by default, ND never recoloured, trademark flagged), attribution tables.
- Engine: `thesvg_registry()` (cached), `search_icons()`; Chromium rasterisation staged under $HOME so snap-confined Chromium works from any output path.

## 0.3.1 (2026-09-27)
- Brand icons from thesvg.org: `fetch_icons` (registry-driven variant + licence metadata), Chromium rasterisation, `icon()` with auto-tint for white marks.
- narrated-collage-explainer: native terminal screens that auto-size to the device's safe area (no clipped GIF crops), `mac` retro-computer device, `icons` beat, `icons` command.

## 0.3.0 (2026-09-27)
- Skill `narrated-collage-explainer`: square, voiceover-driven collage explainer (TTS + Whisper-timed beats, CRT TV / XP window / cards / starburst / collage, pixel dissolves). Example: Prismor, built from its real README GIFs and screenshots.
- Engine: `framesmith.narration` (TTS, word timestamps, script alignment, cue lookup, subtitle chunking).

## 0.2.1 (2026-09-27)
- Fonts: Go Mono replaced by Geist Mono; added Departure Mono (`pixel` role, grid-snapped). No italics anywhere. Code renders with ligatures off.
- Engine: `ui.rise` (masked kinetic type), `ui.fill_text` (texture-filled glyphs), `ui.marker` (highlighter swipe), terminal per-span font roles + marked lines; text fitting (`max_w`, `fit_to`) with overflow/shrink reports; word-wrapping terminal; `ui.chip` removed.
- devtool-launch-video: real logo slot, typeset verdicts with holo leader lines, inverse-video threat styling, pixel-type agent narration, livelier motion throughout.

## 0.2.0 (2026-09-27)
- Skill `devtool-launch-video`: 34 s 16:9 launch film for dev tools / AI-security products (example: Prismor).
- Engine: `framesmith.ui` with window chrome, time-scheduled terminal, chips, stat cards, holographic light field.

## 0.1.0 (2026-09-27)
- Engine `core/framesmith`: seekable timeline with mosaic transitions, easing tokens, typography (scramble/typed/decay), fx (ASCII, word field, glitch rows, smear, mosaic), vector blueprints, any-name wordmark, gpt-image-2 asset pipeline with sprite sheets.
- Skill `brutalist-product-promo`: 22.6 s, 21-scene spec-sheet promo, brief-driven.
- Skill `framesmith`: router + template authoring guide.
- Tools: new_skill, sync_core, catalog, validate.
