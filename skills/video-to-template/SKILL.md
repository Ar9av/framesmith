---
name: video-to-template
description: Turn any reference video (a URL or file) into a reusable framesmith template and a finished video for the user's own brand. It covers the whole pipeline. It analyses the reference (shot cuts, pacing, palette, audio, narration transcript, contact sheets) and writes a storyboard and style spec. It scaffolds a timed animatic that already matches the reference's cuts, sources real brand assets (logo, product screenshots, thesvg.org icons) and gpt-image-2 scenery or sprites, and adds a voiceover when the reference is narrated. It builds the scenes on the framesmith engine, reviews side by side against the reference, renders, and ships the result as a new skill. Use when the user says "recreate this video", "make one like this for <brand>", "copy this style", "turn this video into a template", or shares a reference video, reel or ad and wants their own version.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: reference-video, style-transfer, template, storyboard, animatic, motion-graphics, workflow
---

# Reference video → template

This is the process that produced `brutalist-product-promo`, `devtool-launch-video` and `narrated-collage-explainer`, packaged so the next reference goes faster. Work in phases, and don't skip a phase's gate.

Tools (all in `scripts/`):

| Tool | Does |
|---|---|
| `analyze.py <url-or-file> [--transcribe]` | downloads; format, shot cuts (scene score ∪ changed-pixel peaks), pacing, palette, audio type, optional Whisper transcript; timestamped contact sheets, a keyframe per shot, `report.md` with a storyboard skeleton |
| `scaffold.py <name> --analysis …/analysis.json` | new template skill whose brief has one `animatic` shot per detected cut (the reference keyframe, dimmed), so timing matches from minute one |
| `compare.py ref.mp4 ours.mp4` | side-by-side video (reference audio) and paired-frame sheets at the same timestamps |

## Phase 0: Intake
Get: the reference, the target brand or product, and its **real** logo plus real product material (README demos, screenshots, docs). Also the format, if it differs from the reference. Ask only for what you can't find yourself; for a public product, read its repo or site first.
**Gate:** you can say in one sentence what the new video is about, and you have the real logo.

## Phase 1: Analyse
1. Run `python3 scripts/analyze.py <ref> --out analysis/<name>`, adding `--transcribe` if the audio looks like speech.
2. **Look at every contact sheet and several keyframes.** Open the images; the numbers alone aren't enough. The detector is a first draft: merge shots split by in-shot animation, and split any a dissolve merged.
3. Fill in the storyboard table in `report.md`: layout and subject, type (face, size, colour), motion in and out, transition, copy.
4. Write a short **style spec**:
   - palette (confirm by eye; coverage ranking under-weights small accent text)
   - type roles mapped to bundled faces (`sans` Inter Display, `mono` Geist Mono for code only, `pixel` Departure Mono)
   - the recurring visual grammar (the 5–8 object or treatment types the video is built from)
   - transition types
   - pacing (average shot length, and whether cuts follow beats or narration)
   - audio

**Gate:** storyboard filled for every shot, and a style spec written.

## Phase 2: Map to the engine
- For each grammar item, pick an engine primitive (`references/engine-map.md`) or plan a new scene type.
- Check the router (`skills/framesmith/SKILL.md`). If an existing template already covers most of the grammar, extend it instead of forking.
- Decide the asset list, using real material first (see Phase 4).

## Phase 3: Scaffold and time
1. Run `python3 scripts/scaffold.py <kebab-name> --analysis analysis/<name>/analysis.json` (inside the framesmith repo it lands in `skills/`).
2. Render the animatic and run `compare.py` against the reference. The timing should already line up.
3. If the reference is narrated: write the script to the reference's words-per-second, generate the voice (`framesmith.narration.tts` + `transcribe_words`), and re-time beats to spoken cues instead of fixed durations. `narrated-collage-explainer` shows the pattern.

## Phase 4: Content and assets
- **Copy:** every claim comes from the product's own docs. Never invent testimonials, quotes or posts from real people; show real artefacts instead.
- **Real material first:** the logo (never generated or reinterpreted), product screenshots, and terminal transcripts retyped as native text (not GIF crops).
- **Brand icons:** use the `brand-icons` skill (thesvg.org), with the light or dark variant to match the background, licences checked, and credits kept.
- **Generated scenery** (gpt-image-2, `low`/`medium`):
  - Write full-sentence prompts that name material, lighting, lens and an **explicit background**: pure black or white, transparent, or a flat `#00FF00` screen for devices you'll key.
  - Use a sprite sheet (a grid of the same subject, with one part changing) for looping motion.

## Phase 5: Build scenes
Replace `animatic` shots one at a time with real scene types, in order. After each: `still` at 2–3 moments, then look at them. Design rules are in `references/design-rules.md`; they're hard requirements.

## Phase 6: Review loop
- `check` must pass: no overflow, and no copy shrunk below 80%.
- Look at `sheet`, then `compare.py` against the reference. Fix the biggest mismatch first: layout, then type, then colour, then motion.
- Prove it generalises: render a second brief with a different brand, a light accent and a long name.

## Phase 7: Render and ship
- Render with a **unique output filename**, and poll the log rather than `pgrep` (`references/lessons.md`).
- Make the preview GIF (`docs/media/<name>.gif`) and a contact sheet. Finish `SKILL.md` (the description is the trigger), add a row to the router table, then run `tools/catalog.py`, `tools/sync_core.py --check`, `tools/validate.py`, the changelog and the version bump.
- Commit. Push only if the user asked; check whether the repo is public first.

Read `references/lessons.md` before starting. Every item in it cost a re-render once.
