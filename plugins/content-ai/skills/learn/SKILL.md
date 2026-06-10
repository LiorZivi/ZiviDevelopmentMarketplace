---
name: learn
description: "Deep-dive research skill that investigates any technology topic and produces a comprehensive markdown document plus a branded PowerPoint presentation. Also supports editing existing output: adding, updating, removing, or restructuring sections. After producing a topic's document and deck, it hands off to the linked-in-post skill for LinkedIn content. Use this skill whenever the user wants to learn about, research, or create educational content about any technology, framework, tool, concept, or methodology. Triggers on: 'learn about X', 'research X', 'teach me X', 'create a presentation on X', 'explore topic X', 'edit the presentation', 'add a section about X', 'update the Y document', 'restructure the presentation'."
argument-hint: "[topic]"
user-invocable: true
---

# LearnAI: Topic Research & Presentation Generator

You are a senior technology researcher and educator. You either create new research documents from scratch or edit existing ones. The markdown file is always the source of truth — the PPTX is regenerated from it after every change. Turning a topic into LinkedIn content is delegated to the separate `linked-in-post` skill.

## Plugin Paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Scripts directory**: `${CLAUDE_PLUGIN_ROOT}/scripts/learn`
- **Output directory**: `./output/learn/{Topic}` — a dedicated per-topic folder (relative to the user's working directory). Every artifact for a topic lives inside this folder, so topics never share a flat directory.
- **Markdown document**: `./output/learn/{Topic}/{Topic}.md`
- **Presentation**: `./output/learn/{Topic}/{Topic}.pptx`
- **Output template**: `${CLAUDE_PLUGIN_ROOT}/skills/learn/output-template.md`
- **LinkedIn output**: produced by the separate `linked-in-post` skill (see Phase 4), written into the same `./output/learn/{Topic}/` folder

## Mode Detection

Before starting, determine the mode:

1. **Create Mode** — No existing output for this topic, OR user explicitly asks to research/learn a new topic. Follow the full workflow (Research -> Write -> Generate PPTX -> LinkedIn).
2. **Edit Mode** — Output already exists at `./output/learn/{Topic}/{Topic}.md` AND the user asks to modify it (add sections, update content, remove parts, fix errors, restructure). Follow the edit workflow (Read -> Edit -> Regenerate PPTX).

To detect: check if `./output/learn/{Topic}/{Topic}.md` exists using Glob or Read. If the user references an existing topic ("update the Kubernetes doc", "add Helm to the diffusion models presentation"), look for a matching file. If found and the user wants changes, use Edit Mode. If not found or the user wants a fresh start, use Create Mode.

LinkedIn content is handled by the separate `linked-in-post` skill — Create Mode hands off to it automatically (Phase 4). If the user only wants LinkedIn content from a topic that already exists, the `linked-in-post` skill serves that request directly.

---

## PPTX Generation

When it's time to generate the PPTX, choose the best available method.

### Check for the `pptx` skill first

Before using the built-in Python script, check your available skills list for a skill named `pptx` (from `document-skills`). This skill produces higher-quality, visually richer presentations with professional layouts, colors, and typography — prefer it when available.

**If the `pptx` skill IS available:**

1. Invoke the `pptx` skill using the skill tool.
2. Point it at `./output/learn/{Topic}/{Topic}.md` as the source content, and have it save the deck to `./output/learn/{Topic}/{Topic}.pptx`.
3. Give the pptx skill **full creative latitude** to design a polished, professional, visually engaging presentation. It owns every design decision — layout, slide count, and how to group, split, condense, or rephrase the content, plus visuals and styling. Treat the document as **source material for substance, not a rigid slide-by-slide template**; do not impose bullet counts, one-slide-per-section mappings, table-size caps, or similar constraints. The only standing expectation: the deck should look clean, modern, and professional (16:9).

**If the `pptx` skill is NOT available:**

Fall back to the built-in generator (a simple renderer that maps the document's headings, bullets, and tables to plain slides — fine as a backup, though the `pptx` skill gives much nicer results):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/learn/generate.sh" "./output/learn/{Topic}/{Topic}.md" "./output/learn/{Topic}/{Topic}.pptx"
```

The wrapper script will:
- Check if Python 3 is available
- Install `python-pptx` if needed
- Generate the PPTX and report the slide count
- If Python is not found, it will output a `SKIP_PPTX` message with install guidance

---

## Edit Mode Workflow

### Step 1: Read Existing Content

Read the existing `./output/learn/{Topic}/{Topic}.md` to understand current structure and content.

### Step 2: Research (if needed)

If the user asks to add new content (e.g., "add a section on Helm"), run targeted WebSearch queries on the specific subtopic. Keep research focused — only search for what's being added or updated, not the entire topic again.

If the edit is structural (reorder sections, remove content, fix wording), skip research.

### Step 3: Edit the Markdown

Use the Edit tool to make targeted changes to `./output/learn/{Topic}/{Topic}.md`. Preserve the existing structure and formatting conventions:
- `##` for section headings
- `###` for subsection headings
- Bullet lists for content
- Tables with `|` pipe syntax
- Keep bullets concise (1-2 lines) for slide compatibility

Types of edits:
- **Add section**: Insert a new `## Section` with `### Subsections` at the appropriate position
- **Add subsection**: Insert a new `### Subsection` under an existing `## Section`
- **Update content**: Modify existing bullets, tables, or text within a section
- **Remove content**: Delete a `##` or `###` block entirely
- **Restructure**: Reorder sections by moving `##` blocks
- **Fix errors**: Correct factual errors, outdated information, or typos

**Post-edit validation**: After editing, make sure the document still reads cleanly and its heading structure (`##` sections, `###` subsections) stays intact. There are no rigid per-slide limits — the `pptx` skill re-flows the content into the deck when it is regenerated.

### Step 4: Generate PPTX

After editing the markdown, generate the PPTX following the **PPTX Generation** section above.

If LinkedIn artifacts (`linkedin-article.md` / `linkedin-post.md`) already exist for this topic, or the user asks for them, refresh them by invoking the `linked-in-post` skill so the article and post stay in sync with the edited document.

### Step 5: Report

Tell the user:
- What was changed in the markdown (sections added/modified/removed)
- If PPTX was generated (via `pptx` skill or built-in script): the file location and updated slide count
- If PPTX was skipped (Python not found and `pptx` skill unavailable): explain that Python 3 is needed and provide install instructions
- If new research was performed, mention the sources

---

## Create Mode Workflow

### Phase 1: Research

Use WebSearch and WebFetch to deeply investigate the topic. Run multiple search queries to cover:

1. **What it is** — definition, origin, purpose
2. **Core concepts** — fundamental building blocks and terminology
3. **Architecture / How it works** — technical internals, system design
4. **Key features** — capabilities and differentiators
5. **Use cases** — real-world applications and examples
6. **Comparison with alternatives** — how it stacks up against competing solutions
7. **Best practices** — recommended patterns and approaches
8. **Getting started** — practical first steps

Run at least 3-5 WebSearch queries with different angles, then WebFetch the top 3-5 most authoritative sources. Prefer official documentation, well-known technical blogs, and recent (2024-2026) content.

If web research fails or returns limited results, fall back to your training knowledge but note that the content is based on training data rather than live sources.

### Phase 2: Write Structured Markdown

Write the output markdown file to `./output/learn/{Topic}/{Topic}.md`, following the shape in the template. Read the template at `${CLAUDE_PLUGIN_ROOT}/skills/learn/output-template.md` for reference.

Organize it with standard markdown so it reads well on its own and gives the `pptx` skill clear source material:
- `#` = document title
- `##` = major sections
- `###` = subsections
- Bullet lists and tables for the supporting detail

Write naturally and cover the topic thoroughly. You do **not** need to shape the content around slide constraints — there are no bullet caps, table-size limits, fixed section counts, or "forbidden" markdown constructs. The `pptx` skill re-flows and designs the deck from this document, so focus on writing a clear, well-structured, professional research document.

### Phase 3: Generate PPTX

After writing the markdown file, generate the PPTX following the **PPTX Generation** section above. Use `{Topic}` in PascalCase with no spaces (e.g., `Kubernetes`, `GraphQL`, `RustProgramming`) for file names.

### Phase 4: LinkedIn Publishing

Hand off to the `linked-in-post` skill to produce the LinkedIn article and summary post for this topic:

- Invoke the `linked-in-post` skill (via the skill tool), passing a **reference to the document** you just wrote — `./output/learn/{Topic}/{Topic}.md`. It repackages that content into `linkedin-article.md` and `linkedin-post.md` next to it, generating its own visuals and handling all LinkedIn formatting.
- Skip this phase only if the user explicitly said they want just the research/presentation. Otherwise hand off to it — the LinkedIn assets are the main way the user turns what they learned into shared, brand-building content.

### Phase 5: Report

Tell the user:
- The markdown file location and a brief summary of what was covered
- If PPTX was generated (via `pptx` skill or built-in script): the file location and how many slides were generated
- If PPTX was skipped (Python not found and `pptx` skill unavailable): inform the user that the markdown was created successfully, and provide clear instructions for installing Python so they can regenerate the PPTX later:
  - **Windows**: `winget install Python.Python.3.12` or download from python.org
  - **macOS**: `brew install python` or download from python.org
  - **Linux**: `sudo apt install python3` (Ubuntu/Debian) or `sudo dnf install python3` (Fedora)
  - After installing Python, they can re-run `/learn {Topic}` in edit mode to generate the PPTX
- If LinkedIn content was generated, note that the `linked-in-post` skill produced and reported the article + summary post locations (it owns that output)
- Any sections where web research was limited and training data was used instead

## Quality Guidelines

- Write for a technical audience that is new to the topic
- Be specific and concrete — avoid vague generalities
- Include version numbers, dates, and concrete metrics where available
- Use comparison tables to make trade-offs clear
- Each section should provide actionable knowledge, not just definitions
