---
name: architect
description: Use only when the user explicitly says "complex architect".
---

# Architect

A procedure for turning a task into two artifacts: `spec.md` (PM-level intent) and `plan.md` (phased implementation plan). The skill handles user interaction and spec authoring; the `plan-architect` and `plan-reviewer` agents handle plan drafting and quality review.

## Workflow

```
Step 1  Deep-scan codebase + draft picker questions + ask user
Step 2  Write spec.md from the answers
Step 3  Spawn 2 plan-architect agents in parallel, each given the spec
        → {Plan}-plan-{pragmatic|widescope-refactorimprovements}.md
Step 4  Picker: user selects which design implementation plan to take
        (or chooses a combination of elements from each plan)
        → rename chosen to {Plan}-plan.md; delete the other plan file
Step 5  Spawn plan-reviewer → score
        Skill writes/updates the **Review Score** header in {Plan}-plan.md
          ≥ 8 → Step 7
          < 8 → Step 6
Step 6  Spawn plan-architect with spec.md + {Plan}-plan.md + reviewer feedback
        → re-review (max 2 cycles total). After 2, proceed to Step 7 anyway.
Step 7  Report
```

## Paths

- Output directory: `./output/architect/`
- `{PlanName}` is PascalCase derived from the task (e.g. `UserAuthSystem`).
- Spec: `./output/architect/{PlanName}-spec.md`
- Per-design plans (during generation): `./output/architect/{PlanName}-plan-{pragmatic|widescope-refactorimprovements}.md`
- Canonical chosen plan: `./output/architect/{PlanName}-plan.md`

## Agents

| Agent | Role |
|-------|------|
| **plan-architect** | Sub-agent. Given task + spec + approach, deep-scans the codebase and writes `plan.md`. Does not write the spec and does not ask user questions. |
| **plan-reviewer** | Sub-agent. Scores the plan against the spec (1-10); returns PASS / REVISE with feedback. |

## Mode Detection

- **Create** — no existing spec or plan for this task. Run the full workflow.
- **Edit** — existing `{PlanName}-plan.md` and the user wants changes. Skip Steps 1-4; jump straight to Step 6 with the user's edit request as the feedback.

---

## Step 1: Scan & Clarify (gate)

Do not proceed until the user has answered all questions.

1. **Deep scan** the codebase proportionally to the task — Glob the layout, Grep related code/tests/configs, and Read the most relevant files. Synthesize: what conventions, abstractions, and integration points matter for this task.
2. **Draft 1-4 intent questions** with 2-4 choices each, **grounded in the scan**. Ask only about things only the user can decide — scope, success criteria, priorities, audience, external constraints, behavioral defaults. Don't ask about frameworks or layout (you read those in step 1). Mark a default with `(Recommended)` when you have one.
3. **Ask via the host picker** (`ask_user` / `AskUserQuestion`) — one question per call, sequential.

## Step 2: Write spec.md

Write `./output/architect/{PlanName}-spec.md`. Keep it approach-agnostic. Anchor every section in the user's answers from Step 1 and the relevant findings from the scan. The spec MUST follow every rule in the **Spec Guidance** below and pass the **Pre-write Checklist** before being saved.

### Spec Guidance

The spec is a **product-level requirements document**, not a technical design. It describes WHY we are doing this, WHAT outcome we want, WHO benefits, and HOW we will know it worked. Engineering decisions (which files to touch, what code looks like, which deployment artifact carries the change) belong in the plan, not in the spec.

#### Required Structure

Every spec MUST have these sections, in this exact order:

1. **Title** — `# {Title} — Spec`
2. **One-line summary** — single `>` blockquote stating what we are building, in product terms
3. **Created** — `**Created**: {YYYY-MM-DD}`
4. *(Optional)* **Issue** — `**Issue**: [link] — "<title>"` when an issue tracker reference exists
5. **## Goal** — 1-3 sentences. What outcome are we creating for the user?
6. **## Background & Context** — why now, what problem this solves, what's broken from the user's point of view
7. **## Users & Audience** — who will use this, what role / persona
8. **## User-Facing Behavior** — concrete user-visible capabilities, as a bullet list
9. **## Success Criteria** — testable, observable outcomes; metrics where applicable
10. **## Non-Goals / Out of Scope** — explicit product-level exclusions
11. **## Constraints** — timeline, compliance, integrations, budget, environment
12. **## Open Questions** — product / PM-level unknowns that must be resolved before planning

#### Format Discipline (hard rules)

The spec is read by product, engineering, and validation audiences. Keep it in product language — implementation details belong in the plan.

- **No code snippets.** No copy-pasted C#, YAML, JSON, Bicep, Helm, or any other source fragments.
- **No file paths or repository references.** Describe behavior and capabilities, not files or directories.
- **No line-number citations.** They go stale and they're an implementation concern anyway.
- **No symbol-level references** (class names, method names, package names, config keys). Use product / feature terms the audience uses.
- **No test method names** or test-class references.
- **No PR-cosmetics advice** (alphabetical ordering, diff readability, "keep the change reviewer-friendly"). Belongs in code review.
- **KQL / SQL / shell queries are allowed in Success Criteria only** — they are the acceptance test the operator / SRE will run to confirm the outcome. They MUST NOT appear in Background, Constraints, Open Questions, or anywhere else.
- **Product / capability names are encouraged** when they are part of the vocabulary the audience already uses (e.g., the name of a service, a deployment surface, a user-visible feature). Prefer these over engineering identifiers.

