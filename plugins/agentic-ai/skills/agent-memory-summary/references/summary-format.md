# Memory summary format

The single source of truth for what a `Summary_<name>.md` looks like — shared by **both** modes of the `agent-memory-summary` skill. Mode A embeds a real spec and extracts a real plan into this shape; Mode B reverse-engineers the same shape from a code change. The output file is identical either way; only the source of the `## Spec` and `## Plan` content differs.

## The summary file

Write `Summary_<name>.md` with exactly this structure:

```
# {spec title} — Memory Summary

**Team**: {team}  ·  **Date**: {today YYYY-MM-DD}

## Spec

{the full spec — see "Spec shape" below — verbatim from the spec file (Mode A), or reverse-engineered from the change (Mode B); every section, unedited, **except** the spec's own `**Created**` line, which is dropped — the summary's single date is the header `**Date**` above}

## Plan

**One-line summary**: {the plan's leading `>` blockquote}

### Architecture Plan

{the plan's architecture section — the one headed `## Architecture plan` OR `## Architecture Summary`, whichever is present}

### Resolved Decisions

{the plan's `## Resolved Decisions` section — include only if the plan has one}
```

- **Header** — `{team}` is the owning team; for a cross-team design use the comma-separated team list, and for an org-wide design use `Global (org-wide)`. `**Date**` is the date the summary was last written or updated (today when you write it) — it is the summary's **single** date; the summary carries no separate `**Created**` line.
- **The full spec is the summary's product half** — the durable "why" and "what". Drop the spec's own `**Created**` line when embedding (the summary's single date is the header `**Date**`); the spec keeps its product-level `## Open Questions`, so the Plan section deliberately does **not** repeat Open Questions.
- **From the plan, include only the high-level design above.** Deliberately omit the phases, steps, deliverables, risks table, review metadata, the plan's `**Created**` line, and the plan's `## Open Questions` — they're tactical or go stale once shipped.
- **Omit the `### Resolved Decisions` subsection entirely** when the plan doesn't have one (don't leave an empty heading).

## Spec shape

The spec is a **product-level** requirements document (the `/architect` spec shape). Sections, in order:

1. `# {Title} — Spec`
2. a single `>` blockquote — the one-line product summary of what's being built
3. *(optional)* `**Issue**: [link] — "<title>"` when an issue / PR reference exists
4. `## Goal`
5. `## Background & Context`
6. `## Users & Audience`
7. `## User-Facing Behavior`
8. `## Success Criteria`
9. `## Non-Goals / Out of Scope`
10. `## Constraints`
11. `## Open Questions`

**Single date — drop `**Created**`:** the `/architect` source spec carries a `**Created**: {YYYY-MM-DD}` line just under the blockquote; **omit it when embedding**. The summary's only date is the header `**Date**` (the date it was last updated).

**Product-language discipline:** no code snippets, no file paths, no line numbers, no symbol names — describe behavior and outcomes in the audience's terms. SQL / shell queries are allowed **only** inside Success Criteria, as the acceptance test.

## Plan high-level shape

Only the plan's high-level design lands in the summary:

- a `>` one-line summary of the **implementation approach**
- `## Architecture plan` — 2–6 sentences on **how** it's built: the components, data flow, and integration points. Unlike the spec, this **may** name concrete files / symbols / config keys.
- *(optional)* `## Resolved Decisions` — include only when there's a notable design decision worth recording.

Never carry the plan's phases, steps, deliverables, risks table, or its own `**Created**` / `## Open Questions` into the summary.
