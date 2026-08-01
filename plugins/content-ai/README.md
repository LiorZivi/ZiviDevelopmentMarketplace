# content-ai

AI-powered content generation plugin with skills for deep-dive research, branded presentations, and LinkedIn publishing.

## Skills

### learn
Deep-dive research skill that investigates any technology topic and produces a comprehensive markdown document plus a branded PowerPoint presentation. Once the document and deck exist, it hands off to the `linked-in-post` skill to generate LinkedIn content.

### linked-in-post
Repackages any source document you reference into ready-to-post LinkedIn content: a **paste-ready** newsletter article (an HTML file you open in a browser and copy — headings, subheadings, bold, italic, lists, quotes, code blocks, and links all survive the paste into LinkedIn), a ready-to-paste newsletter announcement, and an auto-generated cover image (1920×1080). Every article ends with Lior Zivi's fixed author signature. Independent of `learn` — works on any document — but `learn` can trigger it automatically.

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

## Structure

```
content-ai/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── learn/
│   │   ├── SKILL.md
│   │   └── output-template.md
│   └── linked-in-post/
│       └── SKILL.md
├── scripts/
│   └── learn/
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
