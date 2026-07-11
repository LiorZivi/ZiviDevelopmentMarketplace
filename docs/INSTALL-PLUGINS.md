# How to Install and Use Marketplace Plugins (GitHub Copilot CLI)

## Adding the Marketplace

Adding the marketplace makes the plugin catalog available — no plugins are activated until you install them.

Make sure you are signed in (using the `/login` command) and then add the marketplace:

```
/plugin marketplace add LiorZivi/ZiviDevelopmentMarketplace
```

This writes an entry to your Copilot config file at `~/.copilot/config.json` under the `marketplaces` section:

```json
{
  "marketplaces": {
    "zivi-development-marketplace": {
      "source": {
        "source": "github",
        "repo": "LiorZivi/ZiviDevelopmentMarketplace"
      }
    }
  }
}
```

## Browsing Available Plugins

Once the marketplace is added, browse its available plugins:

```
/plugin marketplace browse zivi-development-marketplace
```

This lists all plugins published in the marketplace along with their descriptions.

## Installing a Plugin

From the browse results, select the plugin you want to install. Or install via CLI:

```
/plugin install content-ai@zivi-development-marketplace
```

## Removing a Plugin

To remove an installed plugin:

```
/plugin uninstall <plugin-name>
```

This removes the plugin entry from `~/.copilot/config.json` and disables it for future sessions.

## Using a Skill from a Plugin

Plugins can expose **skills** — specialized capabilities that are automatically available in your session once the plugin is installed and enabled.

To see available skills, run:

```
/skills
```

### How Skills Are Triggered

Each skill defines trigger keywords in its `SKILL.md` file. When your message matches one of these keywords or phrases, the CLI automatically invokes the corresponding skill. For example, the `content-ai` plugin provides the `learn` skill and the `agentic-ai` plugin provides the `architect` skill:

| Message | Skill triggered |
|---------|----------------|
| `learn about Kubernetes networking` | `content-ai:learn` |
| `architect a REST API service` | `agentic-ai:architect` |

You can also directly invoke a skill using the `/<plugin-name>:<skill-name>` syntax:

```
/agentic-ai:architect
```

Each plugin's README describes the skills it offers and how to invoke them.

## Plugin Storage and Configuration

### Where Plugins Are Stored

All plugin files are cached under `~/.copilot/installed-plugins/`:

```
~/.copilot/installed-plugins/
├── <marketplace-name>/          # Marketplace-installed plugins
│   └── <plugin-name>/
│       ├── .claude-plugin/
│       ├── agents/
│       ├── skills/
│       ├── plugin.json
│       └── README.md
└── _direct/                     # Directly-installed plugins (from GitHub repo)
    └── <org>--<repo>--<path>/
        ├── .claude-plugin/
        ├── agents/
        ├── commands/
        ├── plugin.json
        └── README.md
```

### config.json

The `~/.copilot/config.json` file is the central registry that tracks all installed plugins, their enabled state, cache paths, and sources.

Marketplace-installed plugins are registered with the marketplace name:

```json
{
  "installed_plugins": [
    {
      "name": "content-ai",
      "marketplace": "zivi-development-marketplace",
      "version": "1.0.0",
      "installed_at": "2026-03-31T15:40:45.095Z",
      "enabled": true,
      "cache_path": "~/.copilot/installed-plugins/zivi-development-marketplace/content-ai"
    }
  ]
}
```

### Direct Install (from a GitHub repo)

You can also install a plugin directly from a GitHub repository without going through a marketplace. Direct-installed plugins are cached under `~/.copilot/installed-plugins/_direct/` using the naming convention `<org>--<repo>--<path>`.

For example, installing `feature-dev` from `anthropics/claude-plugins-official` creates:

```
~/.copilot/installed-plugins/_direct/anthropics--claude-plugins-official--plugins-feature-dev/
```

In `config.json`, direct-installed plugins have an empty `marketplace` field and a `source` pointing to the GitHub repo:

```json
{
  "name": "feature-dev",
  "marketplace": "",
  "enabled": true,
  "cache_path": "~/.copilot/installed-plugins/_direct/anthropics--claude-plugins-official--plugins-feature-dev",
  "source": {
    "source": "github",
    "repo": "anthropics/claude-plugins-official",
    "path": "plugins/feature-dev"
  }
}
```
