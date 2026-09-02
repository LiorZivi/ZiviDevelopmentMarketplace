---
name: pr-explainer
description: "Use only when the current user message explicitly invokes `/pr-explainer`, invokes a namespaced slash command ending in `:pr-explainer`, or affirmatively says `trigger pr-explainer` (case-insensitive). Do not trigger otherwise."
argument-hint: "[PR URL/number, branch, commit range, or local changes]"
user-invocable: true
compatibility: "Python 3.9+ recommended for deterministic HTML rendering; Git plus the repository provider's PR tools for PR inputs."
---

# PR Explainer

Turn a PR or local code change into a self-contained technical walkthrough that helps a reviewer understand:

- what was wrong before;
- where the problem occurred;
- what changed;
- why the new flow works;
- what evidence supports the diagnosis and fix.

The deliverable is one standalone HTML file under `./output/`, styled consistently with the bundled renderer.

## Plugin paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Renderer**: `${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/scripts/render_explainer.py`
- **Spec schema**: `${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/references/spec-schema.md`
- **Example spec**: `${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/assets/example-spec.json`
- **Output directory**: `./output/`

## Input modes

Determine the mode from the user's reference.

### PR mode

Use PR mode for a PR URL, PR number, current-branch PR, or explicit source/target branches.

1. Identify the repository provider from the remote or URL.
2. Prefer the matching provider tools:
   - Azure DevOps PR tools for `dev.azure.com`;
   - GitHub PR tools for `github.com`.
3. Gather the PR title, description, source/target refs, commits, changed files, and diff.
4. Read relevant review comments or linked work items only when they affect the implementation story.
5. If provider tools are unavailable, fetch refs with Git and compare the target merge base to the PR head.

### Local-change mode

Use local-change mode when the user mentions local, current, staged, unstaged, uncommitted, working-tree, branch, or commit-range changes.

1. Inspect `git status`.
2. Read staged and unstaged diffs separately.
3. Include untracked files that are part of the requested change.
4. For a branch diff, compare against the repository's default branch, usually `origin/main`.
5. Treat `HEAD` as the previous state for working-tree changes.

Do not modify source code, PR state, commits, or branches. The only file this skill creates is the explainer and a short-lived renderer spec.

## Ground the explanation in evidence

Read enough code to trace the affected behavior from entry point to persistence or external boundary. Do not infer a flow from filenames alone.

Collect evidence from sources that actually exist:

- PR description and commit history;
- base and changed code;
- tests added or changed;
- build/test output;
- logs, traces, screenshots, database state, or metrics supplied by the user;
- review comments that explain intent.

Never invent production evidence. If no runtime evidence exists, omit the evidence section and state the code-level proof in the explanation cards.

## Reconstruct both states

### Previous state

Read the base revision or pre-change code and identify:

- the user-visible or operational issue;
- the ordered calls and state transitions that produced it;
- the exact problematic steps;
- any missing capability for an additive feature.

For an additive feature with no literal failure, describe the previous state as the missing capability or manual workaround. Mark only that gap red.

### Fixed state

Read the changed code and identify:

- which steps changed;
- which steps stayed the same;
- the dependency or ordering boundary introduced by the fix;
- how tests or runtime evidence prove the fix.

Mark only the changed behavior that solves the issue green. Unchanged healthy behavior stays neutral.

## Required document structure

Use this order every time:

1. **Title** — concise change name.
2. **Explanation title** — one sentence that states the key insight.
3. **Old-flow issue and scope boundary** — distinguish the PR's scope from related work.
4. **Evidence** — include only when concrete evidence exists.
5. **Previous high-level sequence** — simplified left-to-right cards; problematic cards have red borders/backgrounds.
6. **Previous detailed UML sequence** — entities are columns left-to-right, time moves top-to-bottom, calls move horizontally; problematic regions are enclosed in red rectangles.
7. **Post-fix high-level sequence** — simplified left-to-right cards; changed steps that solve the issue have green borders/backgrounds.
8. **Post-fix detailed UML sequence** — same participant columns; fixed regions are enclosed in green rectangles.
9. **More explanations** — changed-file or component cards describing responsibility and meaningful behavior.
10. **Evidence of fix** — include tests, builds, metrics, logs, or observed state when available.

The renderer also adds a footer with the PR/change reference.

## Diagram rules

### Simplified sequence diagrams

- Flow from left to right.
- Use 5-8 steps where possible.
- Each step has an actor, title, short explanation, and tone.
- Use `problem` only for the broken or wrongly ordered steps.
- Use `success` only for steps changed by the fix.
- Keep healthy unchanged steps `normal`.
- End each diagram with a concise callout explaining the red or green chain.

### Detailed UML sequence diagrams

- Participants are entity columns from left to right.
- Time moves from top to bottom.
- Solid arrows are calls; dashed arrows are responses.
- Keep message labels short and concrete.
- Use red zones around the precise before-change message range that caused the issue.
- Use green zones around the precise post-change message range introduced by the fix.
- Keep unrelated messages outside highlighted zones.
- Prefer the same participant ordering before and after so comparison is immediate.

## Build the renderer spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/references/spec-schema.md`, then write a temporary JSON spec matching that schema.

The spec must:

- name every participant with a stable `id`;
- use one-based `start_message` and `end_message` indexes for UML highlight zones;
- include `tone: "problem"` for old-flow zones;
- include `tone: "success"` for fixed-flow zones;
- use truthful evidence labels and source descriptions;
- include the changed files/components under `explanations`;
- omit `evidence` or `fix_evidence` when none exists.

Keep overview step details to roughly 1-2 sentences and UML message labels under about 70 characters.

## Render the HTML

Derive a filesystem-safe change name:

- PR: `{ConcisePrTitle}-PR-{Number}-Explainer.html`
- Local change: `{ConciseChangeName}-Local-Change-Explainer.html`

Always place the final file directly under `./output/`.

Run:

```powershell
python "${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/scripts/render_explainer.py" `
  --spec "<temporary-spec.json>" `
  --output "./output/<ExplainerName>.html"
```

On Unix-like shells:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/pr-explainer/scripts/render_explainer.py" \
  --spec "<temporary-spec.json>" \
  --output "./output/<ExplainerName>.html"
```

Delete only the temporary spec after rendering. Never delete or overwrite unrelated output files.

If Python is unavailable, reproduce the same structure manually in HTML and preserve the bundled visual language: blueprint grid, navy/cyan palette, red problem states, green fix states, white cards, simplified flows, and SVG UML sequences.

## Validate before reporting

1. Confirm the renderer exits successfully.
2. Confirm the HTML exists under `./output/`.
3. Confirm it contains:
   - two simplified overview flows;
   - two detailed UML sequence diagrams;
   - at least one red problem highlight;
   - at least one green fix highlight;
   - scope boundary text;
   - changed-file explanations.
4. If Playwright or another browser tool is available:
   - open the file via `file:///`;
   - wait for load;
   - capture a full-page screenshot;
   - inspect both diagrams for clipping and label overlap;
   - verify the document has no page-level horizontal overflow.
5. Fix visual defects before finishing.

## Final response

Lead with the created HTML path. Mention:

- whether the source was a PR or local change;
- whether runtime evidence was available;
- the PR/change reference used.

Do not add unrelated recommendations.
