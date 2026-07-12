---
name: agent-memory-summary
description: "Record a finished or shipped change as one durable Summary_<name>.md entry in a team's memory — committed in the code repo under `agent-memory/<team>/` in a fixed spec+plan format. Works either from an /architect design (its `spec.md` + `plan.md`) or, when there are no design docs, straight from a code change: the current working-tree edits, a PR, or a commit range against main. Use whenever a design or shipped change should be recorded in a team's memory, e.g. 'summarize this design into the memory', 'create a memory summary', 'add this spec and plan to the platform memory', 'summarize this PR into memory', 'summarize my current changes into the platform memory', 'summarize this branch vs main into memory', or 'store this design summary'. Files a single-team summary into the team folder, a cross-team one into `agent-memory/cross-team/`, and an org-wide one into `agent-memory/global/`."
---

# Memory Summary

Turn a finished change into one durable **`Summary_<name>.md`** entry in a team's **memory** — a fixed **spec + plan** combination that future engineers and agents rely on. It pairs the **full product spec** (the durable "why" and "what") with the plan's **high-level design** — never the tactical phases/steps, which go stale the moment the work ships.

There are two ways to feed the skill, both producing the **same** `Summary_<name>.md` structure:

- **Mode A — Design mode (spec + plan).** You have the `/architect` outputs — `spec.md` + `plan.md`. The skill embeds the spec verbatim and extracts the plan's high-level design, **after reconciling the plan against the real code** (a drift check) so the record reflects what was built.
- **Mode B — Change mode (a diff, no spec or plan).** You have only a code change — the current working-tree edits, a PR, or a commit range against `main` — and no design docs. The skill reads and **understands the change, then reverse-engineers** the same spec + plan high-level design from it. Here the code *is* the source of truth, so there's nothing to drift-check.

Both modes converge on the **same compose step** (Step 3) and emit the same structure; only how the spec + plan content is obtained differs (Step 2A vs Step 2B).

## Mode detection

- `spec.md` + `plan.md` supplied, or found at the architect output paths (`./output/architect/{Name}-spec.md` + `-plan.md`) → **Mode A**.
- No spec/plan, but a change source is given or implied — "summarize this PR / my current changes / this branch vs `main` into the memory" → **Mode B**.
- Ambiguous (both present, or neither) → ask the user which mode to run.

## Inputs

**Shared (both modes):**

