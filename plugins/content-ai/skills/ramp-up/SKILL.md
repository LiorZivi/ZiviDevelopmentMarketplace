---
name: ramp-up
description: "Use when an engineer wants to ramp up on an internal subsystem, flow, or codebase area in this repository. Triggers on: 'ramp me up on X', 'walk me through X', 'teach me about X', 'explain how X works', 'help me understand X', 'I'm new to X — teach me'. Also triggers on edits to an existing ramp-up document: 'add a section about X to the auth ramp-up', 'restructure the deployment explainer', 'update the bullets on Y'. Strictly grounded in the user's workspace + Azure DevOps (code, wiki, commits) — never falls back to the open web or training data; declines topics with no internal coverage. For any ramp-up request, invoke this skill — never invoke the `ramp-up-explorer` agent directly (the agent is an internal subagent this skill spawns at Step 2)."
argument-hint: "[topic]"
user-invocable: true
---

# Ramp-Up: Workspace-Grounded Onboarding

A procedure for producing a grounded markdown explainer and matching PPTX deck about an internal subsystem, flow, or codebase area. The skill handles user interaction, scoping, outline review, markdown drafting, and PPTX generation; the `ramp-up-explorer` agent handles workspace + Azure DevOps discovery and per-section citation ranking.

## Plugin Paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Scripts directory**: `${CLAUDE_PLUGIN_ROOT}/scripts/ramp-up`
- **Output directory**: `./output/ramp-up` (relative to user's working directory)
- **Output template**: `${CLAUDE_PLUGIN_ROOT}/skills/ramp-up/output-template.md`
- **Generator wrapper**: `${CLAUDE_PLUGIN_ROOT}/scripts/ramp-up/generate.sh`

Every factual claim in the output must trace to a real file, wiki page, or commit in the team's workspace or Azure DevOps — never the open web, never model training data. When the team has no internal source for something, the skill records that as a `coverage_gap` rather than inventing.

The markdown file is the source of truth; the PPTX is regenerated from it after every change.

## Workflow

```
Create mode:
  Step 1  Mode Detection (Create vs Edit)
  Step 2  Scope (3 picker gates)
  Step 3  Explore (spawn ramp-up-explorer)
  Step 4  Outline Preview (picker gate: Accept / Refine / Restart)
  Step 5  Write Markdown to ./output/ramp-up/{Topic}.md
  Step 6  Generate PPTX (bundled scripts/generate.sh)
  Step 7  Report

Edit mode:
  Step E1 Read existing ./output/ramp-up/{Topic}.md
  Step E2 Re-explore (only if adding new content)
  Step E3 Apply edits (add / remove / restructure / update)
  Step E4 Regenerate PPTX
  Step E5 Report
```

## Paths

- **Output directory**: `./output/ramp-up/` (relative to the user's workspace root)
- **Markdown**: `./output/ramp-up/{Topic}.md`
- **PPTX**: `./output/ramp-up/{Topic}.pptx`
- **Template** (read once at Step 5 to confirm the structural shape): `${CLAUDE_PLUGIN_ROOT}/skills/ramp-up/output-template.md`
- **Generator wrapper**: `${CLAUDE_PLUGIN_ROOT}/scripts/ramp-up/generate.sh`

### Topic slug rule

`{Topic}` is computed deterministically so Create Mode and Edit Mode agree on filenames:

1. Take the user's topic phrase verbatim.
2. Replace any non-alphanumeric character with a space.
3. Drop these stop-words (case-insensitive): `a`, `an`, `the`, `in`, `of`, `to`, `for`, `on`, `at`, `with`, `from`, `by`, `and`, `or`, `how`, `through`, `about`.
4. For each remaining word: if it was an all-uppercase acronym (≥ 2 chars) in the original phrase (e.g. `API`, `CLI`, `RPC`, `SDK`, `DB`, `SRE`, `CI`, `CD`, `UI`), preserve it verbatim. Otherwise capitalize the first letter and lowercase the rest.
5. Concatenate (no separators).

Examples:
- "monitoring flows in the auth service" → `MonitoringFlowsAuthService`
- "how a request flows through the API" → `RequestFlowsAPI`
- "the CI/CD rollout pipeline" → `CICDRolloutPipeline`
- "ingestion path in the DB" → `IngestionPathDB`
- "auth service monitoring flows" → `AuthServiceMonitoringFlows` (subject-first phrasing — users who want this ordering should phrase the request that way)

If the user dislikes the resulting filename, they can rename the markdown after Create Mode finishes; Mode Detection will still find it via the lookup algorithm below.

## Sub-Agent

| Agent | Role |
|-------|------|
| **ramp-up-explorer** | Sub-agent. Given a topic and optional scope, scans the user's workspace (Glob/Grep/Read) and Azure DevOps via the bluebird MCP server (code + wikis), and returns a structured outline with per-section ranked citations or `coverage_gap` markers. Does not draft prose. |

The explorer is spawned via the host's task tool. You never run web search or training-data fallbacks yourself; the explorer enforces the same rule on its side. If the explorer returns `coverage_gap` markers, surface them in the outline preview and let the user decide whether to drop, narrow, or accept the gap.

## Mode Detection

Before starting, determine the mode using this explicit algorithm:

1. **Glob** `./output/ramp-up/*.md`. Collect the existing slugs (file names without `.md`).
2. **Compute** the user's input slug using the Topic slug rule above.
3. **Exact match** (computed slug equals an existing slug) → **Edit Mode** on that file.
4. **Partial match** (any existing slug is a substring of the computed slug or vice versa, OR the user's phrase explicitly names an existing topic — "update the auth-monitoring ramp-up", "add a section to the API orchestration explainer"):
   - **Exactly one candidate** → **Edit Mode** on that file. Tell the user which file you matched in one line ("Editing `./output/ramp-up/AuthMonitoringFlows.md`") before proceeding to Step E1.
   - **Multiple candidates** → ask via `ask_user` with one choice per candidate filename plus a final "Create a new file at `./output/ramp-up/{computed slug}.md`" choice. Route based on the answer.
5. **No match** AND the user's wording is editorial (verbs like "add", "remove", "restructure", "update", "fix"): there is no existing file to edit. Tell the user that no existing ramp-up document matched and confirm via `ask_user` whether to create a new file at the computed path or abandon. Route based on the answer.
6. **No match** AND the user's wording is exploratory ("ramp me up on", "teach me about", "explain", "walk me through"): enter **Create Mode** directly. Announce the planned filename (`./output/ramp-up/{computed slug}.md`) in one line before doing any work.

---

## Step 1: Scope (Create Mode, gate)

Do not proceed to Step 2 until all three pickers have answers.

Ask via the host picker (`ask_user`) — one question per call, sequential. Picker-only — plain-prose questions are not allowed at this step.

1. **Depth** — choices: `overview` *(Recommended)* / `deep-dive`. `overview` = broader coverage, fewer slides, faster. `deep-dive` = more sections, more citations, slower exploration.
2. **Audience level** — choices: `new-hire` *(Recommended)* / `cross-team-experienced`. `new-hire` assumes no team-internal context. `cross-team-experienced` assumes general team fluency and focuses on what is distinctive about this subsystem.
3. **Focus** — choices: `code-paths` / `ops-runbooks` / `both` *(Recommended)*. `code-paths` = entry points, types, flows. `ops-runbooks` = SOPs, playbooks, monitoring. `both` = mixed.

Capture all three answers; they become the explorer's `Scope` input.

## Step 2: Explore

Spawn the `ramp-up-explorer` sub-agent via the host's task tool with this input:

```
Topic: {topic in user's vocabulary, e.g. "monitoring flows in the auth service"}
Scope:
  depth: {Step 1 answer}
  audience_level: {Step 1 answer}
  focus: {Step 1 answer}
```

Do not pass proposed section titles; let the explorer discover them. Wait for the agent's structured `SECTIONS:` + `OVERALL:` output, then move to Step 3.

If `OVERALL.bluebird_reachable: false`, the explorer fell back to workspace-only and was unable to reach the Azure DevOps content. Do not retry or fail — continue with whatever the explorer produced and surface the limitation prominently in Step 3.

## Step 3: Outline Preview (gate)

Render the explorer's findings as a compact preview the user can scan. Do not write the full document yet.

Preview format (print to chat verbatim):

```
**Outline for {Topic}** (depth: {d}, audience: {a}, focus: {f})
Bluebird reachable: {true | false}
Sections with citations: {N of M}

1. {title} — {summary} — {N citations}
2. {title} — {summary} — coverage_gap: {reason}
3. ...
```

If `OVERALL.coverage_gap_topic: true` (every section is a gap), do not show the Accept/Refine/Restart picker. Tell the user the topic has no internal grounding, suggest two or three nearby topics that did surface in the workspace or bluebird scans (if any showed up as side hits during exploration), and stop. Do not proceed to Step 4 — this is the out-of-scope guard from the spec.

Otherwise, gate via picker:

- **Accept** — proceed to Step 4.
- **Refine** — capture free-text describing the change (add section X, drop section Y, retitle Z, broaden to cover Q). Re-template the preview and re-gate. If the refinement requires new exploration (a new section the explorer didn't surface), spawn the explorer again for just that subtopic and merge results.
- **Restart** — return to Step 1 (the user may want different scoping).

## Step 4: Write Markdown

Read `${CLAUDE_PLUGIN_ROOT}/skills/ramp-up/output-template.md` to confirm the structural shape, then write `./output/ramp-up/{Topic}.md` using:

- `#` = presentation title (one only — the topic name)
- `##` = section dividers (one per accepted outline section)
- `###` = content slides (one or more per `##` section; each maps to exactly ONE slide)
- Bullet lists = bullet slides
- Tables (Markdown pipe syntax) = table slides

### Inline citation rule

Every bullet that makes a factual claim MUST end with an inline citation pointer matching one of the explorer's `citations` for that section. **Use exactly one citation per bullet** — the most specific source for the claim, with file > wiki > commit precedence. If a single bullet truly synthesizes two sources and cannot be split, append both separated by a comma: `(src/Foo.cs:L10-L20, wiki: Service/Playbook#alerts)`. Format:

- **File citation**: `(src/Foo.cs:L120-L145)` — use the explorer's `location` field for the line range; if `location` is null, just the path: `(src/Foo.cs)`.
- **Wiki citation**: `(wiki: Service/MonitoringPlaybook)` — use the wiki path returned by the explorer; if `location` is a section heading, append it: `(wiki: Service/MonitoringPlaybook#alerting)`.
- **Commit citation**: `(commit abc1234)` — short SHA from the explorer.

Bullets that are pure connective text ("This section covers…", "The flow has three stages.") do not need a citation. Bullets that name a behavior, a type, a flow step, a configuration key, or a number DO.

If you find yourself wanting to write a bullet that has no matching citation in the explorer's findings for this section, **stop** — that is the failure mode the ramp-up skill exists to prevent. Either drop the bullet or convert the section to a `coverage_gap` bullet (see below).

### coverage_gap sections

Any section the explorer flagged with a non-null `coverage_gap` is written as **a single bullet** that explicitly states the gap and the reason — e.g. *"No internal source found for the deep architecture of X; the closest neighbor in the codebase is Y. Recommend pairing with the {team} on-call to fill this in. (coverage_gap: {reason from explorer})"* — followed by no other content for that subsection. Do NOT fill `coverage_gap` sections with general-knowledge content or web-style filler.

### One-slide-per-subsection rule

Each `###` subsection maps to exactly ONE slide. To ensure this:

- Max 7 bullet points per `###` (the parser splits at 7)
- Max 8 table data rows per `###` (parser splits at 8; header row excluded)
- A `###` MUST contain EITHER bullets OR one table, not both (each generates a separate slide)
- If content doesn't fit, split into two `###` subsections with distinct titles
- Aim for 6–12 `##` sections total (the explorer typically returns 4–9)

### Forbidden Markdown Constructs

The PPTX parser only handles H1/H2/H3, bullets, and tables. **Never use** the following — they break or bloat slides:

- **No code blocks** (triple backticks): every line inside leaks as a bullet point. Paraphrase code as regular bullets (e.g., "Run `Foo()` after acquiring the lock" as a bullet with backticks inline, not a fenced block).
- **No `####` or `#####` headings**: the parser ignores these structurally — they become plain bullet text. Use only `###` for content slides.
- **No `## Table of Contents`**: TOC lines become bullet slides. Omit entirely.
- **No footer / attribution lines** (e.g., `*Generated on ...*`, `*See also: ...*`): become bullets in the last subsection. Omit.
- **No standalone paragraphs under `##`** before the first `###`: they create an unnamed subsection with its own slide. Move text into the first `###` as bullets, or remove.
- **No blockquotes** (`> ...`) except the subtitle line directly after `# Title`. All other blockquotes are treated as plain text / bullets.
- **No `---` horizontal rules** inside sections.

## Step 5: Generate PPTX

**Always use the `pptx` skill if one is available in this session.** A `pptx` skill may come from any source — an installed plugin, a synced profile, or the local repo — its origin is irrelevant. Do NOT pre-judge whether the skill has a documented "markdown→pptx converter" — that judgment is forbidden here. The pptx skill owns the conversion.

1. **If a skill named `pptx` is available**, invoke it with:
   - Source markdown: `./output/ramp-up/{Topic}.md`
   - Target PPTX: `./output/ramp-up/{Topic}.pptx`
   - The pptx skill owns the deck — slide count, slide-to-heading mapping, citation placement, layout, and visual design are all its call. Hand it the markdown as input and let it create the PPTX as it sees fit. If the skill needs you to parse the markdown into slide structures and hand-author each slide with its tools, do that.
   - On success, record `PPTX engine: pptx-skill` and capture the slide count for Step 6.
   - **Only on a hard error from the pptx skill itself** (e.g., missing system dependency, tool returned non-zero, generation crashed) fall back to the bundled wrapper below. Inconvenience, "no md→pptx converter documented", or "this would take many slides to hand-author" are NOT errors and are NOT grounds for fallback.

2. **Otherwise (no `pptx` skill available at all, OR the pptx skill hard-errored)**, invoke the bundled wrapper from the user's workspace root:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/ramp-up/generate.sh" "./output/ramp-up/{Topic}.md" "./output/ramp-up/{Topic}.pptx"
   ```

   The wrapper bootstraps Python 3 and `python-pptx` on first run. Possible outcomes:

   - **Success** — wrapper prints the slide count; proceed to Report.
   - **`SKIP_PPTX`** — Python 3 is not installed. This is **non-fatal** — the markdown is still shippable. Pass the wrapper's install guidance to the user verbatim and proceed to Report; the slide count is reported as `unknown — PPTX skipped (no Python 3)`.
   - **`bash` invocation fails** — `bash` is missing OR is the Windows-store WSL stub with no distro installed (typical error: `bash: command not found`, `'bash' is not recognized`, or `Windows Subsystem for Linux has no installed distributions`). Before giving up, try Git Bash at these known Windows paths in order: `C:\Program Files\Git\bin\bash.exe`, `C:\Program Files\Git\usr\bin\bash.exe`, `C:\Program Files (x86)\Git\bin\bash.exe`. If any exist, re-invoke the wrapper through that explicit path and proceed. Only if none are found is this **non-fatal**: the markdown is still shippable. Report PPTX as `skipped — no working bash` and include this install guidance verbatim: *"Install Git for Windows (https://git-scm.com/) or a real WSL distro; either provides the `bash` needed to run the wrapper."* Proceed to Step 6.

Record which engine produced the deck (`pptx-skill` vs `bundled-engine`) so Step 6's report can name it.

## Step 6: Report

Tell the user:

- Markdown path: `./output/ramp-up/{Topic}.md`
- PPTX path: `./output/ramp-up/{Topic}.pptx` (or, if skipped, the reason — `no Python 3` or `no working bash` — and the install guidance from Step 5; only applicable when the bundled engine was used)
- PPTX engine used: `pptx-skill` or `bundled-engine`
- Slide count from the engine (or `skipped`)
- Number of sections written
- Any `coverage_gap` sections preserved in the document, each as a one-liner the user owes a teammate-pairing on
- A one-line note if `bluebird_reachable: false` so the user knows cross-repo / wiki coverage was limited and may want to re-run later from a host where bluebird is configured

---

## Edit Mode

Use this workflow when `./output/ramp-up/{Topic}.md` already exists.

### Step E1: Read existing markdown

Read `./output/ramp-up/{Topic}.md` end-to-end. Note the existing sections, their citations, and the original scope (inferred from the document or carried in a metadata comment if present).

### Step E2: Re-explore (only if adding new content)

If the user wants to add a new `##` section or a new `###` subsection that introduces new factual content, spawn `ramp-up-explorer` for just the new subtopic:

```
Topic: {the new subtopic, not the original topic}
Scope: {the original document's scope; default to overview / new-hire / both if unknown}
```

Use the new findings to draft the new section's bullets with inline citations.

If the edit is purely structural (reorder, retitle, drop) or purely textual (fix wording, tighten a bullet, fix a typo), **skip Step E2** — no exploration needed.

### Step E3: Apply edits

Edit `./output/ramp-up/{Topic}.md` in place. Supported edit types:

- **Add section / subsection** — insert with required inline citations from Step E2 findings.
- **Remove section / subsection** — delete the entire `##` or `###` block.
- **Restructure** — reorder `##` blocks; retitle; merge two subsections into one (re-check the one-slide rule on merge).
- **Update bullets** — modify text; preserve the existing inline citation suffix unless the source actually changed (if it did, swap to the new citation from Step E2).

**Post-edit validation**: every modified `###` still complies with the one-slide rule (max 7 bullets OR max 8 table rows; bullets and table are mutually exclusive per `###`). No forbidden constructs introduced.

### Step E4: Regenerate PPTX

Re-run Step 5 (the same `pptx`-skill-else-bundled-wrapper decision applies). **Always** regenerate — never leave a stale PPTX next to an edited markdown.

### Step E5: Report

Tell the user:

- What changed (sections added / removed / restructured / updated)
- Whether the explorer was re-invoked (and the subtopic it was given)
- Updated PPTX path, engine used (`pptx-skill` or `bundled-engine`), and slide count (or skip notice)
- Any new `coverage_gap` sections introduced by the edit

---

## Communication

- Keep the user informed at each step in one short line ("scoping…", "exploring workspace + bluebird…", "outline ready — please review", "writing markdown…", "generating PPTX…").
- Do not show raw explorer output — summarize it into the outline preview format from Step 3.
- Picker discipline: plain-prose questions are not allowed in Step 1 or Step 3. Always use `ask_user`.
- Never invoke `WebSearch`, `WebFetch`, `curl`, or any tool that reaches the public internet for factual content. The explorer enforces this on its side; you enforce it on yours.
