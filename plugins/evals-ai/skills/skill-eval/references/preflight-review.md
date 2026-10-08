# Pre-eval review — judge guidance (Step 2) + scenario review (Step 3)

Two short **human-in-the-loop gates that run before any scoring**, so the author steers the
evaluation and sees exactly what will run. Both are **optional**: if the author skips a gate, never
block. Neither gate
changes the result's structure; they only populate two always-present metadata fields
(`judge_guidance`, `scenarios_reviewed`) seeded at Step 0.

## Step 2 — Judge guidance (how the judge should score)

Before the analyzer/judge run, invite the author to steer them:

> "Any guidance for how I should score this skill? For example: what to weight (safety, token cost),
>  the intended audience/scope, known trade-offs to accept, or anything to discount. Optional — say
>  skip to move on."

Capture the answer into `metadata.judge_guidance`, an object with three fixed string keys (empty = no
guidance):

- `general` — applies to the static analyzer and value judge (e.g. "CLI tool; assume expert users").
- `static` — Mode 1 only (e.g. "don't penalise brevity; verbosity is a real cost here").
- `value` — Mode 3 judging only (e.g. "credit correct command sequences even if terse").

Put a single free-form answer in `general`; only split into the per-mode keys if the author is
specific about a mode. Then, in Steps 4 and 6, pass the relevant strings (`general` + that mode's key,
when non-empty) into the agent prompt under an **"Author guidance"** heading.
Mode 2 runs the approved trigger prompts exactly; guidance must not alter those prompts.

### What guidance may and may not do

Guidance **calibrates emphasis and interpretation** — what "good" means for this skill, what to
weight, what to forgive. It must **not** turn the evaluators into rubber stamps: the analyzer still
scores honestly against the rubric, and the blind judge still grades each `expectation` on its
merits and stays blind to configuration. Guidance amounting to "just pass everything" is ignored.
This keeps guided runs comparable and the with/without delta meaningful.

## Step 3 — Scenario review (approve the test cases before they run)

Right after `evals.json` exists, show the author **exactly what will run** so they can catch a bad
prompt before spending the runtime budget:

```
python "<eval-tool-dir>/scripts/preflight_brief.py" <target>/evals/evals.json
```

It prints, read-only:
- the **value-comparison tasks** (Mode 3) — each task's prompt + the `expectations[]` the blind judge
  will grade against (this is where a vague expectation quietly wrecks the delta), and
- the **triggering prompts** (Mode 2) — each prompt's author-provided Expected Result
  (`should_trigger` / `should_not_trigger`). The user may override it before execution; the Actual
  Result comes from three isolated Copilot invocations.

Then ask the author to **approve or edit**. If they request changes (reword a prompt, fix an
expectation, flip an Expected Result/intent, add/remove a case), edit `evals.json`, then **re-validate before
proceeding**:

```
python "<eval-tool-dir>/scripts/eval_schema.py" evals <target>/evals/evals.json
```

Set `metadata.scenarios_reviewed = true` once the author has seen and accepted the set (edited or
as-is). Leave it `false` if the gate was skipped.

### Reuse vs generate

- **Generated this run** (`evals_source = "generated"`) → always show the brief; a fresh set is
  exactly what needs a human glance.
- **Reused** (`evals_source = "reused"`) → the set was reviewed before, so don't re-litigate it by
  default. Note it in one line — "reusing N tasks / M trigger prompts from a prior sweep; say
  'review' to inspect or edit" — and proceed unless the author asks to look.
