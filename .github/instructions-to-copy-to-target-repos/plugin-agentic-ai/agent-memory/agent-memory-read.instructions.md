---
applyTo: "**"
---

# Read the design memory before you plan or change code

This repo keeps a durable **design memory** under `agent-memory/`, organized by team/area folder and committed alongside the code. Before you plan or modify code, read the relevant memory so your work builds on the recorded design, decisions, and gotchas — not a blank slate.

## Before you plan or change code

If an `agent-memory/` folder exists, read it directly (you can grep it too — it's committed in this repo):

1. **Read the area's memory** at `agent-memory/<team>/`:
   - `index.md` first — it lists the core docs and links the per-feature design summaries (including cross-team ones under `agent-memory/cross-team/`).
   - `memory-notes.md` (if present) — short, dated, graded notes: lessons, decisions, constraints, and gotchas. Apply the rows whose **When to read** trigger matches what you are about to plan or change.
   - the relevant `Summary_<name>.md` entries it references, for the feature area you are touching.
   - `projectBrief.md` — what this area is and where its pieces live.
   - `systemPatterns.md` — the durable conventions and hazards.
2. **Check the org-wide memory** at `agent-memory/global/index.md` (if present) for designs that span the whole codebase, with no single owning area.
3. **Name which memory entries informed your plan** in your response, so the context you relied on is explicit.

A change often spans more than one component or layer. If yours touches only one, confirm whether the others also need updating.

> Companion pieces: `agent-memory-store` (the note-capture instruction that pairs with this one), and the `agent-memory-summary` and `agent-memory-drift` skills (which record and validate larger design summaries).
