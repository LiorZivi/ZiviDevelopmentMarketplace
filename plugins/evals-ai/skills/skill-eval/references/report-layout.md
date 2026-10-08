# Report layout (`report.html`)

`<eval-tool-dir>/scripts/generate_report.py` turns a `result.json` into a **single self-contained**
`report.html` — inline CSS, an inline-SVG radar computed in Python, and inline JS for feedback. No
server, no external assets, no network. The template/CSS/JS live **inside** `generate_report.py`
(not a separate asset file), which keeps the skill fully self-contained.

## Fixed, comparable layout

The section set and order are **fixed and keyed to `schema_version`**, so every skill's report is
structurally identical and directly comparable. Sections never disappear: an absent/`null` block
renders as an explicit **"Not available"** card. To change the layout, bump `SCHEMA_VERSION` in
`scripts/eval_schema.py`.

Order:

1. **Metadata header** — target skill + description, schema version, sweep id, timestamp, runtime,
   evals source, the three evaluator models, `value_repeats`, and provenance badges ("guided" when
   `judge_guidance` was given, "scenarios reviewed" when the author approved the test set). It also
   shows the three actual trigger repeats per prompt.
2. **1 · Static quality** — a radar (one axis per numeric dimension; N/A dimensions are listed in the
   table but omitted from the radar) + a per-dimension table (score / rationale /
   evidence) + `average_score` badge + top improvements.
3. **2 · Actual triggering** — accuracy badge + false-positive / false-negative counts + a
   per-prompt table with adjacent **Expected Result** and **Actual Result** columns. Each row also
   has an **Override Expected Result** selector and note input. Actual results
   show the observed invocation count (for example `Triggered (2/3)`). Matching rows are green,
   mismatches red, and mixed trigger rates receive a warning marker. There is no verdict column.
4. **3 · Value comparison** — per task: `with`/`without` mean bars, the `delta`, a colour-coded
   `verdict`, and a collapsible per-run pass-rate table; plus the overall verdict + confidence.
5. **4 · Prioritized fixes** — the `overall_assessment` and the findings in `priority_order`, each
   with a severity pill, recommendation, rationale, and source modes.
6. **Overall notes** + the **Save feedback** bar.

## Optional feedback controls

Each item carries an inline control (a `stance` select + a `note` field): per-dimension and overall
on static quality, overall on triggering, the value verdict, and each finding — plus a free-text
overall-notes box. **Save feedback** serializes them to a versioned `feedback.json` and triggers a
browser download (server-less, mirroring skill-creator's headless path).

When `metadata.feedback_enabled` is `false`, the page gets a `feedback-off` body class that hides
every control via CSS — the controls are still emitted, so the layout (and the report's structure)
is identical whether feedback is on or off.

## Author override (final word)

When a sibling `human_override.json` is present, the report adds an **"Author override — final word"**
card at the very top (right under the metadata) summarizing every override, and marks the affected
items inline: the value verdict shows the author's call with the AI's struck through, a per-dimension
override strikes the AI score beside the author's, trigger overrides strike the original Expected
Result and recalculate the effective accuracy/false-positive/false-negative summary, the static-average
badge gains an "author avg" pill, and dismissed findings are greyed/struck. `result.json` is never
modified — the report merges the two at render time. See `references/author-response.md`.

## Run it

```
python "<eval-tool-dir>/scripts/generate_report.py" <results>/result.json [--out <path>] [--override <path>]
```
