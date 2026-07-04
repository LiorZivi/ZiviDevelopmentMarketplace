# Plugin Specification

Reference for all file formats used in this marketplace. Based on Claude Code plugin standards (March 2026).

## plugin.json (Manifest)

Located at `<plugin>/.claude-plugin/plugin.json`.

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Brief description",
  "author": { "name": "Name", "email": "optional", "url": "optional" },
  "homepage": "https://docs-url",
  "repository": "https://github-url",
  "license": "MIT",
  "keywords": ["tag1", "tag2"],
  "commands": "./custom/commands/",
  "agents": "./custom/agents/",
  "skills": "./custom/skills/",
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json",
  "outputStyles": "./output-styles/",
  "lspServers": "./.lsp.json"
}
```

Required: `name`. All other fields are optional.

Custom paths supplement default directories — they don't replace them.

## SKILL.md (Skill Definition)

Located at `<plugin>/skills/<skill-name>/SKILL.md`.

### Frontmatter

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | dir name | Identifier (kebab-case, max 64 chars) |
| `description` | string | — | When Claude should auto-load this skill |
| `argument-hint` | string | — | Autocomplete hint in `/` menu |
| `user-invocable` | boolean | `true` | Show in `/` menu |
| `disable-model-invocation` | boolean | `false` | Prevent Claude auto-trigger |
| `model` | string | `inherit` | `sonnet`, `opus`, `haiku` |
| `effort` | string | inherit | `low`, `medium`, `high`, `max` |
| `context` | string | — | `fork` for isolated subagent |
| `agent` | string | — | Subagent type when `context: fork` |
| `hooks` | object | — | Skill-scoped hooks |

### Substitution Variables

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed to skill |
| `$ARGUMENTS[N]` / `$N` | Nth argument (0-based) |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing SKILL.md |
| `${CLAUDE_PLUGIN_ROOT}` | Plugin root directory |
| `${CLAUDE_PLUGIN_DATA}` | Persistent data dir (`~/.claude/plugins/data/<id>/`) |

### Dynamic Context

Use `` !`command` `` to inject shell output before Claude sees the skill:

```markdown
Current branch: !`git branch --show-current`
```

## Agent Definition (agents/\<name\>.md)

Defined as Markdown files with YAML frontmatter. The body becomes the subagent's system prompt.

### Frontmatter

Only `name` and `description` are **required**. All other fields are optional.

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | yes | string | Unique identifier (lowercase, hyphens). Filename does not have to match. |
| `description` | yes | string | When the host should delegate to this agent (routing hint). |
| `tools` | no | string | Comma-separated tool allowlist. **Omitted = inherits all parent tools.** |
| `disallowedTools` | no | string | Tools to remove from the inherited/allowed list. |
| `model` | no | string | `sonnet`, `opus`, `haiku`, a full model ID, or `inherit`. Defaults to `inherit`. |
| `effort` | no | string | `low`, `medium`, `high`, `max`. |
| `maxTurns` | no | integer | Max agentic turns before the subagent stops. |
| `skills` | no | array | Skills to preload into the subagent's context at startup. |
| `background` | no | boolean | Always run in background. |
| `color` | no | string | UI color tag. |
| `isolation` | no | string | `worktree` for an isolated repo copy. |

**Plugin restriction:** plugin subagents do **not** support `hooks`, `mcpServers`, or `permissionMode` (silently ignored). If you need them, place the agent in `.claude/agents/` or `~/.claude/agents/` instead of a plugin.

### Guidance: when to set `model` / `tools`

- **`model`** — set only when you want to pin the model regardless of the parent (e.g., force Opus for judgment-heavy work). Otherwise leave it off and inherit.
- **`tools`** — set when you want a meaningful constraint (e.g., a read-only reviewer with `Read, Glob, Grep`). If your allowlist is broad enough to be near-equivalent to "inherit", drop it.

### Example

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices. Spawn after edits land.
tools: Read, Glob, Grep
model: opus
---

You are a senior code reviewer. ...
```

## hooks.json

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolName|OtherTool",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/my-hook.sh"
          }
        ]
      }
    ]
  }
}
```

Hook types: `command`, `http`, `prompt`, `agent`.

Common events: `SessionStart`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `Stop`, `SessionEnd`.

## .mcp.json

Local (stdio) servers are identified by `command` — omit `type`. Copilot CLI normalizes a `command`-based server to its `local` transport; Claude Code treats it as `stdio`. Keeping `type` off makes one file portable across both hosts.

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": { "KEY": "${ENV_VAR}" }
    }
  }
}
```

Remote servers set `type` explicitly and use a `url`:

```json
{
  "mcpServers": {
    "remote-server": {
      "type": "http",
      "url": "https://example.com/mcp"
    }
  }
}
```

Transports: local stdio (`command`, no `type`), or remote `http` / `sse` (with `url`).

## .lsp.json

```json
{
  "language-id": {
    "command": "language-server-binary",
    "args": ["serve"],
    "extensionToLanguage": { ".ext": "language-id" }
  }
}
```

## Output Styles (output-styles/\<name\>.md)

```yaml
---
name: Style Name
description: Shown in /config picker
keep-coding-instructions: false
---

Custom system prompt instructions here.
```

## Namespacing

All skills and agents from plugins are namespaced:

- Skill: `/marketplace-name:skill-name`
- Agent: `marketplace-name:agent-name`
