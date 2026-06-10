---
name: learn
description: "Deep-dive research skill that investigates any technology topic and produces a comprehensive markdown document plus a branded PowerPoint presentation, and can then repackage them into LinkedIn content — a long-form newsletter ARTICLE plus a short summary POST that links to it, formatted for LinkedIn's editors so they are ready to paste. Also supports editing existing output: adding, updating, removing, or restructuring sections. Use this skill whenever the user wants to learn about, research, or create educational content about any technology, framework, tool, concept, or methodology, or wants to publish that content to LinkedIn. Triggers on: 'learn about X', 'research X', 'teach me X', 'create a presentation on X', 'explore topic X', 'edit the presentation', 'add a section about X', 'update the Y document', 'restructure the presentation', 'make a LinkedIn article', 'turn this into a LinkedIn post', 'write a LinkedIn newsletter issue about X', 'create a summary post for X', 'publish X to LinkedIn'."
argument-hint: "[topic]"
user-invocable: true
---

# LearnAI: Topic Research & Presentation Generator

You are a senior technology researcher and educator. You either create new research documents from scratch or edit existing ones. The markdown file is always the source of truth — the PPTX is regenerated from it after every change.

## Plugin Paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Scripts directory**: `${CLAUDE_PLUGIN_ROOT}/scripts/learn`
- **Output directory**: `./output/learn` (relative to user's working directory)
- **Output template**: `${CLAUDE_PLUGIN_ROOT}/skills/learn/output-template.md`
- **LinkedIn template**: `${CLAUDE_PLUGIN_ROOT}/skills/learn/linkedin-template.md`
- **Slide images directory**: `./output/learn/images`
- **LinkedIn outputs**: `./output/learn/{Topic}-linkedin-article.md` and `./output/learn/{Topic}-linkedin-post.md`

## Mode Detection

Before starting, determine the mode:

1. **Create Mode** — No existing output for this topic, OR user explicitly asks to research/learn a new topic. Follow the full workflow (Research -> Write -> Generate PPTX).
2. **Edit Mode** — Output already exists at `./output/learn/{Topic}.md` AND the user asks to modify it (add sections, update content, remove parts, fix errors, restructure). Follow the edit workflow (Read -> Edit -> Regenerate PPTX).
3. **LinkedIn Mode** — `./output/learn/{Topic}.md` already exists and the user asks specifically for LinkedIn content (e.g., "make a LinkedIn article from the Kubernetes doc", "write a summary post for X"). Skip research/writing/PPTX and run only the **LinkedIn Publishing** section against the existing files.

To detect: check if `./output/learn/{Topic}.md` exists using Glob or Read. If the user references an existing topic ("update the Kubernetes doc", "add Helm to the diffusion models presentation"), look for a matching file. If found and the user wants changes, use Edit Mode. If not found or the user wants a fresh start, use Create Mode. If a matching file exists and the user only wants LinkedIn content, use LinkedIn Mode.

---

## PPTX Generation

When it's time to generate the PPTX, choose the best available method.

### Check for the `pptx` skill first

Before using the built-in Python script, check your available skills list for a skill named `pptx` (from `document-skills`). This skill produces higher-quality, visually richer presentations with professional layouts, colors, and typography — prefer it when available.

**If the `pptx` skill IS available:**

1. Invoke the `pptx` skill using the skill tool
2. Instruct it to create a presentation from the structured markdown at `./output/learn/{Topic}.md`
3. Save the output to `./output/learn/{Topic}.pptx`
4. Provide the following context to the pptx skill:
   - The markdown uses `#` for the presentation title, `##` for section divider slides, and `###` for content slides
   - Each `###` subsection should map to one or more slides — use your judgment on how to split content for readability
   - Bullet lists should remain as slide bullets; tables should be rendered as slide tables
   - The subtitle (blockquote after `#`) should appear on the title slide
   - Use a clean, professional design with 16:9 layout

**If the `pptx` skill is NOT available:**

Fall back to the built-in generator:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/learn/generate.sh" "./output/learn/{Topic}.md" "./output/learn/{Topic}.pptx"
```

The wrapper script will:
- Check if Python 3 is available
- Install `python-pptx` if needed
- Generate the PPTX and report the slide count
- If Python is not found, it will output a `SKIP_PPTX` message with install guidance

---

## LinkedIn Publishing

Once the document and presentation exist, repackage them into two ready-to-post LinkedIn assets:

1. A **newsletter article** -> `./output/learn/{Topic}-linkedin-article.md` — the long-form issue.
2. A **summary post** -> `./output/learn/{Topic}-linkedin-post.md` — a short feed teaser that links to the article.

`{Topic}.md` is the source of truth for substance; the presentation slides become the article's visuals. Why two artifacts: a short native post is what LinkedIn's feed rewards with reach, while the article/newsletter is the durable, subscribable home for the full content — the post exists to drive people to the article.

**Read the format spec at `${CLAUDE_PLUGIN_ROOT}/skills/learn/linkedin-template.md` before writing.** It defines both artifacts precisely, including the critical difference that articles use real rich text while feed posts do not.

### Step 1: Export slide images

Turn the deck into per-slide PNGs the user can drop into the article:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/learn/export_slides.sh" "./output/learn/{Topic}.pptx" "./output/learn/images" "{Topic}"
```

This writes `./output/learn/images/{Topic}-slide-01.png`, `-02`, … in deck order (title slide first, then each section), and prints a `SLIDE NN -> path` manifest plus a final `EXPORTED <n>`. It uses Microsoft PowerPoint (Windows) if present, then LibreOffice, and prints `SKIP_EXPORT` if neither is available.

If export is skipped — or the PPTX was never generated — still write the article: keep the `〔🖼 SLIDE NN〕` markers and tell the user how to export slides by hand (PowerPoint: File > Export > PNG). **Never block article creation on image export.** Reference only the filenames the manifest actually reported.

### Step 2: Write the newsletter article

Follow PART A of the template. The essentials:

- Articles support **real rich text**, so write clean Markdown (headings, bold, lists, images) — do **not** use the Unicode-bold trick here; that is only for feed posts.
- **Reframe** the deck's terse bullets into flowing, plain-English prose. The document is a skeleton; the article is the narrative a reader enjoys. Aim for a 3–5 minute read (~600–1,200 words) and curate to 4–7 sections.
- Place **3–6** slide images where they reinforce the text (the architecture image near the architecture section, the comparison-table slide near the comparison), using the real exported filenames at the `〔🖼 SLIDE NN〕` markers.
- Open the file with the template's "HOW TO POST" comment block so publishing is mechanical, and close with a **Key takeaways** list and a subscribe CTA.

### Step 3: Write the summary post

Follow PART B of the template. The essentials:

- The feed has no formatting, so use **Unicode bold/italic** for emphasis, a 2-line **hook** above the "…see more" fold, short scannable lines, and 3–6 hashtags.
- Keep links **out of the post body** (LinkedIn throttles them) — provide a ready-to-paste **first comment** containing the article link instead.
- End with a subscribe/connect CTA so each post compounds the user's brand.

### Step 4: Personalize and report

Fill `{Author}`, `{role}`, and `{Newsletter name}` from what you know about the user; if genuinely unknown, leave the placeholder and ask them to fill it once — don't invent a newsletter name. Then tell the user both file locations and the one-line publish flow.

---

## Edit Mode Workflow

### Step 1: Read Existing Content

Read the existing `./output/learn/{Topic}.md` to understand current structure and content.

### Step 2: Research (if needed)

If the user asks to add new content (e.g., "add a section on Helm"), run targeted WebSearch queries on the specific subtopic. Keep research focused — only search for what's being added or updated, not the entire topic again.

If the edit is structural (reorder sections, remove content, fix wording), skip research.

### Step 3: Edit the Markdown

Use the Edit tool to make targeted changes to `./output/learn/{Topic}.md`. Preserve the existing structure and formatting conventions:
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

**Post-edit validation**: After editing, verify that modified `###` subsections still comply with the one-slide rule (max 7 bullets OR max 8 table rows, not both). If new content exceeds limits, split into multiple `###` subsections. Also ensure no forbidden constructs (code blocks, H4+ headings, standalone paragraphs) were introduced.

### Step 4: Generate PPTX

After editing the markdown, generate the PPTX following the **PPTX Generation** section above.

If LinkedIn artifacts (`{Topic}-linkedin-article.md` / `{Topic}-linkedin-post.md`) already exist for this topic, or the user asks for them, refresh them too by following the **LinkedIn Publishing** section so the article and post stay in sync with the edited document.

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

Write the output markdown file to `./output/learn/{Topic}.md` using **exactly** the structure defined in the template. Read the template file at `${CLAUDE_PLUGIN_ROOT}/skills/learn/output-template.md` for the precise format.

The structure must be followed strictly because the PPTX generator parses it by heading levels:
- `#` = presentation title
- `##` = section slides
- `###` = content slides
- Bullet lists = bullet slides
- Tables = table slides

### One-Slide-Per-Subsection Rule

Each `###` subsection maps to exactly ONE slide. To ensure this:

- Max 7 bullet points per `###` (the parser splits at 7)
- Max 8 table data rows per `###` (the parser splits at 8, header row excluded)
- A `###` MUST have EITHER bullets OR one table, not both (each generates a separate slide)
- If content doesn't fit, split into two `###` subsections with distinct titles
- Aim for 8-12 `##` sections total

### Forbidden Markdown Constructs

The PPTX parser only handles H1/H2/H3, bullets, and tables. The following constructs break or bloat slides — **never use them** in output:

- **No code blocks** (triple backticks): Every line inside leaks as a bullet point. Paraphrase code as regular bullets instead (e.g., "Run `claude --worktree` to start" as a bullet).
- **No `####` or `#####` headings**: The parser ignores these structurally — they become plain bullet text. Use only `###` for content slides.
- **No `## Table of Contents`**: TOC lines become bullet slides. Omit entirely.
- **No footer/attribution lines** (e.g., `*Guide updated on...*`): These become bullets in the last subsection. Omit from markdown.
- **No standalone paragraphs under `##`** before the first `###`: These create an unnamed subsection with its own slide. Move text into the first `###` as bullets, or remove it.
- **No blockquotes** (`> ...`) except the subtitle line after `# Title`: All other blockquotes are treated as plain text / bullets.
- **No `---` horizontal rules** inside sections: These are ignored but add noise.

### Phase 3: Generate PPTX

After writing the markdown file, generate the PPTX following the **PPTX Generation** section above. Use `{Topic}` in PascalCase with no spaces (e.g., `Kubernetes`, `GraphQL`, `RustProgramming`) for file names.

### Phase 4: LinkedIn Publishing

Repackage the document and presentation into LinkedIn content by following the **LinkedIn Publishing** section above — produce both the newsletter article and the summary post.

Skip this phase only if the user explicitly said they want just the research/presentation. Otherwise generate both artifacts: they are cheap to produce and are the main way the user turns what they learned into shared, brand-building content.

### Phase 5: Report

Tell the user:
- The markdown file location and a brief summary of what was covered
- If PPTX was generated (via `pptx` skill or built-in script): the file location and how many slides were generated
- If PPTX was skipped (Python not found and `pptx` skill unavailable): inform the user that the markdown was created successfully, and provide clear instructions for installing Python so they can regenerate the PPTX later:
  - **Windows**: `winget install Python.Python.3.12` or download from python.org
  - **macOS**: `brew install python` or download from python.org
  - **Linux**: `sudo apt install python3` (Ubuntu/Debian) or `sudo dnf install python3` (Fedora)
  - After installing Python, they can re-run `/learn {Topic}` in edit mode to generate the PPTX
- The LinkedIn article and summary post file locations, plus a one-line reminder of how to publish: Write article -> select your newsletter -> paste the article, then publish the teaser post and put the article link in its first comment
- Any sections where web research was limited and training data was used instead

## Quality Guidelines

- Write for a technical audience that is new to the topic
- Be specific and concrete — avoid vague generalities
- Include version numbers, dates, and concrete metrics where available
- Use comparison tables to make trade-offs clear
- Each section should provide actionable knowledge, not just definitions
