# framesmith engine API (v0.1)

`import framesmith as fs`. It's pure Python: numpy + Pillow, with ffmpeg for encoding. The source of truth is `core/framesmith/`, and each skill vendors a copy under `scripts/framesmith/`.

## Timeline

```python
tl = fs.Timeline([
    fs.Scene("intro", 0.45, intro),
    fs.Scene("title", 1.20, title, fs.Mosaic(0.3, cols=6, rows=10, seed=4)),
], width=720, height=1280, fps=25, data=my_state, theme=theme)

tl.still(3.2, "f.png"); tl.contact_sheet("sheet.png"); tl.render("out.mp4", audio=None)
```

- A scene function receives a `Ctx`: `lt` (local s), `dur`, `t` (global s), `fi` (frame index), `W`, `H`, `data`.
  - `ctx.p(a, b)` gives progress from a to b in local seconds; negative values count from the scene end.
  - `ctx.at(lt)` gives the same context at another local time, for freeze frames and smears.
- A transition belongs to the incoming scene. For `Mosaic`, the previous scene keeps running under the wipe.
- Renders are parallel via fork. Keep state in module globals set before `render()`, never in lambdas that are passed around.

## Easing (`fs.easing`)

`ease_out` (0.23,1,0.32,1) for entrances. `ease_in_out` (0.77,0,0.175,1) for moves and zooms. `ease_drawer` (0.32,0.72,0,1) for panels. `linear` only for constant motion. `bezier(x1,y1,x2,y2)` builds a custom curve. Helpers: `prog(t,a,b)`, `lerp`, `h(*key)` (deterministic hash → [0,1)). Use `h(seed, i, fi // 2)` for 12.5 Hz flicker.

## Typography (`fs.typography`)

Font roles (bundled): `sans` (Inter Display), `sans_medium`, `mono` (Go Mono), `mono_bold`. Get a font with `F(role, px)`.

- `text(draw, xy, s, font, fill, track=0, anchor="la", max_w=None, fit_to=None)`: tracking in px; anchors as in PIL (`mm`, `rm`…). **Always pass `max_w`.** The type shrinks to fit (down to 55%). Unfittable text is logged in `OVERFLOWS`, and heavy shrinks in `SHRINKS`; `overflow_report()` / `overflow_report(warn=True)` summarise them. Pass `fit_to=final_copy` during reveals so the size stays stable.
- `scramble(s, p, seed, fi, tail=5)`: decode reveal. `typed(s, p)`: typewriter. `decay(s, p, keep)`: random dropout.
- `rot_text(img, xy, s, font, fill, angle=-90)`: rotated labels.

## Theme (`fs.Theme`)

`Theme.from_dict({"accent": "#hex", "ink": …, "paper": …, "tint": …})`. Derived colours: `on_accent` (contrast-safe text on the accent), `accent_grid`, `paper_grid`, `mid`.

## Effects (`fs.fx`)

| Function | What it does |
|---|---|
| `ascii_render(gray, w, h, cw, ch, size, fg, bg, chars)` | Brightness-ramp ASCII art |
| `word_field(g, fi, w, h, word, fg, bg)` | Repeating-word text mask over a 0–1 field |
| `noise_tex(seed)` | Streaky multi-octave noise to scroll through |
| `random_text_block(w, h, fi, seed, …)` | Flickering terminal noise |
| `mosaic(a, b, p, cols, rows, seed, flashes)` | Block wipe A → flash → B |
| `glitch_rows(w, h, fi, seed, density, words, ink, paper)` | Rows of word-fragment blocks |
| `smear(frame, fi, color)` | Band displacement + mono tint |
| `barcode`, `crosshair`, `dashed` | Drawing primitives |

## Blueprints (`fs.blueprint`)

`top_view(img, cx, cy, scale, col, label_fg, t, draw, lw, seed, labels, label)` and `front_view(...)`: vector drawings redrawn every frame, so zooms stay crisp. `draw` sets the draw-on progress and `t` drives counting dimension labels. `dim_label` and `arrow_dim` are the annotation primitives.

## Wordmark (`fs.wordmark`)

- `wordmark_mask(word, size, unit, letters_dx=None, outline=0)` returns `(L-mask, letter_boxes)`. It uses a blocky 5×5 chamfered font covering A–Z, 0–9 and `-`, `.`, space.
- `fit_unit(word, max_w, max_unit)` sizes any brand length to fit. `spread(n, px)` gives letter offsets for spread-apart outros.

## Media (`fs.media`)

- `Assets(dir1, dir2…)` looks names up across dirs, with png/jpg/webp fallback. Put placeholders last.
- `cover(im, w, h, zoom, fx, fy)` does a cover-fit crop. `cover_point(...)` maps a source point into the crop, e.g. for overlays that track a detail.
- `sprite_masks(sheet, cols, rows)` returns line-art frames cropped to a shared bbox. `pingpong(n)` gives a seamless loop order.
- `generate_images(specs, out_dir, key=None, names=None, force=False, fmt=None)` calls gpt-image-2 in parallel, skipping existing files.

## UI (`fs.ui`)

For software and dev-tool videos:
- `window(img, box, bg, bar, title)` draws macOS-style chrome and returns the content box.
- `terminal(img, origin, lines, t, size, max_width=…)` renders a time-scheduled transcript. Each line is `{"spans": [(text, rgb)], "t": start, "type": secs, "bg": rgb?}`. Lines word-wrap at `max_width` and it scrolls with `max_lines`. It returns `{line: [(x0, y, x_end) per row]}` for overlays such as leader lines and strike-throughs.
- `stat_card(...)` and `rrect(...)` are basic panels. There is deliberately no pill/chip/badge primitive.
- `holo_field(w, h, t, palette)` produces animated iridescent interference light in any palette. Render it small and upscale for speed.
