# Source & Attribution — `ad-creative` skill

This skill is a **vendored copy** of a third-party, open-source skill. The files in this folder (other than this `SOURCE.md`) were copied **verbatim** from the upstream repository and verified against the upstream git blob hashes. This is a snapshot — it does **not** auto-update from upstream.

## Upstream

| | |
|---|---|
| **Repository** | https://github.com/coreyhaines31/marketingskills |
| **Upstream path** | `skills/ad-creative` |
| **Author** | Corey Haines ([@coreyhaines31](https://github.com/coreyhaines31)) |
| **License** | MIT — see [`LICENSE`](./LICENSE) in this folder (Copyright © 2025 Corey Haines) |
| **Upstream skill version** | `2.11.0` (the `metadata.version` field in `SKILL.md` frontmatter) |
| **Upstream plugin version** | `2.11.27` (`marketing-skills` in upstream `.claude-plugin/plugin.json`) |
| **Commit copied** | `0f8d89961cdf782dd02644b9df3ddc671c21a7f0` |
| **Commit date** | 2026-10-13 |
| **Copied on** | 2026-10-14 |
| **Stars at copy time** | ~54.6k |

## What it does

Generates, iterates, and scales ad creative — headlines, primary text, and full ad variations — plus short-form video ad formats and a survey of generative image, video, and voice tools.

## Files copied

`assets/creative-review-template.html`, `evals/evals.json`, `references/awareness-headlines.md`, `references/creative-review-page.md`, `references/creative-roadmap.md`, `references/generative-tools.md`, `references/hook-system.md`, `references/imessage-video-ads.md`, `references/meta-creative-formats.md`, `references/motion-video-ads.md`, `references/platform-specs.md`, `references/short-form-video-specs.md`, `references/static-ad-templates.md`, `SKILL.md`

## Updating this vendored copy

Because this is a copy, upstream changes are **not** pulled automatically. Refresh every skill in this plugin together from one upstream commit; see the plugin [`README.md`](../../README.md#updating-the-vendored-skills) for the script. Then:

1. Update the **Upstream skill version**, **Upstream plugin version**, **Commit copied**, **Commit date**, and **Copied on** rows in the table above.
2. Bump the `ads-commercials` version in all four manifest/registry files per the repository `AGENTS.md` version-sync rule (`plugins/ads-commercials/plugin.json`, `plugins/ads-commercials/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.github/plugin/marketplace.json`).