- **target(s)** (required) — one or more owning team folders, e.g. `platform`, `frontend`, `backend`, `infra`, **or** the special target `global` for an org-wide design. If the user hasn't named any, **suggest** likely target(s) — inferred from the spec/plan or the change content and the code areas it touches — and confirm before writing.
  - **One team** → the summary is filed into that team's folder (`agent-memory/<team>/`) and its `index.md`.
  - **Multiple teams (cross-team design)** → the summary is filed **once** into `agent-memory/cross-team/`, and **each** named team's `index.md` gets a row linking to it — so the content lives in one place and every relevant team can discover it.
  - **Org-wide (`global`)** → for a design the whole org should know about, with no single owning team, the summary is filed into `agent-memory/global/` and registered in `agent-memory/global/index.md` (the skill creates this index on the first global summary). Agents reach it via a global instruction (e.g. in the repo's `AGENTS.md`) that points at `agent-memory/global/index.md`.
- **name** (optional) — the `<name>` in `Summary_<name>.md`. Default to the architect slug (Mode A), the PR title or branch name (Mode B), or a PascalCase form of the change's primary component / spec title.

**Mode A (design) only:**

- **spec** and **plan** — paths to the two design files. Default to the architect outputs `./output/architect/{Name}-spec.md` and `./output/architect/{Name}-plan.md` if present; otherwise ask the user for the paths.

**Mode B (change) only:**

- **change source** — what to summarize, resolved in this precedence: an explicit **PR** (number or URL); an explicit **branch or commit range** (diffed against `main` at the merge-base); or — if none is named — the **current work** (staged + unstaged changes vs `HEAD`, plus the branch vs `main` if it carries commits). See Step 2B for how each is gathered.

## Workflow

### Step 1 — Locate the memory (both modes)

The memory is committed **in the code repo you're working in**, at `agent-memory/<team>/` (`index.md`, `projectBrief.md`, `systemPatterns.md`, `Summary_<name>.md`). It lives with the code, so the summary you write lands in the **same PR** as the implementation — no separate repo, no sync step.

- The target for a single-team design is `agent-memory/<team>/`. If that folder doesn't exist, this team has no memory yet — stop and tell the user to seed it first (`agent-memory/<team>/` with `index.md`, `projectBrief.md`, `systemPatterns.md`).
- For a **cross-team** design, the summary's home is `agent-memory/cross-team/` (create it if missing); each referencing team must still have its own seeded `<team>/` memory, because the discovery row lives in the team's `index.md`.
- For an **org-wide** design, the summary's home is `agent-memory/global/` (create it if missing); it has its own `index.md` — create it from the team index's table shape if it doesn't exist yet — read by a global instruction in the repo's agent instructions (e.g. `AGENTS.md`).

### Step 2 — Obtain the spec + plan design (mode-specific)

Run **either Step 2A or Step 2B**, per Mode detection. Both hand Step 3 the same two things: the **spec content** (full product intent) and the **plan's high-level design** (one-line summary, architecture plan, and any resolved decisions).

#### Step 2A — Mode A: from a finished spec + plan

**Read both, in full.** Read the **entire** spec (you'll embed it verbatim in Step 3) and the **entire** plan (you'll extract its high-level parts — the *Plan high-level shape* in [`references/summary-format.md`](references/summary-format.md) — for the summary, and use its phases/steps as the checklist for the drift check below).

**Reconcile the plan with the implementation (drift check) — before summarizing.** This summary becomes the durable record of the design, and it captures the plan's design — so the plan should match what was actually built. If the plan drifted from reality during implementation, summarizing it as-is would enshrine the original intent as though it were the outcome. Reconcile first.

Run the shared compare engine — **`../agent-memory-drift/references/compare-summary-to-code.md`** — to walk the plan against the real code: decompose the plan into atomic assertions (its `[V]` steps and named deliverables — files, symbols, config keys — plus the architecture paragraph's components, data flow, and integration points), verify each against the implementation **with a code citation**, and aggregate. The same load-bearing rules apply: a Broken/Diverged claim with no citation is downgraded to **Unverifiable**, and Unverifiable is not drift. This is the very same engine the `agent-memory-drift` skill runs continuously — here it runs once, at authoring time, so the two checks can never diverge.

If you find drift, **do not silently summarize the stale plan**. Surface it concisely and propose concrete plan edits — to **both** the high-level **Architecture plan** paragraph **and** the affected **steps** — then let the user apply them (or explicitly confirm proceeding as-is) before you continue. A reconciled plan makes a truthful summary; an unreconciled one quietly bakes in a lie.

If you genuinely can't reach the implementation (the code lives in a repo you don't have open), say so and proceed — but note in your hand-off that the summary was not drift-checked.

#### Step 2B — Mode B: from a code change (no spec or plan)

Mode B runs when there are no design docs. The **code is the source of truth** — there's no plan to drift-check; instead, every sentence you write must be **grounded in the actual change**. You reverse-engineer the spec and plan content from the diff and write it **straight into `Summary_<name>.md` (Step 3) — never as standalone `spec.md` / `plan.md` files.**

1. **Confirm the approach (unless already clear).** No spec/plan was supplied. Unless the user has already made clear they have none, give them the choice: point you at existing `spec.md` + `plan.md` files — then switch to **Mode A** (higher fidelity; it also drift-checks the plan against the code) — or have you build the summary directly from the change. When they have no design docs (the usual case for an already-shipped change) or tell you to proceed, continue below. Either way, Mode B writes **only** the summary — it never creates separate spec/plan files.

2. **Resolve the change set.** Determine exactly what to summarize, in precedence order:
   - **A named PR** (number or URL) → fetch its diff, title, description, and any linked work item / issue, using the host CLI that matches the repo's remote (`gh pr diff` / `gh pr view` for GitHub; `az repos pr show` for Azure DevOps).
   - **A named branch or commit range** → diff it against `main` at the merge-base (e.g. `git diff main...<ref>`) and read the commit messages in the range (`git log main..<ref>`).
   - **No source named** → summarize the **current work**: staged + unstaged changes vs `HEAD`, and — if the branch carries commits — the branch vs `main` (merge-base). Prefer the union so nothing in-flight is missed.

   Capture the changed-file list, the diff hunks, the commit messages, and any PR / issue text: the messages and PR/issue are your best evidence for the **why**.

3. **Understand the change.** Don't summarize hunks blind. Open the touched files and enough surrounding code to understand **what** user-visible behavior changed, **which** components / symbols / config keys / data flows are involved, and **how** the pieces integrate. Read the way the drift-check engine reads, but constructively — you're describing what the code *does*, each claim anchored to a real file or symbol in the diff. If the **why** isn't evident from the code, the commit messages, or the PR/issue, infer it conservatively and mark the inference — or surface it as an open question and ask the user, rather than inventing motivation.

4. **Write the spec + plan content directly into the summary.** From that understanding, construct the summary's `## Spec` and `## Plan` sections to the shapes defined in **[`references/summary-format.md`](references/summary-format.md)** (the *Spec shape* and *Plan high-level shape*) — composed in Step 3, not as separate files. On top of that shared format, Mode B adds:
   - Ground **every** line in the diff. The spec stays product-level (no file paths or symbols); only the `## Architecture plan` may name concrete files / symbols / config keys.
   - The summary carries a single date — the header `**Date**` (today, when you author the summary); do **not** emit a `**Created**` line. If noting when the change shipped matters, put that in the Step 5 hand-off, not in the summary.
   - Where the change gives no signal for a section, write the honest minimum (e.g. `## Open Questions` → "None — reverse-engineered from a shipped change.") rather than padding; and don't invent phases, steps, risks, any `**Created**` line, or plan-level Open Questions.

   You now hold exactly what Mode A holds at the end of Step 2A — a full spec and a plan high-level — ready for Step 3 to lay out.

### Step 3 — Compose `Summary_<name>.md` (both modes)

Write the summary to its home — `agent-memory/<team>/Summary_<name>.md` for a single-team design, `agent-memory/cross-team/Summary_<name>.md` for a cross-team design, or `agent-memory/global/Summary_<name>.md` for an org-wide design — following the structure in **[`references/summary-format.md`](references/summary-format.md)**: the summary envelope, the spec / plan shapes it embeds, and the header / omit rules. Both modes emit the identical file; only the source of the `## Spec` and `## Plan` content differs (verbatim spec + extracted plan in Mode A; both reverse-engineered from the change in Mode B).

### Step 4 — Register it in the index (idempotent, both modes)

Upsert a row matched on the `Summary_{name}` key (so re-running never duplicates): replace it in place if present, otherwise append it and drop any `_(none yet)_` placeholder. Which index depends on the target:

- **team** or **cross-team** → for **each** owning team, open `agent-memory/<team>/index.md`, find the **Design Summaries** table, and upsert the row.
- **org-wide (`global`)** → open `agent-memory/global/index.md` and upsert the row there. If that index doesn't exist yet, create it first with the same shape as a team index (a short heading plus a `| Entry | Title | Date | Summary | When to read |` table) — it comes into being with the first global summary.

The **Design Summaries** table carries five columns — `| Entry | Title | Date | Summary | When to read |`. The **When to read** cell is a short trigger that tells a future agent, scanning the index, whether *this* entry is relevant to the task in front of it — so it opens only the summaries that matter instead of all of them. Derive it from the spec's scope: name the task, feature area, and concrete code anchors (components, files, symbols, config keys, metric names) that touching *this* design would put someone near. Keep it to one scannable clause, and make it distinct from the **Summary** (which says *what* the design is, not *when* to open it). If the index's Design Summaries table predates this column (only four columns), add the `When to read` header and its separator cell too, so the table stays well-formed.

Link the entry to wherever the file actually lives, relative to the index:

- single-team summary (file in the team folder): `| [Summary_{name}](./Summary_{name}.md) | {spec title} | {today} | {one-line summary} | {when-to-read trigger} |`
- cross-team summary (file in `cross-team/`, linked from a team index): `| [Summary_{name}](../cross-team/Summary_{name}.md) | {spec title} | {today} | {one-line summary} | {when-to-read trigger} |`
- org-wide summary (file in `global/`, linked from `global/index.md`): `| [Summary_{name}](./Summary_{name}.md) | {spec title} | {today} | {one-line summary} | {when-to-read trigger} |`

Because the summaries and indexes are all committed files in the same repo, the relative links resolve directly — there's nothing else to wire up (no separate registry, no sync step). `cross-team/` has no index of its own (a cross-team summary is discovered through the owning team indexes); `global/` has its own `index.md`, which a global instruction (e.g. in the repo's `AGENTS.md`) points agents at.

