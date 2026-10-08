---
name: skill-eval
description: >
  Evaluate how good an existing skill is. Run a one-shot quality sweep over a target skill that
  (1) scores how well it is written, (2) checks whether its description triggers on the right
  requests, and (3) measures whether it adds real value versus no skill at all — then write a
  local JSON result and a self-contained HTML report with prioritized fixes. Use this whenever
  the user wants to evaluate, score, audit, test, benchmark, or measure a skill's quality or worth;
  asks "is this skill any good", "does this skill actually help", "should we keep this skill", or
  "how do I know if my skill works"; wants a with/without comparison, a description/trigger check,
  or a skill quality report; or wants to compare skills against each other. Operates on any local
  skill directory, including workspace skills and skills inside plugins. Diagnose-only: it never
  edits the evaluated skill's implementation.
argument-hint: "<skill-name-or-path> [evaluation options]"
user-invocable: true
---

# Skill Eval

Measure whether a skill is well-written, correctly triggered, and genuinely valuable. One **sweep**
evaluates one target skill three ways and writes two local artifacts the author can review and
compare across skills and over time. This is **diagnose-only** — it never edits the target; acting on
the findings (fixing the skill) is the author's job.

## When to use

Use it when an author wants to know if a skill earns its place: before publishing a new skill,
when auditing an existing one, or when comparing skills. It shines on substantive, multi-step
skills — that is where the with/without comparison has signal.

## When not to use

Don't use it to *change* a skill (that's the author's job, informed by the findings), to evaluate
untrusted third-party skills, or to run unattended CI — it is a manual, human-in-the-loop tool.

## Self-contained — no external dependencies

skill-eval references **nothing else in the repo**. All validation, scaffolding, staging, isolated
execution, and reporting live in its own `scripts/`; all protocols live in its own `references/`; it
bundles its own agents. Its only repo touchpoints are the target skill (and the dependency closure it
stages for the with-skill run) it reads, the two agents it spawns, the isolated `copilot` arms it runs
for Mode 3, and the `evals/` outputs it writes. Do not add a dependency on any other skill, plugin, or
shared script. (Mode 3 shells out to the `copilot` CLI to run each arm in its own isolated workspace —
that is the one external tool it invokes.)

At invocation time, `${CLAUDE_SKILL_DIR}` is this installed skill directory. Treat that absolute path
as `<eval-tool-dir>` throughout the workflow. Every command in this skill and its references that uses
`<eval-tool-dir>` must be expanded to that directory; never assume the current workspace contains the
evaluator's `scripts/` or `references/`.

## The sweep (pipeline)

```
Step 0  Pre-flight        resolve + validate target, scaffold the sweep folder
Step 1  Test cases        reuse-or-generate evals.json             → references/evals-lifecycle.md
Step 2  Judge guidance    author's scoring steer (skippable)       → references/preflight-review.md
Step 3  Scenario review   author approves the prompts (skippable)  → references/preflight-review.md
Step 4  Mode 1 (analyzer) static quality rubric, run once          → references/static-rubric.md
Step 5  Mode 2 (isolated CLI) actual skill triggering, 3×/prompt → references/triggering-check.md
Step 6  Mode 3 (isolated arms+judge) with/without value comparison → references/value-comparison.md
Step 7  Synthesis         consolidate findings (diagnose-only)     → references/findings-synthesis.md
Step 8  Assemble          fill + validate result.json
Step 9  Report            generate the self-contained report.html  → references/report-layout.md
Step 10 Feedback+override optional; author's verdict is the final word → references/author-response.md
```

Read each reference file just before you run that step — keep this body lean (progressive
disclosure). The exact JSON shapes for every artifact are in `references/schema.md`, enforced by
`scripts/eval_schema.py`.

## Bundled agents (spawned via the `task` tool)

Two evaluator agents score **text**, so they run as ordinary subagents:

| Agent | Model | Role |
|-------|-------|------|
| `evals-ai:skill-eval-analyzer` | Runtime-selected | Independent text evaluator: scores Mode 1 (static rubric) over the target's authored text in fresh context. |
| `evals-ai:skill-eval-judge` | Runtime-selected | Independent **blind grader**: scores one output against a task's `expectations[]` into a `pass_rate`, blind to which configuration produced it. |

