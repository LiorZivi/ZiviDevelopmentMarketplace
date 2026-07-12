# general-mcp

Bundles ready-to-use **MCP servers** as a marketplace plugin. Installing the plugin registers the servers at the **user level** (`~/.copilot/`), so they are available in **every** repo and session — no per-repo configuration.

## What it provides

| Server | Command | Capabilities | Auth |
|---|---|---|---|
| `playwright` | `npx @playwright/mcp@latest --allow-unrestricted-file-access` | Browser automation: navigate, click, type, snapshot, scrape, assert. Also renders local `file://` HTML (e.g. hand-authored SVG/HTML diagrams). | None (browsers download on first run). |
| `ado` | `npx -y @azure-devops/mcp ZiviDevelopment-DD-Org1` | Azure DevOps: work items, boards, repos, pull requests, pipelines, wiki. | Azure CLI (`az login`). |
| `azure` | `npx -y @azure/mcp@latest server start` | `azmcp`: query and manage Azure resources (storage, Key Vault, Cosmos DB, Monitor, and more). | Azure CLI (`az login`) / `DefaultAzureCredential`. |

This is a pure MCP-only plugin — it ships no skills or agents, just the server definitions.

> **Security note — Playwright file access.** The `playwright` server is launched with `--allow-unrestricted-file-access` so the automated browser can navigate to `file://` URLs and read files **outside** the workspace root (rendering a local HTML file, for example). By default `@playwright/mcp` blocks `file://` navigation and restricts file access to the workspace root; this flag lifts that safety rail, so a malicious page or prompt injection could read arbitrary local files. If you don't need local-file rendering, remove the flag from the `playwright` entry in `.mcp.json` (and bump the version across the four sync files); without it, serve the file over local HTTP and navigate to `http://127.0.0.1:PORT/…` instead.

## Why a plugin (vs. `~/.copilot/mcp-config.json`)

A local `mcp-config.json` only lives on your machine. Publishing the same servers as a marketplace plugin makes the configuration **public knowledge** and reusable: anyone can `/plugin install general-mcp@zivi-development-marketplace` and get the same servers, user-wide, across all their repos.

## Prerequisites

- **Node.js ≥ 20** on `PATH` (required by `@azure/mcp`; `npx` ships with Node).
- **Azure CLI** signed in for the `ado` and `azure` servers: `az login`.
- Network access on first run (npx package downloads + Playwright browsers).

## Install

```
/plugin marketplace add LiorZivi/ZiviDevelopmentMarketplace
/plugin install general-mcp@zivi-development-marketplace
```

Then run `/mcp` to confirm `playwright`, `ado`, and `azure` are listed with source `plugin`.

## Configuration format

Servers use the **canonical stdio form** — `command` + `args`, with no `type` field:

- **Copilot CLI** normalizes a `command`-based server to its `local` transport automatically.
- **Claude Code** treats a `command`-based server as `stdio`.

This keeps a single `.mcp.json` portable across both hosts. Remote servers instead use `{ "type": "http", "url": "…" }`.

## Customization

- **Azure DevOps organization** — the `ado` server is pinned to `ZiviDevelopment-DD-Org1`. To target a different org, edit the third argument of the `ado` entry in `.mcp.json`, then bump the version across all four sync files (see below).
- **Tool filtering** — add a `"tools"` allow-list to any server in `.mcp.json` to expose only specific tools (defaults to all tools).

## Suggested additional servers

Not bundled, but easy to add to `.mcp.json` if useful:

- **Microsoft Learn Docs** (remote HTTP) — authoritative Azure / M365 / .NET docs: `{ "type": "http", "url": "https://learn.microsoft.com/api/mcp" }`.
- **Context7** — up-to-date, version-specific library docs and code examples: `npx -y @upstash/context7-mcp`.
- **GitHub** — already **built into** Copilot CLI (no plugin needed); enable via `/mcp`.

## Structure

```
general-mcp/
├── .claude-plugin/
│   └── plugin.json        # canonical manifest (mcpServers -> ./.mcp.json)
├── plugin.json            # mirror of the canonical manifest
├── .mcp.json              # the bundled MCP server definitions
└── README.md
```

## Version sync

Per repo convention, every version bump must update the same `version` in **four** files: `plugins/general-mcp/plugin.json`, `plugins/general-mcp/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `.github/plugin/marketplace.json`.
