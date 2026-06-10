# How to Add a New Plugin

## Step 1: Choose a template

Pick a template from `templates/` and copy it into `plugins/`:

| Template | Use when you need | What's included |
|----------|-------------------|-----------------|
| **`plugin-basic`** | A standalone skill (most common) | `plugin.json`, one skill, README |
| **`plugin-full`** | Skills + agents + hooks + MCP server | Everything in basic, plus agents, hooks, scripts, `.mcp.json` |

```bash
cp -r templates/plugin-basic plugins/my-plugin-name
```

---

### plugin-basic structure

```
my-plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Plugin identity & metadata (Copilot reads this)
├── plugin.json              # Root copy (npm/marketplace tooling reads this)
├── skills/
│   └── my-skill/
│       └── SKILL.md         # Skill instructions (frontmatter + body)
└── README.md
```

### plugin-full structure

```
my-plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Plugin identity & metadata (Copilot reads this)
├── plugin.json              # Root copy (npm/marketplace tooling reads this)
├── skills/
│   └── my-skill/
│       └── SKILL.md         # Skill instructions
├── agents/
│   └── my-agent.md          # Agent definition (frontmatter + body)
├── hooks/
│   └── hooks.json           # Lifecycle hook definitions
├── scripts/
│   └── on-file-change.sh    # Scripts referenced by hooks
├── .mcp.json                # MCP server configuration
└── README.md
```

---

## Step 2: Configure plugin.json

`plugin.json` lives in **two places** — `.claude-plugin/plugin.json` (read by Copilot) and `plugin.json` at the plugin root (used by npm/marketplace tooling). Keep both files in sync. The content is identical except that the `.claude-plugin/` copy may include Copilot-specific fields like `hooks`.

### plugin-basic — plugin.json

```json
{
  "name": "PLUGIN_NAME",
  "version": "1.0.0",
  "description": "PLUGIN_DESCRIPTION",
  "author": {
    "name": "AUTHOR_NAME"
  },
  "keywords": []
}
```

### plugin-full — plugin.json

The full template adds a `hooks` field that points to the hooks config:

```json
{
  "name": "PLUGIN_NAME",
  "version": "1.0.0",
  "description": "PLUGIN_DESCRIPTION",
  "author": {
    "name": "AUTHOR_NAME"
  },
  "keywords": [],
  "hooks": "./hooks/hooks.json"
}
```

### plugin.json field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Plugin identifier. **Must match** your plugin directory name. |
| `version` | ✅ | Semver version string (e.g. `"1.0.0"`). Bump on every update. |
| `description` | ✅ | What the plugin does. Shown in the marketplace listing. |
| `author.name` | ✅ | Your name or email (e.g. `"you@microsoft.com"`). |
| `keywords` | No | Tags for search/filtering in the marketplace. |
| `hooks` | No | Relative path to a hooks config file (e.g. `"./hooks/hooks.json"`). Only needed if your plugin defines lifecycle hooks. |

---

## Step 3: Implement your skill

Every plugin needs at least one skill. Rename `skills/my-skill/` to your skill name and edit `SKILL.md`:

```yaml
---
name: my-skill-name
description: When should Copilot load this skill? Be specific.
argument-hint: "[expected-args]"
user-invocable: true
allowed-tools: Read, Grep, Glob
---

Your skill instructions here. Copilot follows these when the skill is invoked.

User arguments: $ARGUMENTS
```

Use `${CLAUDE_PLUGIN_ROOT}` in your skill body to reference files relative to your plugin directory (scripts, templates, etc.).

### Skill frontmatter fields

| Field | Purpose |
|-------|---------|
| `name` | Skill identifier (kebab-case) |
| `description` | Copilot uses this to decide when to auto-load the skill |
| `argument-hint` | Shows in `/` autocomplete menu |
| `user-invocable` | Set `false` to hide from `/` menu (background knowledge only) |
| `disable-model-invocation` | Set `true` to prevent Copilot auto-triggering (manual `/` only) |
| `allowed-tools` | Tools the skill can use without prompting for permission |

