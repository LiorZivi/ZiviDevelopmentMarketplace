# Shared Spec Guidance

Use this guidance whenever an architect workflow creates or revises a spec.

The spec is a product-level requirements document. It describes why the work matters, what outcome is wanted, who benefits, and how success will be recognized. Engineering decisions belong in the plan.

## Required structure

Use these sections in this order:

1. `# {Title} - Spec`
2. A one-line blockquote summary in product terms
3. `**Created**: {YYYY-MM-DD}`
4. Optional `**Issue**: [link] - "{title}"` when an issue exists
5. `## Goal`
6. `## Background & Context`
7. `## Users & Audience`
8. `## User-Facing Behavior`
9. `## Success Criteria`
10. `## Non-Goals / Out of Scope`
11. `## Constraints`
12. `## Open Questions`

## Content rules

- Keep the goal to 1-3 sentences.
- Explain the user problem and why the work matters now.
- State concrete user-visible behavior.
- Make success criteria observable and testable; use metrics when useful.
- Make exclusions explicit.
- Capture product-level constraints and unresolved product decisions.
- Keep the spec approach-agnostic.

## Format discipline

- Do not include code snippets or source fragments.
- Do not include file paths, repository references, line numbers, symbols, config keys, or test method names.
- Do not include pull-request cosmetics advice.
- Queries may appear only in Success Criteria when they are the acceptance mechanism.
- Product and capability names are encouraged when they are part of the audience's vocabulary.

## Length budget

- Background & Context: at most 30 lines.
- Every other section: at most 15 lines.
- Open Questions: at most 5 items. Ask the user instead when more decisions remain.
- Total: at most 250 lines for small or medium work and 350 lines for large work.

## Pre-write checklist

Before saving, verify:

- All required sections are present and ordered correctly.
- The spec contains no implementation-level details prohibited above.
- Queries appear only in Success Criteria.
- Every section is within its length cap.
- The document reflects the user's latest answers without contradictions.
- Open Questions contains only genuine unresolved product decisions.

Fix every failed check before saving.
