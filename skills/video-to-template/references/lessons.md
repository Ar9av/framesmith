# Lessons (each one cost a re-render)

## Analysis
- ffmpeg's scene score misses cuts on a constant background (collage/minimal styles). `analyze.py` also uses changed-pixel peaks with an adaptive threshold. Still, sanity-check against the contact sheets.
- The silence-based audio guess can't tell narration over music from music. Use `--transcribe`: more than 1.2 words/s means narration.
- Palette ranking is by coverage, so small accent text (a maroon keyword) can drop out. Confirm accents by eye.

## Assets
- gpt-image-2 transparent or "green screen" devices may come back with holes in the screen. Key green **and** transparent pixels inside the green bounding box together (see `device_parts` in narrated-collage-explainer).
- GIF or screen-recording crops inside a small device screen are illegible and clip lines. Retype them as native terminal text, keep lines ≤ 26 characters, and let the screen auto-size.
- thesvg icons: prefer the `light`/`dark` variant, tint white-only marks on light grounds (never ND-licensed ones), and skip "Unknown" licences.
- ImageMagick's SVG parser fails on compact arc syntax, `em` sizes and `currentColor`. Rasterise with headless Chromium (`media.rasterize_svg`).
- **Snap-packaged Chromium can't see `/tmp` or hidden folders**; it has a private `/tmp`. Stage files under a normal folder in `$HOME` (the engine does this).

## Type
- Geist Mono has programming ligatures (`<!--`, `-->` become arrows). Render code with `ui.CODE_FEATURES`.
- Check glyph coverage before choosing a face (Fraunces and Departure Mono lack `●`; Go Mono lacks `✓`). Keep bullets in a face that has them.
- A scrambled string's width changes every frame. Size with `fit_to=<final copy>` or the type will pulse.

## Narration
- Whisper misspells ("EcuSecrets"). The script is the source of truth: `narration.align` takes timing from Whisper and spelling from the script.
- Balanced subtitle chunks avoid orphaned single words.

## Rendering
- `ffmpeg -shortest` with audio trims the video to the voice length and loses the tail and black end. The engine pads audio (`apad`).
- **Never render two jobs to the same output file.** Stopping a render leaves its ffmpeg child finalising into the file, and the next render corrupts it. Use a new filename per render, and kill stray ffmpeg processes first.
- `pgrep -f "<pattern>"` matches the shell running the wait loop, so the loop never ends. Poll the render's log for its final line instead.
- A 1080p render is roughly 0.4 s per frame per core with these effects. Budget ~10 min for 50 s on 2 cores, and review stills before every full render.

## Environment
- Don't `pip install` into a PEP 668 system Python. Use the tools already present (ffmpeg, Chromium, ImageMagick) or a venv.
- Load API keys from the project's `.env` only when the user has allowed it, and never print them.
- Before pushing, confirm the repo's visibility; git may use a stale stored credential, so use the `gh` credential helper for that one push if needed.
