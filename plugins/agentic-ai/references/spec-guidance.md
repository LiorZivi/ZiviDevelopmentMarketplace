# Spec Guidance

The spec is a **product-level requirements document**, not a technical design. It describes WHY we are doing this, WHAT outcome we want, WHO benefits, and HOW we will know it worked. Engineering decisions (which files to touch, what code looks like, which deployment artifact carries the change) belong in the plan, not in the spec.

## Required Structure

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

## Format Discipline (hard rules)

The spec is read by product, engineering, and validation audiences. Keep it in product language — implementation details belong in the plan.

- **No code snippets.** No copy-pasted C#, YAML, JSON, Bicep, Helm, or any other source fragments.
- **No file paths or repository references.** Describe behavior and capabilities, not files or directories.
- **No line-number citations.** They go stale and they're an implementation concern anyway.
- **No symbol-level references** (class names, method names, package names, config keys). Use product / feature terms the audience uses.
- **No test method names** or test-class references.
- **No PR-cosmetics advice** (alphabetical ordering, diff readability, "keep the change reviewer-friendly"). Belongs in code review.
- **KQL / SQL / shell queries are allowed in Success Criteria only** — they are the acceptance test the operator / SRE will run to confirm the outcome. They MUST NOT appear in Background, Constraints, Open Questions, or anywhere else.
- **Product / capability names are encouraged** when they are part of the vocabulary the audience already uses (e.g., the name of a service, a deployment surface, a user-visible feature). Prefer these over engineering identifiers.

## Length Budget (hard rules)

- **Background & Context**: ≤ 30 lines.
- **Every other section** (Goal, Users & Audience, User-Facing Behavior, Success Criteria, Non-Goals, Constraints, Open Questions): ≤ 15 lines each.
- **Open Questions**: ≤ 5 items. If you have more, the picker step missed scope — go back and ask an additional picker question rather than punting it to an open question.
- **Total**: ≤ 250 lines for small/medium specs, ≤ 350 lines for large.

## Pre-write Checklist

Before saving the spec, verify:

- [ ] All required sections present, in order, with the right heading levels.
- [ ] No code snippets, no YAML/JSON/Helm fragments.
- [ ] No file paths or repository references.
- [ ] No line-number citations anywhere.
- [ ] No symbol-level references (class / method / config-key names).
- [ ] No test method names.
- [ ] KQL / queries appear only inside Success Criteria.
- [ ] Each section is within its length cap.

If any check fails, fix the spec before continuing.
