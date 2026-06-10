# Teams-Remote — Long-Poll Flow (v1.7.0)

Visual reference for the long-poll idle-polling architecture shipped in `general-ops` v1.7.0. Companion docs:

- [`teamsMCP32001ErrorExplanation.md`](./teamsMCP32001ErrorExplanation.md) — root cause of the `-32001` MCP error and the HTTP-redirect fix that this long-poll work builds on.
- [`longPollImprovements.md`](./longPollImprovements.md) — **measured end-to-end results** (baseline vs. long-poll): 80→26 turns, 16.9K→9.4K output tokens, 13→1 Stop-hook reminders, ~20× turn reduction on the idle-only slice.

## TL;DR

The old short-poll loop forced ~60 LLM round-trips per 10-minute idle window (one full agent turn every ~10s just to call `teams-ListChannelMessageReplies` and sleep). The new long-poll path collapses that to ~1 turn per window by blocking **inside the `poll.py` subprocess** on a loop of short direct HTTP GETs against the Teams Graph API.

## Before vs. After

```
BEFORE (short-poll):                     AFTER (long-poll):
┌──────────────────────────┐             ┌──────────────────────────┐
│ Turn 1: tick → sleep 10s │             │ Turn 1: tick --long-poll │
│         ListReplies MCP  │             │  (blocks up to 600s      │
│         process (empty)  │             │   inside subprocess)     │
│         → Stop hook BLOCK│             │   returns on first reply │
│ Turn 2: tick ...         │             │   OR timeout             │
│ Turn 3: tick ...         │             │         process (reply)  │
│  ... ~60 turns / 10 min  │             │         → ack → work     │
│                          │             │  ≈ 1 turn / 10 min       │
└──────────────────────────┘             └──────────────────────────┘
       ~60× LLM round-trips                     ~1× LLM round-trip
```

## Turn flow — single idle window

```
┌─────────┐      ┌──────────────┐      ┌───────────────────┐      ┌─────────┐
│  Agent  │      │   poll.py    │      │  teams_transport  │      │  Teams  │
│  (LLM)  │      │ (subprocess) │      │    .long_poll     │      │  Graph  │
└────┬────┘      └──────┬───────┘      └─────────┬─────────┘      └────┬────┘
     │                  │                        │                     │
     │ Stop hook fires  │                        │                     │
     │ → forced turn    │                        │                     │
     │                  │                        │                     │
     │  tick --mode idle│                        │                     │
     │  --long-poll ───►│                        │                     │
     │                  │ detect transport       │                     │
     │                  │ (oauth / proxy)        │                     │
     │                  │                        │                     │
     │                  │ long_poll_replies() ──►│                     │
     │                  │                        │ refresh token (1×)  │
     │                  │                        │                     │
     │                  │                        │ ┌─── loop ────────┐ │
     │                  │                        │ │ GET replies ───►│ │
     │                  │                        │ │◄─── []  ────────│ │
     │                  │                        │ │ sleep 5s        │ │
     │                  │                        │ │ (stderr hb/60s) │ │
     │                  │                        │ │ GET replies ───►│ │
     │                  │                        │ │◄── [new msg] ───│ │
     │                  │                        │ │ filter own_ids  │ │
     │                  │                        │ │ + after_iso     │ │
     │                  │                        │ └─────────────────┘ │
     │                  │                        │                     │
     │                  │◄── (replies, False) ───│                     │
     │                  │                        │                     │
     │                  │ emit envelope:         │                     │
     │                  │  {action: poll_result, │                     │
     │                  │   replies: [...],      │                     │
     │                  │   next_step: process}  │                     │
     │◄── stdout JSON ──│                        │                     │
     │                  │                        │                     │
     │ pipe envelope to │                        │                     │
     │ poll.py --step   │                        │                     │
     │ process          │                        │                     │
     │ --replies-json ─►│                        │                     │
     │                  │ dedupe, classify:      │                     │
     │                  │  • "end" → terminate   │                     │
     │                  │  • else  → inject      │                     │
     │◄── action+text ──│                        │                     │
     │                  │                        │                     │
     │ (Rule 2a) ack ─────────────────────────────────────────────────►│
     │ record-own-id ──►│                        │                     │
     │                  │                        │                     │
     │ do the work ...  │                        │                     │
     │                  │                        │                     │
     │ post result ──────────────────────────────────────────────────► │
     │ Stop hook fires → next idle long-poll                           │
     ▼
```

## Timeout branch (no reply for 600s)

```
long_poll_replies()  ──► loops 120 × 5s GETs, all empty
                     ──► returns ([], timed_out=True)
poll.py emits        ──► {action: poll_result, replies: [], timed_out: true}
agent process        ──► action: "continue"
Stop hook            ──► blocks → next long-poll turn
```

So in the worst case (total silence from Teams) the cadence degrades gracefully to 1 turn per 600s instead of 1 turn per 10s — still a ~60× reduction.

