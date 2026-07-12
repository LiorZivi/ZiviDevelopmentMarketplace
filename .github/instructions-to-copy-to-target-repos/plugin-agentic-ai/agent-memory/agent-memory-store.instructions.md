---
applyTo: "**"
---

# Capture durable notes into the design memory

While working, watch for durable knowledge worth remembering across sessions, and — with the user's approval — record it, either in the team **memory notes** (`agent-memory/<team>/memory-notes.md`) or in the user's **personal Copilot memory**.

This captures **atomic notes** — a single lesson, decision, constraint, or gotcha (not a full feature design; those go through the `agent-memory-summary` skill). Do not register them in `index.md`; record them as described below.

## What is worth remembering — grade every signal

Only some moments are worth persisting. As you work, grade the signals you see against this table — see **When to check** below for the two moments to act on them:

| Confidence | Trigger | Examples |
|-----------|---------|----------|
| **HIGH** | A user correction, an explicit decision + its reasoning, a design insight, or a constraint / non-goal | "no", "not like that", "never do X"; "we don't retry on 4xx — the caller already handles it"; "don't write to the production database from dev tooling" |
| **MED** | A confirmed approach / tool preference, or an edge case discovered | "use X instead of Y"; "what if the cache is cold?"; "that worked — keep doing it that way" |
| **LOW** | A repeated pattern noticed over the session | the same command / check reached for several times |

## When to propose a note

Propose only when the evidence is strong enough — otherwise stay silent and keep working:

- **≥ 1 HIGH** signal, **or**
- **≥ 2 MED** signals, **or**
- **≥ 3 LOW** signals — and only when they are the **same** pattern *repeated*, never three unrelated one-offs.

**Bias toward HIGH.** A correction, an explicit decision, or a stated constraint is almost always worth keeping — propose HIGH signals readily. Be more selective with MED — propose one only when the preference or edge case is clearly durable. Propose LOW only when the same pattern has genuinely repeated across the session; one or two LOW signals alone → skip. Never interrupt the task below the threshold.

## When to check

Grade at two moments and propose as soon as the threshold above is met:

- **On each user message** — as a new message arrives, grade it against the table: a correction, decision + reasoning, or constraint / non-goal (HIGH); a confirmed approach, preference, or edge case (MED); or a pattern that repeats one from earlier in the session (LOW). Keep a running tally across the session so MED and LOW signals can accumulate toward the threshold.
- **Before you finish** — wrapping up your response, handing back, or opening a PR — sweep the whole session for anything that cleared the threshold and wasn't already proposed. Run this sweep every time, but keep it silent when nothing qualifies — no note, no interruption.

Propose every candidate that clears the bar (**≥ 1 HIGH / ≥ 2 MED / ≥ 3 LOW**), following **Always ask before saving** below. Proposing a strong HIGH signal the moment it lands is always welcome.

## Always ask before saving

**Never write a note silently.** When the threshold is met, present the exact row you propose to add and ask the user to **approve / edit / skip** — using an interactive ask-user / question tool if one is available, otherwise ask in plain text and wait for the answer. Show all four fields:

- **Date** — today, `YYYY-MM-DD`.
- **Note** — one self-contained sentence: the lesson / decision / constraint / gotcha. For a decision, include the *reasoning* ("… because …").
- **When to read** — a short trigger naming the task or code area where this note matters (feature area + concrete anchors: components, files, symbols, config keys). This is how a future agent scanning the notes decides whether to open this row — mirror the `index.md` **When to read** column.
- **Confidence** — HIGH / MED / LOW.

Only after the user approves (or edits) the content do you move on to **where** it should be stored.

## Where to store — ask the user

Once the content is approved, ask the user **where** this memory should live. Two destinations:

1. **Team memory** — `agent-memory/<team>/memory-notes.md` in this repo. Best for **team / domain / codebase knowledge**: how the system works, decisions + reasoning, constraints, and gotchas tied to the code. It is committed, greppable, reviewed in the same PR, and read by every teammate's agent (via the `agent-memory-read` instruction).
2. **Personal Copilot memory** — the user's own GitHub Copilot memory, managed at <https://github.com/settings/copilot/memory>. Best for **personal, cross-repo preferences** — how *you* like to work — that should not live in a shared team file. Store it as a **user-scoped** memory using your memory tool if one is available; otherwise show the exact text and point the user to <https://github.com/settings/copilot/memory> to add it there. You can also suggest the user simply **prompt Copilot to remember it** — e.g. "remember that I prefer …" — and Copilot's own memory will capture it as a user preference.

Suggest a default from the note's nature — team / domain knowledge → team memory; a personal habit or cross-repo preference → personal Copilot memory — but the user decides.

### Writing to the team memory file

When the user chooses **team memory**, write to **`agent-memory/<team>/memory-notes.md`** (committed in the code repo, next to `agent-memory/<team>/index.md`):

1. **Create it lazily on the first note.** If the file does not exist yet, create it with exactly this shape, then add the approved row:

   ```markdown
   # Memory Notes

   Short, durable notes — lessons, decisions, constraints, and gotchas — captured during work and scoped by **When to read** so an agent opens only what is relevant. Companion to `index.md`, which lists the larger design summaries.

   | Date | Note | When to read | Confidence |
   |------|------|--------------|------------|
   ```

2. **Upsert, don't duplicate.** If a row already covers the same fact (same note or same When-to-read scope), update it in place instead of adding a duplicate. Otherwise append a new row at the bottom of the table.

3. **Leave it uncommitted.** The note lives in the same repo as the code, so it ships in the **same PR** as the change — the developer reviews and commits it. Do not commit or open a PR yourself.

## Boundaries

- Record only **durable** knowledge that helps future work: lessons, decisions + reasoning, constraints / non-goals, gotchas, stable conventions.
- Never store secrets, credentials, raw logs, or transient status (CI / PR / build state).
- If a note is really a broad, recurring rule, suggest promoting it into `agent-memory/<team>/systemPatterns.md` — the notes file is for the lighter, faster-moving items.
