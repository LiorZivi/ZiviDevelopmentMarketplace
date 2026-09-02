# agentic-ai

Agentic engineering plugin: complex and simplified architecture planning, workspace-grounded onboarding, a full **agent-memory** stack, and visual PR/change explainers.

## Skills

### architect
Complex planning skill that turns a task into a PM-level `spec.md` and phased `plan.md` through parallel plan alternatives and review. Trigger it explicitly with `complex architect`.

### simplified-architect
Direct planning skill that uses thorough questioning, drafts the same spec and plan formats, then asks a second round of draft-informed questions and revises both. It defaults to the simplest clean path and flags omitted edge cases for an explicit scope decision. Trigger it explicitly with `simple architect`.

### ramp-up
Workspace-grounded onboarding skill that produces a markdown explainer plus matching PPTX deck about an internal subsystem, flow, or codebase area. Every claim is cited to a real file, wiki page, or commit in the user's workspace or Azure DevOps — never the open web or training data. Uses the `ramp-up-explorer` sub-agent to scan workspace + Azure DevOps (via the bluebird MCP server) and return ranked citations per section.

### pr-explainer
Analyzes an Azure DevOps/GitHub pull request, branch diff, commit range, or local staged/unstaged change and creates a standalone HTML walkthrough. Every explainer uses the same reviewer-friendly structure: evidence when available, simplified before/after flows, detailed UML sequence diagrams, red problem highlights, green fix highlights, changed-file explanations, and proof of the fix.

### agent-memory-summary
Records a finished or shipped change as one durable `Summary_<name>.md` entry in a team's memory under `agent-memory/<team>/`, in a fixed spec+plan format. Works from an `/architect` design (`spec.md` + `plan.md`) or straight from a code change (working-tree edits, a PR, or a commit range vs `main`). Files single-team, cross-team, and org-wide (`global`) summaries, registers them in the team index, and leaves everything uncommitted for the same PR as the code.

### agent-memory-drift
Re-validates one committed design summary against the current code and reports whether the code has drifted from the recorded design — classified as **architecture drift** (the design notes are stale) or **spec drift** (the code no longer meets the intent), with cited evidence. Human-gated: never commits, never opens a PR, and never edits the spec half on its own. Shares one compare engine with `agent-memory-summary`.

> **Ambient companions (instructions, not skills):** `agent-memory-read` (read the memory before you work) and `agent-memory-store` (capture durable notes as you work) ship as always-on instruction files — see **Always-on agent-memory instructions** below.

## Prerequisites

- **Required**: None — markdown and manually rendered HTML can be produced without dependencies
- **Recommended**: Python 3.9+ — used by `ramp-up` for PPTX generation and by `pr-explainer` for deterministic standalone HTML
- **Optional (`ramp-up` grounding)**: the bluebird MCP server — lets `ramp-up-explorer` cite Azure DevOps code and wiki pages in addition to the local workspace

If Python is unavailable, `ramp-up` still creates the markdown document and `pr-explainer` falls back to manually writing the same HTML structure.

## Usage

### architect — plan a complex feature or change

```
/zivi-development-marketplace:architect complex architect add a retry budget to the ingestion path
```

### simplified-architect — plan with a simplicity-first workflow

```
/zivi-development-marketplace:simplified-architect simple architect add a retry budget to the ingestion path
```

### ramp-up — explain an internal subsystem

Automatic triggering is intentionally strict: the current request must explicitly say `ramp up` or `rampup`. Generic requests to explain, teach, walk through, or onboard do not invoke this skill.

```
/zivi-development-marketplace:ramp-up monitoring flows in the auth service
```

### ramp-up — edit an existing explainer

```
/zivi-development-marketplace:ramp-up add a section about retries to the AuthMonitoringFlows explainer
```

### pr-explainer — explain a PR or local change

Automatic semantic triggering is intentionally disabled. Invoke the skill with its slash command or explicitly say `trigger pr-explainer`. Generic requests to explain, review, summarize, or walk through a PR do not invoke it.

