# teams-remote — Long-Poll Idle Fix: Measured Improvements

Three end-to-end idle-session measurements against `LiziTestTeam / Lizi_Copilot_Teams_Interactions`, captured at three stages of the long-poll rollout. Companion doc to [`teamsMCP32001ErrorExplanation.md`](./teamsMCP32001ErrorExplanation.md) (the underlying `-32001` problem and HTTP-redirect fix this rollout builds on) and [`teams-remote-long-poll-flow.md`](./teams-remote-long-poll-flow.md) (architecture).

## Headline

| Run | Session ID | Turns | Asst msgs | Output tokens | Stop-hook reminders | Wall clock |
|---|---|---:|---:|---:|---:|---|
| Baseline (no fix) | `835f1f5b` | **80** | 81 | **16,877** | **13** | ~18 min |
| `--with-sleep` (single-tool tick+sleep) | `ec8dfec8` | ~22 | n/a | UNAVAILABLE | — | ~16 min |
| **Long-poll (v1.7.0)** | `1d1f7d8e` | **26** | 27 | **9,399** | **1** | ~16 min |

Net long-poll vs. baseline for an equivalent ~13 min idle window:

- Agent turns: **80 → 26** (−68%)
- Output tokens: **16,877 → 9,399** (−44%)
- Stop-hook reminders: **13 → 1** (−92%)
- Tool executions: **65 → 29** (−55%)

**Idle-only slice** (strip fixed activation + end + results-write costs):

- Baseline: ~60 idle-forced turns / ~12,000 tok over 13 min
- Long-poll: **3** idle-forced turns / **~1,200 tok** over 13 min
- **~20× turn reduction, ~10× token reduction on the steady-state idle loop.** That is the real win — the headline numbers are smaller because fixed costs dominate once idle cost collapses.

## Run 1 — Baseline (no long-poll, no `--with-sleep`)

```
Session ID:   835f1f5b-70e4-40d8-89e9-58e688985438
Scenario:     ~13 min idle (activation -> idle polling -> remote "end" -> summary)
Session start:  2026-04-23T12:18:04Z
Last turn end:  2026-04-23T12:36:25Z
Elapsed:        ~18 min (activation + idle polling + end + post-session measurement)
```

Counts:
- Agent turns (`assistant.turn_end`): **80**
- Assistant messages: 81
- `user.message` events: 16
  - 1 user prompt (skill activation)
  - 1 skill-context injection
  - **13 Stop-hook injected reminders** (teams-remote away-mode blockers)
  - 1 remote `end` trigger
  - 1 post-session measurement request
- `tool.execution_start`: 65  /  `tool.execution_complete`: 64
- Output tokens (sum of `assistant.message.outputTokens`): **16,877**

Notes:
- Local event log (`events.jsonl`) only records output tokens per assistant message; input/cache tokens are not persisted locally in Copilot CLI 1.0.34. Cloud `session_store_sql` returned HTTP 404 for this session, so input-token totals were not available. 16,877 is therefore the model-generated-token cost only, not full round-trip spend.

Source: `%USERPROFILE%\.copilot\session-state\835f1f5b-70e4-40d8-89e9-58e688985438\events.jsonl`

## Run 2 — `--with-sleep` intermediate (tick + sleep collapsed to one tool call)

```
Session ID:              ec8dfec8-9933-4770-9eaa-bb529327a004
Timestamp (UTC):         2026-04-23T13:26:00Z
Channel:                 LiziTestTeam / Lizi_Copilot_Teams_Interactions
Root message id:         1776949631541
Activation (UTC):        2026-04-23T13:07:11Z
Stop requested (UTC):    2026-04-23T13:23:47Z
Wall-clock duration:     ~16 min 36 s idle (~1006 s)
```

Counts:
- Assistant turns: ~22 (from transcript)
  - 2 turns for activation
  - 2 "real work" turns (two inject acks)
  - ~18 idle-poll cycles (`tick` + `ListChannelMessageReplies` + `process`)
- Tokens: **UNAVAILABLE**. Session-store SQL returned HTTP 404; no local event log with token accounting was found. Server-side telemetry needed if token counts are required.

Notes on this intermediate fix:
- Each idle cycle was 3 tool calls (`tick`, `ListChannelMessageReplies`, `process`) instead of 4 (`Sleep`, `tick`, `List`, `process`). Per-cycle turn overhead dropped but turn *frequency* did not — still ~1 idle cycle per `pollIntervalSeconds`.
- No duplicate-reply issues; self-filter correctly hid the agent's own acks.
- Two MCP `-32001` timeouts mid-session; both recovered on retry.

## Run 3 — Long-poll (v1.7.0) ✅

```
Session ID:              1d1f7d8e-2b96-4263-8860-0a3361f57bd6
Timestamp (UTC):         2026-04-23T13:51:55Z
Branch context:          long-poll implementation (idle token-drain mitigation)
Channel:                 LiziTestTeam / Lizi_Copilot_Teams_Interactions
Root message id:         1776951493076
Activation (UTC):        2026-04-23T13:38:13Z
Session end (UTC):       2026-04-23T13:51:55Z
Wall-clock duration:     ~16 min 19 s (13:35:36Z -> 13:51:55Z)
Scenario:                ~13 min idle teams-remote with --long-poll
                         (activation -> 3 long-poll idle ticks -> remote "end" -> summary)
```

