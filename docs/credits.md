# Credits and further reading

framesmith's templates apply rules distilled from these public agent skills. No text from them is copied here; follow the links for the originals.

| Skill | Author | Used for |
|---|---|---|
| [animate](https://github.com/emilkowalski/skills/tree/main/skills/animate) | Emil Kowalski | Easing tokens, durations, stagger ranges, "never ease-in on entrances" |
| [animation-vocabulary](https://github.com/emilkowalski/skills/tree/main/skills/animation-vocabulary) | Emil Kowalski | Naming motion precisely in storyboards |
| [better-typography](https://github.com/jakubkrehel/skills/tree/main/skills/better-typography) | Jakub Krehel | Display/mono pairing, tracking |
| [better-colors](https://github.com/jakubkrehel/skills/tree/main/skills/better-colors) | Jakub Krehel | Few-colour systems, contrast |
| [prompt-images](https://github.com/replicate/skills/tree/main/skills/prompt-images) | Replicate | Natural-language, material/lighting/lens-specific image prompts |
| [hyperframes](https://github.com/heygen-com/hyperframes/tree/main/skills/hyperframes) | HeyGen | Seekable, frame-deterministic video composition |
| [canvas-design](https://github.com/anthropics/skills/tree/main/skills/canvas-design) | Anthropic | Grid discipline and negative space |

Catalogue: [AI UX Playground: visual design skills](https://aiuxplayground.com/skills/category/visual-design/).

## Opus 5.5 motion-design references (v0.20.0)

The four print-and-grid templates follow styles from public collections of motion design made with Claude Opus 5.5 writing animation code. We used them as written references only; no code was copied.

- [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15): the Bauhaus / geometric study (`prompts/09-bauhaus.md`) for `bauhaus-grid-poster`, and its "how to work" rules (hook in 0.5 s, hero at 60–75 %, a held end frame with micro-motion).
- [motionvideohq/awesome-opus-5-5-motion-design](https://github.com/motionvideohq/awesome-opus-5-5-motion-design): the risograph street-poster prompt (techhalla) for `riso-poster-promo`, the drafting-table three-ink prompt (heyiamnick) for `drafting-table-film`, and the one-dot / halftone films (ultimaxbt) for `halftone-dot-film`.
- [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) and [zhuyansen/awesome-opus-5.5-video](https://github.com/zhuyansen/awesome-opus-5.5-video): broader surveys we used to choose styles.
- [makevoid/motion-graphics-music-video-skill](https://github.com/makevoid/motion-graphics-music-video-skill): the riso grain recipe (`1 - amount·r²·2` per 2 px cell).
- [howseen-ai/claude-motion-design](https://github.com/howseen-ai/claude-motion-design) (MIT): craft rules on object-carried transitions and flood circles that clear the farthest corner.

Bundled font added in this release: Anton (OFL-1.1, The Anton Project Authors), plus the Inter Display Bold and Black weights (OFL-1.1).

## More Opus 5.5 references (v0.21.0)

- `type-architecture-film`: the "BUILD THE FLOOR" brief by [Gdgtify](https://x.com/Gdgtify/status/2103458245213929495), via [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos).
- `one-line-film`, `morph-chain-film`, `pixel-quest-intro`: the line-art, morph and pixel-art studies in [Vincentwei1021/mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15).
- The 16-colour palette in `pixel-quest-intro` is PICO-8's (Lexaloffle). Bundled font added: Instrument Serif (OFL-1.1, The Instrument Serif Project Authors).
