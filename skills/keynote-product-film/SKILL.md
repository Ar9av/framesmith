---
name: keynote-product-film
description: Render a 16:9 keynote-style product film (about 60–90 s, music-driven, no voiceover) in the clean Apple-event look. Charcoal and white grounds alternate. Centred sentences blur in word by word, with inline line icons (Lucide), app-icon tiles and staircase layouts. Real product UI does the proving: a prompt bar being typed, an agent session panel (Claude Code style), permission prompts, a step list with brand icons, a benchmark bar chart, a rolling "X can …" ticker, a masked-secret field, an agent icon row, and a logo reveal on the brand's gradient wash. Use when the user wants a product launch film, keynote or reveal video, "introducing X" video, feature tour set to music, or a video like Apple, Arc or Aside launch films, especially for developer tools, AI agents and security products. Brief-driven, deterministic Python + ffmpeg.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: keynote, product-film, launch, kinetic-typography, product-ui, icons, 16x9
  reference: "https://files.catbox.moe/ymuy5g.mp4 (analysed with video-to-template)"
---

# Keynote product film

The film is a sequence of `shots` in `brief.json`, each with a `type` and a `dur`. Text carries the story, so write it like a keynote: short lines, one idea per shot, the product UI as proof. The example is `examples/prismor/`, 74.6 s in 21 shots. Its copy and UI come from Prismor's real site components and benchmark. Storyboard: `references/storyboard.md`.

## Workflow

1. **Story:** problem (3–4 shots) → reveal ("Introducing" and the logo on the wash) → what it is (a staircase sentence) → proof in real UI (prompt → session → steps) → evidence (chart) → capabilities (ticker) → a trust detail (mask) → integrations (icon row) → name, tagline, URL.
2. **Brief:** copy `examples/prismor/brief.json` and replace the shots. Keep every claim sourced: session lines, benchmark numbers and feature names come from the product's own repo or site.
3. **Icons:** `python3 scripts/main.py icons --brief brief.json` fetches every `{icon:name}` / `lucide:` line icon (Lucide, ISC) and every brand mark used in `{tiles:…}`, `brand:` and `icons` (thesvg.org, with licence metadata). Put the real logo at `assets/logo.png`.
4. **Check:** `check` fails on text overflow and warns when a sentence had to shrink below 80%. Review with `still … t1 t2 …` or `sheet`.
5. **Render:** `render --brief … [--audio music.m4a]`. It's music-driven: keep shot lengths on the track's beat grid (0.5 s at 120 BPM).

## Shot types

| type | shows | keys |
|---|---|---|
| `sentence` | centred lines, words blurring in | `lines` (tokens: words, `_muted`, `{icon:lucide-name}`, `{tiles:slug,slug}`), `bg` dark/light/wash, `size`, `layout: stairs` + `align`, `bar: [w, h]` (dark input bar around line 1), `logo` |
| `prompt` | a prompt bar being typed, with an I-beam | `typed`, `placeholder`, `bg`, `logo_above`, `type_at`, `type_s` |
| `session` | Claude Code-style session panel with timed lines | `lines: [{t, type: user/agent/command/reason/warden/blocked/success, text}]`, `caption`, `cwd`, `zoom: [z, fx, fy]`, `scale` |
| `permission` | the agent's permission prompt, optionally cascading, with a cursor | `caption`, `command`, `desc`, `copies`, `every`, `select`, `select_at` |
| `steps` | a step list with brand or line icons and connectors | `caption`, `rows: [{t, icon: brand:slug / lucide:name, text, sub, tone: blocked/success}]` |
| `chart` | a benchmark bar chart that morphs between phases | `sub`, `rows: [{label, note, highlight}]`, `phases: [{title, values}]` |
| `ticker` | a fixed prefix with a rolling list | `prefix`, `items: [{icon, text}]`, `every` |
| `mask` | an input whose secret becomes a placeholder on click | `caption`, `value`, `masked`, `click_at`, `footnote` |
| `icons_row` | caption plus a row of integration marks | `caption`, `icons: ["logo", slugs…]` |
| `black` | black frame | — |

Transitions: `"tr": "dissolve"` (crossfade with a blur peak) or `"pixel"`; the default is a hard cut.

## Design rules

- No pills, chips or badges. The reference's rounded chat chips and pill buttons were translated into plain lines and the agent's real text-based permission prompt.
- No italics. Inter Display for all copy, Geist Mono only for literal commands and keys (ligatures off).
- Nothing overflows. Sentences shrink as a block, panels word-wrap and scroll, and `check` must pass.
- Real logos and marks only (brand-icons / thesvg). Show only UI data the product can actually produce.
