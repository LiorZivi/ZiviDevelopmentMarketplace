# ZiviDevelopmentMarketplace

Copilot plugin marketplace for ZiviDevelopment team. A curated collection of skills, agents, hooks, and integrations purpose-built for ZiviDevelopment — providing shared tooling that keeps the team aligned on standards, speeds up common workflows, and encodes team knowledge into reusable automation.

## Getting Started

👉 **[Install Plugins](docs/INSTALL-PLUGINS.md)** — How to add the marketplace and install plugins into your project

## Available Plugins

| Plugin | Description |
|--------|-------------|
| [content-ai](plugins/content-ai/) | AI-powered content generation — research, comparison, and visual documentation |

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
