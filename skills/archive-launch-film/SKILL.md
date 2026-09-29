---
name: archive-launch-film
description: Render a narrated archive-to-product launch film (about 60–90 s, 16:9). A dark documentary cold open plays single words synced to the voice over a falling dotted chart, archival engravings made with gpt-image-2, cutaway line drawings whose interiors flood yellow to red, and a document where everything greys out except one line that a highlighter sweeps. Black then dawns into a drifting pastel ground for a chrome-object brand reveal and light product UI driven by a cursor (live activity, cloaked secrets, approvals, a signed policy, audit records). Enterprise beats add a fleet wall that pulls back from one device to hundreds, a holographic "Enterprise" reveal on black, a terminal enroll with a device table, console panels, and an end card with the open source repo. Use when the user wants a launch film that opens on history or a documentary hook, "start with Titanic/Troy style failures then reveal the product", or a security or infrastructure product story told from past failures to the fix.
license: MIT
metadata:
  framework: framesmith
  version: 0.1.0
  tags: launch-video, documentary, engraving, gpt-image-2, voiceover, product-ui, enterprise
---

# Archive-to-product launch film

Act one borrows the grammar of a documentary: history's failures, told in engravings and cutaways, with one or two words on screen at a time. Act two turns the lights on: a chrome reveal, then the product doing the job on a pastel ground. There are two examples:
- `examples/prismor/` is a 65 s Prismor launch.
- `examples/prismor-enterprise/` is an 84 s Prismor Enterprise cut. It adds the fleet wall, the holographic reveal, enroll, shadow AI and the Enterprise end card, and shares the first example's assets.

## Workflow

1. **Start:** run `python3 scripts/main.py init my-film` or `init my-film prismor-enterprise`.
2. **Script** (`vo.txt`): the arc is:
   - a failure hook
   - two true historical failures (one image, then its cutaway)
   - the present-day parallel
   - the specific risk (a document with the dangerous line)
   - "most find out afterwards"
   - the product
   - three or four proofs
   - positioning and CTA

   Use only facts you can source for the history. Run the script through `no-ai-slop`.
3. **Assets** (`assets.json`): engravings and cutaways generated with gpt-image-2. Cutaways need clean line art on white, because the flood fill finds enclosed regions. Chrome objects are generated on transparent backgrounds. Run `python3 scripts/main.py assets`.
4. **Voice:** `python3 scripts/main.py voice` (latest TTS snapshot, default `marin`, windowed Whisper timings). `holds` in the brief add silence after a phrase. To trim a spoken list without re-recording, cut the words from `vo.wav` and `words.json`, then fix `vo.txt` to match.
5. **Check** → **still** → **render**. Set `FRAMESMITH_PRESET=veryfast` for a faster encode on slow machines.

## Beats

| type | what it does |
|---|---|
| `grid` | falling dotted chart on a black grid; the camera pulls back as the axis box draws |
| `photo` | archival still with push, weave, grain and vignette; optional `icons` that pop on cues plus a `more` row on a cue |
| `cutaway` | line drawing whose enclosed interior floods (`rise`, or `sweep: right_to_left` up to a `cap` line) |
| `doc` | a page where every paragraph but the `target` greys out, then a highlighter sweeps the `hl` phrase |
| `words` | words on black, dawning into the pastel ground from the bottom (`grad_at`) |
| `brand` | chrome objects fly in, the logo pops, the name types with a caret |
| `session` | agent tiles make room for a live activity panel; a tool-call card shows a secret as a Cloak placeholder |
| `approve` | a held action; the cursor clicks Approve and the status flips |
| `flow` | source cards connect by curved lines into a central policy card that fills and signs |
| `records` | an audit record highlights line by line, then "See history" stacks older records |
| `fleetwall` | one device tile, the camera pulls back, hundreds light up in a wave, and a count appears |
| `reveal` | black stage, chrome orbit, logo + name + a holographic "Enterprise" wipe, and a subline |
| `enroll` | a terminal types the enroll command; devices stream into a console table |
| `panel` | any `framesmith.console` component (shadow, proof, egress, mcp, kpis…) rising in |
| `ent_end` / `tagline` | end cards: lockup, lines, GitHub repo on its cue, CTA, fade to black |

## Notes

- The pastel ground is rebuilt from prismor.dev's hero (peach, rose, sky and lavender blobs drifting on warm white). Change `BLOBS` in `main.py` for another brand.
- On-screen text never ends with a period (captions strip trailing punctuation), and there are no pills (the device count sits on a soft wash).
- Sample text that looks like exfiltration (curl uploads of `.env`) can trip agent security hooks such as Prismor's. Keep demo commands harmless-looking.
