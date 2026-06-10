# content-ai

AI-powered content generation plugin with skills for research, presentations, LinkedIn publishing, and architecture planning.

## Skills

### learn
Deep-dive research skill that investigates any technology topic and produces a comprehensive markdown document plus a branded PowerPoint presentation. It can then repackage them into LinkedIn content: a long-form newsletter article (with slide images embedded) and a short summary post that links to it, formatted for LinkedIn's editors so they're ready to paste.

### ramp-up
Workspace-grounded onboarding skill that produces a markdown explainer plus matching PPTX deck about an internal subsystem, flow, or codebase area. Every claim is cited to a real file, wiki page, or commit in the user's workspace or Azure DevOps — never the open web or training data. Uses the `ramp-up-explorer` sub-agent to scan workspace + Azure DevOps (via the bluebird MCP server) and return ranked citations per section.

### architect
Planning skill that turns a task into two artifacts: a PM-level `spec.md` and a phased `plan.md`. Uses the `plan-architect` and `plan-reviewer` sub-agents to draft and score the plan.

## Prerequisites

- **Required**: None — the markdown output works without any dependencies
- **Optional**: Python 3.9+ — needed for PPTX (PowerPoint) generation
- **Optional (LinkedIn slide images)**: Microsoft PowerPoint (Windows) or LibreOffice + PyMuPDF — needed to auto-export slide images into the LinkedIn article. Without them, the article is still written with image placeholders you can fill by exporting slides manually.

If Python is not installed, the skill will create the markdown document and guide you through installing Python for PPTX support.

## Usage

### learn — create a new topic

```
/zivi-development-marketplace:learn Kubernetes
```

### learn — edit an existing topic

```
/zivi-development-marketplace:learn add a section on Helm to the Kubernetes document
```

### learn — turn a topic into LinkedIn content

```
/zivi-development-marketplace:learn make a LinkedIn article and summary post from the Kubernetes document
```

### ramp-up — explain an internal subsystem

```
/zivi-development-marketplace:ramp-up monitoring flows in the auth service
```

### ramp-up — edit an existing explainer

```
/zivi-development-marketplace:ramp-up add a section about retries to the AuthMonitoringFlows explainer
```

### architect — plan a feature or change

```
/zivi-development-marketplace:architect add a retry budget to the ingestion path
```

## What it produces

| Output | Location | Requires |
|--------|----------|----------|
| `learn` markdown | `./output/learn/{Topic}.md` | Nothing |
| `learn` presentation | `./output/learn/{Topic}.pptx` | Python 3 |
| `learn` LinkedIn article | `./output/learn/{Topic}-linkedin-article.md` | Nothing |
| `learn` LinkedIn post | `./output/learn/{Topic}-linkedin-post.md` | Nothing |
| `learn` slide images | `./output/learn/images/{Topic}-slide-NN.png` | PowerPoint or LibreOffice |
| `ramp-up` markdown | `./output/ramp-up/{Topic}.md` | Workspace + (optional) bluebird MCP |
| `ramp-up` presentation | `./output/ramp-up/{Topic}.pptx` | Python 3 |
| `architect` spec | `./output/architect/{PlanName}-spec.md` | Nothing |
| `architect` plan | `./output/architect/{PlanName}-plan.md` | Nothing |

## Structure

```
content-ai/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── plan-architect.md
│   ├── plan-reviewer.md
│   └── ramp-up-explorer.md
├── skills/
│   ├── architect/
│   │   └── SKILL.md
│   ├── learn/
│   │   ├── SKILL.md
│   │   ├── output-template.md
│   │   └── linkedin-template.md
│   └── ramp-up/
│       ├── SKILL.md
│       └── output-template.md
├── scripts/
│   ├── learn/
│   │   ├── generate.sh
│   │   ├── export_slides.sh
│   │   ├── md_to_pptx.py
│   │   ├── export_slides.py
│   │   ├── pptx_engine.py
│   │   ├── requirements.txt
│   │   └── themes/
│   │       ├── __init__.py
│   │       └── anthropic.py
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

If you want PPTX generation, install Python 3:

- **Windows**: `winget install Python.Python.3` or download from [python.org](https://www.python.org/downloads/)
- **macOS**: `brew install python` or download from [python.org](https://www.python.org/downloads/)
- **Linux (apt)**: `sudo apt install python3`
- **Linux (dnf)**: `sudo dnf install python3`

The `python-pptx` pip package will be installed automatically on first use.
