# PR Explainer Renderer Spec

The renderer consumes one UTF-8 JSON object.

## Top-level shape

```json
{
  "title": "Starter credits were correct",
  "explanation_title": "The screen read them too early.",
  "subtitle": "Short context paragraph.",
  "issue_summary": "One-sentence old-flow issue.",
  "scope_boundary": "What this change does and does not cover.",
  "reference": {
    "label": "PR 41",
    "url": "https://example.test/pr/41"
  },
  "meta": [
    {"label": "Branch: fix/example"},
    {"label": "Deployed", "tone": "success"}
  ],
  "evidence": [],
  "old_flow": {},
  "new_flow": {},
  "explanations": [],
  "fix_evidence": [],
  "footer_title": "Fix the ordering, preserve the parallelism.",
  "footer_text": "One-sentence closing."
}
```

Required top-level fields:

- `title`
- `explanation_title`
- `issue_summary`
- `scope_boundary`
- `old_flow`
- `new_flow`
- `explanations`

Optional:

- `subtitle`
- `reference`
- `meta`
- `evidence`
- `fix_evidence`
- `footer_title`
- `footer_text`

## Evidence item

```json
{
  "label": "17:55:13 UTC",
  "title": "Balance read",
  "detail": "The API returned zero before registration.",
  "tone": "problem",
  "source": "Application Insights"
}
```

`tone` is `neutral`, `problem`, or `success`.

## Flow object

Both `old_flow` and `new_flow` use:

```json
{
  "title": "The balance request crossed the line first.",
  "summary": "Short comparison guidance.",
  "overview": {
    "label": "Before PR 41 - simplified",
    "steps": [],
    "callout": "What the colored chain means."
  },
  "sequence": {
    "label": "Before PR 41",
    "participants": [],
    "messages": [],
    "zones": [],
    "note": {
      "tone": "problem",
      "text": "Optional note below the sequence."
    }
  }
}
```

## Overview step

```json
{
  "actor": "Credits API",
  "title": "Balance returns zero",
  "detail": "The starter event has not been written yet.",
  "tone": "problem",
  "tag": "Wrong moment"
}
```

`tone` is `normal`, `problem`, or `success`.

## UML participant

```json
{"id": "credits", "label": "Credits API"}
```

Use 2-9 participants. Keep IDs unique and stable between before/after diagrams.

## UML message

```json
{
  "from": "page",
  "to": "credits",
  "label": "GET credits before registration",
  "kind": "call",
  "tone": "problem"
}
```

- `from` and `to` must match participant IDs.
- `kind` is `call` or `return`.
- `tone` is `normal`, `problem`, `success`, or `config`.
- Messages are rendered in array order from top to bottom.

## UML highlight zone

```json
{
  "label": "Error: premature credit read",
  "start_message": 3,
  "end_message": 6,
  "from": "page",
  "to": "database",
  "tone": "problem"
}
```

- Message indexes are one-based and inclusive.
- `from` and `to` define the horizontal participant range.
- Old-flow zones normally use `problem`.
- New-flow zones normally use `success`.

## Explanation card

```json
{
  "component": "FrontEndWebApp / NewVideoPage.tsx",
  "title": "Gate only the balance query",
  "detail": "Configuration still starts immediately while credits wait for profile readiness."
}
```

## Fix evidence row

```json
{
  "concern": "Configuration request",
  "before": "Started immediately.",
  "after": "Still starts immediately in parallel.",
  "result": "No added delay",
  "tone": "success"
}
```

Use `tone: "problem"` only when the result intentionally calls out a remaining risk.

