# Storyboard: devtool-launch-video

| # | Scene | Start | Dur | What happens | Brief keys |
|---|---|---|---|---|---|
| 1 | `hook` | 0.0 | 2.4 | Black; two mono lines type in at 64 px; band glitch on the way out. | `hook` |
| 2 | `names` | 2.4 | 1.2 | Integration names flash every 0.1 s, alternating ink and paper backgrounds, jittered; ends on `names_end` in the danger colour. | `names`, `names_end` |
| 3 | `rogue` | 3.6 | 4.8 | Threat photo at 42% brightness behind a terminal. Lines accelerate (gap 0.62 → 0.30 s) and captions stack on the right. For the last 2.4 s, a red vignette, screen shake and RGB-split glitch build up. | `rogue_*`, threat |
| 4 | `freeze` | 8.4 | 0.6 | The last rogue frame freezes and desaturates; the logo-diagonal blade (holo upper-right, ink lower-left) closes in. | holo |
| 5 | `reveal` | 9.0 | 1.0 | White flash (2 frames), then the hero image with a push-in; `meet` types in. | `meet`, reveal |
| 6 | `title` | 10.0 | 1.4 | Full split: the brand name at 230 px scrambles in on the ink side, with a sub-line. | `brand`, `product_sub` |
| 7 | `intercept` | 11.4 | 7.0 | The same actions replay. For each: the command types, a holo scan line sweeps it, a verdict chip slides in, and blocked lines get struck through. Counters sit top right. | `intercept*`, `verdicts` |
| 8 | `features` | 18.4 | 4.4 | 8 beats of 0.55 s, alternating ink and holo. Word at 176 px (scramble), mono sub-line typed. | `features` |
| 9 | `dashboard` | 22.8 | 4.0 | Light UI builds: cards count up, stacked bars grow (50 ms stagger), distribution bars, table rows slide in, then the caption pill rises. 3.5% push-in. | `dashboard*` |
| 10 | `install` | 26.8 | 3.5 | Terminal: commands type, output prints, agent chips stagger, caption. | `install*` |
| 11 | `end` | 30.3 | 3.5 | Holo glow, logo diagonal wipe-in, tagline scramble, holo CTA pill, links and licence typed. | `tagline`, `cta`, `links`, `license` |

Motion: ease-out entrances, ease-in-out moves and zooms, linear typing. Randomness is hashed from the frame index, so renders are identical every time.
