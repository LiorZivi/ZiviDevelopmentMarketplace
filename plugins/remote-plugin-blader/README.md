# remote-plugin-blader

A vendored copy of the **humanizer** skill from [blader/humanizer](https://github.com/blader/humanizer).

This is a standalone plugin that packages a single third-party skill for this marketplace. The skill under `skills/` is a **snapshot copy** of the upstream — it does **not** auto-update. See [`skills/humanizer/SOURCE.md`](./skills/humanizer/SOURCE.md) for provenance (repository, author, license, commit, copy date) and how to refresh it.

## Skill

### humanizer

Removes signs of AI-generated writing from text to make it read as natural, human-written prose — inflated symbolism, promotional language, em-dash overuse, the "rule of three", AI vocabulary, vague attributions, negative parallelisms, and filler phrases. Based on Wikipedia's "Signs of AI writing" guide.

- **Source:** [blader/humanizer](https://github.com/blader/humanizer) — MIT, © 2025 Siqi Chen
- **Provenance:** [`skills/humanizer/SOURCE.md`](./skills/humanizer/SOURCE.md)

## Usage

```
/zivi-development-marketplace:humanizer

[paste the text you want to humanize]
```

## License & attribution

The `humanizer` skill is MIT-licensed (© 2025 Siqi Chen); its original `LICENSE` is preserved at `skills/humanizer/LICENSE`, and full attribution is recorded in `skills/humanizer/SOURCE.md`.
