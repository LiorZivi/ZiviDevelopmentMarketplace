# PLUGIN_NAME

PLUGIN_DESCRIPTION

## Usage

### Skills
```
/zivi-development-marketplace:SKILL_NAME
```

### Agents
Available as `zivi-development-marketplace:AGENT_NAME` in the agents picker.

## Structure

```
PLUGIN_NAME/
├── .claude-plugin/
│   └── plugin.json
├── plugin.json
├── skills/
│   └── SKILL_NAME/
│       └── SKILL.md
├── agents/
│   └── AGENT_NAME.md
├── hooks/
│   └── hooks.json
├── scripts/
│   └── on-file-change.sh
├── .mcp.json
└── README.md
```
