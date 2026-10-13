# ads-commercials

A vendored subset of ten skills from [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills), selected for running paid ads and commercials end to end: campaign strategy, ad creative, measurement, and the landing, signup, paywall, and pricing steps that ads drive traffic into.

The skills under `skills/` are **snapshot copies** of upstream commit `0f8d89961cdf782dd02644b9df3ddc671c21a7f0` (upstream plugin `marketing-skills` v2.11.27) — they do **not** auto-update. Each skill folder carries the upstream `LICENSE` and a `SOURCE.md` with full provenance.

## Skills

| Skill | Upstream version | Use it for |
|---|---|---|
| [`ads`](./skills/ads/SOURCE.md) | 2.4.6 | Paid campaign strategy, targeting, bidding, budget pacing, and optimization, including Meta decision and audit playbooks |
| [`ad-creative`](./skills/ad-creative/SOURCE.md) | 2.11.0 | Ad copy and creative variations, short-form video ad formats, and generative creative tooling |
| [`attribution`](./skills/attribution/SOURCE.md) | 1.1.4 | Attribution models, UTMs, first-party tracking, and reconciling conflicting conversion numbers |
| [`analytics`](./skills/analytics/SOURCE.md) | 2.1.0 | Tracking plans, event instrumentation, GA4, and conversion tracking audits |
| [`cro`](./skills/cro/SOURCE.md) | 2.0.3 | Conversion optimization for landing pages, homepages, pricing pages, and forms |
| [`signup`](./skills/signup/SOURCE.md) | 2.0.1 | Signup, registration, and trial-activation flow optimization |
| [`paywalls`](./skills/paywalls/SOURCE.md) | 2.0.0 | In-app paywalls, upgrade screens, upsell modals, and feature gates |
| [`pricing`](./skills/pricing/SOURCE.md) | 2.1.3 | Pricing, packaging, tiers, trials, and monetization strategy |
| [`video`](./skills/video/SOURCE.md) | 2.2.1 | Video production with AI generation, avatars, and programmatic frameworks |
| [`product-marketing`](./skills/product-marketing/SOURCE.md) | 2.1.0 | The shared product-marketing context the other skills read first |

Most of these skills start by looking for the product-marketing context file created by `product-marketing`; run that skill once per product so the others have positioning, audience, and value-proposition context.

## Install

```
copilot plugin marketplace add LiorZivi/ZiviDevelopmentMarketplace
copilot plugin install ads-commercials@zivi-development-marketplace
```

## Before you use it

- **Guidance only.** No skill in this plugin ships executable scripts or credentials. Live ad-account access must come from a separately configured integration, such as Meta's official Ads MCP server (`https://mcp.facebook.com/ads`), and is governed by that integration's own permissions.
- **Paid generation services.** `video` and `ad-creative` recommend paid generation APIs (for example fal.ai, Veo, Runway, Kling, HeyGen, and ElevenLabs) and include example API calls. Do not call any paid generation service without the owner's explicit approval for that run.
- **Broad skill names.** Names such as `ads`, `video`, `pricing`, and `cro` can trigger on general requests. If one competes with a repository's own skills, disable it with `copilot skill disable <name>`; project and personal skills with the same `name` already take precedence over plugin skills.
- **References to omitted skills.** Upstream skills point to sibling skills that are not vendored here (for example `copywriting`, `social`, and `cold-email`) and to upstream `tools/` integration guides by GitHub URL. Those links are informational; install the full upstream plugin if you need them.

## Updating the vendored skills

Refresh all ten skills from a single upstream commit, verify every file against the upstream git blob hash, then update each `SOURCE.md` and bump the plugin version in all four manifest/registry files per the repository `AGENTS.md` version-sync rule.

```powershell
$plugin = "plugins/ads-commercials"
$skills = "ads","ad-creative","attribution","analytics","cro","signup","paywalls","pricing","video","product-marketing"
$headers = @{ "User-Agent" = "ads-commercials-refresh"; Accept = "application/vnd.github+json" }
$sha = (Invoke-RestMethod -Headers $headers "https://api.github.com/repos/coreyhaines31/marketingskills/commits/main").sha
$tree = Invoke-RestMethod -Headers $headers "https://api.github.com/repos/coreyhaines31/marketingskills/git/trees/${sha}?recursive=1"

foreach ($skill in $skills) {
    Get-ChildItem "$plugin/skills/$skill" -Recurse -File |
        Where-Object Name -NotIn "SOURCE.md" | Remove-Item
    $blobs = $tree.tree | Where-Object { $_.type -eq "blob" -and $_.path -like "skills/$skill/*" }
    foreach ($blob in $blobs) {
        $target = Join-Path $plugin $blob.path
        New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
        Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/coreyhaines31/marketingskills/$sha/$($blob.path)" -OutFile $target
        if ((git hash-object --no-filters $target) -ne $blob.sha) { throw "Hash mismatch: $($blob.path)" }
    }
    Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/coreyhaines31/marketingskills/$sha/LICENSE" -OutFile "$plugin/skills/$skill/LICENSE"
}
"Copied commit $sha"
```

Review the upstream diff for new scripts, tool integrations, or changed guardrails before publishing a refreshed version.

## License & attribution

All skills are MIT-licensed (© 2025 Corey Haines). The original `LICENSE` is preserved in every skill folder, and full attribution is recorded in each skill's `SOURCE.md`.
