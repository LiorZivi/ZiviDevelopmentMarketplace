# Mode 1 — static quality rubric (analyzer, run once)

A fast, text-only scoring of how well the skill is **written**. The analyzer reads the target's
`SKILL.md` (and skims its references if present) and never executes anything. This is the cheap
pre-flight that catches vague instructions, missing examples, and absent guardrails before the
expensive runtime modes.

## The five fixed dimensions (`dimension_set_version` = `skill-eval-dims/v2`)

Scored 1–5, or **`"N/A"`** when a dimension genuinely does not apply (see below). The set is versioned
so scores stay comparable across skills; change it only by bumping the version.

| Dimension | What a 5 looks like |
|-----------|---------------------|
| Instruction Clarity | Unambiguous, ordered, imperative steps; the agent always knows what to do next. |
| Behavioral Completeness | Covers the normal path *and* edge cases, failures, and stop conditions. |
| Safety & Guardrails | Clear "must not" rules; protects against destructive/unsafe actions and prompt-injection from data. |
| User Experience | Sensible defaults, asks before risky actions, communicates progress, no needless friction. |
| Robustness | Defined behavior for missing inputs, large/odd inputs, and tool/script failures. |

### Anchors
- **1** absent or actively misleading · **2** present but weak/partial · **3** adequate · **4** strong, minor gaps · **5** excellent, hard to improve.

### Not applicable (N/A)
Score a dimension **`"N/A"`** instead of 1–5 only when it genuinely does not apply to *this* skill —
e.g. User Experience for a skill with no user-facing interaction, or Safety for a pure read-only
lookup with no destructive surface. **N/A requires a one-line justification in `rationale`** and is
reserved for real non-applicability — a normal multi-step skill should almost never mark a core
dimension N/A just to dodge a low score. N/A dimensions are **excluded from `average_score`**.

## How to run

Spawn `evals-ai:skill-eval-analyzer` in **static-rubric** mode. Pass it: the full target `SKILL.md` text, the
five dimensions + anchors above, and the exact output contract below. It reads only — it does not
run the skill. If `metadata.judge_guidance.general` or `.static` is non-empty, pass it too under an
**"Author guidance"** heading — it calibrates emphasis (what to weight or forgive), never a licence
to inflate scores (see `references/preflight-review.md`).

`average_score` = mean of the dimension scores that are **numeric** (N/A dimensions are excluded),
rounded to one decimal. `top_improvements` are the 2–4 highest-leverage changes, each tied to a
dimension.

## Output contract (`static_quality` fragment)

The analyzer returns **only** this JSON; the orchestrator copies it into `result.json` under
`static_quality`:

```
{
  "dimension_set_version": "skill-eval-dims/v2",
  "scale": "1-5",
  "dimensions": [
    {"name": "Instruction Clarity", "score": 4, "rationale": "...", "evidence": "quote/anchor from the skill"},
    {"name": "User Experience", "score": "N/A", "rationale": "no user-facing interaction — pure batch step", "evidence": "..."}
    // ... all five, in the order above (score is 1–5 or "N/A")
  ],
  "average_score": 3.9,
  "top_improvements": [
    {"text": "Add an error-recovery section for missing input files", "priority": "high", "dimension": "Robustness"}
  ]
}
```