---

## Step 4: Configure agents (plugin-full only)

Agents are subagents spawned with their own context window. Create one `.md` file per agent in `agents/`:

```yaml
---
name: my-agent
description: AGENT_DESCRIPTION — when should Copilot spawn this agent?
model: sonnet
tools: Read, Grep, Glob, Bash
---

# My Agent

Your agent instructions here. This agent is spawned as a subagent with its own context.
```

### Agent frontmatter fields

| Field | Purpose |
|-------|---------|
| `name` | Agent identifier (kebab-case). Invoked as `PLUGIN_NAME:AGENT_NAME`. |
| `description` | When Copilot should spawn this agent |
| `model` | LLM model to use (`sonnet`, `haiku`, `opus`, etc.) |
| `tools` | Comma-separated list of tools available to the agent |

---

## Step 5: Configure hooks (plugin-full only)

Hooks run scripts in response to Copilot lifecycle events. Define them in `hooks/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/on-file-change.sh"
          }
        ]
      }
    ]
  }
}
```

The hook script receives input as JSON on stdin. Exit `0` for success, exit `2` for a blocking error.

**Remember:** `plugin.json` must include `"hooks": "./hooks/hooks.json"` for hooks to be loaded.

---

## Step 6: Configure MCP servers (plugin-full only)

If your plugin needs external tool servers (e.g. a database, API wrapper), define them in `.mcp.json` at the plugin root:

```json
{
  "mcpServers": {
    "example-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {}
    }
  }
}
```

This file follows the standard MCP server configuration format. Each entry defines a server with its transport type, startup command, arguments, and environment variables.

---

## Step 7: Add a README

Update `plugins/my-plugin-name/README.md` with:
- What the plugin does
- How to invoke it (skill commands, agent names)
- Any prerequisites or configuration needed

---

## Step 8: Register in the marketplace

Add an entry to `.github/plugin/marketplace.json` in the `plugins` array:

```json
{
  "name": "my-plugin-name",
  "source": "./plugins/my-plugin-name",
  "description": "What your plugin does",
  "version": "1.0.0",
  "tags": ["relevant", "tags"]
}
```

---

## Step 9: Test locally

Before submitting a PR, test your plugin locally using the `--plugin-dir` flag. This loads the plugin for a single session without installing it — nothing is changed on your machine.

Open a **new terminal** (this flag only works at startup, not inside an existing session) and run from the marketplace repo root:

```bash
copilot --plugin-dir ./plugins/<my-plugin-name>
```
For example:
```bash
copilot --plugin-dir ./plugins/cmops
```

`./plugins/my-plugin-name` is the path to your plugin directory (the folder containing `.claude-plugin/plugin.json`).

Once the session starts, invoke your skill:

```
/my-plugin-name:my-skill-name
```

If the skill responds, your plugin is working. Close the session and proceed to the PR.

You can also test multiple plugins at once:

```bash
copilot --plugin-dir ./plugins/my-plugin-name --plugin-dir ./plugins/another-plugin
```

---

## Step 10: Open a pull request

## Checklist

- [ ] Plugin directory name matches `name` in `plugin.json`
- [ ] `plugin.json` exists in **both** `.claude-plugin/` and the plugin root
- [ ] Both `plugin.json` files have name, version, description, author and are in sync
- [ ] At least one skill with a `SKILL.md`
- [ ] `README.md` documents usage and purpose
- [ ] Entry added to `.github/plugin/marketplace.json`
- [ ] Tested locally with `copilot --plugin-dir`
- [ ] No secrets or credentials in any files (use `${ENV_VAR}` references)
- [ ] Version bumped if updating an existing plugin
- [ ] *(plugin-full)* `plugin.json` includes `"hooks"` path if hooks are defined
- [ ] *(plugin-full)* `.mcp.json` is valid JSON if MCP servers are configured
- [ ] *(plugin-full)* Agent `.md` files have required frontmatter (name, description, model, tools)