Mode 3's **executor is deliberately NOT a subagent** — it must run in a truly isolated environment. A
subagent shares this session's workspace, so the runtime would advertise the target skill to the
baseline and every other skill to the with-skill arm (a subagent might even invoke one on its own).
Instead, `scripts/run_isolated_arm.py` runs each arm as its own headless `copilot` process rooted
(`-C`) in a dedicated env whose `.github/skills/` we control (per `baseline_mode`: `isolated` = empty
baseline / target-closure with-skill; `in-context` = a repo worktree overlaid with the real `.github/`,
ablated by only the target folder). The `executor` entry in `metadata.evaluator_models` is the model
that script passes to `--model`. See `references/value-comparison.md`.

The analyzer and judge have no pinned model: omit the `model` argument when spawning them unless the
author explicitly requests an override. Runtime session and subagent preferences determine their
models. `metadata.evaluator_models.analyzer` and `.judge` default to `"runtime-default"`; record the
resolved model there when it is available. The isolated executor remains
separately configurable with `--executor-model`, but also defaults to `"runtime-default"` so the
Copilot CLI selects its current supported default. The orchestrator (you) owns *structure and
synthesis only*; it never scores anything itself. When
`metadata.judge_guidance` is non-empty, pass the relevant part into the analyzer/judge prompts under
an "Author guidance" heading (Steps 4 and 6). Mode 2 runs the approved prompts exactly and is never
modified by guidance.

## Step 0: Pre-flight

1. Resolve the target skill directory from the user's name or path. Accept any directory containing
   `SKILL.md`, including workspace locations such as `.github/skills/<name>/`,
   `.claude/skills/<name>/`, and plugin locations such as `plugins/<plugin>/skills/<name>/`. For a
   bare name, search the current workspace for matching `skills/<name>/SKILL.md` paths. If more than
   one matches, use the host's user picker to select one; never guess.
2. Validate it:
   `python "<eval-tool-dir>/scripts/eval_schema.py" frontmatter <target>/SKILL.md`. If invalid, stop and
   tell the author — there is nothing meaningful to evaluate.
3. Read the target `SKILL.md` (you need the authored text for Mode 1 and the target name for Mode 2).
4. Decide the sweep config: `value_repeats` (default 2), `trigger_prompts_total` (default 10),
   `trigger_repeats` (default 3), `comparison_tasks` (default 2), the `baseline_mode`
   (`isolated` default, or `in-context`; see Step 6), and whether feedback is enabled
   (default **on**; the author can turn it off).
5. Scaffold the sweep folder and skeleton `result.json`:
   `python "<eval-tool-dir>/scripts/new_sweep.py" <target-dir> --value-repeats 2 --feedback on` — it prints the
   `results/<timestamp>/` path. Everything else writes under there.

## Step 1: Test cases — reuse or generate

Follow `references/evals-lifecycle.md`. In short: if `<target>/evals/evals.json` exists, **reuse it
unchanged** (so scores stay comparable over time) and set `metadata.evals_source = "reused"`. Only
when it is missing — or the author explicitly asks to regenerate — generate the value-comparison
tasks (with `expectations[]`) and the balanced should-/should-not-trigger prompts, validate with
`python "<eval-tool-dir>/scripts/eval_schema.py" evals <path>`, write the committed file, and set
`evals_source = "generated"`.

## Step 2: Judge guidance (optional, skippable)

Follow `references/preflight-review.md`. On an interactive single-skill sweep, before any scoring,
ask the author how the judge should score this skill — what to weight, the intended audience/scope,
trade-offs to accept or discount. Record it in `metadata.judge_guidance` (`general` + optional
per-mode `static`/`value`); Steps 4 and 6 pass the relevant part to the analyzer/judge under
an "Author guidance" heading. Guidance calibrates emphasis, **never** a licence to inflate scores.
If the author skips it, leave `judge_guidance` empty and move on — **never block**.

## Step 3: Scenario review (optional, skippable)

