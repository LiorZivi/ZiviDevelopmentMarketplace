# Synthesis — consolidated findings (orchestrator, diagnose-only)

After the three modes have written their blocks, you (the orchestrator) merge them into one
prioritized, deduplicated list of what to fix. **You recommend only — never edit the target skill.**

## Where findings come from

- **Static (Mode 1)**: any dimension scoring ≤ 3, and each `top_improvements` entry.
- **Triggering (Mode 2)**: observed `false_negative > 0` → description too narrow / missing trigger
  vocabulary; observed `false_positive > 0` → description too broad or an Expected Result that the
  author/user should reconsider; low `accuracy` overall.
- **Value (Mode 3)**: `verdict` of `skill hurts` (serious) or `no clear value` (the skill may not
  earn its context cost); also tasks where with-skill underperforms baseline.

Deduplicate: if multiple modes point at the same root cause (e.g. weak instructions show up as a low
Instruction-Clarity score *and* a poor value verdict), make **one** finding and list both in
`source_modes`.

## Severity

- **high** — undermines the skill's core purpose: `skill hurts`, or the skill never triggers on its
  intended prompts, or a missing safety guardrail.
- **medium** — meaningfully limits value: `no clear value`, broad over-triggering, weak examples.
- **low** — polish: wording, minor robustness gaps, small context savings.

## `phase2_actionable`

`true` if a future automated fix could plausibly apply it by editing the skill text (e.g. "add an
error-recovery section", "tighten the description"). `false` if it needs human judgment or a new
script/asset.

## Output contract (`consolidated_findings`)

```
{
  "findings": [
    {"id": "f1", "title": "Description misses common trigger phrasings",
     "severity": "high", "source_modes": ["triggering"],
     "recommendation": "Add explicit trigger phrases for X and Y to the description.",
     "rationale": "2 expected-trigger prompts did not invoke the skill in a majority of runs.",
     "phase2_actionable": true}
  ],
  "priority_order": ["f1", "f2", "..."],
  "overall_assessment": "One-paragraph verdict: is the skill worth keeping as-is, worth fixing, or weak?"
}
```

`priority_order` lists finding ids high→low. Keep `overall_assessment` honest and short — it is the
first thing the author reads.
