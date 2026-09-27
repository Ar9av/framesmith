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

1. `python3 tools/new_skill.py <kebab-name> "<description>"`
2. Build scenes and write `references/storyboard.md`. Add an example brief plus assets under `examples/<brand>/`.
3. Write the `description` as the trigger: what it makes, when to use it, and phrases users say. Keep it ≤ 1024 chars.
4. Add a GIF at `docs/media/<name>.gif` (270 px wide, 12 fps, ≤ 5 MB) and a contact sheet in the example folder.
5. Add a row to the router table in `skills/framesmith/SKILL.md`, then run `python3 tools/catalog.py` (README) and `python3 tools/validate.py`.
6. Bump `version` in `.claude-plugin/plugin.json` and note the change in `CHANGELOG.md`.

## Style

Match the existing code: small pure functions, one function per scene, and comments only where intent isn't obvious. Motion follows `references/engine.md`: ease-out for entrances, ease-in-out for moves, linear only for constant motion, 30–80 ms staggers, and hard cuts on a beat grid.
