# Mode 2 — actual triggering (isolated Copilot runs)

Does Copilot actually invoke the skill for the right requests and stay out of the way for the
wrong ones? This mode runs every approved trigger prompt **three times** in a clean environment
containing the target skill, then observes the CLI's real `skill` tool invocation events.

## Expected Result

Each `trigger_prompts[]` entry in `evals.json` has an author-provided `intent`:

- `should_trigger` — the target skill is expected to be invoked.
- `should_not_trigger` — the target skill is expected not to be invoked.

This is the skill author's expected result, not an analyzer prediction. During Step 3 scenario
review, the user can override it by flipping the intent before any run starts. Re-validate
`evals.json` after an edit.

## How to run

For each prompt, run `metadata.config.trigger_repeats` isolated checks (default **3**) with the
same executor model:

```
python "<eval-tool-dir>/scripts/run_trigger_check.py" \
  --skill-dir <target-skill-dir> \
  --prompt "<exact trigger prompt>" \
  --out-dir <results>/trigger-runs/<prompt-id>-<run-index> \
  [--model <executor-model>]
```

Omit `--model` when `metadata.evaluator_models.executor` is `runtime-default`; both trigger and value
runs then inherit the Copilot CLI's current supported default.

The runner:

1. Stages the target skill and dependency closure, excluding `evals/`.
2. Uses a temporary authentication-only Copilot home, with ambient personal/plugin skills disabled.
3. Restricts available tools to the `skill` tool to prevent trigger tests from modifying state.
4. Runs the exact prompt through headless Copilot JSONL output.
5. Records `triggered: true` only when it observes:

   ```json
   {
     "type": "tool.execution_start",
     "data": {"toolName": "skill", "arguments": {"skill": "<target-skill>"}}
   }
   ```

`session.skills_loaded` proves only that the skill was available; it is **not** a trigger result.
Any failed or timed-out run is incomplete coverage — stop and retry or report the failure rather
than counting it as `not_triggered`.

After all prompt runs complete:

```
python "<eval-tool-dir>/scripts/assemble_triggering.py" \
  <target>/evals/evals.json \
  <results>/trigger-runs \
  --repeats 3 \
  --out <results>/triggering.json
```

The actual result is the majority of the three observations:

- 2/3 or 3/3 invoked → `triggered`
- 0/3 or 1/3 invoked → `not_triggered`

The report shows **Expected Result** beside **Actual Result** (including the invocation count).
It has no redundant verdict column: matching rows are green, mismatches red, and mixed 1/3 or 2/3
observations also receive a warning marker.

## Summary

Compute:

- `matches`, `mismatches`, `total`, `accuracy`
- `false_positive` — expected `should_not_trigger`, actual `triggered`
- `false_negative` — expected `should_trigger`, actual `not_triggered`

False negatives usually mean the description is too narrow. False positives usually mean it is
too broad or the test's expected result needs author/user correction.

## Output contract (`triggering` fragment)

```json
{
  "trigger_repeats": 3,
  "prompts": [
    {
      "id": "t1",
      "prompt_text": "...",
      "expected_result": "should_trigger",
      "actual_result": "triggered",
      "trigger_rate": 1.0,
      "runs": [
        {
          "run_index": 1,
          "triggered": true,
          "events_ref": "trigger-runs/t1-1/events.jsonl",
          "response_ref": "trigger-runs/t1-1/response.md",
          "duration_s": 12.4,
          "errors": 0
        }
      ]
    }
  ],
  "summary": {
    "matches": 9,
    "mismatches": 1,
    "total": 10,
    "accuracy": 0.9,
    "false_positive": 1,
    "false_negative": 0
  }
}
```
