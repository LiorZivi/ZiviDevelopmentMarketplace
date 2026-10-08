# Test-case lifecycle — reuse or generate `evals.json`

`evals.json` holds the **reusable** test cases for a target skill: the value-comparison `value_tasks`
and the `trigger_prompts`. Reusing the same cases across runs is what makes a skill's scores
comparable over time, so the rule is: **reuse if present, generate only if missing.**

## The gate

1. Look for `<target>/evals/evals.json`.
2. **If it exists** → reuse it unchanged. Set `metadata.evals_source = "reused"`. Do not regenerate
   just because the skill changed; only regenerate if the author explicitly asks (e.g. "regenerate
   the test cases"). Reusing keeps the comparison fair across time.
3. **If it is missing** (or the author asked to regenerate) → generate it (below), validate, write
   it, and set `metadata.evals_source = "generated"`.

## Generating

Read the target `SKILL.md` to understand what the skill is for, then write realistic cases.

### `value_tasks[]` (default `comparison_tasks` = 2)

Each task is a realistic, substantive request a real user of this skill's domain would make — the
kind of multi-step task where a good skill should actually help. For each task write:

- `id` — short stable slug (e.g. `"rotate-pdf"`).
- `prompt` — the user request, concrete and self-contained (include any small inputs inline).
- `expectations[]` — 3–6 **objectively checkable** statements the output must satisfy (these are
  what the blind judge grades against). Good expectations test *outcomes*, not style:
  - good: `"The output is a valid table with one row per input file"`,
    `"The summary names the specific failing pipeline stage"`.
  - weak: `"The answer is helpful"`, `"It is well written"`.

Pick tasks the skill claims to handle but that a bare model would plausibly do worse on — that is
where the comparison has signal. Avoid trivial one-step prompts.

### `trigger_prompts[]` (default `trigger_prompts_total` = 10, balanced)

Half `should_trigger`, half `should_not_trigger`. Make them realistic — what a user would actually
type, with concrete detail (file names, context, casual phrasing). For `should_not_trigger`, the
valuable ones are **near-misses**: prompts that share vocabulary with the skill but actually need
something else. Avoid obviously-irrelevant negatives — they test nothing. Each prompt: `id`, `prompt_text`, `intent` (`should_trigger` | `should_not_trigger`).
The intent is the skill author's Expected Result. The user reviews it before execution and may
override it by flipping the value; the Actual Result comes from three isolated Copilot runs.

## Validate + write

```
python "<eval-tool-dir>/scripts/eval_schema.py" evals <target>/evals/evals.json
```

Write the committed file at `<target>/evals/evals.json` with `evals_version`, `target_skill`,
`generated_at`, `value_tasks[]`, `trigger_prompts[]` (see `references/schema.md`). Only proceed once
it validates.
