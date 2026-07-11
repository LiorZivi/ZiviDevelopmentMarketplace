# agentic-ai

Agentic engineering plugin with skills for architecture planning, workspace-grounded onboarding, and design memory. Each skill is backed by purpose-built planning and exploration sub-agents.

## Skills

### architect
Planning skill that turns a task into two artifacts: a PM-level `spec.md` and a phased `plan.md`. Uses the `plan-architect` and `plan-reviewer` sub-agents to draft and score the plan.

### ramp-up
Workspace-grounded onboarding skill that produces a markdown explainer plus matching PPTX deck about an internal subsystem, flow, or codebase area. Every claim is cited to a real file, wiki page, or commit in the user's workspace or Azure DevOps — never the open web or training data. Uses the `ramp-up-explorer` sub-agent to scan workspace + Azure DevOps (via the bluebird MCP server) and return ranked citations per section.

### memory-summary
Records a finished or shipped change as one durable `Summary_<name>.md` entry in a team's memory under `Doc/memory/<team>/`, in a fixed spec+plan format. Works from an `/architect` design (`spec.md` + `plan.md`) or straight from a code change (working-tree edits, a PR, or a commit range vs `main`). Files single-team, cross-team, and org-wide (`global`) summaries, registers them in the team index, and leaves everything uncommitted for the same PR as the code.

### memory-drift
Re-validates one committed design summary against the current code and reports whether the code has drifted from the recorded design — classified as **architecture drift** (the design notes are stale) or **spec drift** (the code no longer meets the intent), with cited evidence. Human-gated: never commits, never opens a PR, and never edits the spec half on its own. Shares one compare engine with `memory-summary`.

## Prerequisites

- **Required**: None — the markdown output works without any dependencies
- **Optional**: Python 3.9+ — needed for `ramp-up` PPTX (PowerPoint) generation
- **Optional (`ramp-up` grounding)**: the bluebird MCP server — lets `ramp-up-explorer` cite Azure DevOps code and wiki pages in addition to the local workspace

If Python is not installed, the `ramp-up` skill will create the markdown document and guide you through installing Python for PPTX support.

## Usage

### architect — plan a feature or change

```
/zivi-development-marketplace:architect add a retry budget to the ingestion path
```

### ramp-up — explain an internal subsystem

```
/zivi-development-marketplace:ramp-up monitoring flows in the auth service
```

### ramp-up — edit an existing explainer

```
/zivi-development-marketplace:ramp-up add a section about retries to the AuthMonitoringFlows explainer
```

### memory-summary — record a shipped change into memory

```
/zivi-development-marketplace:memory-summary summarize my current changes into the platform memory
```

### memory-drift — check a design summary against the code

```
/zivi-development-marketplace:memory-drift check Doc/memory/platform/Summary_RetryBudget.md for drift
```

## What it produces

| Output | Location | Requires |
|--------|----------|----------|
| `architect` spec | `./output/architect/{PlanName}-spec.md` | Nothing |
| `architect` plan | `./output/architect/{PlanName}-plan.md` | Nothing |
| `ramp-up` markdown | `./output/ramp-up/{Topic}.md` | Workspace + (optional) bluebird MCP |
| `ramp-up` presentation | `./output/ramp-up/{Topic}.pptx` | Python 3 |
| `memory-summary` record | `Doc/memory/<team>/Summary_<name>.md` (+ `index.md` row) | Nothing |
| `memory-drift` report | Drift verdict in chat (+ optional staged architecture-section edit) | Nothing |

## Structure

```
agentic-ai/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── plan-architect.md
│   ├── plan-reviewer.md
│   └── ramp-up-explorer.md
├── skills/
│   ├── architect/
│   │   └── SKILL.md
│   ├── memory-drift/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── compare-summary-to-code.md
│   │       └── verdict-report-template.md
│   ├── memory-summary/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── summary-format.md
│   └── ramp-up/
│       ├── SKILL.md
│       └── output-template.md
├── scripts/
│   └── ramp-up/
│       ├── generate.sh
│       ├── md_to_pptx.py
│       ├── pptx_engine.py
│       ├── requirements.txt
│       └── themes/
│           ├── __init__.py
│           └── anthropic.py
└── README.md
```

## Installing Python (optional)

If you want `ramp-up` PPTX generation, install Python 3:

- **Windows**: `winget install Python.Python.3` or download from [python.org](https://www.python.org/downloads/)
- **macOS**: `brew install python` or download from [python.org](https://www.python.org/downloads/)
- **Linux (apt)**: `sudo apt install python3`
- **Linux (dnf)**: `sudo dnf install python3`

The `python-pptx` pip package will be installed automatically on first use.
