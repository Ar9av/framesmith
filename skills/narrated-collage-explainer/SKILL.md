---
name: narrated-collage-explainer
description: Render a square (1080×1080), voiceover-driven explainer or founder-story video in a warm paper-white collage style. One big pixel-type keyword at a time, tiny subtitles synced word by word, and media placed inside objects (a retro CRT TV, an XP-style window on green hills, stacked dark cards, navy starbursts, scattered archival photos), with pixel-block dissolves. It writes the voiceover with OpenAI TTS, gets Whisper word timestamps, and cuts every beat on a spoken cue phrase. Use when the user wants a narrated product explainer, "why we built this" story, launch video for socials (Instagram, LinkedIn, X), a collage or retro-internet aesthetic, or to turn a script plus screenshots and GIFs into a video. Deterministic Python + ffmpeg.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: explainer, voiceover, narration, collage, subtitles, square-video, tts, gpt-image-2
---

# Narrated collage explainer

The voiceover drives everything. Write the script, generate the voice, and each beat starts on the words it names. The example is `examples/prismor/`: a 50 s Prismor explainer with 16 beats that uses Prismor's real README GIFs and screenshots.

## Workflow

1. **Script** (`vo.txt`): write 90–120 words, which is about 45–50 s. Use short sentences and name one idea per sentence. Every beat needs a phrase you can cue on. Claims must come from the product's own docs.
2. **Voice:** `python3 scripts/collage.py voice --brief brief.json` runs OpenAI TTS (`vo.voice`, `vo.instructions`), then Whisper for word timestamps. The script stays the source of truth for spelling; Whisper only supplies timing.
3. **Beats:** in `brief.json`, each beat has `"at": "<cue phrase from the script>"` and a `type` (below). A beat runs until the next beat's cue. Cards and overlays inside a beat can have their own `"at"` cues.
4. **Media:** prefer real material, meaning the product's own screenshots, played inside a window.
   - **Terminal content goes in as native text** (`kind: terminal`), not GIF crops, which cut lines off and go illegibly small inside a device. Retype the real transcript as short lines of ≤ 26 characters. The screen auto-sizes the font to fill its safe area and never clips.
   - **Brand icons** come from [thesvg.org](https://thesvg.org). `python3 scripts/collage.py icons --brief …` downloads every slug used by `icons` beats (the light-background variant when there is one), rasterises it with headless Chromium, and records source and licence in `assets/icons/icons.json`.
   - Generate only scenery (`assets`: hills, CRT, retro computer, archival photos) at low/medium quality. The logo slot is always the real logo.
5. **Check:** `check` prints the beat table, confirms the voice exists, and fails on any text overflow. Then review with `still … t1 t2` and `sheet`.
6. **Render:** `render` muxes the voiceover automatically.

## Beat types

| type | shows | keys |
|---|---|---|
| `tv` | a device with media on its screen: `device: crt` (TV) or `mac` (retro all-in-one) | `device`, `media`, `bg` (`plain`/`hills`), `y`, `width` |
| `window` | XP-style window with media | `media`, `title`, `bg` |
| `cards` | dark cards that stack as they're mentioned | `cards: [{at, title, meta, logo?, lines: [{t, mark?, tone?}]}]` |
| `word` | one big keyword in pixel type | `text`, `photo?` (image beside the word), `stars?`, `word_at?` |
| `burst` | navy starburst holding an image plus a word | `media` (default `logo`), `text`, `word_at` |
| `collage` | photos landing in a loose pile | `media: [...]`, `step` |
| `icons` | brand marks from thesvg: leads land large on their cues with pixel captions, the rest fill two faded rows | `lead: [{slug, label, at}]`, `rest: [slugs]`, `rest_at` |
| `end` | logo, word, sub-line, then black | `text`, `sub` |

Any beat can have `overlays: [{at, text, style: "inverse"|"cyan", y}]`, a keyword laid over the media. A beat can set `"tr": "pixel"` (dissolve) or `"cut"`; changing background dissolves by default.

Media spec: `{"kind": "terminal", "lines": [{"t", "tone": cmd|dim|ok|hi|bad|plain}], "step", "max_size"}` for screens; `{"src": "file.jpg|gif", "frames", "crop", "zoom"}` for images and footage in windows; `{"kind": "static"}` for TV snow.

## Design rules

- No pills, chips or badges. Card meta and verdicts are typeset text. In cards, threats are inverse video on a signal-red marker.
- No italics. Big words and subtitles use the `pixel` face; card titles use the sans; code uses Geist Mono.
- Nothing overflows. `check` must pass. Cards fit their lines, and subtitles fit the frame and get a soft halo over busy footage.
- Use the real logo only. Don't invent testimonials or quote real people's posts. Show real product artefacts instead.
