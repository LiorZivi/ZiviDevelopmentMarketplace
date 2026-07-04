# ZiviDevelopment Marketplace

This is a Claude Code plugin marketplace repository for ZiviDevelopment team.

> This file mirrors `AGENTS.md` for Claude Code compatibility. **If you change one, change the other.**

## Repository Structure

- `.claude-plugin/marketplace.json` — Central plugin registry (canonical — consumed by Claude Code and Copilot CLI `/plugin` commands)
- `.github/plugin/marketplace.json` — Mirror registry used by some GitHub-side tooling — must stay in sync with `.claude-plugin/marketplace.json`
- `plugins/<name>/` — Individual plugin directories (each is a standalone Claude Code plugin)
- `templates/` — Starter scaffolds for new plugins (`plugin-basic/`, `plugin-full/`)
- `docs/` — Contribution, installation, and spec guides

## Plugin Structure Convention

Every plugin under `plugins/` must follow this layout:

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json        # Required manifest (name must match directory)
├── skills/                # Optional (see note below)
│   └── <skill-name>/
│       └── SKILL.md
└── README.md              # Required documentation
```

Optional components: `agents/`, `hooks/`, `scripts/`, `.mcp.json`, `.lsp.json`, `output-styles/`.

A plugin must provide **at least one capability component** — a skill, agent, hook, MCP server (`.mcp.json`), or LSP server — but it does **not** have to be a skill. For example, `general-mcp` is an MCP-only plugin (a `.mcp.json` with no skills).

## When Adding a Plugin

Every version bump or plugin change must update **four** files in lockstep:

1. `plugins/<name>/plugin.json` — root manifest (read by some tooling)
2. `plugins/<name>/.claude-plugin/plugin.json` — canonical Copilot CLI / Claude Code manifest
3. `.claude-plugin/marketplace.json` — the canonical plugin registry (what `/plugin update` reads)
4. `.github/plugin/marketplace.json` — mirror registry consumed by GitHub-side tooling

Steps:

1. Create or edit the plugin directory under `plugins/`.
2. Bump `version` in **both** `plugins/<name>/plugin.json` **and** `plugins/<name>/.claude-plugin/plugin.json`. These two manifests must stay identical.
3. Add or update the plugin's entry in **both** `.claude-plugin/marketplace.json` **and** `.github/plugin/marketplace.json`. Keep `version`, `description`, and `tags` identical between the two registries and matching the plugin manifests.

### Version-sync rule (non-negotiable)

The `version` string for a given plugin **must be identical** across all four files:

| File | Field |
|---|---|
| `plugins/<name>/plugin.json` | `version` |
| `plugins/<name>/.claude-plugin/plugin.json` | `version` |
| `.claude-plugin/marketplace.json` | `plugins[].version` (entry where `name == <name>`) |
| `.github/plugin/marketplace.json` | `plugins[].version` (entry where `name == <name>`) |

If any one of the four drifts, `/plugin update` will either report a stale version or refuse to update. Before committing a plugin change, verify all four match — e.g.:

```powershell
$name = "general-ops"
(Get-Content "plugins/$name/plugin.json" | ConvertFrom-Json).version
(Get-Content "plugins/$name/.claude-plugin/plugin.json" | ConvertFrom-Json).version
((Get-Content ".claude-plugin/marketplace.json" | ConvertFrom-Json).plugins | ? name -eq $name).version
((Get-Content ".github/plugin/marketplace.json" | ConvertFrom-Json).plugins | ? name -eq $name).version
```

All four lines must print the same value.

> ⚠️ Forgetting the second registry (`.github/plugin/marketplace.json`) is the #1 cause of `/plugin update` reporting a stale version. Always bump all four files together.

## Naming

- All names use `kebab-case`
- Plugin directory name must match the `name` field in `plugin.json`