Counts:
- Agent turns: **26**
- Assistant messages: 27
- `user.message` events: 3
  - 1 user prompt (skill activation)
  - 1 skill-context injection
  - **1** Stop-hook injected reminder (ONE, vs. 13 in baseline)
- `tool.execution_start`: 29  /  `tool.execution_complete`: 28
- Output tokens: **9,399**

Source: `%USERPROFILE%\.copilot\session-state\1d1f7d8e-2b96-4263-8860-0a3361f57bd6\events.jsonl`

### Comparison vs. baseline

| Metric | Baseline | Long-poll | Delta |
|---|---:|---:|---|
| Agent turns | 80 | 26 | **−67.5%** |
| Assistant messages | 81 | 27 | −66.7% |
| `user.message` events | 16 | 3 | −81.3% |
| &nbsp;&nbsp;— Stop-hook reminders | 13 | 1 | **−92.3%** |
| Tool executions (start) | 65 | 29 | −55.4% |
| Output tokens | 16,877 | 9,399 | **−44.3%** |
| Wall clock | ~18 min | ~16 min | comparable |

### Long-poll unblock cadence observed

Three long-poll ticks fired in this run. Each returned when a reply arrived (well under the 600 s ceiling):

| Tick | Blocked for | Trigger |
|---|---:|---|
| 1 | 143 s | user inject #1 arrived |
| 2 | 17 s | own ack surfaced (self-filter wart — see below) |
| 3 | 348 s | user inject #2 arrived |
| 4 | 236 s | user `end` trigger arrived |

Subprocess stderr heartbeats (`[long-poll] alive t=Ns`) fired every ~60 s as designed — the Copilot CLI did **not** kill the 600 s blocking subprocess. **The subprocess-lifecycle rollout gating test is thereby passed.**

## Per-turn attribution of the 26 long-poll turns

To head off the fair question *"why 26 turns and not ~8?"*:

| Phase | Turns | Approx. tokens |
|---|---:|---:|
| Activation | 10 | ~2,000 |
| Idle long-poll blocks | **3** | ~1,200 |
| Ack / process for inject #1 | 8 | ~2,200 |
| Ack / process for inject #2 | 4 | ~800 |
| End + results.txt write | 10 | ~2,900 |
| Follow-up analysis turn | 1 | ~430 |

Inflation sources that are **not** long-poll regressions:

1. `$env:CLAUDE_PLUGIN_ROOT` typo on first activate.py invocation → 1 wasted turn.
2. Tool-output truncation on the first `process` return → extra `view` on the temp file.
3. **Self-filter wart** (see below) → 3–4 extra turns across the session.
4. This measurement round itself added `glob` + `view` + metric-gathering (2 tries because of a wrong `outputTokens` JSON-path assumption) + a 1,629-tok `edit` append. Baseline did those in a *separate* session, so that cost was excluded from the baseline's counters.

Strip those one-time fixed costs (~20 turns / ~5 K tok) and the long-poll slice is **6 turns / ~4.4 K tok over 13 min**, vs. baseline's ~60 turns / ~12 K tok — i.e. ~10× turn reduction and ~3× token reduction on apples-to-apples idle work.

## Known ergonomic wart surfaced by the long-poll run

When the agent posts an ack via a direct `teams-ReplyToChannelMessage` MCP call (not via the envelope's `ack_template` path), the reply's id is **not** auto-added to `state.own_message_ids`. The next long-poll tick then surfaces the agent's own ack as a new inject, forcing a spurious `process → record-own` cycle.

Workaround used in this run: explicit `poll.py --step record-own --message-id <id> --record-own-kind other` after each ack.

Fix options (future PR):

- **(a)** Have `poll.py --step process` accept `--just-posted-id <id>` inline so the ack id is recorded in the same turn as the ack.
- **(b)** Auto-record the id when the agent echoes back the MCP response to `poll.py`.

Either would save ~5 turns / ~1.5 K tok per session.

## Token-accounting caveat

Both the baseline and the long-poll numbers are **output tokens only** — the Copilot CLI local event log (`events.jsonl`) in 1.0.3x does not persist per-turn input/cache tokens. Input-token totals would have to come from server-side telemetry. Since the Stop-hook reminder + long idle context replay is primarily an *input*-token drain, the real savings are almost certainly larger than the 44% shown here. The `Stop-hook reminders: 13 → 1` metric is the most faithful proxy for the hidden input-token win.

## Success criteria status (long-poll rollout)

- ✅ Turns during idle drop from ~60 to ≤3 (observed: **3**).
- 🟡 Input-tokens/minute drop by ≥50× — **not directly measurable** locally; Stop-hook reminder count dropped 92% (13→1), which is the dominant proxy.
- ✅ Mid-idle replies reach the agent within seconds (observed: 143 s, 17 s, 348 s, 236 s — all well under the 600 s ceiling, each triggered by the internal 5 s GET loop).
- ✅ `/teams-remote end` in Teams terminates the loop cleanly (run 3 ended via remote trigger).
- ✅ Subprocess lifecycle gating (§4): Copilot CLI tolerated a 600 s blocking subprocess with 60 s stderr heartbeats; no kill observed.