Follow `references/preflight-review.md`. Show the author exactly what will run before spending the
runtime budget:
`python "<eval-tool-dir>/scripts/preflight_brief.py" <target>/evals/evals.json` prints the Mode-3 value
tasks (+ their pass/fail expectations) and the Mode-2 should-/should-not-trigger prompts. Let them
approve or edit. The trigger intent is the skill author's **Expected Result**; the user can override
it here by flipping `should_trigger` / `should_not_trigger`. Apply edits to `evals.json` and
**re-validate** (`eval_schema.py evals`) before proceeding, then set
`metadata.scenarios_reviewed = true`. On reuse, note the set is reused and
proceed unless asked to review. If the author skips it, leave `scenarios_reviewed = false`.

## Step 4: Mode 1 — static quality rubric (analyzer, run once)

Follow `references/static-rubric.md`. Spawn `evals-ai:skill-eval-analyzer` to read only the target's authored
text (never execute it) and score the five fixed dimensions 1–5 (or `N/A` when a dimension doesn't
apply) with rationale + evidence, an
`average_score`, and `top_improvements[]`. Write the `static_quality` block.

## Step 5: Mode 2 — actual triggering (isolated CLI, three runs per prompt)

Follow `references/triggering-check.md`. For every approved trigger prompt, run
`<eval-tool-dir>/scripts/run_trigger_check.py` three times in an isolated environment containing the target skill.
The runner observes the CLI's exact `skill` tool invocation event; merely loading the skill does not
count. Assemble the observations with `<eval-tool-dir>/scripts/assemble_triggering.py`, then write the `triggering`
block. Failed runs are incomplete coverage, never `not_triggered`.

## Step 6: Mode 3 — value comparison (isolated arms + judge, mean-based)

