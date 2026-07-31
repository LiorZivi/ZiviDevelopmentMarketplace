---
name: simplified-architect
description: Use only when the user explicitly says "simple architect".
---

# Simplified Architect

Create a PM-level spec and a phased implementation plan directly through two deliberate rounds of user questioning.

## Shared guidance

- Spec rules: `../../references/spec-guidance.md`
- Plan rules: `../../references/plan-guidance.md`

Read both files before drafting or revising artifacts.

## Paths

- Output directory: `./output/architect/`
- `{PlanName}` is PascalCase derived from the task.
- Spec: `./output/architect/{PlanName}-spec.md`
- Plan: `./output/architect/{PlanName}-plan.md`

## Core planning principle

Prefer the simplest clean design that satisfies the confirmed goal.

When broader scenario coverage, defensive flexibility, or an edge case would make the design harder to understand or implement:

1. Treat it as out of scope in the default design.
2. Record and explain the resulting gap plainly.
3. Ask whether the user wants that gap promoted into scope.
4. Add the complexity only when the user chooses it or the confirmed goal cannot work safely without it.

Do not silently ignore correctness, security, data-loss, or compatibility requirements. Simplicity means avoiding speculative complexity, not accepting a broken design.

## Mode detection

- **Create**: no matching spec and plan exist. Run the full workflow.
- **Revise**: matching artifacts exist. Read them, interview the user about the requested change, and revise both when product intent changes.

## Workflow

### 1. Scan the workspace

Inspect the relevant repository structure, code, tests, configuration, documentation, and existing patterns. Learn technical facts from the workspace rather than asking the user to supply them.

### 2. First questioning round: understand the purpose

Ask one question at a time through the host picker. Prefer choices when they capture the real decision; use free text when they do not.

Continue until all material areas are clear:

- Goal and problem being solved
- Users and audience
- User-visible behavior
- Scope and non-goals
- Success criteria
- Constraints and integrations
- Behavioral defaults
- Compatibility or migration expectations
- Failure behavior and meaningful risks
- Simplicity trade-offs and intentionally uncovered edge cases

Questions should be thorough, grounded in the scan, and limited to decisions only the user can make. Do not impose a fixed question count or stop because a small quota was reached.

Before drafting, summarize the understood intent internally and check that no answer conflicts with another. Ask another question whenever the purpose or acceptance boundary is still ambiguous.

### 3. Draft the spec and plan

Write both artifacts using the shared guidance.

Use `Pragmatic` as the plan approach unless the user explicitly requests another label. Keep the plan focused on the simplest implementation that fulfills the spec. Put excluded scenarios in the spec's Non-Goals and any implementation consequence in plan risks or open questions.

### 4. Second questioning round: challenge the drafts

Read the complete draft spec and plan together. Look for:

- Assumptions that became visible only after decomposition
- Conflicts between product intent and implementation steps
- Missing acceptance boundaries
- Dependencies or migrations that change the scope
- Edge cases whose omission creates a meaningful gap
- Places where a simpler design is possible
- Places where the simple path has a trade-off the user should consciously accept

Ask one focused question at a time about every material decision found. Always perform this round; if the drafts expose no unresolved decision, ask the user to confirm the summarized simple path and its explicitly listed gaps.

### 5. Revise both artifacts

Apply the second-round answers to both spec and plan wherever relevant. Re-run the shared pre-write checklists and fix contradictions, stale open questions, and scope drift.

After revision, proceed directly to the report without adding a review score.

### 6. Report

Report:

- Spec and plan paths
- Brief phase and step counts
- The chosen simple approach
- Edge cases or scenarios intentionally left out
- Any unresolved question that the user explicitly deferred

## Communication

- Ask every user question through the host picker.
- Ask exactly one question per picker call.
- Keep progress updates brief.
