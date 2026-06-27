# remote-plugin

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

### brainstorming

Explores user intent, requirements, and design **before** implementation — for features,
components, or behavior changes. Includes an optional visual brainstorming companion (a local
server under `scripts/`).

- **Source:** [obra/superpowers](https://github.com/obra/superpowers) — MIT, © 2025 Jesse Vincent
- **Provenance:** [`skills/brainstorming/SOURCE.md`](./skills/brainstorming/SOURCE.md)

### deep-research

Multi-source research with citation tracking, evidence persistence, and structured report
generation (Markdown/HTML). Triggers on "deep research", "comprehensive analysis", "research
report", or "compare X vs Y". Ships Python helper scripts (see `skills/deep-research/requirements.txt`).

- **Source:** [199-biotechnologies/claude-deep-research-skill](https://github.com/199-biotechnologies/claude-deep-research-skill) — MIT
- **Provenance:** [`skills/deep-research/SOURCE.md`](./skills/deep-research/SOURCE.md)

## Usage

```
/zivi-development-marketplace:humanizer

[paste the text you want to humanize]
```

Or just ask: "humanize this text: …". To match your own voice, paste 2–3 paragraphs of your own
writing as a sample before the text you want rewritten.

## Structure

```
remote-plugin/
├── .claude-plugin/
│   └── plugin.json
├── plugin.json
├── skills/
│   ├── humanizer/        # vendored skill (SKILL.md + SOURCE.md + LICENSE)
│   ├── brainstorming/    # vendored skill (+ scripts/ visual companion)
│   └── deep-research/    # vendored skill (+ scripts/ Python, schemas/, templates/)
└── README.md
```

## License & attribution

Each skill retains its upstream license; all three vendored here are **MIT**:

- `humanizer` — © 2025 Siqi Chen ([blader/humanizer](https://github.com/blader/humanizer))
- `brainstorming` — © 2025 Jesse Vincent ([obra/superpowers](https://github.com/obra/superpowers))
- `deep-research` — MIT per upstream README ([199-biotechnologies/claude-deep-research-skill](https://github.com/199-biotechnologies/claude-deep-research-skill))

Each skill's original `LICENSE` (where the upstream provides one) and full provenance — author,
upstream commit, and copy date — are recorded in its `SOURCE.md`.
