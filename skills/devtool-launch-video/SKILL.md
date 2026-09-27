---
name: devtool-launch-video
description: Render a 34-second 16:9 launch film for a developer tool, CLI, AI agent product or security product. It follows a problem → reveal → proof → features → dashboard → install → end-card arc. A terminal goes rogue with danger-red glitches, freezes, and the brand's real logo is revealed in its brand light. The same commands then replay and get caught, each annotated with a typeset verdict and a leader line, followed by kinetic feature beats, an animated product dashboard, a real install sequence and a CTA card. Use when the user asks for a launch video, product demo teaser, "what is X" explainer for first-time viewers, Product Hunt / X / LinkedIn / YouTube launch clip, or an AI-security / devtool / open-source launch video. Brief-driven, deterministic Python + ffmpeg.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: launch-video, product-demo, devtools, cli, ai-security, kinetic-typography, terminal, gpt-image-2
---

# Dev-tool launch video

This template produces 33.8 s at 30 fps, 1920×1080, in 11 scenes. It is built for viewers who have never heard of the product: it shows the pain first, then the product catching exactly that pain, then how to get it. The whole film is driven by a JSON brief. Example: `examples/prismor/brief.json` (Prismor, an AI-agent runtime security tool). Storyboard: `references/storyboard.md`.

## Workflow

1. **Understand the product.** Read its README or site. Pull out:
   - the 4–9 concrete dangerous or painful actions it prevents (as real-looking terminal lines)
   - the verdicts it produces
   - 8 features, each one word or phrase plus a line of detail
   - the install commands
   - the tagline, the brand colours and the logo motif

   Use the product's real vocabulary: its rule names, CLI verbs, version.
2. **Script.** Write the problem lines (`rogue_lines`) so they escalate, and make the last one the scariest. Make `intercept` replay the same actions with a verdict each, ending on one ALLOWED so it doesn't read as "blocks everything".
3. **Brief.** Copy the example brief and replace `copy`, `theme`, `verdicts`, `holo` (brand light palette) and the `assets` prompts. Validate with `python3 scripts/launch.py check --brief brief.json`.
4. **Images.** Put the brand's **real logo** at `assets/logo.png` (square PNG with alpha); never generate or reinterpret it. Then `python3 scripts/launch.py assets --brief brief.json` generates `threat` (medium) and `holo` (low) with gpt-image-2.
5. **Check and review.** `check` samples the whole cut and fails on any text overflow. It also warns when copy had to shrink below 80%; shorten that copy. Then look at `still --brief … 3 7.5 10.5 14 20 25 29 33` or `sheet`.
6. **Render:** `render --brief … [--audio track.mp3]`. It takes about 4 min on 2 cores. Cuts land on a 0.55 s beat in the features scene, so a ~110 BPM track fits.

## Image slots

| Slot | Scene | Framing |
|---|---|---|
| `threat` | rogue terminal background (shown at 42% brightness) | dark, ominous, one red light source; the subject on the right third (the terminal covers the left) |
| `logo` | reveal, end card, dashboard | the brand's real mark, supplied by the user or the brand site; square PNG with alpha |
| `holo` | brand light: split reveal, feature beats, CTA text fill, logo glow | full-frame abstract texture in the brand palette, no objects |

## Brief keys (copy)

- `hook` [2]: typed cold-open lines.
- `names` [n] + `names_end`: machine-gun list (integrations, platforms).
- `rogue_title`, `rogue_lines` [{text, kind}]. kind ∈ `agent` | `inject` (red highlight) | `cmd` (`$ …`) | `leak` | `dim` | `ok`.
- `rogue_captions` [[line1, line2] × 3]: line 2 is shown in the danger colour.
- `meet`, `brand`, `product_sub`.
- `intercept_title`, `intercept_caption`, `intercept` [{cmd, verdict, rule, out?}]. `out` is an extra output line coloured by its verdict. Verdict colours come from top-level `verdicts`.
- `features` [8 × {word, sub}]: word ≤ 16 chars.
- `dashboard` {app, title, nav[6], cards[4 × [label, value]], chart_title, dist_title, table_title, rows[4 × [call, agent, rule, verdict]]} and `dashboard_caption`.
- `install_title`, `install` [{text, kind}], `install_agents` [names, typed as one line], `install_caption`.
- `tagline`, `cta`, `links`, `license`.

Timing: `"scenes": {"names": 0}` drops a scene; `"speed": 1.2` shortens everything.

## Design rules

- Never use pills, chips or badges. Verdicts, statuses and CTAs are typeset text (colour, weight, leader lines, rules).
- Every string has a width budget. Long terminal lines word-wrap inside their window, and `check` must pass before rendering.
- Use the brand's real logo only, and no literal visual puns on the brand name.

## Guardrails

- Only use a brand the user owns or has asked for. Keep claims factual: every feature and number shown should come from the product's own docs.
- Fake secrets in terminal lines must be obviously fake. Never paste a real key into a brief.
- Change motion in `scripts/launch.py`, never in `scripts/framesmith/`, which is vendored from the repo's `core/`.
