---
applyTo: "agent-memory/**,human-docs/**"
---

# Documentation conventions (`agent-memory\` and `human-docs\`)

When writing or editing any doc under `agent-memory\` or `human-docs\`:

- **Always reference files and folders by their full path from the project root.** Example: write `src\<module>\<area>\<file>.ext`, not `<file>.ext`, not `<area>\<file>.ext`, and not a language's dotted/module form. A reader must be able to copy the path and find the file without guessing where it lives.
- Use **Windows-style backslash** separators in these root-relative paths.
- For installed third-party tools, give a **locatable hint** (where the binary or install lives) rather than a bare tool name, when the reader may need to find it.
- For generated artifacts (templates, build output, produced media), give the **real on-disk location** rather than a vague label.
- **Exceptions — keep these as written:**
  - Genuine code identifiers: entry-point literals and real `import` / `from ... import` (or equivalent) statements inside code blocks.
  - Real shell invocations of a tool, e.g. `<tool> run --json`.
  - Markdown link targets `[text](path)` must stay forward-slash (they are URLs).
  - ASCII tree diagrams may keep forward-slash directory indicators.
- **The split is by audience:** `agent-memory\` is written to be read by the **coding agent** (keep it short and high-signal); `human-docs\` is written to be read by **humans** (may be narrative). When behavior changes, update `agent-memory\` and the README so the agent's context stays accurate; update `human-docs\` when a human asks.
