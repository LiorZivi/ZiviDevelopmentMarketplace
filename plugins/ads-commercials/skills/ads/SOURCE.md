# Source & Attribution — `ads` skill

This skill is a **vendored copy** of a third-party, open-source skill. The files in this folder (other than this `SOURCE.md`) were copied **verbatim** from the upstream repository and verified against the upstream git blob hashes. This is a snapshot — it does **not** auto-update from upstream.

## Upstream

| | |
|---|---|
| **Repository** | https://github.com/coreyhaines31/marketingskills |
| **Upstream path** | `skills/ads` |
| **Author** | Corey Haines ([@coreyhaines31](https://github.com/coreyhaines31)) |
| **License** | MIT — see [`LICENSE`](./LICENSE) in this folder (Copyright © 2025 Corey Haines) |
| **Upstream skill version** | `2.4.6` (the `metadata.version` field in `SKILL.md` frontmatter) |
| **Upstream plugin version** | `2.11.27` (`marketing-skills` in upstream `.claude-plugin/plugin.json`) |
| **Commit copied** | `0f8d89961cdf782dd02644b9df3ddc671c21a7f0` |
| **Commit date** | 2026-10-13 |
| **Copied on** | 2026-10-14 |
| **Stars at copy time** | ~54.6k |

## What it does

Paid advertising strategy, audience targeting, bidding, budget pacing, and optimization across Meta, Google, LinkedIn, X, and other ad platforms, with Meta-specific decision and audit playbooks under `references/`.

## Files copied

`evals/evals.json`, `references/abm-playbook.md`, `references/ad-copy-templates.md`, `references/audience-targeting.md`, `references/audit-guardrails.md`, `references/b2b-paid-playbook.md`, `references/conversion-tracking.md`, `references/creative-research-automation.md`, `references/google-ads-audit-checklist.md`, `references/google-search-playbook.md`, `references/linkedin-b2b-playbook.md`, `references/meta-andromeda-playbook.md`, `references/meta-decision-system.md`, `references/payback-period.md`, `references/platform-setup-checklists.md`, `references/reading-google-ads-data.md`, `references/rsa-output-spec.md`, `SKILL.md`

## Updating this vendored copy

Because this is a copy, upstream changes are **not** pulled automatically. Refresh every skill in this plugin together from one upstream commit; see the plugin [`README.md`](../../README.md#updating-the-vendored-skills) for the script. Then:

1. Update the **Upstream skill version**, **Upstream plugin version**, **Commit copied**, **Commit date**, and **Copied on** rows in the table above.
2. Bump the `ads-commercials` version in all four manifest/registry files per the repository `AGENTS.md` version-sync rule (`plugins/ads-commercials/plugin.json`, `plugins/ads-commercials/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.github/plugin/marketplace.json`).
