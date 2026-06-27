# remote-skills

Third-party skills vendored from external open-source repositories into this marketplace.

Each skill under `skills/` is a **copy** of an upstream skill, with a `SOURCE.md` next to it
documenting where it came from (repository, author, license, commit, and copy date). These are
snapshots — they do **not** auto-update from upstream. See each skill's `SOURCE.md` for how to
refresh it.

## Skills

### humanizer

Removes signs of AI-generated writing from text to make it read as natural, human-written prose —
inflated symbolism, promotional language, em-dash overuse, the "rule of three", AI vocabulary,
vague attributions, negative parallelisms, and filler phrases. Based on Wikipedia's "Signs of AI
writing" guide.

- **Source:** [blader/humanizer](https://github.com/blader/humanizer) — MIT, © 2025 Siqi Chen
- **Provenance:** [`skills/humanizer/SOURCE.md`](./skills/humanizer/SOURCE.md)

## Usage

```
/zivi-development-marketplace:humanizer

[paste the text you want to humanize]
```

Or just ask: "humanize this text: …". To match your own voice, paste 2–3 paragraphs of your own
writing as a sample before the text you want rewritten.

## Structure

```
remote-skills/
├── .claude-plugin/
│   └── plugin.json
├── plugin.json
├── skills/
│   └── humanizer/
│       ├── SKILL.md      # vendored verbatim from upstream
│       ├── SOURCE.md     # provenance + how to update
│       └── LICENSE       # upstream MIT license
└── README.md
```

## License & attribution

Skills here retain their upstream licenses. The `humanizer` skill is MIT-licensed
(Copyright © 2025 Siqi Chen); its original `LICENSE` is preserved at
`skills/humanizer/LICENSE`. Full attribution and the exact upstream commit are recorded in
`skills/humanizer/SOURCE.md`.
