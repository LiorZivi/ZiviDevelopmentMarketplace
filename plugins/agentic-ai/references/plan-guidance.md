# Shared Plan Guidance

Use this guidance whenever an architect workflow creates or revises a plan.

The plan is a phased implementation document grounded in the actual codebase. It translates the spec into system boundaries, dependencies, deliverables, risks, and testable phase outcomes.

Read the spec first. When revising an existing plan, edit it in place, preserve good content and progress markers, and address the user's latest decisions.

## Hard rules

Do not include:

- Code snippets or code fences.
- Line-number citations.
- Shell commands.
- Full KQL, SQL, or PromQL query bodies.
- Exact test method names.
- Implementation-cosmetics advice.

Reference an existing pattern by file path and symbol name rather than transcribing it.

## Length budget

- Step `What`: 1-3 sentences.
- Step `Deliverables`: short names-only list of paths, APIs, symbols, or config keys.
- Step `Dependencies`: `None` or comma-separated step IDs.
- Phase `Milestone` and `Acceptance`: 1 sentence each, with at most 3 supporting bullets.
- Architecture plan: 2-6 sentences.
- Whole plan: aim for at most 200 lines for small or medium work and 400 lines for large work.

## Plan format

# {Title} - Plan

> {One-line implementation summary}

**Created**: {YYYY-MM-DD}
**Approach**: {Pragmatic | WideScope-RefactorImprovements | Custom}
**Spec**: {relative path to spec}

## Architecture plan

{2-6 sentences}

## [ ] Phase 1: {Name}

> {Phase goal}

**Milestone**: {What is true when done}
**Acceptance**: {Testable phase-level criteria}

### [ ] Step 1.1: {Name}

- **What**: {Description}
- **Deliverables**: {Names only}
- **Dependencies**: {None or step IDs}

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|

## Open Questions

- {Implementation-level unknowns}

## Planning rules

- Use 2-5 phases for small or medium work and 3-7 for large work.
- Use 2-6 steps per phase.
- End every phase in a working state.
- Keep dependencies explicit.
- Name concrete files, APIs, tests, and existing patterns.
- Put acceptance criteria on phases, not steps.
- Start every phase and step heading with `[ ]`.
- During implementation, replace `[ ]` with `🚧` while active and `✅` when complete.

## Pre-write checklist

Before saving, verify:

- No prohibited content appears.
- Each step `What` is 1-3 sentences.
- The plan stays within its length budget.
- Every phase and step heading starts with a progress marker.
- All required sections are present.
- The plan covers the spec and reflects the user's latest answers.
- Every phase has a verifiable working outcome.

Fix every failed check before saving.
