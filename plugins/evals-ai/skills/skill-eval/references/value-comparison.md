# Mode 3 — value comparison (isolated arms + blind judge, mean-based)

The core question: **does the skill add real value over no skill at all?** We answer it by running
the same task with and without the skill, scoring each run blind against fixed expectations, and
comparing the *averages*. This mirrors skill-creator's benchmark (mean pass-rate + delta), not a
pick-a-winner duel.

## Protocol (per `value_task`)

`value_repeats` defaults to **2** — the only repeated step. For each task, do `2 × value_repeats`
**arm runs** total. Each arm runs as a **separate, headless `copilot` process rooted in its own
isolated environment directory** — never as a `task`-spawned subagent (see *Why isolated processes*).
`<eval-tool-dir>/scripts/run_isolated_arm.py` does the whole thing: it builds the env, runs the arm, and captures the
response. Write the task `prompt` to a file first (self-contained — inline any inputs) and pass it as
`@<task-file>` so multi-line prompts survive.

For `run_index` in `1..value_repeats`, and for each `configuration`:

1. **Run the arm** with `--mode <baseline_mode>` (default `isolated`; `in-context` for skills that need
   the real codebase — see *Two baseline modes* below):
   - **without-skill (baseline)** —
     `python "<eval-tool-dir>/scripts/run_isolated_arm.py" --arm without --mode <mode> --skill-dir <target-skill-dir> --task "@<task-file>" --out <runs>/<task>-without-<i>/output.md`
   - **with-skill** —
     `python "<eval-tool-dir>/scripts/run_isolated_arm.py" --arm with --mode <mode> --skill-dir <target-skill-dir> --task "@<task-file>" --out <runs>/<task>-with-<i>/output.md`

   In **`isolated`** mode the without env is empty and the with env holds only the target's staged
   closure (`stage_skill.py`; `evals/` excluded). A target with `plugin.json` is also loaded with
   `--plugin-dir` so its bundled agents are registered. In **`in-context`** mode both envs are a worktree of
   the repo (`--repo`, or the cwd's repo) with the real `.github/` overlaid, differing only by the
   target skill's own folder and any required bundled agents; the with-skill arm restages the current
   source even if the installed copy is stale. Both arms also replicate your uncommitted work by
   default (`--head-only` for a clean HEAD). Either way, review the arm's printed manifest — an
   `unresolved` entry may flag a missing dependency. Pass `--model <executor-model>` (record it in
   `metadata.evaluator_models.executor`) and optionally `--timeout <sec>` to bound a flailing arm
   (default: 1800 seconds per arm). Use the same time limit for both configurations. A timed-out arm
   is killed; there is no late subagent result to await. Keep and blindly grade its partial output,
   record the failure in `runs[].metrics.errors`, and lower confidence rather than discarding that repeat.
   Pass `--model <executor-model>` only when the author explicitly selected one; when metadata says
   `runtime-default`, omit the flag so both configurations inherit the current Copilot CLI default.
   If the with-skill preflight rejects a bundled agent hidden from both user and model invocation,
   **stop without scoring Mode 3**: this headless CLI cannot dispatch it, so the comparison would
   measure an incomplete skill. Report the agent names and ask the author to fix invocation metadata
   or use a compatible runner. Do not rewrite the target's agents in scratch just to get a score.
2. **Persist the run** (`run_isolated_arm.py` already wrote the response to `--out`): copy any files
   the arm produced in its env into `runs/<task>-<config>-<i>/`, and keep the response as both the
   `output` and a short `transcript`. Then the env may be deleted.

Keep effort symmetric — the task, model, and prompt are identical across arms; the **only** difference
is whether the target skill and its required closure are discoverable.

## Two baseline modes (`metadata.config.baseline_mode`)

**`isolated`** (default) — cheap synthetic envs; for skills whose tasks are **self-contained** (the
prompt carries everything: install-python, api-design-helper, a lookup). without = only CLI built-ins;
with = built-ins plus the target's dependency closure. Measures the skill's value **vs no added
skill**. No repo code in the env. Bundled plugin agents are staged under `.github/agents/` and the
plugin is loaded with `--plugin-dir`; both are necessary for an honest multi-agent comparison.

**`in-context`** — for skills that need the **real codebase** (PR review, anything that opens files).
Per arm, `run_isolated_arm.py` builds a **detached git worktree at HEAD** of the repo skill-eval is
invoked in (real code; shares `.git`; git works) and **overlays the real `.github/`** (all synced
skills/agents/knowledge_base/instructions — the worktree's gitignore skips them). The arms then differ
by the target skill and any bundled agents: with-arm restages the current target source;
without-arm deletes its skill folder — all other skills stay. So the delta is the target's
**marginal** value on real code, *among all the other skills* (the realistic deployed question), not vs
nothing. By default both arms also replicate your **uncommitted work** — working tree **and** index (via
`git stash create` / `apply --index`) plus untracked files — so the eval reflects the code you actually
have in front of you; pass `--head-only` to evaluate the clean HEAD commit instead. Full worktrees (not
sparse) so the reviewer can open any file. The env is a real git
root, so `copilot -C <env>` still scopes skill discovery to it. Cleanup: `git worktree remove --force`.

## Why the whole closure (not just SKILL.md)

A skill is more than its `SKILL.md`. It bundles `references/` and `scripts/`, it dispatches agents
(which read their own `knowledge_base`/`instructions` files), and it links sibling skills. If the
with-skill run only saw `SKILL.md`, a multi-agent reviewer that delegates to a specialist agent,
reads bundled review rules, and calls a sibling helper skill would run crippled; its `delta` would
understate its real value, and the verdict would be wrong.
`scripts/stage_skill.py` resolves the **transitive** closure (skill → its files → its agents → their
files → linked skills → …, de-duplicated and depth-capped) into the env's `.github/` mirror, so the
with-skill arm sees the skill exactly as it works in production. It **excludes every `evals/` subtree**
— the arm must never see the cases it will be graded on.

## Why isolated processes (not subagents)

The Copilot **runtime auto-discovers skills** from the workspace's `.github/skills/` and advertises
them to the model — and to any subagent it spawns. A `task`-spawned executor therefore shares the
current session's workspace: on a real repo with synced skills, the baseline would have the target
skill advertised to it, and the with-skill arm would see every *other* skill too — the comparison is
no longer "just this skill". A "don't read the repo" instruction cannot stop the runtime from loading
a skill, and a subagent might invoke one on its own.

The fix is **environment isolation, by construction**: `run_isolated_arm.py` runs each arm as its own
`copilot` process rooted with `-C <env>` in a dedicated directory (its own git root). It supplies a
temporary `COPILOT_HOME` with only the user's authentication config, a temporary home directory, and
`COPILOT_PLUGIN_DIR_ONLY=true` so personal skills, agents, instructions, and installed plugins are
not discovered. The runtime's `skill list --json` is checked before scoring: any skill outside the
workspace (apart from built-ins) aborts the arm. The authentication copy is deleted after each CLI
process, including timeouts. The arm runs **without** `--allow-all-paths`, so its file tools stay
inside the env and cannot read the real repo.

**Validated:** an env holding a canary skill (with an unguessable secret) yields the secret; an empty
env cannot — the model searches, finds no such skill, and returns nothing.

## Residual gap (honest bound)

This closes skill auto-discovery and confines the arm's file tools to its env, but it is **not** a
hard OS sandbox: a determined arm could still shell out to read a foreign absolute path (empirically
Copilot even denies most out-of-workspace shell reads, but that is not guaranteed). Full airtightness
needs an OS-isolated container that mounts only the env (the MSBench model), deliberately out of scope
here. If a `delta` looks suspiciously low (≈0 where the skill clearly carries knowledge the model
lacks), spot-check the baseline `output.md` for stray reads.

## Grading (blind)

For **every** output (all `2 × value_repeats` of them), spawn `evals-ai:skill-eval-judge` with the output (or
its path), the task `prompt`, and the task's `expectations[]`. If `metadata.judge_guidance.general`
or `.value` is non-empty, pass it under an **"Author guidance"** heading — it clarifies what a good
answer means for this task, but the judge still grades each expectation honestly. **Do not tell the
judge which configuration produced the output.** It returns per-expectation pass/fail + evidence and a
`pass_rate` (0–1). Because each output is scored independently and blind, there is no pairing and
therefore no position bias to correct; blindness handles any pro-skill bias.

## Aggregate (orchestrator)

Per configuration, over its `value_repeats` runs, compute `mean`, `stddev`, `n` of `pass_rate` →
`with_skill_summary` / `without_skill_summary`. Then:

- `delta` = `with_mean − without_mean` (a pass-rate difference in [−1, 1]).
- `verdict` (default thresholds — document if you change them):
  - `delta ≥ 0.15` → **skill helps**
  - `delta ≤ −0.15` → **skill hurts**
  - otherwise → **no clear value**
- `confidence` = `high` if `|delta|` clearly exceeds the run-to-run spread (e.g. `|delta| ≥ 2×max(stddev)`),
  `low` if the spread swamps the delta, else `medium`. Low confidence is a signal to raise
  `value_repeats` or sharpen the expectations.

Roll the per-task results into a top-level `summary` (`delta` = mean of task deltas, an overall
`verdict`, and `confidence`).

## Output contract (`value_comparison` fragment + `runs[]` registry)

```
{
  "value_repeats": 2,
  "tasks": [
    {
      "id": "rotate-pdf", "prompt": "...", "expectations": ["...", "..."],
      "runs": [
        {"run_index": 1, "configuration": "without_skill",
         "score": {"pass_rate": 0.5, "passed": 2, "total": 4, "quality_score": 6},
         "output_ref": "runs/rotate-pdf-without-1/output.md",
         "transcript_ref": "runs/rotate-pdf-without-1/transcript.md"}
        // ... with_skill and the other repeats
      ],
      "with_skill_summary": {"mean": 0.875, "stddev": 0.125, "n": 2},
      "without_skill_summary": {"mean": 0.5, "stddev": 0.0, "n": 2},
      "delta": 0.375, "verdict": "skill helps"
    }
  ],
  "summary": {"delta": 0.375, "verdict": "skill helps", "confidence": "high"}
}
```

Also append one entry per arm run to the top-level `runs[]` registry (`run_id`, `configuration`,
`task_id`, `run_index`, `transcript_ref`, `output_ref`, `metrics`).
