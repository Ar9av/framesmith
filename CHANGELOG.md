# Changelog

## 0.17.0 (2026-10-01)
- Engine: image generation defaults to `gpt-image-2.5-sunburst` (`FRAMESMITH_IMAGE_MODEL`, or `"model"` per asset; `-flare` for speed). When a model refuses `background: transparent`, `generate_images` falls back to a flat chroma key and `media.chroma_cutout` (border flood fill, enclosed-hole keying, feathered edge, despill).
- Skill `abstract-journey-film`: music-only title film, a glowing orb through 22 abstract worlds to the logo, gpt-image-2.5 transparent assets, procedural scenes and a synthesised score. Example: Prismor (83 s).
- video-to-template lessons: image model IDs, transparent fallback, read-only `fromarray` buffers, RGBA drawing semantics, seeded particle tables, Whisper windowing, TTS voice choice, render backpressure and presets, agent security hooks.

## 0.16.1 (2026-09-29)
- brutalist-product-promo: `meta.logo` puts the brand's real logo beside the wordmark (hairline on dark grounds); new example `examples/prismor/` (software product in the ARC style: violet accent, key closeups, padlock sprite, server-rack line art, prismor.dev copy).

## 0.16.0 (2026-09-29)
- Engine `framesmith.motion` (ideas from howseen-ai/claude-motion-design, MIT, ported to pure Python): closed-form springs, voice-synced masked word rises with accent fills, letter stretch, words on dashed paths, scatter, 3D perspective tilt, detection boxes, border and connector beams, spinner, code-synthesised SFX and a voice+SFX mixer.
- Engine: `narration.transcribe_windows` (overlapping-window Whisper; long takes no longer lose stretches of timings); `Timeline.render` feeds the encoder in bounded batches (no more out-of-memory kills on small machines) and takes `preset=` / `FRAMESMITH_PRESET`.
- Skill `kinetic-launch-film`: text-led launch film with product UI and synthesised sound. Example: Prismor launch (67 s).
- Skill `archive-launch-film`: documentary cold open to product film, pastel prismor.dev ground, Enterprise beats (fleet wall, holographic reveal, enroll, console panels, repo end card). Examples: Prismor (65 s) and Prismor Enterprise (84 s).

## 0.15.0 (2026-09-28)
- Skill `animated-character-explainer`: the layered, character-driven explainer as its own template. `cast` builds a whole cast from `cast.json` (bases → on-model poses via gpt-image-2 edits → props → backdrops), `init` copies a fill-in starter (11-beat arc, stand-in cast), `check` warns on unfilled placeholders and trailing periods, previews work before the voiceover exists. Example: Prismor Enterprise (4 characters, 14 poses).

## 0.14.0 (2026-09-28)
- Engine: reference-guided gpt-image-2 generation (`"ref"` in an asset spec calls the edits endpoint) to keep characters on-model across poses.
- illustrated-explainer: layered `stage` beat (transparent-PNG cast, props, backdrops; parallax camera; slide/pop/rise entrances; idle breathe/bob/float; pose swaps on spoken cues; spring icon tiles with Lucide + thesvg; whiteboard flows, lists, connector lines, map pins; side veil). Example `prismor-layered` with a 4-character cast in 14 poses.

## 0.13.0 (2026-09-28)
- Skill `illustrated-explainer`: narrated flat-vector explainer (cue-timed beats, house-style gpt-image-2 illustrations via a STYLE prompt prefix, scene/bullets/split/logo/map/cards/cta beats, zoom-blur whoosh). Example: Prismor Enterprise, 62.8 s with voiceover.

## 0.12.0 (2026-09-28)
- Engine `framesmith.console`: 10 animatable enterprise-console components rebuilt from Prismor's admin console: posture, KPI strip, guard pipeline, agent trust card, coverage/devices table, shadow AI, network egress, security proof pack, live activity, MCP gateway.
- glass-saas-promo / blue-story-film: `tilt` shots can show a live console component (`component`, `data`, `console_data`).
- Prismor Enterprise glass film v3 built on the new components.

## 0.11.0 (2026-09-28)
- glass-saas-promo + blue-story-film: `pillars`, `flow`, `orbit` icon shots and an `icons` verb; Prismor Enterprise examples rebuilt on real prismor.dev dashboard components (overview, permission profiles, runtime monitor, agent stack, closed-loop, routing diagram, session), with AI agent governance pillars, the runtime pipeline and a platform orbit of 19 brand marks.
- video-to-template: `grab.mjs`/`lib.mjs` (CDP capture of real product UI from a live site).

## 0.10.0 (2026-09-28)
- Skill `glass-saas-promo`: frosted-glass SaaS promo (perspective UI, screen tunnel, gradient stream into a progress bar, confetti check, card scatter, carousel, glass heroes). Example: Prismor Enterprise with gpt-image-2 glass objects.
- Skill `blue-story-film`: blue-light story film (typewriter captions with selection, "Meet" collapse, split UI-to-terminal, bracket and wide words, form fly-over, black CTA). Example: Prismor Enterprise with gpt-image-2 backdrops.

## 0.9.0 (2026-09-28)
- keynote-product-film: `checklist` and `graph` shot types; `examples/enterprise-onboarding/` (Prismor Enterprise onboarding film built from prismor-web-preview's onboarding checklist, enroll drawer, prompt guardrails, agent instances and the org-context graph).

## 0.8.0 (2026-09-27)
- Skill `no-ai-slop` (Peter Yang, MIT) added to the catalog; required pass for all video copy.
- keynote-product-film: `examples/starter/` fill-in template (the Prismor keynote arc with [placeholders]) and `init` verb; `check` warns on unfilled placeholders and trailing periods.

## 0.7.0 (2026-09-27)
- keynote-product-film: shot types `fleet_grid` (device fleet with enrol / flag / policy-push wave), `table` (console table with live cell updates), `feed` (streaming receipts), `card` (approval / exemption / enrolment / attestation detail with typeset actions); `brand_icons` in briefs.
- New example `examples/fleet/`: Prismor Control Plane feature film (enrol, devices live, signed org policy push, redacted live receipts, human approvals, expiring exemptions, shadow-AI discovery, attestation).

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
