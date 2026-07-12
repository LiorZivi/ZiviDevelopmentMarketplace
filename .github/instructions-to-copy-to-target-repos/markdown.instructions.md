---
applyTo: "**/*.md"
---

# Markdown authoring style (repo-wide)

Write every Markdown file with **one line per paragraph** — no hard-wrapping or manual line breaks at a fixed column (~80 chars). Let each paragraph flow as one continuous line and rely on the editor's soft-wrap. In Markdown a single newline inside a paragraph renders as a space, but in the raw file it makes prose look chopped and produces noisy word-level diffs whenever a sentence changes.

Scope is **every `.md` file anywhere in the repo** — root docs (`README.md`, `spec.md`, `BUILD_PROMPT.md`), `human-docs\`, `agent-memory\`, `.github\` (instructions and skills), and `output\architect\` — so `applyTo` is `**/*.md` rather than a fixed folder list (a folder list would miss the root-level docs).

## Rules

- **One continuous line per paragraph.** Break lines only between blocks (separated by a blank line), never mid-sentence to wrap.
- **One line per list item**, including its wrapped continuation text. Keep separate items on their own lines and preserve nested-list indentation.
- **One line per blockquote paragraph**, with a single leading `>`.
- **Never reflow inside block elements.** Leave fenced code blocks, tables (one row per line), headings, horizontal rules, and YAML front matter exactly as authored.
- Keep one blank line between blocks (headings, paragraphs, lists, code, tables).
