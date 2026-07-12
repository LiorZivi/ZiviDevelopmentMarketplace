---
name: agent-memory-drift
description: "Re-validate a single committed memory design summary (a Summary file under agent-memory/) against the current code, and report whether the code has drifted from the recorded design. It classifies drift as architecture drift (the code still meets the spec, but the recorded architecture is stale) or spec drift (the code no longer does what the spec requires), and reports it with cited code evidence for a human to approve — never committing, never opening a PR, never editing the spec half on its own. Use this whenever someone wants to check a design summary against the implementation: 'check this summary for drift', 'has the auth service drifted from its memory summary', 'is the architecture in this summary still accurate', 'audit or validate this design summary against the code', 'reconcile the memory with reality', or a periodic freshness check of a committed summary. Assesses one summary per run; never auto-fixes code and never opens a pull request."
---

# Memory Drift Check

Take one committed design summary from a team's memory and ask: **does the current code still match what this record says?** Report the answer with evidence, tell apart a *stale design note* from a *broken intent*, and let a human approve any change — this skill alters nothing on its own.

It is the **continuous** counterpart to the one-time drift check the `agent-memory-summary` skill runs at authoring time (its step 3). Both share one engine — `references/compare-summary-to-code.md` — so the two checks can never drift apart. This skill adds the classification gate and the human-gated routing on top.

## Input

- **summary** (required) — the path to one committed `agent-memory/<team>/Summary_<name>.md`. One summary per run (sweeping a whole memory is out of scope). If the user names a team or feature instead of a path, locate the matching summary under `agent-memory/<team>/` and confirm.

## Workflow

### 1. Read the record and reach the code
Read the summary's two halves — `## Spec` (the **intent**: its Success Criteria and User-Facing Behavior) and `## Plan` → `### Architecture Plan` (the **recorded design**). The summary is committed in the same repo as the code it describes, so you compare it against the **current** code in that repo.

### 2. Run the compare engine
Follow **`references/compare-summary-to-code.md`** to decompose both halves into atomic assertions, verify each against the code **with a mandatory citation**, and aggregate into `{half, assertion, status, citation, confidence}` plus per-half tallies and an overall confidence. Two load-bearing rules from the engine carry the whole skill:
- A **Broken / Diverged / Gone** claim with **no code citation** is downgraded to **Unverifiable** — the skill never reports drift it can't point at.
- **Unverifiable is not drift.** It lowers confidence; it never triggers an action.

### 3. Classify — spec first
Apply the gate in this order, because intent matters more than the design notes:
- Any **intent (Spec)** assertion is **Broken** above the noise floor → **Spec drift**. Stop here; never reach for a doc-fix when the intent itself is broken.
- Else any **design (Architecture)** assertion is **Diverged / Gone** above the floor → **Architecture drift**.
- Else → **No drift**.
- **Edge case:** if the intent half is largely **Unverifiable** (not Broken), you cannot claim "intent satisfied." Report **low overall confidence** and say intent could not be confirmed — do not present a confident architecture-drift verdict on an unconfirmed intent.

### 4. Report and route — everything is human-gated
Write the verdict with **`references/verdict-report-template.md`**. The skill **never commits and never opens a PR.**
- **Spec drift** → *present only.* Give the broken criterion, its citation, and the two resolution paths — *the code regressed (fix the code)* or *the intent changed (update the spec)*. Change no file, draft no fix; the human decides and drives.
- **Architecture drift — high confidence and looks intentional** → show the exact before/after of the `### Architecture Plan` section and ask for approval. On **yes**, apply that edit to the **architecture section only** (never the `## Spec` block) and leave it **uncommitted** for the human's next PR.
- **Architecture drift — low confidence or looks accidental** (a *partial or inconsistent* migration — the new shape in some call paths but the old one still live in others, leftover dead/commented-out code from the old design, or a `TODO`/`WIP` marker that says it isn't finished) → present it as a *question*, citing the inconsistency; do **not** draft a doc change. A migration that's only half-applied is an in-progress change, not a settled new design to record. (Assume the code builds — the signal is inconsistency, not compilation.)
- **No drift / below the floor** → say so; optionally note "verified on {today}".

### 5. Hand off
Report the verdict, the cited evidence, and — for an approved architecture fix — that the summary edit is staged **uncommitted** for the human to submit. Confirm nothing was committed or opened as a PR.

## Why it's built this way

- **The spec is a human-owned contract.** Code not matching the intent is never something to quietly paper over by editing the record — it's a person's decision, so spec drift always escalates and never edits a file.
- **The architecture record can self-heal.** When the code still meets the intent but the design notes are stale, the record should catch up — yet a person still approves, because a divergence that *looks* like a refactor might be an unfinished bug.
- **Evidence or it didn't happen.** Citations are mandatory so the skill only ever reports drift it can point at — that is what makes its findings trustworthy enough to act on.
