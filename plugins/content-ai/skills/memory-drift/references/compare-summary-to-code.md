# Compare a design record to the code

A procedure for checking whether code still matches a **design record** — and producing evidence, not a vibe. Given a design record plus the current code, it returns a structured list of findings: for each claim the record makes, whether the code still bears it out, with a citation. It runs in three phases — **decompose → verify → aggregate** — and stops there. It does not classify the result, decide a course of action, or change anything (see *Scope* at the end).

The point is to turn a fuzzy "does the code still match the design?" question into **small, individually checkable claims, each backed by a citation into the code.** That structure is what makes the result trustworthy: a reader can re-walk any line of it.

## Input: a design record + the code

The record has two halves, treated separately because they carry very different weight:

- **Intent** — what the code must *do* (its success criteria / user-facing behavior).
- **Design** — how it was *built* (the architecture: named components, data flow, integration points, key decisions).

A mismatch against **intent** is far more serious than a mismatch against the recorded **design** — keep the two apart in the output so a reader can act on that difference.

The caller extracts these two halves from whatever design artifact it holds and hands them in with the code — this procedure doesn't need to know which artifact they came from, only that it has the intent, the design, and the code in front of it.

---

## Phase 1 — Decompose into atomic assertions

Turn each half into a list of **atomic assertions** — single, concrete claims you can check one at a time. Vague prose can't be verified; atomic claims can.

- **Intent → behavior assertions.** From the success criteria / user-facing behavior, extract claims of the form *"the system does X"* or *"X produces observable Y."*
- **Design → structural assertions.** From the architecture, extract claims about *structure* — the named components, the data flow, the integration points, and the key decisions (e.g. *"A gates B," "C is the single writer of D," "X calls Y"*).

**Scope from the names the record already gives you.** A good architecture names concrete anchors — symbols, files, components. Those names *are* your search seeds: grep / symbol-search for each, open it, follow its references. You do not need a separate list of covered files to locate the code.

If an assertion names nothing concrete (pure prose), keep it — but expect it to come back **Unverifiable** in Phase 2. That is fine; it simply won't drive a finding.

---

## Phase 2 — Verify each assertion against the code, with a citation

For **every** assertion, go to the current code, decide its status, and record **at least one citation** (a `path:line` range or a symbol name) that backs your decision.

**Status vocabulary:**

| Half | Statuses |
|---|---|
| Behavior (intent) | **Met** · **Broken** · **Unverifiable** |
| Structural (design) | **Holds** · **Diverged** · **Gone** · **Unverifiable** |

- **Met / Holds** — the code does what the assertion says; cite where.
- **Broken** — the behavior is absent, contradicted, or clearly does something else; cite the offending code.
- **Diverged** — the structure still exists but is shaped differently than described (renamed, relocated, a different approach); cite the new shape.
- **Gone** — the named structure no longer exists at all; cite the absence (e.g. the call site that no longer references it).
- **Unverifiable** — you could not reach conclusive evidence either way (code not present/readable, assertion too vague, anchor not found).

### The citation rule (this is what makes the result mean something)

**A claim of Broken / Diverged / Gone counts only if it carries a concrete code citation.** Without one, downgrade it to **Unverifiable**. This is the anti-hallucination guard: never report a mismatch you can't point at. Treat a confident-sounding "this is broken" with no `path:line` as *not yet evidence*.

**Unverifiable is not drift.** It means "I don't know," and it should *lower* the overall confidence, never trigger an action. Escalating whenever you're confused would be worse than useless — it cries wolf. When much of a half is Unverifiable, say so plainly; don't round it up to a confident verdict.

### Confidence per assertion — a rubric, not a guess

Rate each finding's confidence as **High / Med / Low**, justified by four signals (prefer this ordinal over a false-precision number like `0.83` — there's nothing to calibrate such a number against, and an ordinal backed by named signals survives review):

1. **Directness** — did you find the *exact* implementing symbol/path, or infer it indirectly?
2. **Specificity** — is the assertion concrete and checkable, or vague?
3. **Coherence** — does the evidence agree across *all* the touchpoints, or contradict itself (a change applied in some places but not others)?
4. **Reachability** — was the relevant code actually present and readable?

Signal #3 (coherence) does double duty: it is also the **intentional-vs-accidental** read. A divergence that is clean and consistent everywhere looks like a deliberate change; one that is partial or inconsistent looks *accidental*. That distinction matters when deciding how to surface a structural divergence.

**Assume committed code builds and passes CI** — so the accidental signal is *not* "it doesn't compile" (a safeguard already catches that). The realistic signal is **inconsistency and incompleteness across touchpoints**: the new shape applied in some call paths while the old one is still live in others; leftover dead or commented-out code from the old design; or a `TODO`/`WIP` marker that says a migration isn't finished. A change like that compiles and may even pass tests, yet it reads as an *in-progress* change rather than a settled new design. Pull coherence — and the "is this intentional?" read — down hard when the divergence is partial or inconsistent.

---

## Phase 3 — Aggregate

Roll the per-assertion findings up into a structured result:

- **Per half**: how many assertions Met/Held, how many Broken/Diverged/Gone (each with its citation), how many Unverifiable.
- **Overall confidence**: driven by the per-assertion confidences and by how much of the record you could actually verify. **A record that is mostly Unverifiable yields *low* overall confidence** — neither a confident "all clear" nor a confident "mismatch."
- **Noise floor**: a finding whose confidence is Low (or that rests only on Unverifiable assertions) is below the floor — record it, but don't raise it as actionable. This is the alert-fatigue guard: surface signal, swallow noise.

Return the aggregate as a structured list of `{ half, assertion, status, citation, confidence }`, plus the per-half tallies and the overall confidence.

> **Graceful degradation:** when the architecture names only prose with no concrete anchor, don't fail — score those assertions low on Reachability and report them Unverifiable. Degrade to "I couldn't confirm," never to a fabricated finding.

---

## Scope — what this procedure does and doesn't do

It produces evidence; it does not decide what to do with it.

- It does **not** classify the kind of mismatch, prioritize it, or pick a course of action — that belongs to whatever consumes the result.
- It does **not** edit any file, propose a fix, commit, or open a PR.
- It checks a **given** record against the code. It does not discover records, and it does not hunt for code that has *no* record — that is the inverse problem, and it needs a code-territory boundary (which files belong to this area) that a record does not carry.

Keeping every decision out of this procedure is what lets the same comparison serve different checks consistently.
