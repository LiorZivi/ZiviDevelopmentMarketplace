# ZiviDevelopmentMarketplace

Copilot plugin marketplace for ZiviDevelopment team. A curated collection of skills, agents, hooks, and integrations purpose-built for ZiviDevelopment — providing shared tooling that keeps the team aligned on standards, speeds up common workflows, and encodes team knowledge into reusable automation.

## Getting Started

👉 **[Install Plugins](docs/INSTALL-PLUGINS.md)** — How to add the marketplace and install plugins into your project

## Available Plugins

| Plugin | Source | Description |
|--------|--------|-------------|
| [content-ai](plugins/content-ai/) | Local | AI-powered content generation — research, comparison, and visual documentation |
| [general-ops](plugins/general-ops/) | Local | Bidirectional Copilot CLI ↔ Microsoft Teams bridge via the Teams MCP |
| [remote-skills](plugins/remote-skills/) | Local | Third-party skills vendored from external repos (e.g. humanizer) |
| [code-simplifier](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-simplifier) | Referenced → Anthropic | Simplifies and refines code for clarity, consistency, and maintainability |
| [frontend-design](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design) | Referenced → Anthropic | Production-grade frontend interfaces with high design quality |
| [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) | Referenced → Anthropic | Create, improve, and measure the performance of skills |
| [document-skills](https://github.com/anthropics/skills/tree/main/skills) | Referenced → Anthropic | Document processing suite — Excel (xlsx), Word (docx), PowerPoint (pptx), and PDF |

> **Referenced** plugins are not copied into this repo — their marketplace entry points at Anthropic's official repos ([claude-plugins-official](https://github.com/anthropics/claude-plugins-official) and [skills](https://github.com/anthropics/skills)) via a `github` source, so `/plugin install` pulls them live from Anthropic. `document-skills` selects the `xlsx`, `docx`, `pptx`, and `pdf` skills from `anthropics/skills` (`strict: false` + a `skills` list).

## Repository Structure

```
ZiviDevelopmentMarketplace/
├── .github/
│   └── plugin/
│       └── marketplace.json              # Plugin registry
├── plugins/
│   └── content-ai/                   # AI content generation plugin
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