### Step 5 — Hand off (both modes)

Report the written summary path, the index row(s) you added/updated, and a one-line note on provenance:
- **Mode A** → the drift-check result (reconciled / no drift / not drift-checked).
- **Mode B** → the change source it was reverse-engineered from (working tree / PR #N / `<range>`), noting the summary was derived directly from the code (no drift check needed).

Leave everything **uncommitted** — the summary and index changes are now in the working tree of the same repo as the code, so they go in the **same PR** as the feature; the developer reviews and commits them alongside the code.

## Notes

- **Same output, two inputs**: Mode A (spec + plan) and Mode B (a diff) converge on the identical `Summary_<name>.md` structure — a `## Spec` + `## Plan` combination. The only difference is provenance: Mode A embeds an existing spec and drift-checks the plan; Mode B reverse-engineers both from the change — writing them only inside the summary, never as separate `spec.md` / `plan.md` files — and skips the drift check (the code is the source).
- **Idempotent**: re-running for the same `<name>` overwrites `Summary_<name>.md` and updates the matching index row (in each referencing team, or in `global/index.md` for an org-wide design), matched by the `Summary_<name>` key. No duplicates.
- **The index is a discovery surface**: each Design Summaries row carries a **When to read** trigger, so an agent that reads `index.md` first opens only the summaries relevant to its current task rather than every entry.
- **Committed with the code**: the memory lives in the repo (`agent-memory/...`), not under the gitignored `.github/`, so summaries are greppable and ship in the same PR as the feature they document.
- **Cross-team designs**: the summary is written once into `agent-memory/cross-team/` and linked from each relevant team's `index.md` (content is never duplicated; the team indexes are the discovery path — `cross-team/` has no index of its own); a single-team design stays in its team folder.
- **Org-wide designs**: a `global` summary is written once into `agent-memory/global/` and registered in `global/index.md` (the skill creates this index on the first global summary); it has no team row — agents reach it via a global instruction (e.g. in the repo's `AGENTS.md`) that points at `global/index.md`.
- **Drift check (Mode A) is a reconciliation, not a rewrite**: it proposes plan edits for the user to approve; it doesn't silently rewrite the plan or block on perfection.