#### Length Budget (hard rules)

- **Background & Context**: ≤ 30 lines.
- **Every other section** (Goal, Users & Audience, User-Facing Behavior, Success Criteria, Non-Goals, Constraints, Open Questions): ≤ 15 lines each.
- **Open Questions**: ≤ 5 items. If you have more, the picker step missed scope — go back and ask an additional picker question rather than punting it to an open question.
- **Total**: ≤ 250 lines for small/medium specs, ≤ 350 lines for large.

#### Pre-write Checklist

Before saving the spec, verify:

- [ ] All required sections present, in order, with the right heading levels.
- [ ] No code snippets, no YAML/JSON/Helm fragments.
- [ ] No file paths or repository references.
- [ ] No line-number citations anywhere.
- [ ] No symbol-level references (class / method / config-key names).
- [ ] No test method names.
- [ ] KQL / queries appear only inside Success Criteria.
- [ ] Each section is within its length cap.

If any check fails, fix the spec before continuing to Step 3.

## Step 3: Generate 2 Designs (parallel)

Spawn **2 plan-architect agents in parallel**. Each prompt includes:

- The task description
- The path to the spec: `./output/architect/{PlanName}-spec.md` (so the agent reads it for intent + scope)
- A summary of the user's clarifying answers from Step 1
- The approach: one of `Pragmatic` | `WideScope-RefactorImprovements`
- The output path: `./output/architect/{PlanName}-plan-{approach}.md`

## Step 4: User Selects

Read each plan briefly. Then present the user with **both** of the following before asking the picker:

**1. Invite the user to review both plans at their paths.** State that the two designs have been written and that the user can inspect them at:
- `./output/architect/{PlanName}-plan-pragmatic.md`
- `./output/architect/{PlanName}-plan-widescope-refactorimprovements.md`

**2. Print this exact markdown comparison table to chat:**

| Aspect | Pragmatic | WideScope-RefactorImprovements |
|---|---|---|
| Phases | {N} | {N} |
| Steps | {N} | {N} |
| Plan Short Summary Overview | {1-2 sentences} | {1-2 sentences} |
| Spec vs Scope | {Exact / Extends / Subset} | {Exact / Extends / Subset} |
| Refactors | {short bullets, or "None"} | {short bullets, or "None"} |
| Risk Delta | {Lower / Same / Higher} | {Lower / Same / Higher} |

Then ask via picker which design implementation plan to take: `Pragmatic` | `WideScope-RefactorImprovements` | `Combine elements`. Mark one option with `(Recommended)` (default Pragmatic; recommend WideScope-RefactorImprovements when the scan surfaced notable code/architecture smells in the task area, or the task crosses module boundaries / touches code owned by multiple teams). The combine option lets the user blend pieces from both plans — capture their description via free-text.

Then:
- Rename the chosen design's plan to `./output/architect/{PlanName}-plan.md`.
- Delete the other plan file. The spec is unchanged and stays as-is.
- If the user picked "Combine", spawn a single plan-architect with `approach=Custom`, the user's described blend, the spec path, and the canonical plan path (`./output/architect/{PlanName}-plan.md`).

## Step 5: Review

Spawn **plan-reviewer** with the path to `{PlanName}-plan.md` and `{PlanName}-spec.md`.

When the reviewer returns, **the skill updates the `**Review Score**: {N}/10` header line in `{PlanName}-plan.md`** to the score this reviewer pass returned (see *Score Maintenance* below). Then route:

- Score ≥ 8 → Step 7.
- Score < 8 → Step 6.

## Step 6: Revise (max 2 cycles)

Spawn **plan-architect** with:
- The spec path: `./output/architect/{PlanName}-spec.md`
- The existing plan path: `./output/architect/{PlanName}-plan.md`
- The reviewer feedback

The agent edits the plan in place. **It must not touch the `**Review Score**:` header** (the architect agent is instructed accordingly). Then re-spawn plan-reviewer per Step 5 — and the skill again rewrites the header to the new score.

After 2 cycles regardless of score → Step 7 (note remaining issues).

## Score Maintenance (skill-owned)

The `**Review Score**: {N}/10` line in `{PlanName}-plan.md` is owned by this skill, not by either sub-agent. The contract:

- After **every** plan-reviewer pass (Steps 5 and 6), the skill rewrites that single line in `{PlanName}-plan.md` to reflect the most recent reviewer score and verdict, in the form `**Review Score**: {N}/10 — {PASS | REVISE} ({YYYY-MM-DD})`. If the line is absent (first review after Step 4), the skill inserts it immediately after the `**Spec**:` line.
- The plan-architect agent never writes or edits this line — it is instructed to leave it alone during revisions.
- The plan-reviewer agent never writes or edits this line — it reports its score in its own output only.
- This guarantees the score in the plan file matches the score reported in the CLI Step-7 report; the file is never stuck at a stale "score-that-triggered-revision" value.

## Step 7: Report

Tell the user:
- Paths to `{PlanName}-spec.md` and `{PlanName}-plan.md`
- Brief plan summary (phases, total steps)
- Final review score
- Chosen approach
- What was changed during revision (if any)
- Any unresolved reviewer findings

## Communication

- Keep the user informed at each step in one short line.
- Do not show raw agent output — summarize.
- Plain-prose questions are not allowed in Step 1 or Step 4 — always use the picker.
