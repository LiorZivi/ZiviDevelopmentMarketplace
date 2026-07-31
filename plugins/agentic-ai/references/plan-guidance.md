# Plan Guidance

## Hard Rules — what the plan you write MUST NOT include

You are writing a planning document for a stakeholder, not implementing code. The plan you save to disk MUST NOT include any of the following:

- **Code snippets** — no inline code in any language (C#, Rust, Go, Python, YAML, JSON, HCL, KQL, SQL, PowerShell, bash, Helm). If a step needs to point at a pattern, name the pattern and the file it lives in (e.g. *"mirror the `--metrics-dir` convention already used in this chart"*); do not paste it.
- **Code fences (` ``` `)** — no fenced blocks anywhere in the plan you write. The template below uses a fenced block to delimit its shape; that is template-shape syntax, not license to use fences in your output.
- **Line numbers** — never cite specific lines (`line 760`, `lines 1120–1136`, `:474`, `~554`). Files and symbol / method / section names only. Line numbers go stale the moment any unrelated PR touches the file.
- **Shell commands** — no `grep`, `kubectl`, `helm`, `dotnet build`, `Select-String`, `curl`, or other invocations. State the intent (*"build the affected project"*, *"render the helm template and confirm the new arg appears"*); the implementer chooses the command.
- **Exact test method names** — describe the test's purpose (*"a UT asserting the CLI arg flows into the manifest field"*), not its identifier.
- **Embedded queries** — no full KQL, SQL, or PromQL bodies. State the query's intent and the table / source it runs against; the implementer writes the query.
- **Implementation-cosmetics advice** — no *"preserve alphabetical ordering"*, *"keep the diff reviewer-friendly"*, *"place between X and Y for diff aesthetics"*. That detail belongs in code review.

If you genuinely need to show an existing pattern the implementer must follow, link to the file (path + symbol name) and let them read it — do not transcribe it into the plan.

## Length Budget (hard rules)

A plan a stakeholder won't scroll is a plan a stakeholder won't read.

- **Step `What`** — 1–3 sentences. If you need more, split into multiple steps.
- **Step `Deliverables`** — short bullet list of file paths / API or symbol names / config keys. Names only, never contents. No explanatory paragraphs.
- **Step `Dependencies`** — `None` or comma-separated step IDs. No prose.
- **Phase `Milestone`** and **Phase `Acceptance`** — 1 sentence each, plus up to 3 supporting bullets.
- **Architecture plan** section — 2–6 sentences as the template says, not paragraphs.
- **Whole plan** — aim for ≤ 200 lines for a small/medium task, ≤ 400 lines for a large one. If you cross either ceiling, you are writing implementation, not a plan.

## Pre-Save Checklist (self-verification gate)

Before writing the plan to disk, you MUST run through this checklist explicitly and fix anything that fails. Do not save a plan that has any unchecked item.

- [ ] No code fences (` ``` `) anywhere in the plan.
- [ ] No line-number citations anywhere.
- [ ] No shell commands anywhere.
- [ ] No KQL / SQL / PromQL query bodies anywhere.
- [ ] No test method names.
- [ ] No cosmetics advice (alphabetical ordering, diff readability, etc.).
- [ ] Each step `What` is 1–3 sentences.
- [ ] Plan total is ≤ 200 lines (small/medium) or ≤ 400 lines (large).
- [ ] Every phase and step heading **starts** with `[ ]` as a prefix (before the phase/step number), not as a suffix.
- [ ] All required sections present per the Plan Format below.

If any check fails, edit the plan in memory and re-check — do not save until every box is checked.

## Plan Format

```
# {Title} — Plan

> {One-line summary of the implementation approach}

**Created**: {YYYY-MM-DD}
**Approach**: {Pragmatic | WideScope-RefactorImprovements | Custom}
**Spec**: {relative path to spec.md}

## Architecture plan
{2-6 sentences.}

## [ ] Phase 1: {Name}
> {Phase goal}

**Milestone**: {What is true when done}
**Acceptance**: {Testable criteria for the phase as a whole}

### [ ] Step 1.1: {Name}
- **What**: {Description}
- **Deliverables**: {File paths / API or symbol names / config keys — names only, never contents}
- **Dependencies**: {None, or step IDs}

### [ ] Step 1.2: ...

## [ ] Phase 2: ...

## Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|

## Open Questions
- {Implementation-level unknowns}
```

> The fenced block above shows the template *shape*. Do NOT use code fences (` ``` `) in the plan you write.

**Progress markers:** every phase and step heading **starts** with a `[ ]` checkbox as a prefix (before the phase/step number, e.g. `### [ ] Step 1.1: Foo`). During implementation, replace the `[ ]` with 🚧 while the phase/step is in progress and ✅ once completed (e.g. `### ✅ Step 1.1: Foo`). Start every plan with all boxes empty.

## Rules

- 2-5 phases (small/medium), 3-7 (large); 2-6 steps per phase.
- Each phase ends in a working state. No big bang.
- Dependencies between steps are explicit.
- Name concrete files/APIs/tests; reference existing patterns from the scan.
- Plan reflects the chosen approach.
- Acceptance criteria live on **phases**, not steps. Steps describe work; phases describe verifiable outcomes.
