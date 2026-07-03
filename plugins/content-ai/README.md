# content-ai

AI-powered content generation plugin with skills for research, presentations, LinkedIn publishing, and architecture planning.

## Skills

### learn
Deep-dive research skill that investigates any technology topic and produces a comprehensive markdown document plus a branded PowerPoint presentation. Once the document and deck exist, it hands off to the `linked-in-post` skill to generate LinkedIn content.

### linked-in-post
Repackages any source document you reference into ready-to-post LinkedIn content: a **paste-ready** newsletter article (an HTML file you open in a browser and copy — headings, subheadings, bold, italic, lists, quotes, code blocks, and links all survive the paste into LinkedIn), a ready-to-paste newsletter announcement, and an auto-generated cover image (1920×1080). Independent of `learn` — works on any document — but `learn` can trigger it automatically.

### ramp-up
Workspace-grounded onboarding skill that produces a markdown explainer plus matching PPTX deck about an internal subsystem, flow, or codebase area. Every claim is cited to a real file, wiki page, or commit in the user's workspace or Azure DevOps — never the open web or training data. Uses the `ramp-up-explorer` sub-agent to scan workspace + Azure DevOps (via the bluebird MCP server) and return ranked citations per section.

### architect
Planning skill that turns a task into two artifacts: a PM-level `spec.md` and a phased `plan.md`. Uses the `plan-architect` and `plan-reviewer` sub-agents to draft and score the plan.

## Prerequisites

- **Required**: None — the markdown output works without any dependencies
- **Optional**: Python 3.9+ — needed for PPTX (PowerPoint) generation
- **Optional (LinkedIn visuals)**: an image- or diagram-generation tool/skill — `linked-in-post` uses it to generate the article's visuals from the content. Without one, the article is written with labeled image placeholders you can fill in later.

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

### linked-in-post — turn a topic into LinkedIn content

```
/zivi-development-marketplace:linked-in-post make a LinkedIn article and announcement from the Kubernetes topic
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
| `learn` markdown | `./output/learn/{Topic}/{Topic}.md` | Nothing |
| `learn` presentation | `./output/learn/{Topic}/{Topic}.pptx` | Python 3 |
| `linked-in-post` article (paste-ready) | `{DocName}-LinkedIn-Article.html` next to the source doc | Nothing |
| `linked-in-post` article (source) | `{DocName}-LinkedIn-Article.md` next to the source doc | Nothing |
| `linked-in-post` announcement | `{DocName}-LinkedIn-Announcement.md` next to the source doc | Nothing |
| `linked-in-post` cover image | `images/cover.png` (1920×1080) | image tool |
| `linked-in-post` visuals | `images/` next to the article | image/diagram tool |
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
│   │   └── output-template.md
│   ├── linked-in-post/
│   │   └── SKILL.md
│   └── ramp-up/
│       ├── SKILL.md
│       └── output-template.md
├── scripts/
│   ├── learn/
│   │   ├── generate.sh
│   │   ├── md_to_pptx.py
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