## Transport selection

`long_poll_replies` picks whichever transport is already discoverable for the session:

| Transport | When used | HTTP caller |
|---|---|---|
| **oauth** | Disk-config OAuth token present (personal dev setup) | `direct_http_call` (Graph endpoint) |
| **agency proxy** | Agency-hosted Copilot CLI loopback proxy | `_proxy_http_call` (local JSON-RPC proxy) |
| **none** | Neither discoverable | Returns `([], True)` immediately → caller falls back to short-poll cleanly |

Token refresh happens **once** at the top of each `long_poll_replies` call. Because the configured `timeout_seconds=600` is smaller than the token skew window (`_DEFAULT_SKEW_SECONDS=600`), a single long-poll call is guaranteed not to straddle a refresh boundary.

## Contract changes vs. short-poll

| Element | Old (short-poll) | New (long-poll) |
|---|---|---|
| Turn cadence | ~10s | ~600s (or first reply) |
| LLM tool calls / idle window | `tick` + `MCP ListReplies` + `process` × N | `tick` + `process` × 1 |
| Envelope action | `poll` (carries `mcp_call`) | `poll_result` (carries `replies` inline) |
| MCP `ListReplies` caller | Agent (MCP round-trip) | `long_poll_replies` (direct HTTP) |
| Heartbeat | Agent-level (log only) | `[long-poll] alive t=Ns` to stderr every 60s |
| Token refresh | Every tick | Once per long-poll call |
| Opt-in flag | n/a (default) | `--long-poll` |

## Envelope — `poll_result`

Emitted by `poll.py --step tick --mode idle --long-poll` after `long_poll_replies` returns:

```json
{
  "action": "poll_result",
  "mode": "idle",
  "replies": [ /* pre-fetched Graph message objects */ ],
  "timed_out": false,
  "next_step": "process",
  "session_id": "…",
  "idle_seconds": 600,
  "long_poll_timeout_seconds": 600,
  "correlation_token": "…",
  "after_timestamp": "2026-04-23T12:30:00Z",
  "transport": "oauth"
}
```

No `mcp_call` / `mcp_args` field — the replies are already fetched. The agent pipes the whole envelope JSON straight into `poll.py --step process --replies-json`; the existing `_parse_replies_json` accepts either the envelope or the raw list.

## Agent responsibilities (minimal)

1. Call `poll.py --step tick --mode idle --long-poll`. **Wait for it** — that subprocess blocks up to 600s.
2. Pipe stdout into `poll.py --step process --replies-json`.
3. Branch on returned action: `inject` (do the work), `terminate` (run end flow), `heartbeat`, or `continue`.

Everything between (the GET loop, the dedup, the heartbeat to stderr, the timeout accounting) happens inside the subprocess and costs **zero LLM tokens**.

## State keys (optional overrides)

Both have sensible defaults; override in the per-session state JSON if needed:

| Key | Default | Meaning |
|---|---|---|
| `long_poll_timeout_seconds` | `600` | Max wall time one long-poll call will block for. |
| `long_poll_internal_interval` | `5` | Sleep between GETs inside the subprocess. |

## Gating test (per fix plan §4) — ✅ PASSED

The 600s blocking subprocess was validated live in session `1d1f7d8e` (see [`longPollImprovements.md`](./longPollImprovements.md) Run 3). The Copilot CLI tool-call watchdog tolerated the blocking child across four long-poll ticks (143 s, 17 s, 348 s, 236 s) with stderr heartbeats every ~60 s. No subprocess kills observed.

Fallbacks kept documented in case a future CLI build changes that behaviour:

- Lower `long_poll_timeout_seconds` to `120` (still a 12× reduction).
- Switch to an exponential-backoff design in `poll.py` (base 10 s, doubled on every `continue`, capped at 5 min) — strictly inferior to long-polling but a viable fallback if the subprocess-lifecycle assumption breaks.

## Files touched in v1.7.0

- `plugins/general-ops/scripts/teams-remote/teams_transport.py` — added `long_poll_replies`, `_proxy_http_call`, `_extract_replies`, `_reply_is_new`, `_parse_iso_z`.
- `plugins/general-ops/scripts/teams-remote/poll.py` — added `--long-poll` flag, `_cmd_tick_long_poll` helper, dispatch guard in `cmd_tick`.
- `plugins/general-ops/scripts/teams-remote/tests/test_teams_transport.py` — 5 new tests under `LongPollRepliesTests` (all 34/34 pass).
- `plugins/general-ops/skills/teams-remote/SKILL.md` — Rule 2 rewritten (long-poll preferred; short-poll is the fallback).
- `plugins/general-ops/scripts/hooks/teams_remote_stop.py` — `_block_reason` now points agents at `--long-poll`.
- 4× manifest version bumps `1.6.0` → `1.7.0`.