```
/zivi-development-marketplace:pr-explainer https://dev.azure.com/org/project/_git/repo/pullrequest/41
/zivi-development-marketplace:pr-explainer explain my current staged and unstaged changes
trigger pr-explainer for PR 41
```

### agent-memory-summary — record a shipped change into memory

```
/zivi-development-marketplace:agent-memory-summary summarize my current changes into the platform memory
```

### agent-memory-drift — check a design summary against the code

```
/zivi-development-marketplace:agent-memory-drift check agent-memory/platform/Summary_RetryBudget.md for drift
```

## What it produces

| Output | Location | Requires |
|--------|----------|----------|
| `architect` spec | `./output/architect/{PlanName}-spec.md` | Nothing |
| `architect` plan | `./output/architect/{PlanName}-plan.md` | Nothing |
| `simplified-architect` spec | `./output/architect/{PlanName}-spec.md` | Nothing |
| `simplified-architect` plan | `./output/architect/{PlanName}-plan.md` | Nothing |
| `ramp-up` markdown | `./output/ramp-up/{Topic}.md` | Workspace + (optional) bluebird MCP |
| `ramp-up` presentation | `./output/ramp-up/{Topic}.pptx` | Python 3 |
| `pr-explainer` standalone HTML | `./output/{ChangeName}-PR-Explainer.html` | Python 3 recommended |
| `agent-memory-summary` record | `agent-memory/<team>/Summary_<name>.md` (+ `index.md` row) | Nothing |
| `agent-memory-drift` report | Drift verdict in chat (+ optional staged architecture-section edit) | Nothing |

## Always-on agent-memory instructions (optional)

`agent-memory-read` and `agent-memory-store` ship as **instructions**, not skills — so they apply **automatically, repo-wide** rather than being invoked. To use them, copy these files into a target repo's `.github/instructions/`:

- `agent-memory-read.instructions.md` — read the design memory before planning or changing code
- `agent-memory-store.instructions.md` — grade signals and capture durable notes during work
- `docs.instructions.md` — conventions for writing `agent-memory/` docs

They live in this marketplace repo under `.github/instructions-to-copy-to-target-repos/plugin-agentic-ai/agent-memory/` and apply repo-wide (`applyTo: "**"`). Plugins can't ship auto-applying instructions, so a `/plugin install` delivers the **skills** (`architect`, `simplified-architect`, `ramp-up`, `pr-explainer`, `agent-memory-summary`, `agent-memory-drift`); copying these instruction files is the manual, opt-in step for the read/store behaviors.

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
│   ├── simplified-architect/
│   │   ├── SKILL.md
│   │   └── evals/
│   │       └── evals.json
│   ├── agent-memory-summary/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── summary-format.md
│   ├── agent-memory-drift/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── compare-summary-to-code.md
│   │       └── verdict-report-template.md
│   ├── pr-explainer/
│   │   ├── SKILL.md
│   │   ├── assets/
│   │   │   └── example-spec.json
│   │   ├── references/
│   │   │   └── spec-schema.md
│   │   ├── scripts/
│   │   │   └── render_explainer.py
│   │   └── evals/
│   │       └── evals.json
│   └── ramp-up/
│       ├── SKILL.md
│       └── output-template.md
├── references/
│   ├── plan-guidance.md
│   └── spec-guidance.md
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

## Installing Python (recommended)

Install Python 3 for `ramp-up` PPTX generation and deterministic `pr-explainer` rendering:

- **Windows**: `winget install Python.Python.3` or download from [python.org](https://www.python.org/downloads/)
- **macOS**: `brew install python` or download from [python.org](https://www.python.org/downloads/)
- **Linux (apt)**: `sudo apt install python3`
- **Linux (dnf)**: `sudo dnf install python3`

The `python-pptx` pip package will be installed automatically on first use.
