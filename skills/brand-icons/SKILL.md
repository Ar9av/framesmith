---
name: brand-icons
description: Find, fetch, preview and credit real brand/logo SVG icons from thesvg.org (7,400+ marks, e.g. Claude, OpenAI, Cursor, GitHub Copilot, Stripe, Vercel, AWS, Figma, Docker). It picks the right variant for a light or dark background and renders crisp transparent PNGs with headless Chromium. It tracks each icon's licence (CC0, MIT, CC-BY-ND, trademark), refuses unknown licences by default, never recolours no-derivatives marks, and writes an attribution table. Use when a video, slide, landing page, README, diagram or UI needs real company or tool logos, e.g. "works with" or "integrates with" rows, tech-stack grids, partner walls, or agent/tool icons, or when the user mentions thesvg, brand icons, logos or SVG icons. Prefer this over drawing, generating or approximating a brand's mark.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: icons, logos, svg, brand, thesvg, attribution, licensing
---

# Brand icons (thesvg.org)

Real brand marks, fetched properly: the right variant for the background, a real SVG renderer, and the licence recorded next to the file. Never generate, trace or approximate a company's logo.

## Commands

```bash
python3 scripts/icons.py search copilot                    # ranked: slug · title · licence · variants
python3 scripts/icons.py info github-copilot               # full registry entry + plain-language usage note
python3 scripts/icons.py fetch claude openai cursor --out assets/icons --theme light
python3 scripts/icons.py sheet claude openai cursor --out preview.png --bg "#EEF1EC"
python3 scripts/icons.py credits assets/icons --md         # attribution table for a README / video description
```

- `fetch` writes `<slug>.svg` and a transparent 512 px `<slug>.png` (use `--png N` for other sizes), plus `icons.json` with the title, variant, source URL, licence and brand URL.
- `--theme light|dark` is the background the icon will sit on. It picks thesvg's `light`/`dark` variant when there is one, and falls back to `default`, then `mono`.
- `sheet` is the quick visual check. Look at it before using icons in a design. Single-colour marks that would vanish on the chosen background are tinted to ink or paper, except no-derivatives marks.

## Workflow

1. **Resolve slugs with `search`.** Brands often have several entries (`claude`, `claude-ai`, `claude-code`; `aws` vs `aws-amazon-q`). Pick the one that matches what the copy says: for "works with Claude Code" use `claude-code`.
2. **Check the licence column** before using an icon:
   - `CC0` / `MIT` / `Apache-2.0` / `ISC` / `BSD`: fine.
   - `CC-BY-*`: credit it. For `ND`, don't recolour, crop or alter the mark.
   - `brand-use` / `Trademark`: follow the brand's guidelines; use it only to refer to the product ("works with", "integrates with").
   - `Unknown`: skipped by default. Use `--allow-unknown` only if the user has the brand's permission.
3. **Fetch** into the project's assets, then `sheet` to review on the real background colour.
4. **Credit:** add the `credits --md` output wherever attribution belongs, such as the README, the video description, or a slide footer.

## Using the files

- In framesmith templates, `framesmith.media.icon(svg_path, size, tint=None)` loads the cached PNG, trimmed and squared, and `is_light_mark(im)` tells you whether a white mark needs tinting. The `narrated-collage-explainer` `icons` beat uses these directly.
- Anywhere else, use the SVG for web and vector work, and the PNG for raster pipelines.

## Rules

- Real marks only. Don't redraw, "stylise" or AI-generate a brand's logo, and don't combine brand marks into new logos.
- Keep proportions, and don't add effects to a mark. Place icons on plain grounds, never inside pills or badges.
- One brand, one mark: don't mix a company's icon and wordmark in the same row.

## Requirements

Python 3.9+, Pillow, numpy. For rendering, headless Chromium or Chrome is recommended (it handles gradients, clip paths and compact path syntax). Without it, the script falls back to cairosvg if installed, then ImageMagick, which fails on some icons. Snap-packaged Chromium can't see `/tmp` or hidden folders, so rendering is staged under `~/framesmith-svg-stage` automatically.