Follow `references/value-comparison.md`. For each comparison task, run `value_repeats`
**without-skill** arms and `value_repeats` **with-skill** arms (the only repeated step) — each as an
**isolated `copilot` process**, not a subagent, via
`python "<eval-tool-dir>/scripts/run_isolated_arm.py" --arm {without|with} [--skill-dir <target>] --task "@<file>" --out <runs>/...`.
Each arm has a **1,800-second default timeout** (override with `--timeout <seconds>`); pass the
same limit to both configurations. Expiry kills that process and its subagents, so no late result
can arrive from the timed-out run.
Pass `--mode <metadata.config.baseline_mode>`: **`isolated`** (default) builds cheap synthetic envs
(baseline empty; with-skill = only the target's staged closure) for self-contained skills;
**`in-context`** builds a git worktree of the repo at HEAD — replicating your uncommitted work (working
tree + index + untracked) by default, `--head-only` for a clean HEAD — with the real `.github/` overlaid,
ablated so the baseline omits the target — for skills that need the real codebase (PR review).
The with-skill arm restages the **current target source** (not a stale installed copy) and
loads its bundled plugin agents. Each CLI process uses a temporary Copilot home (authentication
only), suppresses ambient plugins and personal skills, and verifies its effective skill list;
the private home is removed when the process exits. Either way the env, not an instruction,
controls what the runtime can discover, which keeps the comparison honest (see *Why isolated
processes* and *Two baseline modes*). You (the
orchestrator) then persist each arm's response (already written to `--out`) plus any files it produced
into `runs/`. Spawn `evals-ai:skill-eval-judge` once per output as a **blind** grader
scoring it against the task's `expectations[]` into a `pass_rate`. Aggregate each configuration to
`mean ± stddev`, compute a single `delta = with_mean − without_mean`, and a `verdict` (skill helps /
no clear value / skill hurts). Independent blind scoring means there is no pairing and no position
bias to correct. Write the `value_comparison` block and append each run to the `runs[]` registry.
If the executor rejects bundled agents as undispatchable, stop before scoring Mode 3 and report
missing coverage; do not treat a CLI compatibility failure as evidence that the skill hurts.

## Step 7: Synthesis — consolidated findings (diagnose-only)

Follow `references/findings-synthesis.md`. Merge the three blocks into one deduplicated,
severity-ranked `consolidated_findings` list, each with `source_modes`, a concrete `recommendation`,
and a `phase2_actionable` flag. **Recommend only — never edit the target skill.**

## Step 8: Assemble + validate

Write the filled `result.json` into the sweep folder, then validate it:
`python "<eval-tool-dir>/scripts/eval_schema.py" result <results>/result.json`. Fix any reported error before
continuing — a malformed result breaks cross-skill comparison.

## Step 9: Report

`python "<eval-tool-dir>/scripts/generate_report.py" <results>/result.json` writes a self-contained `report.html`
next to it (radar, Mode-3 mean comparison, actual-triggering table, prioritized fixes). The layout is fixed
and keyed to `schema_version`, so every skill's report is structurally identical and comparable. See
`references/report-layout.md`.

## Step 10: Feedback + human override (optional)

Follow `references/author-response.md`. Two optional ways for the author to respond to the report:

- **Feedback (advisory)** — structured notes/stances per mode and per finding, saved to a versioned
  `feedback.json`. Does **not** change any verdict.
- **Human override (authoritative)** — if the author disagrees with a judge decision or a trigger
  prompt's Expected Result, record their call in `human_override.json`; it **supersedes** the original
  value where set, while `result.json` keeps the immutable record for a traceable audit trail.
  Validate with `python "<eval-tool-dir>/scripts/eval_schema.py" override
  <path>`, then re-run `generate_report.py` so the report shows the override banner.

**Never block** — if the author skips, finish. `metadata.feedback_enabled` records the choice (set at
Step 0; the result's structure is unchanged either way).

## Local output

Tell the author where to find the artifacts. Only the reusable `evals.json` test cases may be
committed after review; everything under `evals/results/` remains local. When the target belongs to
a Git repository, `new_sweep.py` records the results path in the repository's local
`.git/info/exclude` without changing tracked ignore files:

```
<target>/evals/evals.json                       (reusable cases; review before committing)
<target>/evals/results/<timestamp>/result.json  (local source of truth)
<target>/evals/results/<timestamp>/report.html  (open in a browser)
<target>/evals/results/<timestamp>/feedback.json (only if captured)
<target>/evals/results/<timestamp>/human_override.json (only if the author overrode the judge)
```

Never force-add `evals/results/` to Git or include its prompts, transcripts, feedback, or report in a
commit. Verify the path is ignored before finishing. Keep the full sweep and any author override
together on the local machine.

## Must not

- **Never edit the evaluated skill.** This sweep diagnoses and recommends; applying the fixes is the
  author's job.
- **Run every Mode-3 arm in an isolated environment, never as a subagent.** The Copilot runtime
  auto-advertises workspace skills (even to subagents), so a subagent baseline is not skill-free. Use
  `scripts/run_isolated_arm.py` (a headless `copilot -C <env>` per arm). In `isolated` mode the baseline
  env has only the CLI's built-ins and the with-skill env holds the target's closure; in `in-context`
  mode both envs are a worktree with the real `.github/` overlaid, ablated by the target folder;
  the with-skill arm also stages the target's required agents. A contaminated baseline silently
  collapses the Mode-3 delta.
- Give the **with-skill** arm the skill's *whole* dependency closure (via `scripts/stage_skill.py`),
  not just `SKILL.md` — a skill starved of its references/agents/linked-skills understates its value
  just as badly. Never stage a skill's `evals/` into an arm's env — it would leak the very cases the
  judge grades against. Never change the evaluated skill's agent invocation flags to make an arm pass.
- Never change the JSON shape or report layout without bumping `SCHEMA_VERSION` in
  `scripts/eval_schema.py` — comparability depends on it.
- A `human_override.json` is the author's final word and supersedes the original Expected Result or
  AI judgment where set, but **never edit `result.json` to bake it in** — that file must stay the
  immutable record so the
  override remains an auditable diff (see `references/author-response.md`).

## Self-Evolution

This skill improves by being used. After a sweep, briefly note any friction and offer to fix it —
keep changes proportional, and remember the skill is run by another agent instance.

| Signal | What it means | Likely fix |
|--------|---------------|------------|
| The analyzer/judge often returns malformed JSON | The mode reference's output contract is unclear | Tighten the example in the relevant `references/*.md` |
| Verdicts feel noisy run-to-run | `value_repeats` too low, or expectations too vague | Raise the repeat default, or sharpen `evals.json` expectations |
| The same fix recommendation recurs across many skills | A real cross-skill pattern | Encode it as a rubric anchor in `references/static-rubric.md` |
| A step needed info not in its reference | Reference gap | Add the missing guidance to that `references/*.md` |

If two or more signals occur in one run, surface a short, specific improvement suggestion (name the
file and the change) and ask before applying.
