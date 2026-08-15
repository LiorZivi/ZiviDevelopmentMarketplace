---
applyTo: "**"
---

# Read the design memory for intent before you plan or change code

This repo keeps a durable **design memory** under `agent-memory/`, organized by team/area folder and committed alongside the code. It complements the repository by preserving context a future reader cannot recover from the implementation itself: **why** decisions were made, which alternatives were rejected, and which constraints or non-goals shaped the result.

The source code, tests, configuration, and repository documentation remain authoritative for **what** the system currently does and **how** it is structured. Do not use memory as a substitute for reading them, and do not rely on a memory entry that merely restates facts visible in the repository.

## Before you plan or change code

If an `agent-memory/` folder exists, read it directly (you can grep it too — it's committed in this repo):

1. **Read the area's memory** at `agent-memory/<team>/`:
   - `index.md` first — it lists the core docs and links the per-feature design summaries (including cross-team ones under `agent-memory/cross-team/`).
   - `memory-notes.md` (if present) — short, dated, graded notes containing non-obvious rationale, decisions, constraints, and gotchas. Apply the rows whose **When to read** trigger matches what you are about to plan or change.
   - the relevant `Summary_<name>.md` entries it references, for the feature area you are touching; use them for design intent and decision context, then verify current implementation details in the repository.
   - `projectBrief.md` — the area's purpose and context; verify current component and file locations in the repository.
   - `systemPatterns.md` — durable intent, constraints, and hazards; verify conventions that can be observed from code instead of treating memory as authoritative.
2. **Check the org-wide memory** at `agent-memory/global/index.md` (if present) for designs that span the whole codebase, with no single owning area.
3. **Name which memory entries informed your plan** and the non-code context they added, so the rationale you relied on is explicit.

A change often spans more than one component or layer. If yours touches only one, confirm whether the others also need updating.

> Companion pieces: `agent-memory-store` (the note-capture instruction that pairs with this one), and the `agent-memory-summary` and `agent-memory-drift` skills (which record and validate larger design summaries).
