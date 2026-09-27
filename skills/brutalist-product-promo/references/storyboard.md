# Storyboard: brutalist-product-promo

This is a 22.64 s cut in 21 scenes. All cuts are hard unless marked ▦, a pixel-mosaic wipe where the outgoing scene keeps running underneath. Local times (lt) are seconds from the start of the scene.

| # | Scene | Start | Dur | What happens | Brief keys |
|---|---|---|---|---|---|
| 1 | `intro` | 0.00 | 0.45 | Black. Empty `[   ]` bracket appears at 0.2 s. | — |
| 2 | `tagline_bar` | 0.45 | 0.27 | Accent screen split by a black bar; tagline text-scrambles in. | `tagline` |
| 3 | `word_field` | 0.72 | 1.00 | Horizontal noise streaks rendered as repeating brand text. Paper background for 0.23 s, then ink. The caption decays to its keyword. | `field_word`, `tagline_keyword` |
| 4 | `model_black` | 1.72 | 1.00 | Sprite loops at the top; blueprint top view draws on with counting dims; big `[MODEL]`. | `model`, `dim_label`, sprite |
| 5 | `accent_zoom` | 2.72 | 0.25 | Blueprint punches in on the accent. | — |
| 6 | `spec_sheet` | 2.97 | 1.78 | Paper grid page, title scramble, and four blueprint cuts: pull-out → front elevation → top view → half-ring zoom. | `company`, `origin`, `sheet_title` |
| 7 | `environment` | 4.75 | 1.25 | Inverted B/W environment in drifting vertical strips; terminal readout types in. | `terminal`, environment |
| 8 | `env_ascii` ▦ | 6.00 | 1.45 | 0.85 s mosaic into the ASCII version of the environment, which scrolls. | environment |
| 9 | `hero` | 7.45 | 1.00 | Hero render with a slow push. Targeting box snaps onto `meta.hero_target`; product name; terminal noise fills in below. | `product_name`, hero |
| 10 | `arrow` | 8.45 | 0.27 | Giant ↘ shrinks into the header position of the next scene. | — |
| 11 | `overview` | 8.72 | 1.73 | Rotated editorial page: title, words, spec list and fine print stagger in 60 ms apart; line art wipes down. | `overview_*` |
| 12 | `closeup` | 10.45 | 1.80 | Paper flash with a grey wordmark (0.17 s), then the close-up over glitch rows of word fragments. | `glitch_words`, closeup |
| 13 | `specs` ▦ | 12.25 | 2.20 | 0.3 s mosaic into accent grid + sprite; rotated "Specs" with typed blocks; barcode. | `specs_title`, `spec_blocks`, `spec_side_labels` |
| 14 | `lineart` ▦ | 14.45 | 2.00 | 0.55 s fine mosaic into white line art; tint cells with crosshairs switch on. | lineart |
| 15 | `checker` | 16.45 | 1.00 | Flickering checkerboard; cutout with flashing accent bands; boxed labels type in. | `labels`, cutout |
| 16 | `connecting` | 17.45 | 0.27 | `[CONNECTING]` next to an outlined cell column. | `connecting` |
| 17 | `connected` | 17.72 | 1.00 | Thresholded close-up drifts; `[ CONNECTED ]` in accent with jitter; paper blocks wipe in. | `connected` |
| 18 | `smear` | 18.72 | 0.25 | The last frame smeared horizontally in the tint colour. | — |
| 19 | `cross` | 18.97 | 0.25 | Accent cross carrying a front elevation, the wordmark and the footer. | `footer` |
| 20 | `logo` | 19.22 | 2.23 | Wordmark on ink; footer types in. | `brand`, `footer` |
| 21 | `outro` | 21.45 | 1.19 | Ghost outline → barcode interrupt → letters spread and drop out. | `brand` |

## Motion rules used

- Entrances use ease-out `cubic-bezier(0.23, 1, 0.32, 1)`. Zooms and moves use ease-in-out `(0.77, 0, 0.175, 1)`. Linear is used only for scrolls and counters.
- Staggers are 60 ms. Text reveals are scramble decodes (a 4–5 glyph tail) or typewriter.
- Randomness is hashed from (seed, cell, frame // 2), so the flicker runs at 12.5 Hz and every render is identical.
- There's no easing on cuts: rhythm comes from hard cuts on a ~0.25 s grid.
