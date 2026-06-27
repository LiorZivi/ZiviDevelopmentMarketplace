# Source & Attribution — `brainstorming` skill

This skill is a **vendored copy** of a single skill taken from a third-party, open-source
**monorepo**. The files in this folder (`SKILL.md`, `visual-companion.md`,
`spec-document-reviewer-prompt.md`, `scripts/`, `LICENSE`) were copied **verbatim** from the
upstream repository's `skills/brainstorming/` directory. This is a snapshot — it does **not**
auto-update from upstream.

## Upstream

| | |
|---|---|
| **Repository** | https://github.com/obra/superpowers |
| **Skill path** | `skills/brainstorming/` (one of 14 skills in the `superpowers` plugin) |
| **Author** | Jesse Vincent ([@obra](https://github.com/obra)) |
| **License** | MIT — see [`LICENSE`](./LICENSE) in this folder (Copyright © 2025 Jesse Vincent) |
| **Parent plugin version** | `superpowers` `6.0.3` (the skill's own `SKILL.md` has no `version:` field) |
| **Commit copied** | `896224c4b1879920ab573417e68fd51d2ccc9072` |
| **Commit date** | 2026-06-18 |
| **Copied on** | 2026-06-28 |
| **Stars at copy time** | ~240k |

## Why vendored (and not referenced)

The `superpowers` repo *is* referenceable as a whole plugin (its root has a
`.claude-plugin/plugin.json`), but referencing it installs **all 14** skills. A single skill
inside a plugin cannot be referenced on its own, and `skills/brainstorming/` has no manifest of
its own. To expose **only** this one skill under our marketplace, it must be vendored. MIT
permits this provided the copyright notice and license text are retained (see `LICENSE`).

## What it does

Explores user intent, requirements, and design **before** implementation — for any creative
work such as creating features, building components, or modifying behavior. Includes an optional
visual brainstorming companion (`visual-companion.md` + `scripts/` local server).

## Updating this vendored copy

Because this is a copy, upstream changes are **not** pulled automatically. To refresh it:

```powershell
$skill = "plugins/remote-skills/skills/brainstorming"
$tmp = Join-Path $env:TEMP "sp-refresh"
git clone --depth 1 https://github.com/obra/superpowers.git $tmp
Remove-Item "$skill/*" -Recurse -Force -Exclude "SOURCE.md"
Copy-Item "$tmp/skills/brainstorming/*" $skill -Recurse -Force
Copy-Item "$tmp/LICENSE" "$skill/LICENSE" -Force
git -C $tmp rev-parse HEAD    # the new "Commit copied" value
Remove-Item $tmp -Recurse -Force
```

Then:

1. Update the **Commit copied** / **Commit date** / **Copied on** rows in the table above.
2. Bump the `remote-skills` version in all four manifest/registry files per the repository
   `AGENTS.md` version-sync rule (`plugins/remote-skills/plugin.json`,
   `plugins/remote-skills/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.github/plugin/marketplace.json`).
