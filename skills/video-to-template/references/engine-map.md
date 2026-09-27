# Visual grammar → framesmith primitives

Map what you see in the reference to what already exists before writing anything new.

| You see | Use | Where |
|---|---|---|
| Hard cuts on a beat | `Scene` durations on a 0.25 s grid | timeline |
| Pixel/block dissolve | `Mosaic(dur, cols, rows, seed, flashes)` | timeline |
| Text decoding / scrambling in | `scramble(s, p, seed, fi)` + `text(max_w, fit_to)` | typography |
| Text rising out of a mask | `ui.rise(img, xy, s, font, fill, p)` | ui |
| Typewriter | `typed(s, p)` | typography |
| Highlighter / inverse-video block | `ui.marker(draw, box, col, p)` | ui |
| Terminal / CLI output | `ui.terminal(..., max_width=)` with per-span fonts and `mark` | ui |
| Window chrome (macOS) | `ui.window` | ui |
| XP window, CRT TV, retro computer | `draw_window`, `draw_tv(device=…)` | narrated-collage-explainer |
| Stacked cards | `card()` + the `cards` beat | narrated-collage-explainer |
| Starburst / sticker shapes | `starburst()` | narrated-collage-explainer |
| Big single keyword | `big_word` / `s_word` | collage / scaffold |
| ASCII / text-mask fields | `fx.ascii_render`, `fx.word_field`, `fx.noise_tex` | fx |
| Glitch rows, smears, RGB split | `fx.glitch_rows`, `fx.smear`, band rolls | fx |
| Blueprints with counting dimensions | `blueprint.top_view` / `front_view` | blueprint |
| Brand wordmark for any name | `wordmark_mask`, `fit_unit`, `spread` | wordmark |
| Holographic / iridescent light | `ui.holo_field` + a foil texture, `ui.fill_text` | ui |
| Brand logos in a row | `media.fetch_icons` + `media.icon` (brand-icons skill) | media |
| Looping object motion | gpt-image-2 sprite sheet + `media.sprite_masks` + `pingpong` | media |
| Narration-timed beats and subtitles | `narration.tts`, `transcribe_words`, `align`, `find`, `chunks` | narration |
| Product photo / hero with a tracked callout | `media.cover` + `media.cover_point` | media |
| Dashboard / stats UI | `ui.stat_card`, bars drawn directly | ui / devtool-launch-video |

If nothing fits, add the scene type to the template first. Promote it to `core/` only once a second template needs it.
