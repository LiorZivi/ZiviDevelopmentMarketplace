---
applyTo: "**"
---

# Capture durable notes into the design memory

While working, watch for durable context that a future agent **cannot recover by reading the repository**, and — with the user's approval — record it, either in the team **memory notes** (`agent-memory/<team>/memory-notes.md`) or in the user's **personal Copilot memory**.

This captures **atomic notes** — a single piece of non-obvious rationale, decision context, constraint, non-goal, rejected alternative, or personal preference (not a full feature design; those go through the `agent-memory-summary` skill). Do not register them in `index.md`; record them as described below.

## Hard eligibility gate — memory is for why, not what

Before grading any signal, ask:

> Could a fresh agent learn this by reading the current source code, tests, configuration, comments, or repository documentation?

If the answer is **yes**, do not propose or store it. Memory must not duplicate the repository.

A candidate is eligible only when it:

- was explicitly stated or confirmed by the user — never infer rationale from code or behavior;
- is durable enough to affect future work; and
- adds context the repository does not reveal, such as reasoning, intent, a trade-off, a rejected alternative, an external constraint, or a non-goal.

Eligible examples include "we chose polling over webhooks because the customer network blocks inbound traffic" and "do not merge these services even though they share code; separate ownership is an intentional boundary."

Do **not** store architecture facts, file or symbol locations, current behavior, API contracts, commands, conventions visible in code, edge cases captured by tests, or observations discovered while investigating the repository. A file or symbol may still appear in **When to read** as an anchor, but the **Note** itself must add non-inferable context.

## What is worth remembering — grade every signal

Only signals that pass the hard eligibility gate may be graded. See **When to check** below for the two moments to act on them:

| Confidence | Trigger | Examples |
|-----------|---------|----------|
| **HIGH** | An explicit decision with its reasoning, a rejected alternative, or a stated constraint / non-goal whose purpose is not represented in the repository | "we don't retry on 4xx because the caller owns recovery"; "keep the services separate because different teams deploy them independently" |
| **MED** | An explicitly confirmed personal preference or external context that is durable, affects future work, and is not represented in the repository | "I prefer reversible migrations because our rollback window is short"; "the partner only accepts weekly schema changes" |

## When to propose a note

Propose only when the evidence is strong enough — otherwise stay silent and keep working:

- **≥ 1 HIGH** signal, **or**
- **≥ 2 MED** signals that confirm the same durable context.

The hard eligibility gate is mandatory and cannot be overridden by confidence or repetition. **Bias toward HIGH**, but remember that a correction or implementation choice without non-obvious reasoning is not memory-worthy: preserve the reason, not the code-visible outcome. Never interrupt the task below the threshold.

## When to check

Grade at two moments and propose as soon as the threshold above is met:

- **On each user message** — look only for explicit or user-confirmed non-code context, apply the hard eligibility gate, then grade eligible signals against the table. Keep a running tally so MED signals can accumulate toward the threshold.
- **Before you finish** — wrapping up your response, handing back, or opening a PR — sweep the user's statements and confirmations for anything that passed the gate, cleared the threshold, and was not already proposed. Do not turn code findings or inferred patterns into candidates. Run this sweep every time, but keep it silent when nothing qualifies — no note, no interruption.

Propose every candidate that passes the gate and clears the bar (**≥ 1 HIGH / ≥ 2 MED**), following **Always ask before saving** below. Proposing a strong HIGH signal the moment it lands is always welcome.

## Always ask before saving

**Never write a note silently.** When the threshold is met, present the exact row you propose to add and ask the user to **approve / edit / skip** — using an interactive ask-user / question tool if one is available, otherwise ask in plain text and wait for the answer. Show all four fields:

- **Date** — today, `YYYY-MM-DD`.
- **Note** — one self-contained sentence stating the non-inferable rationale, decision context, constraint, non-goal, rejected alternative, or preference. Do not merely restate what the code does. For a decision, include the *reasoning* ("… because …").
- **When to read** — a short trigger naming the task or code area where this note matters (feature area + concrete anchors: components, files, symbols, config keys). This is how a future agent scanning the notes decides whether to open this row — mirror the `index.md` **When to read** column.
- **Confidence** — HIGH / MED.

Only after the user approves (or edits) the content do you move on to **where** it should be stored.

## Where to store — ask the user

Once the content is approved, ask the user **where** this memory should live. Two destinations:

1. **Team memory** — `agent-memory/<team>/memory-notes.md` in this repo. Best for shared context the repository does not explain: reasoning behind decisions, rejected alternatives, constraints / non-goals, and externally imposed gotchas tied to the code. It is committed, greppable, reviewed in the same PR, and read by every teammate's agent (via the `agent-memory-read` instruction).
2. **Personal Copilot memory** — the user's own GitHub Copilot memory, managed at <https://github.com/settings/copilot/memory>. Best for **personal, cross-repo preferences** — how *you* like to work — that should not live in a shared team file. Store it as a **user-scoped** memory using your memory tool if one is available; otherwise show the exact text and point the user to <https://github.com/settings/copilot/memory> to add it there. You can also suggest the user simply **prompt Copilot to remember it** — e.g. "remember that I prefer …" — and Copilot's own memory will capture it as a user preference.

Suggest a default from the note's nature — team / domain knowledge → team memory; a personal habit or cross-repo preference → personal Copilot memory — but the user decides.

### Writing to the team memory file

When the user chooses **team memory**, write to **`agent-memory/<team>/memory-notes.md`** (committed in the code repo, next to `agent-memory/<team>/index.md`):

1. **Create it lazily on the first note.** If the file does not exist yet, create it with exactly this shape, then add the approved row:

   ```markdown
   # Memory Notes

   Short, durable notes preserving rationale, constraints, non-goals, and other context that cannot be recovered from the repository. Each note is scoped by **When to read** so an agent opens only what is relevant. Companion to `index.md`, which lists the larger design summaries.

   | Date | Note | When to read | Confidence |
   |------|------|--------------|------------|
   ```

2. **Upsert, don't duplicate.** If a row already covers the same fact (same note or same When-to-read scope), update it in place instead of adding a duplicate. Otherwise append a new row at the bottom of the table.

3. **Leave it uncommitted.** The note lives in the same repo as the code, so it ships in the **same PR** as the change — the developer reviews and commits it. Do not commit or open a PR yourself.

## Boundaries

- Record only **durable, non-inferable** context that helps future work: decision reasoning, rejected alternatives, constraints / non-goals, external context, and explicit personal preferences.
- Never record facts that can be recovered from source code, tests, configuration, comments, or repository documentation, including architecture, current behavior, file locations, commands, conventions, and tested edge cases.
- Never invent or infer a reason. If the rationale matters but was not stated, ask the user to explain or confirm it instead of proposing a memory.
- Memory should explain **why**; the repository should explain **what** and **how**.
- Never store secrets, credentials, raw logs, or transient status (CI / PR / build state).
- If an eligible note is really a broad, recurring rule, suggest promoting it into `agent-memory/<team>/systemPatterns.md` — the notes file is for the lighter, faster-moving items.
