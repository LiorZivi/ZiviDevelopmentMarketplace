# ZiviDevelopmentMarketplace

Copilot plugin marketplace for ZiviDevelopment team. A curated collection of skills, agents, hooks, and integrations purpose-built for ZiviDevelopment — providing shared tooling that keeps the team aligned on standards, speeds up common workflows, and encodes team knowledge into reusable automation.

## Getting Started

👉 **[Install Plugins](docs/INSTALL-PLUGINS.md)** — How to add the marketplace and install plugins into your project

## Available Plugins

| Plugin | Source | Description |
|--------|--------|-------------|
| [content-ai](plugins/content-ai/) | Local | AI-powered content generation — deep-dive research, branded presentations, and LinkedIn publishing |
| [agentic-ai](plugins/agentic-ai/) | Local | Architecture planning, workspace-grounded onboarding, design-memory workflows, and visual PR/change explainers |
| [general-ops](plugins/general-ops/) | Local | Bidirectional Copilot CLI remote-control bridges for Microsoft Teams and Telegram |
| [remote-plugin-blader](plugins/remote-plugin-blader/) | Local | humanizer — removes signs of AI-generated writing (from blader/humanizer) |
| [remote-plugin-199-biotechnologies](plugins/remote-plugin-199-biotechnologies/) | Local | deep-research — multi-source research with citations (from 199-biotechnologies) |
| [code-simplifier](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-simplifier) | Referenced → Anthropic | Simplifies and refines code for clarity, consistency, and maintainability |
| [frontend-design](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design) | Referenced → Anthropic | Production-grade frontend interfaces with high design quality |
| [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) | Referenced → Anthropic | Create, improve, and measure the performance of skills |

> **Referenced** plugins are not copied into this repo — their marketplace entry points at a subdirectory of [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) via a `github` source, so `/plugin install` pulls them live from Anthropic's official marketplace.

## Deprecated Plugins

Deprecated plugin sources are retained under [`deprecated/`](deprecated/) for provenance and license compliance, but they are not listed in the active marketplace registries.

| Plugin | Status |
|--------|--------|
| [remote-plugin-obra](deprecated/remote-plugin-obra/) | Archived; no longer distributed by this marketplace |

## Repository Structure

```
ZiviDevelopmentMarketplace/
├── .github/
│   └── plugin/
│       └── marketplace.json              # Plugin registry
├── plugins/
│   ├── content-ai/                   # Research, presentations & LinkedIn publishing
│   └── agentic-ai/                   # Architecture, onboarding, design memory & PR explainers
├── deprecated/
│   └── remote-plugin-obra/           # Archived plugin source; not actively distributed
├── templates/
│   ├── plugin-basic/                 # Minimal plugin scaffold
│   └── plugin-full/                  # Full-featured plugin scaffold
└── docs/
    ├── INSTALL-PLUGINS.md            # How to install plugins
    ├── CREATE-PLUGIN.md              # How to add plugins
    ├── ARCHITECTURE.md               # Design and architecture plan
    └── PLUGIN-SPEC.md                # File format reference
```

## Documentation

- [Create a Plugin](docs/CREATE-PLUGIN.md) — Step-by-step guide to add your own plugin
- [Architecture](docs/ARCHITECTURE.md) — Design and architecture plan
- [Plugin Spec](docs/PLUGIN-SPEC.md) — File format reference
