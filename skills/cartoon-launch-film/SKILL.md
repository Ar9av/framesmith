---
name: cartoon-launch-film
description: Render a music-only, hand-drawn cartoon launch film (about 45 s, square 1080, 30 fps) for an X, LinkedIn or Threads post. It has boiling ink linework, a mascot with on-model poses, squash and stretch, a paper-and-grass world and a synthesised 120 BPM score with cartoon SFX. Beats are a dark terminal cold open where the agent forgets, a comic burst, a notebook slam title, the mascot eating old chats and docs, a linked-notes graph, a grid of the agents it works in, a hand-drawn Chrome window where a browser extension captures a page and fills a form with sourced answers, a cited answer note, a speed gauge, a star counter and an end card. Use for a GitHub-stars milestone post, open-source launch, devtool or AI-agent feature announcement, Chrome extension demo, or when the user wants a playful cartoon / indie-animation style instead of a polished SaaS look.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: cartoon, hand-drawn, mascot, boil, square, social, music, sfx, chrome-extension, devtool, launch
---

# Cartoon launch film

A square, music-only cartoon in an indie-animation style. Every sprite boils on threes (three mesh-warped redraws), characters hop and squash, the camera shakes on hits, and the score is synthesised in code with the cuts on its beat grid. Example: `examples/obsidian-wiki/` is the obsidian-wiki 3.5k-stars film (44.9 s) with Mo, a pink brain mascot.

## Workflow

1. **Start:** `python3 scripts/main.py init my-film`, which copies the example.
2. **Copy:** edit `brief.json`. Every on-screen string lives there: terminal lines and slash menu, captions, note names, agents, the browser article, popup and form, the answer note, gauge numbers, star count and end card. Run the copy through `skills/no-ai-slop` first. Don't put trailing periods on captions.
3. **Cast:** restyle `style`, `mascot`, `poses` and `props` in `assets.json`, then run `python3 scripts/main.py assets --brief my-film/brief.json` (or `assets mo_wave` to regenerate one). The mascot base is generated first, and every pose is a reference-guided edit of it, so the character stays on-model.
4. **Real marks:** put the agent logos and your product or extension icon in `assets/icons/` as PNGs. They're named by the `agents` slugs and `browser.icon`. Never generate logos.
5. **Check:** run `check --brief …`. It samples the whole cut and fails on missing assets or on any copy that had to shrink below 80% of its designed size. The fix is shorter copy.
6. **Review:** run `sheet --brief …` (a frame every 1.5 s) and `still --brief … 22.8 30.6`.
7. **Render:** run `render --brief …`, which renders the frames, synthesises `out/mix.m4a` with `scripts/audio.py` and muxes the result. On slow machines, render halves in parallel with `render --from 0 --to 674` and `--from 674 --to 1347`, then concat them and mux `out/mix.m4a`.

## Slots

| asset | used in | framing |
|---|---|---|
| `mo` + poses `mo_sad`, `mo_gulp`, `mo_chomp`, `mo_read`, `mo_point`, `mo_cheer`, `mo_wave`, `mo_card`, `mo_run` | everywhere | full-body mascot, transparent, no ground or shadow |
| `notebook` | title slam, end gag | closed notebook straight on, blank label (the label is typeset) |
| `paper`, `chat`, `shot`, `card` | ingest, graph, answer | single prop, transparent; `chat` has three dots that get painted out for the question |
| `monitor`, `gauge`, `burst`, `smoke`, `star`, `sun` | grid, gauge, transitions, stars | single prop, transparent, no text |
| `icons/<slug>.png` | agent grid, browser toolbar and popup | the real logo, any size |

## Notes

- Draw connector lines before the sprites and cards so they always pass behind them. Popups open over a sidebar, never over body text.
- Pillow's `ImageDraw` on an RGBA layer replaces pixels instead of blending them. Translucent lines or fading text on an opaque card punch holes in it, so use `mixc()` (colour toward the card fill) instead of alpha.
- gpt-image cut-outs carry a soft halo; `clean_alpha` thresholds it. Boil variants are cached in `out/boil/` and cleared by `assets`.
- Timings are on a 120 BPM grid (`B(k)` = beat k after the burst at 4.2 s). The browser and answer beats are inserted at `B(32)`, and everything after them plays `SH` s later. `audio.py` uses the same map, so if you retime a scene, move its cues in both files.
- Roughly 1350 frames take about 5 min on 2 idle cores, and longer when the machine is loaded.
