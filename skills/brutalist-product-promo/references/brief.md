# Brief reference

The brief is a single JSON file. Relative paths resolve from the brief's folder. Renders go to `<brief dir>/out/` and generated images to `<brief dir>/assets/`, or to `assets_dir` if set.

## Top level

| Key | Default | Notes |
|---|---|---|
| `size` | `[720, 1280]` | Designed for 9:16 at 720×1280. |
| `fps` | `25` | |
| `speed` | `1.0` | >1 makes the cut shorter and faster. |
| `theme` | ARC orange | `accent`, `ink`, `paper`, `tint` (hex). If `tint` is omitted, it's derived as accent mixed toward ink. |
| `assets_dir` | `"assets"` | Where slot images live. |
| `meta.hero_target` | `[0.8, 0.3]` | Point on the hero image (fractions) for the targeting box. |
| `scenes` | `{}` | `{scene_name: seconds}`; `0` drops a scene. Names are in the storyboard. |
| `assets` | — | Slot → `{prompt, size, quality, background?, grid?}`. Prompts can use `{brand}`, `{company}`, `{model}`, etc. |

## Copy

Keep every string short. Most copy sits in mono at 9–15 px or display at 52–104 px.

| Key | Type | Where it shows / guidance |
|---|---|---|
| `brand` | str | Wordmark. A–Z, 0–9, `-`, `.`, space; ≤ 8 chars looks best. |
| `company` | str | Spec-sheet header, left. |
| `origin` | str | Spec-sheet header, right (e.g. "Made in Berlin"). |
| `tagline` | str | UPPERCASE, ≤ 34 chars. Shown bracketed. |
| `tagline_keyword` | str | A word inside `tagline` that survives the decay. Optional. |
| `field_word` | str | Repeating text in the noise field, e.g. brand + category. |
| `model` | str | Short model code shown as `[S1]`. |
| `dim_label` | str | Blueprint dimension label prefix, e.g. "BASE DIA", "ROTOR SPAN". |
| `sheet_title` | str | ≤ 14 chars at 88 px. |
| `terminal` | [3 str] | Mono readout lines under the environment scene. |
| `product_name` | str | ≤ 22 chars at 52 px. |
| `overview_header` | str | Accent header bar. |
| `overview_title` | [2 str] | Two display lines, ≤ 20 chars each. |
| `overview_words` | [2 str] | Two single words. |
| `overview_specs` | [6 str] | Tiny mono spec list. |
| `overview_fineprint` | str | ≥ 26 chars; repeated as texture. |
| `overview_side` | [[2 str], [2 str]] | Two 2-line captions beside the line art. |
| `glitch_words` | [str] | Optional fragments for the glitch rows. Scrambled and reversed brand words look right. |
| `specs_title` | str | Display word on the specs page. |
| `spec_blocks` | [{head, lines[]}] | 3 blocks of 3–4 lines, each ≤ 34 chars. |
| `spec_side_labels` | [3 str] | Rotated micro-labels around the sprite. |
| `labels` | [2 str] | Boxed labels typed in the checkerboard scene. |
| `connecting` / `connected` | str | Status lines for scenes 16–17. |
| `footer` | [3 str] | Tiny centred footer on the logo scenes. |
