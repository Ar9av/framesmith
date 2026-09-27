# AGENTS.md: working on framesmith

This is for agents and humans extending the repo. (`CLAUDE.md` points here.)

## Invariants

- `core/framesmith/` is the **only** place to edit engine code. After changing it, run `python3 tools/sync_core.py` to refresh every `skills/*/scripts/framesmith/` copy. CI fails on stale copies.
- Skills are **self-contained**: a skill folder must work after being copied alone, with no imports from outside the folder.
- Frames must be **pure functions of time**. Get randomness from `h(seed, …, fi // k)` or seeded `np.random.default_rng(...)`, never from global state or the wall clock.
- All user-facing copy lives in the brief, never hard-coded in scenes.
- Image slots declare their framing and background in `SKILL.md`. Generation defaults to `low`/`medium` quality.
- Templates expose the verbs `check | assets | still | sheet | render` with `--brief`.

## Adding a skill

From a reference video, follow `skills/video-to-template/SKILL.md`. Otherwise:


1. `python3 tools/new_skill.py <kebab-name> "<description>"`
2. Build scenes and write `references/storyboard.md`. Add an example brief plus assets under `examples/<brand>/`.
3. Write the `description` as the trigger: what it makes, when to use it, and phrases users say. Keep it ≤ 1024 chars.
4. Add a GIF at `docs/media/<name>.gif` (270 px wide, 12 fps, ≤ 5 MB) and a contact sheet in the example folder.
5. Add a row to the router table in `skills/framesmith/SKILL.md`, then run `python3 tools/catalog.py` (README) and `python3 tools/validate.py`.
6. Bump `version` in `.claude-plugin/plugin.json` and note the change in `CHANGELOG.md`.

## Design rules (hard requirements)

- **No overflow, ever.** Every string drawn with `text()` gets a `max_w` budget (pass `fit_to=` the final copy while it scrambles or types). Terminals get `max_width` and word-wrap. A template's `check` samples the cut and fails on overflow. It warns when copy shrinks below 80% of its designed size; the fix is shorter copy.
- **No pills, chips or badges.** They read as generic AI-UI slop. Status is typeset: a coloured word in mono caps, with a leader line or rule if it needs anchoring. Captions sit on a scrim, not inside a rounded box. (`ui.chip` was removed on purpose.)
- **No default-terminal look.** No typewriter or slab mono, and no salmon/amber/grey 'syntax theme' colouring. Use a tight palette: ink, paper, one signal colour used as solid fields (inverse video), and the brand's own light for positive states. Mono is for literal code only. Statements go in the sans; accents, the agent's voice and reasons go in `pixel` (Departure Mono).
- **No italics.** Not for emphasis, captions or taglines. Emphasis comes from inverse video, the pixel face, scale or brand light.
- **Make it move.** Text enters with `ui.rise` (masked, staggered 40–60 ms), highlights sweep with `ui.marker`, cameras drift and punch on beats. A static frame held for more than ~0.5 s needs a reason.
- **Use the brand's real logo.** Logos are a supplied asset slot, never generated or reinterpreted. Don't substitute a literal metaphor for the name (e.g. a stock prism for "Prismor").

## Style

Match the existing code: small pure functions, one function per scene, and comments only where intent isn't obvious. Motion follows `references/engine.md`: ease-out for entrances, ease-in-out for moves, linear only for constant motion, 30–80 ms staggers, and hard cuts on a beat grid.
