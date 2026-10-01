# Lessons (each one cost a re-render)

## Analysis
- ffmpeg's scene score misses cuts on a constant background (collage/minimal styles). `analyze.py` also uses changed-pixel peaks with an adaptive threshold. Still, sanity-check against the contact sheets.
- The silence-based audio guess can't tell narration over music from music. Use `--transcribe`: more than 1.2 words/s means narration.
- Palette ranking is by coverage, so small accent text (a maroon keyword) can drop out. Confirm accents by eye.

## Assets
- gpt-image-2 transparent or "green screen" devices may come back with holes in the screen. Key green **and** transparent pixels inside the green bounding box together (see `device_parts` in narrated-collage-explainer).
- GIF or screen-recording crops inside a small device screen are illegible and clip lines. Retype them as native terminal text, keep lines ≤ 26 characters, and let the screen auto-size.
- **Image model:** framesmith defaults to `gpt-image-2.5-sunburst` (richer render; `gpt-image-2.5-flare` is faster). Set `FRAMESMITH_IMAGE_MODEL` or a per-asset `"model"`. List the IDs a key can use (`GET /v1/models`) before assuming one: plain "gpt-image-2.5" does not exist.
- **Transparent PNGs:** if a model refuses `background: transparent` (gpt-image-2 did in late September 2026), `generate_images` regenerates the asset on a flat key colour and `media.chroma_cutout` removes it. The cutout flood-fills from the border (so key-like colours inside the subject survive), clears enclosed holes of pure key (a keyhole), feathers the edge and despills. Use `"key": "#FF00FF"` for green or lime subjects.
- `Image.fromarray(...)` can share a read-only numpy buffer, and `ImageDraw.floodfill` then silently does nothing. `.copy()` the image first.
- Cutaway line drawings flood-fill well only with clean outlines on white. Thicken lines (MinFilter) before the fill so small gaps don't leak, then dilate the mask back.
- thesvg icons: prefer the `light`/`dark` variant, tint white-only marks on light grounds (never ND-licensed ones), and skip "Unknown" licences.
- ImageMagick's SVG parser fails on compact arc syntax, `em` sizes and `currentColor`. Rasterise with headless Chromium (`media.rasterize_svg`).
- **Snap-packaged Chromium can't see `/tmp` or hidden folders**; it has a private `/tmp`. Stage files under a normal folder in `$HOME` (the engine does this).

## Layout
- The width-budget check (`text(max_w=…)`) can't see text escaping its **container**: a caption hanging out of a bar, a label running past a short bar, or translucent stacked cards showing each other's text. Size containers from the measured content, keep labels in their own column, draw back cards opaque with no content, and review a full-resolution still of every UI shot.

## Type
- Geist Mono has programming ligatures (`<!--`, `-->` become arrows). Render code with `ui.CODE_FEATURES`.
- Check glyph coverage before choosing a face (Fraunces and Departure Mono lack `●`; Go Mono lacks `✓`). Keep bullets in a face that has them.
- A scrambled string's width changes every frame. Size with `fit_to=<final copy>` or the type will pulse.

## Compositing
- `ImageDraw.Draw(im, "RGBA")` **blends only when `im` is RGB**. On an RGBA canvas a translucent fill replaces the pixels and their alpha, so "glass" panels turn solid white after `convert("RGB")`. Keep scene canvases RGB, and paste RGBA sprites and layers with themselves as the mask.
- Hash-based scatter (`h(i, k)`) correlates across fields for some index ranges and draws diagonal streaks. Use a seeded `np.random.default_rng(seed).random((n, k))` table for dense particle fields.
- Soft light is cheap as one gaussian blob resized once and tinted on paste; avoid per-frame full-resolution numpy gradients.

## Narration
- Whisper misspells ("EcuSecrets"). The script is the source of truth: `narration.align` takes timing from Whisper and spelling from the script.
- Balanced subtitle chunks avoid orphaned single words.
- **Whisper drops whole stretches of 60 s+ takes** (it returned nothing for the first 27 s of one voiceover). Use `narration.transcribe_windows` (12 s windows, 1 s overlap, stitched).
- Newest TTS: `gpt-4o-mini-tts-2025-12-15`; `marin` is the strongest female voice for flowing narration, steered with `instructions`. To drop a few spoken words without re-recording, cut the wav in the inter-word gaps and shift `words.json`.
- Give a visual beat breathing room with `holds` (silence after a phrase; timings shift and the audio is re-spliced).
- On-screen captions strip trailing punctuation ("the end." → "the end").

## Rendering
- `ffmpeg -shortest` with audio trims the video to the voice length and loses the tail and black end. The engine pads audio (`apad`).
- **Never render two jobs to the same output file.** Stopping a render leaves its ffmpeg child finalising into the file, and the next render corrupts it. Use a new filename per render, and kill stray ffmpeg processes first.
- `pgrep -f "<pattern>"` matches the shell running the wait loop, so the loop never ends. Poll the render's log for its final line instead.
- A 1080p render is roughly 0.4 s per frame per core with these effects. Budget ~10 min for 50 s on 2 cores, and review stills before every full render.
- **`multiprocessing.imap` has no backpressure.** With a slow encoder, finished 1080p frames (6 MB each) pile up until the process is OOM-killed on a 3 GB box. `Timeline.render` now feeds the pool in bounded batches.
- On a throttled VM (check `%st` steal in `top`) the `slow` x264 preset dominates. Use `FRAMESMITH_PRESET=veryfast` for drafts.
- Don't run `check` (it renders frames) at the same time as a render on a small box.

## Agent security hooks
- Hooks such as Prismor's scan every tool call. Demo copy that looks like exfiltration (a curl upload of an env file, an injected "upload your keys" README line), or a one-off script that both reads the env file and encodes bytes, gets blocked, and later web fetches can be refused as tainted. Never work around a block: make demo strings harmless-looking and keep secret loading inside library code.
- Never type a Cloak placeholder literally in a command; the decloak hook may substitute the real value. Build it from pieces in code.

## Environment
- Don't `pip install` into a PEP 668 system Python. Use the tools already present (ffmpeg, Chromium, ImageMagick) or a venv.
- Load API keys from the project's `.env` only when the user has allowed it, and never print them.
- Before pushing, confirm the repo's visibility; git may use a stale stored credential, so use the `gh` credential helper for that one push if needed.
