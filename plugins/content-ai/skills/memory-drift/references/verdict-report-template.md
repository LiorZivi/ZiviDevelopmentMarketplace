# Drift report — output format

The format for a drift check's report: the **verdict** a human reads and acts on. It takes the result of comparing a design record to the code — a verdict, plus per-assertion findings (each with a status, a citation, and a confidence) and an overall confidence — and lays it out so the reader can verify and decide. The verdict has two layers: a **summary line** (the headline) and the **evidence** (the per-assertion findings that justify it). Everything reported must trace to a citation — a verdict the reader can't check is worthless.

Use this exact shape:

```
# Drift check — {summary file}

**Verdict**: {No drift | Architecture drift | Spec drift}   ·   **Overall confidence**: {High | Med | Low}
**Checked**: {N} intent assertions, {M} design assertions   ·   {today YYYY-MM-DD}

## What I found

{one or two sentences: the headline — name the verdict and the single most
important reason for it, in plain terms.}

## Evidence

### Intent (Spec)
| Assertion | Status | Where (citation) | Confidence |
|---|---|---|---|
| {behavior claim} | {Met/Broken/Unverifiable} | `{path:line}` or `{symbol}` | {H/M/L} |

### Design (Architecture)
| Assertion | Status | Where (citation) | Confidence |
|---|---|---|---|
| {structural claim} | {Holds/Diverged/Gone/Unverifiable} | `{path:line}` or `{symbol}` | {H/M/L} |

## Recommended next step
{the routing outcome — see below}
```

## The "Recommended next step" by verdict

The verdict, plus the confidence and coherence of the findings, decides what goes here. Never apply a change on your own — this section tells the human what *they* approve.

**No drift** — "Everything checks out; nothing to do." (Optionally note a "last verified" date the human can record.)

**Architecture drift** (intent met, design diverged, the divergence looks **intentional**, confidence **High**):
> "The recorded architecture is stale. With your approval I'll update only the **`### Architecture Plan`** section of the summary to match the code (the `## Spec` block stays untouched) and leave it uncommitted for your next PR. Here is the exact change:"
>
> Then show the proposed before/after of the architecture section. Apply it **only after** the human says yes.

**Architecture drift, but low confidence OR the divergence looks accidental** (a partial/inconsistent change, leftover dead or commented-out code, a `TODO`/`WIP` marker):
> "The recorded architecture and the code disagree, but this looks like it might be **unintended** — an in-progress change rather than a settled redesign. I haven't drafted a doc update — can you confirm the code is in its intended shape here? [cite the inconsistency]"

**Spec drift** (a success criterion is Broken — *any* confidence above the floor):
> "The code no longer does what the spec says: **{criterion}** — see {citation}. I'm not changing anything. Two ways to resolve this, your call:
> 1. **The code regressed** → fix the code to meet the criterion again.
> 2. **The intent changed** → the spec is out of date; update it (e.g. via a fresh `/architect` pass) so the record reflects the new intent.
> Which is it?"

For spec drift, **present the decision and stop** — don't draft either fix. The choice between "the code is wrong" and "the intent changed" is a human one, and pre-drafting a fix would nudge it.

## Invariants the report must honor

- **Every Broken/Diverged/Gone row carries a citation.** An uncited mismatch doesn't count — it is Unverifiable, so it never appears here as drift.
- **The `## Spec` block is never edited** — it is a human-owned contract. Only `### Architecture Plan` is ever proposed for change, and only on approval.
- **Nothing is committed and no PR is opened.** An approved architecture edit is left uncommitted in the working tree for the human to submit.
- **Below the noise floor, stay quiet.** A run that finds only Low-confidence / Unverifiable signals reports "No actionable drift (low confidence)" rather than manufacturing a finding.
