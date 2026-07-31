---
name: architect
description: Use only when the user explicitly says "complex architect".
---

# Architect

Create a PM-level spec and a phased implementation plan through alternative plan generation and review.

## Shared guidance

- Spec rules: `../../references/spec-guidance.md`
- Plan rules: `../../references/plan-guidance.md`

Read the relevant shared guidance before writing or revising either artifact.

## Paths

- Output directory: `./output/architect/`
- `{PlanName}` is PascalCase derived from the task.
- Spec: `./output/architect/{PlanName}-spec.md`
- Candidate plans: `./output/architect/{PlanName}-plan-{pragmatic|widescope-refactorimprovements}.md`
- Canonical plan: `./output/architect/{PlanName}-plan.md`

## Mode detection

- **Create**: no existing artifacts for the task. Run the full workflow.
- **Edit**: an existing canonical plan is being revised. Skip to revision using the user's request as feedback.

## Workflow

### 1. Scan and clarify

Deep-scan the relevant code, tests, configuration, and documentation. Ask 1-4 grounded intent questions through the host picker, one at a time. Ask only about decisions the user owns: purpose, scope, success criteria, priorities, audience, external constraints, and behavioral defaults.

Do not continue until the questions are answered.

### 2. Write the spec

Write the canonical spec using `../../references/spec-guidance.md`. Keep it independent of implementation approach.

### 3. Generate two plans

Run two `plan-architect` tasks in parallel with the task, spec path, user answers, output path, and one approach each:

- `Pragmatic`
- `WideScope-RefactorImprovements`

### 4. Let the user select

Invite the user to inspect both candidate plans and print this comparison:

| Aspect | Pragmatic | WideScope-RefactorImprovements |
|---|---|---|
| Phases | {N} | {N} |
| Steps | {N} | {N} |
| Plan Short Summary Overview | {1-2 sentences} | {1-2 sentences} |
| Spec vs Scope | {Exact / Extends / Subset} | {Exact / Extends / Subset} |
| Refactors | {short bullets, or "None"} | {short bullets, or "None"} |
| Risk Delta | {Lower / Same / Higher} | {Lower / Same / Higher} |

Ask through the host picker: `Pragmatic`, `WideScope-RefactorImprovements`, or `Combine elements`. Recommend Pragmatic by default; recommend the wider plan when notable architectural problems or cross-module ownership justify it.

Rename the selected plan to the canonical path and delete the unselected candidate. For a combination, run one `plan-architect` task with `Custom` and the user's requested blend.

### 5. Review and revise

Run `plan-reviewer` against the canonical spec and plan. Store its latest result after the `**Spec**:` line as:

`**Review Score**: {N}/10 - {PASS | REVISE} ({YYYY-MM-DD})`

If the score is below 8, run `plan-architect` to revise the existing plan from the feedback, then review again. Stop after two revision cycles and report any remaining issues.

### 6. Report

Report the artifact paths, selected approach, phase and step counts, final score, material revisions, and unresolved findings. Summarize task output rather than showing raw task transcripts.

## Communication

- Keep progress updates short.
- Use the host picker for clarification and plan selection.
- Ask one question per picker call.
