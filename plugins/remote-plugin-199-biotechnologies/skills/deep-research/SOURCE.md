# Source & Attribution — `deep-research` skill

This skill is a **vendored copy** of a third-party, open-source skill. The files in this folder
(`SKILL.md`, `reference/`, `schemas/`, `scripts/`, `templates/`, `requirements.txt`, `README.md`)
were copied **verbatim** from the upstream repository (the skill lives at the repo root). This is
a snapshot — it does **not** auto-update from upstream. The upstream `tests/` directory and
`.gitignore` were intentionally **not** vendored (not needed at runtime).

## Upstream

| | |
|---|---|
| **Repository** | https://github.com/199-biotechnologies/claude-deep-research-skill |
| **Author** | 199 Biotechnologies ([@199-biotechnologies](https://github.com/199-biotechnologies)) |
| **License** | MIT — declared in the upstream `README.md` ("## License — MIT - modify as needed for your workflow."). The upstream ships **no standalone `LICENSE` file**, so the [`LICENSE`](./LICENSE) in this folder is the standard MIT text with the copyright attributed to the upstream author. |
| **Upstream skill version** | `2.2` (per the upstream README changelog; `SKILL.md` has no `version:` field) |
| **Commit copied** | `f2f2c0fa4e7617ca84c86b63f4bb40f77a746933` |
| **Commit date** | 2026-04-11 |
| **Copied on** | 2026-06-28 |
| **Stars at copy time** | ~800 |

## Why vendored (and not referenced)

The upstream repo is a **bare skill** — a `SKILL.md` at the repo root with no
`.claude-plugin/plugin.json` (and no `marketplace.json`). Copilot CLI can only reference a
remote source that resolves to a packaged plugin (one with a `plugin.json`), so this skill
cannot be referenced from our marketplace. Vendoring is the only way to expose it; MIT permits
this provided attribution is retained (see `LICENSE` and this file).

## What it does

Multi-source research with citation tracking, evidence persistence, and structured report
generation. Triggers on "deep research", "comprehensive analysis", "research report",
"compare X vs Y", "analyze trends", or "state of the art" — not for simple lookups. Ships Python
helper scripts (`scripts/`) and JSON schemas (`schemas/`); see `requirements.txt` for Python
dependencies and the upstream `README.md` for usage details.

## Updating this vendored copy

Because this is a copy, upstream changes are **not** pulled automatically. To refresh it:

```powershell
$skill = "plugins/remote-plugin-199-biotechnologies/skills/deep-research"
$tmp = Join-Path $env:TEMP "dr-refresh"
git clone --depth 1 https://github.com/199-biotechnologies/claude-deep-research-skill.git $tmp
# keep SOURCE.md + our LICENSE; refresh the upstream files
Get-ChildItem $skill -Exclude 'SOURCE.md','LICENSE' | Remove-Item -Recurse -Force
foreach ($i in 'SKILL.md','README.md','requirements.txt','reference','schemas','scripts','templates') {
  Copy-Item "$tmp/$i" $skill -Recurse -Force
}
git -C $tmp rev-parse HEAD    # the new "Commit copied" value
Remove-Item $tmp -Recurse -Force
```

Then:

1. Update the **Commit copied** / **Commit date** / **Copied on** rows in the table above.
2. Bump the `remote-plugin-199-biotechnologies` version in all four manifest/registry files per the repository
   `AGENTS.md` version-sync rule (`plugins/remote-plugin-199-biotechnologies/plugin.json`,
   `plugins/remote-plugin-199-biotechnologies/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.github/plugin/marketplace.json`).
