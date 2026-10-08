# Author response — feedback (advisory) and override (authoritative)

After the report is generated (Step 10), the author can respond two ways — both **optional**, both
after the fact, neither changes how the sweep ran:

- **Feedback (advisory)** — structured notes/stances that record what the author thinks, captured as
  `feedback.json`. It never changes a verdict or score.
- **Human override (authoritative)** — the author's corrected call, captured as `human_override.json`.
  Where present it **supersedes** the AI judge as the final word, while `result.json` keeps the AI's
  original for a traceable audit trail.

Invite it, don't block on it: "Open `report.html`; if you'd like, leave feedback on any mode or finding,
and if you disagree with a verdict I can record your override as the final word." If the author skips,
finish the sweep. `metadata.feedback_enabled` (set at Step 0) records whether feedback was offered; it
never changes the result's structure, so a feedback-on and a feedback-off sweep share one
`structural_signature`.

---

## Feedback (advisory) → `feedback.json`

`report.html` is a static file with no server, so its single **Save feedback** button serializes the
inline controls and triggers a browser **download** of `feedback.json`. The feedback bar also carries an
**"authoritative override (final word)"** checkbox (ticked by default) plus the override inputs
(value verdict / dimension score / per-prompt Expected Result / finding disposition / author).
When the box is ticked, the emitted `feedback.json`
additionally carries `override_requested: true` and an embedded, ready-to-write `override` payload. After
saving, an on-page notice tells the author to return to the agent and say **"store my feedback"**
(advisory) or **"apply my override"** (authoritative) — the server-side step a static page cannot do
itself. On that prompt the agent files `feedback.json` into the local sweep folder and, when `override_requested`
is set, writes + validates `human_override.json` from the embedded payload and regenerates the report (see
the override section below). Validate before keeping it locally:

```
<target>/evals/results/<timestamp>/feedback.json
python "<eval-tool-dir>/scripts/eval_schema.py" feedback <path>
```

Captured across all three modes plus every finding (see `report-layout.md` for the controls):

```json
{
  "schema_version": "skill-eval/v5",
  "target_skill": "<name>",
  "sweep_ref": "results/<timestamp>",
  "created_at": "<iso>",
  "static_quality_feedback": {"overall": {"stance": "agree", "note": "..."},
                              "dimensions": [{"name": "Robustness", "stance": "disagree", "note": "..."}]},
  "triggering_feedback": {"overall": {"stance": "agree", "note": "..."}},
  "value_comparison_feedback": {"stance": "agree", "note": "verdict matches my experience"},
  "findings_feedback": [{"finding_id": "f1", "stance": "agree", "note": "yes, fix this first"}],
  "overall_notes": "free text"
}
```

`stance` ∈ `agree | disagree | edit | annotate` (use `annotate` for a bare note). Empty controls are
omitted — no feedback means the author was fine with that item.

---

## Human override (authoritative) → `human_override.json`

The AI judge and the original trigger Expected Results are **inputs, not the final word**. When the
author disagrees with a judge decision or wants to correct a prompt's Expected Result, record a
`human_override.json` next to the sweep's `result.json`. When present it is authoritative;
`result.json` is never touched, so an override is always a **traceable diff** (the original said X,
the author made it Y), never a silent rewrite.

Capture only what the author actually wants to change — every field is optional (a `null` scalar or
empty list means "no override here", and the `result.json` value stands):

| Field | Overrides | Values |
|-------|-----------|--------|
| `value_verdict` | `value_comparison.summary.verdict` | `skill helps` \| `no clear value` \| `skill hurts` |
| `static_average` | `static_quality.average_score` | a number 1–5 |
| `dimension_overrides[]` | a static dimension's `score` | `{name, score (1–5 or "N/A"), note}` |
| `trigger_overrides[]` | a trigger prompt's Expected Result | `{prompt_id, expected_result: should_trigger\|should_not_trigger, note}` |
| `finding_overrides[]` | a finding's disposition | `{finding_id, action: keep\|dismiss\|reseverity, severity?, note}` |
| `value_note` / `static_note` / `overall_note` | — (the author's reasoning) | free text |

`action = reseverity` requires a `severity`; `dismiss` drops the finding from the effective fix list;
`keep` records an explicit "I looked — leave it".

```json
{
  "schema_version": "skill-eval/v5",
  "target_skill": "<name>",
  "sweep_ref": "results/<timestamp>",
  "created_at": "<iso>",
  "author": "<alias>",
  "value_verdict": "skill helps",
  "value_note": "the baseline only passed because it guessed; the skill's real leverage is X",
  "static_average": null,
  "static_note": "",
  "dimension_overrides": [{"name": "Safety & Guardrails", "score": 4, "note": "the must-not list does cover the destructive path"}],
  "trigger_overrides": [{"prompt_id": "draft-release-notes", "expected_result": "should_trigger", "note": "The release workflow should load before drafting release notes."}],
  "finding_overrides": [{"finding_id": "f2", "action": "dismiss", "note": "by design for this fixture"}],
  "overall_note": "Net: keep the skill; the low delta is a test-isolation artifact, not real no-value."
}
```

Persist → validate → re-render:

1. Write the file into the sweep folder (above).
2. `python "<eval-tool-dir>/scripts/eval_schema.py" override <path>` — fix any error first.
3. `python "<eval-tool-dir>/scripts/generate_report.py" <results>/result.json` — it auto-detects the sibling
   `human_override.json` and renders an **"Author override — final word"** banner plus inline markers
   (the original Expected Result or AI value struck through, the author's value beside it). Trigger
   summary counts and row colors are recalculated from the authoritative Expected Results.
4. Keep `human_override.json` next to the local `result.json` and `report.html`; do not force-add
   `evals/results/` to Git.

**Authority rule (for any reader):** where `human_override.json` provides a value, that value wins;
where it is null/empty, the `result.json` value stands. Keep `result.json` itself untouched — that is
what makes the override auditable.
