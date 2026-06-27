# Source & Attribution — `humanizer` skill

This skill is a **vendored copy** of a third-party, open-source skill. The files in this
folder (`SKILL.md`, `LICENSE`) were copied **verbatim** from the upstream repository. This
is a snapshot — it does **not** auto-update from upstream.

## Upstream

| | |
|---|---|
| **Repository** | https://github.com/blader/humanizer |
| **Author** | Siqi Chen ([@blader](https://github.com/blader)) |
| **License** | MIT — see [`LICENSE`](./LICENSE) in this folder (Copyright © 2025 Siqi Chen) |
| **Upstream skill version** | `2.8.0` (the `version:` field in `SKILL.md` frontmatter) |
| **Commit copied** | `9600f2b7241cb4eed6ad803abee5ea01d67fe8e4` |
| **Commit date** | 2026-06-07 |
| **Copied on** | 2026-06-27 |
| **Stars at copy time** | ~26.4k |

## What it does

Removes signs of AI-generated writing from text — inflated symbolism, promotional language,
em-dash overuse, the "rule of three", AI vocabulary words, vague attributions, negative
parallelisms, passive voice, and filler phrases — so prose reads as natural and human-written.
Based on Wikipedia's "Signs of AI writing" guide (WikiProject AI Cleanup).

## Updating this vendored copy

Because this is a copy, upstream changes are **not** pulled automatically. To refresh it:

```powershell
$skill = "plugins/remote-skills/skills/humanizer"
curl.exe -s -o "$skill/SKILL.md" "https://raw.githubusercontent.com/blader/humanizer/main/SKILL.md"
curl.exe -s -o "$skill/LICENSE"  "https://raw.githubusercontent.com/blader/humanizer/main/LICENSE"
gh api repos/blader/humanizer/commits/main --jq '.sha'   # the new "Commit copied" value
```

Then:

1. Update the **Commit copied** / **Commit date** / **Copied on** rows in the table above.
2. Bump the `remote-skills` version in all four manifest/registry files per the repository
   `AGENTS.md` version-sync rule (`plugins/remote-skills/plugin.json`,
   `plugins/remote-skills/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.github/plugin/marketplace.json`).
