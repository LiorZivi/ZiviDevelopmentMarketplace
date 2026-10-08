# skill-eval data contract (`skill-eval/v5`)

This is the human-readable source of truth for reusable cases and local sweep artifacts.
The machine source of truth is `scripts/eval_schema.py` (`SCHEMA_VERSION =
"skill-eval/v5"`), which validates each shape and computes a content-independent
`structural_signature`. **If you change a shape here, change it there and bump
the version.** Every consumer depends on this contract, so it must stay stable.

## Where artifacts live (co-located, results local)

Every sweep writes under the **evaluated** skill. Only `evals.json` is intended for version
control; `evals/results/` is ignored by Git and remains on the author's machine:

```
<target-skill>/evals/
  evals.json                          # reusable test cases (review before committing)
  results/<YYYYMMDD-HHMMSS>/
    result.json                       # the sweep result (source of truth)
    report.html                       # self-contained viewer
    feedback.json                     # optional advisory review (interactive path)
    human_override.json               # optional authoritative override of the judge
    runs/                             # raw executor/judge transcripts & outputs
```

Local `result.json` history accumulates as timestamped folders — that is the score
history on this machine; there is no separate trend file or committed run output.

## Cross-skill comparability

`structural_signature(result)` returns a key skeleton with all values and list
lengths erased, so **two conformant results for any two skills produce the same
signature**. The report layout is keyed to `schema_version`. Together these
guarantee every skill's outputs are directly comparable. `metadata.feedback_enabled`,
`metadata.judge_guidance` (fixed keys), and `metadata.scenarios_reviewed` are always
present, so the signature is identical whether or not feedback, guidance, or a scenario
review happened.

---

## result.json

| key | meaning |
|-----|---------|
| `schema_version` | fixed `"skill-eval/v5"` |
| `metadata` | provenance + config (below) |
| `static_quality` | Mode 1 output |
| `triggering` | Mode 2 output |
| `value_comparison` | Mode 3 output |
| `consolidated_findings` | synthesis across the three modes |
| `runs[]` | execution registry: one entry per executor/judge run |

**metadata**: `target_skill`, `target_skill_path`, `target_skill_description`,
`sweep_id`, `created_at` (ISO-8601), `evaluator_models` (`executor` / `analyzer`
/ `judge`; each uses `"runtime-default"` when inheriting the runtime-selected model, or the resolved
model when explicitly known), `eval_runtime` (e.g. `"copilot-cli"`), `evals_source`
(`generated` | `reused`), `feedback_enabled` (bool), `judge_guidance` (fixed keys
`general`/`static`/`value`, empty = none — the author's Step-2 scoring
steer), `scenarios_reviewed` (bool — author approved the test set at Step 3), `config`
(`trigger_prompts_total`, `trigger_repeats`, `comparison_tasks`, `value_repeats`,
`baseline_mode` = `isolated` | `in-context` — the Mode-3 environment strategy).

**static_quality** (Mode 1, run once): `dimension_set_version`, `scale`
(e.g. `"1-5"`), `dimensions[]` (`name`, `score` 1–5 or `"N/A"`, `rationale`, `evidence`),
`average_score` (mean of the numeric scores; N/A excluded), `top_improvements[]` (`text`, `priority`,
`dimension`). The five fixed dimensions are defined in `references/static-rubric.md`.

**triggering** (Mode 2, actual isolated runs): `trigger_repeats`; `prompts[]` (`id`,
`prompt_text`, `expected_result` = `should_trigger`|`should_not_trigger`,
`actual_result` = `triggered`|`not_triggered`, `trigger_rate`, `runs[]`).
Each run records `run_index`, `triggered`, `events_ref`, `response_ref`,
`duration_s`, and `errors`. `summary` contains `matches`, `mismatches`, `total`,
`accuracy`, `false_positive`, and `false_negative`.

**value_comparison** (Mode 3, mean-based): `value_repeats`; `tasks[]` each with
`id`, `prompt`, `expectations[]`, `runs[]`, `with_skill_summary`,
`without_skill_summary`, `delta`, `verdict`; plus a top-level `summary`
(`delta`, `verdict`, `confidence`).
- each `runs[]` item → `run_index`, `configuration` (`with_skill`|`without_skill`),
  `score` (`pass_rate` 0–1, `passed`, `total`, optional `quality_score`),
  `output_ref`, `transcript_ref`.
- each `*_summary` → `mean`, `stddev`, `n` (over the repeats of that configuration).
- `verdict` ∈ {`skill helps`, `no clear value`, `skill hurts`}, derived from the
  delta and the spread.

**consolidated_findings**: `findings[]` (`id`, `title`, `severity` =
high|medium|low, `source_modes[]`, `recommendation`, `rationale`,
`phase2_actionable` bool), `priority_order[]` (finding ids), `overall_assessment`.

**runs[]** (registry): `run_id`, `configuration`, `task_id`, `run_index`,
`transcript_ref`, `output_ref`, `metrics` (`tool_calls`, `tokens`,
`duration_s`, `errors`).

---

## evals.json (reusable test cases)

`evals_version` (`"skill-eval-evals/v1"`), `target_skill`, `generated_at`,
`value_tasks[]` (`id`, `prompt`, `expectations[]` — verifiable statements the
grader scores each run against), `trigger_prompts[]` (`id`, `prompt_text`,
`intent` = `should_trigger`|`should_not_trigger`). The intent is the skill author's
Expected Result; the user may override it during scenario review before scoring.

Generated once, then **reused** on every later run so scores stay comparable;
regenerated only when missing or on explicit request (see
`references/evals-lifecycle.md`).

---

## feedback.json (optional, interactive path only)

`schema_version`, `target_skill`, `sweep_ref` (which `results/<timestamp>/` it
annotates), `created_at`, `static_quality_feedback` (overall and/or per-dimension
`stance`/`note`), `triggering_feedback` (overall and/or per-prompt `stance`/`note`),
`value_comparison_feedback` (`stance`/`note` on the `delta`/`verdict`),
`findings_feedback[]` (`finding_id`, `stance` = agree|disagree|edit|annotate,
`note`), `overall_notes`.

Capture only — advisory. See `references/author-response.md`.

---

## human_override.json (optional, authoritative)

The author's final word, overriding the AI judge where present; kept as a separate
file so `result.json` stays the pristine AI record (see `references/author-response.md`).
`schema_version`, `target_skill`, `sweep_ref`, `created_at`, `author`, and — each one
optional (null scalar / empty list = no override) — `value_verdict` (∈ the value
verdicts), `value_note`, `static_average` (1–5), `static_note`, `dimension_overrides[]`
(`name`, `score` 1–5 or `"N/A"`, `note`), `trigger_overrides[]` (`prompt_id`,
`expected_result` = `should_trigger`|`should_not_trigger`, `note`),
`finding_overrides[]` (`finding_id`, `action`
= keep|dismiss|reseverity, `severity?`, `note`), `overall_note`.

Where it provides a value, that value wins; otherwise `result.json` stands.

---

## Validate from the command line

```
python "<eval-tool-dir>/scripts/eval_schema.py" result    <path>/result.json
python "<eval-tool-dir>/scripts/eval_schema.py" evals      <path>/evals.json
python "<eval-tool-dir>/scripts/eval_schema.py" feedback   <path>/feedback.json
python "<eval-tool-dir>/scripts/eval_schema.py" override   <path>/human_override.json
python "<eval-tool-dir>/scripts/eval_schema.py" frontmatter <skill>/SKILL.md
python "<eval-tool-dir>/scripts/eval_schema.py" signature  <path>/result.json
```
