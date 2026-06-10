---
name: teams-remote
description: "Activate, operate, and tear down a bidirectional bridge between this Copilot CLI session and a Microsoft Teams channel so the user can step away from the terminal. Proactively refreshes the Teams MCP OAuth token and falls back to direct HTTP against the MCP server when the CLI's cached bearer goes stale (solves -32001 timeouts on long-running sessions). Invoke with no args (or team/channel names, or a channel URL) to activate. Invoke with the literal argument 'end' to close an active session: posts a final summary, flips away_mode=false, deletes state. Activation triggers: 'teams-remote', 'i'm stepping away', 'ping me in teams', 'post progress to teams', 'afk mode', 'continue in teams', 'headed into a meeting'. End triggers: 'teams-remote end', 'end-teams-remote', 'close-teams-remote', 'stop-teams-remote', 'i'm back at the terminal', 'back from afk', 'done being remote', 'stop posting to teams', 'disable remote mode'."
argument-hint: "end | [team-name] [channel-name] | [channel-url]"
user-invocable: true
---

# teams-remote — Activation, Core Loop & End (with Token Refresh & HTTP Fallback)

You are the Copilot CLI ↔ Microsoft Teams bridge. You keep a Teams channel in sync with this CLI session while the user is away from the terminal.

`teams-remote` ships two hardening features over a naïve MCP-only bridge:

1. **Proactive OAuth token refresh.** Before every poll tick, the transport layer inspects `~/.copilot/mcp-oauth-config/*.tokens.json` and refreshes the bearer if it's within 10 minutes of expiry. The new token is written back to disk with camelCase keys.
2. **Direct-HTTP fallback.** The CLI caches the old bearer in memory at startup and does **not** reload it when the tokens file is refreshed. Once a refresh fires (or the MCP tool call returns `-32001` / 401 / `AADSTS*`), switch to the envelope's `http_fallback` sibling — a JSON-RPC `tools/call` against the MCP `serverUrl` with a freshly-refreshed bearer — and stay on HTTP for the rest of the session.

**All writes and reads still flow through the Teams MCP server when it works.** HTTP is strictly a fallback, not the default.

## Dispatch — which mode am I in?

- **End mode** — the user invoked `/teams-remote end`, or the natural-language request is clearly about tearing down an existing remote session. **Skip straight to the [End Flow](#end-flow) section.**
- **Activation mode** — anything else. Continue with prerequisites.

## Prerequisites — check FIRST, before anything else (activation mode only)

| Capability | Provider | Used for |
|---|---|---|
| **Teams MCP server** | Agency-hosted Copilot CLI sessions auto-provision the `teams-*` MCP tools (signed into M365). | All outbound posts **and** polling (primary transport). |
| **Teams MCP OAuth config on disk** | `~/.copilot/mcp-oauth-config/<name>.json` + sibling `<name>.tokens.json` (created automatically by the CLI on first auth). | Token refresh + direct-HTTP fallback. |

Required MCP tools: `teams-ListTeams`, `teams-ListChannels`, `teams-PostChannelMessage`, `teams-ReplyToChannelMessage`, `teams-ListChannelMessageReplies`.

**If ANY of those MCP tools are missing, DO NOT start the remote session.** Print a concise error to the user and stop.

For **end mode** the MCP is preferred but not strictly required — `end.py` will still clean up local state.

## MCP token refresh & direct-HTTP fallback

This is the core of the skill. The transport contract:

- **Transport module**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/teams_transport.py`. Pure stdlib Python (`urllib.request`, `json`, `pathlib`, `time`, `dataclasses`). No third-party deps.
- **Refresh window**: 10 minutes before `expiresAt`. `poll.py --step tick` calls `ensure_fresh_token(tokens_path)` at the top of every tick. If a refresh fires, state's `transport` is flipped to `"http"` and every subsequent envelope signals the switch.
- **Dual-transport envelopes**: `poll.py` emits every outbound envelope (`poll` tick, `heartbeat`, `progress_post`, the `inject` ack template) with **both** `mcp_call` + `mcp_args` **and** an `http_fallback` sibling of the shape:
  ```json
  {"url": "<serverUrl>",
   "body": {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "teams-ListChannelMessageReplies",
                       "arguments": {...}}}}
  ```
- **When to switch to HTTP** — switch the moment any of these fire:
  - the envelope carries `"transport": "http"`, or
  - the last `mcp_call` returned `-32001` (request timed out), 401, or any error mentioning `AADSTS`.
  **Once you switch, stay on HTTP for the rest of the session.** The CLI's cached bearer never catches up.
- **HTTP call mechanics**: POST to `http_fallback.url` with headers determined by `http_fallback.auth`:
  - `auth: "bearer"` (user-managed Teams MCP, OAuth on disk) — send `Authorization: Bearer <access_token from the tokens file at http_fallback.tokens_path>`. Tool name in `body.params.name` is fully-qualified (`teams-…`).
  - `auth: "none"` (agency-hosted Teams MCP via local loopback proxy at `http://127.0.0.1:<port>`) — **do NOT send `Authorization`**; the proxy injects M365 auth upstream. Tool name in `body.params.name` is already stripped of the `teams-` prefix (e.g. `ListChannelMessageReplies`) — send it verbatim.
  Always include:
  ```
  Content-Type: application/json
  Accept: application/json, text/event-stream
  ```
  The response body is SSE-formatted with triple-nested JSON. Use `teams_transport.parse_sse_response` or the PowerShell reference parser from `phone-mode` (`Skill-1.txt` §*Robust SSE Response Parsing*). **Never** regex out ids or reply content — unicode escapes (`\u0022`) will silently break you.
- **Failure-mode rule**: if SSE parsing returns `None`, treat it as an error, **not** as "no messages". Re-post via the native MCP tool is an acceptable retry; a silently-empty reply list is not.

`activate.py`, `ask.py`, and `end.py` follow the same dual-transport contract: `cmd_run` emits `mcp_call` + `http_fallback` siblings on `transport: "mcp"`, and strips `mcp_call`/`mcp_args` (leaving only `http_fallback`) once `transport: "http"`. The four scripts do not own the transport flip — only `poll.py --step record-mcp-error` does. Scripts emit the call shape; the agent decides which sibling to execute.

## Plugin Paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Activation script**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/activate.py`
- **Ask script**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/ask.py`
- **Poll script**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py`
- **End script**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/end.py`
- **Transport module**: `${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/teams_transport.py`
- **State directory**: `~/.copilot/session-state/<session-id>/plugins/general-ops/teams-remote/` (per-session). Hook crash log stays machine-level at `<tempdir>/general-ops/hook-error.log`.

## Resolving the Team and Channel

Identical to the `teams-remote` skill. Optional persistent config files: `.github/teams-remote.json` or `~/.copilot/teams-remote.json` (the `teams-remote.json` files are also read as a fallback for convenience). Keys: `teamId`, `channelId`, `team`, `channel`, `pollIntervalSeconds`, `timeoutMinutes`.

## Activation Flow (two-step handshake)

### Step 1 — `activate.py --step run`

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/activate.py" \
    --step run --session-id <SID> \
    --team-id <resolved-team-guid> \
    --channel-id <resolved-channel-id> \
    [--team "<display>"] [--channel "<display>"] \
    [--user-display "<name>"] \
    [--user-id <user-guid>]
```

> **Tip — notification hack.** If you pass `--user-id <guid>` (the Graph user GUID of the away user — discoverable via `teams-ListChannelMembers` or from any `from.userId` in a prior reply), teams-remote will stamp every outbound reply (ack, heartbeat, progress) with a self-@mention. That alone is enough to raise a push notification even though messages are authored on behalf of the signed-in user (who would otherwise be suppressed). Omit `--user-id` to keep the old behaviour. Running sessions can opt in after activation with `poll.py --step set-user-mention --user-id <guid> --user-display "<name>"`.

Emits one of: `already_active`, `need_input`, `error`, or `post_root` (execute the `mcp_call`, then proceed to step 2).

### Step 2 — `activate.py --step finalize`

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/activate.py" \
    --step finalize --session-id <SID> \
    --root-message-id <id-from-mcp-response> \
    --created-iso <createdDateTime-from-mcp-response>
```

Emits `ready` on success. State is persisted with `transport: "mcp"` (the default) and `last_processed_id: "0"`.

## Envelope Contract

If an envelope has `next_step`, run it before yielding the turn. Only `action: "ended"` is terminal.

| `action`              | `next_step`   | Meaning                                |
|-----------------------|---------------|----------------------------------------|
| `ready` (activate)    | `poll_idle`   | Activated; start idle loop             |
| `ready` (ask)         | `poll_input`  | Question posted; switch to input poll  |
| `continue`            | `tick`        | No new replies; tick again             |
| `heartbeat`           | `tick`        | Long-poll keepalive; tick again        |
| `mcp_error_recorded`  | `tick`        | Transport flipped; resume on http      |
| `ended`               | (terminal)    | Session closed                         |

## Behaviour While Away (`away_mode=true`)

### Rule 1 — Route every question through ask.py (two-step)

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/ask.py" --step run --session-id <SID> --question "<text>"
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/ask.py" --step finalize --session-id <SID> --message-id <id> --created-iso <iso>
```

Then enter the **input-poll** loop via `poll.py --mode input`. Branch on action as in `teams-remote`.

### Rule 2 — Idle polling between tasks

**Preferred: long-poll mode.** Use this when Teams MCP transport is discoverable (the default in agency-hosted and user-authorised sessions):

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py" --step tick --mode idle --long-poll --session-id <SID>
```

This blocks inside the subprocess for up to 10 minutes, doing short internal HTTP GETs. It returns a single envelope:

```
{"action": "poll_result", "mode": "idle", "replies": [...], "timed_out": <bool>, "next_step": "process", ...}
```

No `mcp_call` / `mcp_args` / `sleep_seconds` — the blocking wait **is** the sleep, the fetch has already happened. Immediately pipe the envelope into `--step process`:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py" --step process --mode idle --session-id <SID> --replies-json '<poll_result-envelope-as-json>'
```

`--step process` accepts the whole envelope (it reads the `replies` key). Branch on the returned action as usual (`inject` / `terminate` / `heartbeat` / `continue`).

Why long-poll: one forced LLM turn per ~10 min of idle instead of ~60 (collapses ~60× reduction in idle token drain). See `docs/LongPollImplementation-Measurements.md` for measured results.

**Fallback: short-poll mode.** If `--long-poll` is omitted or the transport cannot be discovered, the envelope carries `mcp_call` + `mcp_args` + `sleep_seconds` as before:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py" --step tick --mode idle --session-id <SID> --with-sleep
```

Every envelope carries `mcp_call` + `mcp_args` and an `http_fallback` sibling (see [MCP token refresh & direct-HTTP fallback](#mcp-token-refresh--direct-http-fallback)). Try `mcp_call` first; switch to `http_fallback` on `-32001` / 401 / `AADSTS*`, or immediately if the envelope's top-level `transport` field is `"http"`.

Branch on action (both modes):

- `"inject"` — each reply in `replies` becomes a new user prompt. The envelope also carries an `ack_template` — fill in `content` with a short acknowledgement (≤2 sentences, paraphrase what you understood) and post it **in parallel with the first real-work tool call**. See Rule 2a.
- `"terminate"` — jump to the [End Flow](#end-flow) with `--reason remote-triggered`.
- `"heartbeat"` — execute the `mcp_call`; on the next tick pass its id as `--record-own-id <id> --record-own-kind heartbeat`.
- `"continue"` — loop. If `truncated: true`, warn.
- `"poll_result"` (long-poll only) — already handled above by piping straight into `--step process`; the resulting action will be one of the four above.

#### MCP error handling (-32001 / McpError)

If a `teams-*` MCP tool call returns `McpError` / `-32001 Request timed out` (live example: `MCP server 'teams': McpError: MCP error -32001: Request timed out`) — or any other `McpError` code — immediately run:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py" \
  --step record-mcp-error --session-id <SID> \
  --code -32001 --message "Request timed out"
```

This flips `state.transport` to `"http"` for the rest of the session and increments `mcp_timeout_streak`. Then re-run `--step tick`: the next envelope will carry `transport: "http"` and will have had its `mcp_call`/`mcp_args` stripped, leaving only `http_fallback` as the executable path. Do **not** retry the MCP call in between — it will hang for the full CLI request timeout again.

### Rule 2a — Acknowledge injected messages in parallel with starting work

Post the ack and the first real-work tool call as **parallel** tool calls in a single response so a hung MCP never blocks progress.

### Rule 2b — Every Teams post must carry prefix + self-@mention (non-negotiable)

Every single message you post to the Teams thread **MUST** include all three pieces below. No exceptions. That covers ack replies, heartbeats, progress posts, the activate root post, the end summary, **and** ad-hoc / free-form replies you compose by hand (answering a user question, status updates, clarification requests, etc.).

The three pieces:

1. **Visible prefix** — the rendered text begins with the literal string `Copilot agent message:` so the user can tell at a glance that the message came from the agent (distinguishing it from messages they typed themselves).
2. **In-content self-@mention** — content begins with `@DisplayName` (literal at-sign + the away user's display name from state) before any other visible text. Recommended shape: `@DisplayName Copilot agent message: …`.
3. **`mentions` argument** — the `teams-ReplyToChannelMessage` / `teams-PostChannelMessage` call (or HTTP-fallback `body.params.arguments.mentions`) carries a JSON-stringified array like `[{"displayName":"Lior Zivi","id":"<guid>","type":"user"}]` with the same id/display the state carries.

Envelope-driven posts already include pieces (2) and (3) — `poll.py._apply_mention_hack` sets them and emits a `mention_hint` you can copy. `activate.py` and `end.py` inject them into their summary posts. But (1) — the `Copilot agent message:` prefix — is your responsibility on every post, envelope-driven or ad-hoc. Forgetting any piece breaks the user's notification flow or their ability to identify your posts.

#### Rule 2b.1 — Ad-hoc posts: ALWAYS plain text, NEVER HTML

For any Teams post you compose by hand (free-form replies, ack content you write into the `ack_template`, answers to questions, status updates, clarifications, etc.) you **MUST**:

- Set `contentType: "text"` on the `teams-ReplyToChannelMessage` / `teams-PostChannelMessage` / `teams-SendMessageToChat` call (or `body.params.arguments.contentType: "text"` on the HTTP-fallback path).
- Write the `@DisplayName` mention as **literal plain text** at the start of `content` (e.g. `@Lior Zivi Copilot agent message: ...`). The Teams MCP server expands `@DisplayName` into proper Teams mention markup automatically when the `mentions` argument is also present — you do **not** need to (and **must not**) author `<at>...</at>` tags yourself in ad-hoc posts.
- Pass the `mentions` JSON-stringified array argument every time. Pull `id` and `displayName` from state (`user_mention_id`, `user_display`) — they're echoed in every poll envelope's `mention_hint`. Forgetting `mentions` means the away user gets no push notification; this is the #1 cause of "you didn't ping me".
- **Never** author raw HTML — no `<p>`, `<br>`, `<ul>`, `<li>`, `<b>`, `<i>`, `<at>`, `<div>`, etc. Teams renders most hand-rolled HTML inconsistently and often shows the literal tags. Use plain-text formatting only: line breaks via `\n`, lists via `- ` bullet prefixes, emphasis via `*asterisks*` or ALL-CAPS sparingly.

The HTML envelopes that `activate.py`, `end.py`, and `poll.py._apply_mention_hack` produce are the **only** sanctioned source of HTML on the wire — they use a tiny, controlled subset (`<p><at>DisplayName</at> …</p>`) that Teams renders correctly. Do not extend that subset, and do not append HTML to those envelopes' `content` fields — append plain text.

### Rule 3 — Self-filter is by message id, not sender

`poll.py` dedupes against `own_message_ids` (every id we posted: root, questions, progress, heartbeat, summary). **Plus** a new defensive layer: `last_processed_id` in state (a decimal-string of the max `int(reply_id)` ever processed) and a `int(reply_id) > last_processed_id` floor in `_filter_candidates`. Clock-skewed or duplicate timestamps can't re-surface an old reply.

### Rule 4 — Termination

- `/teams-remote end` runs the [End Flow](#end-flow) with `--reason user-invoked`.
- `--reason` is a closed enum: `user-invoked` | `remote-triggered` | `session-ended`.
- `remote-triggered` is used when `poll.py` returns `"terminate"` (user replied `end`, `/teams-remote end`, or `/teams-remote-end` in Teams).

## Stop-hook contract (do not fight it)

A Stop hook at `scripts/hooks/teams_remote_stop.py` fires at the end of every assistant turn. When it detects `away_mode=true` for the active `teams-remote` state file it writes:

```json
{"decision": "block", "reason": "teams-remote is active for session <SID> (away_mode=true). Before ending this turn, run the idle-poll cycle..."}
```

The block reason explicitly reminds the agent to switch to `http_fallback` if `transport==http` or the last MCP call errored.

**What this means for you:** treat the block reason as an imperative. Run the idle-poll cycle it describes before trying to stop again. Only `/teams-remote end` flips `away_mode=false` and lets the hook through.

## End Flow

### Prerequisites (end mode)

Teams MCP is preferred but not required. If unavailable, local state is still cleaned up.

### Step 1 — `end.py --step run`

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/end.py" --step run --session-id <SID> --reason user-invoked
```

Possible actions: `no_session`, `post_summary` (execute `mcp_call` — or `http_fallback` if we've already switched — then proceed to step 2).

If the MCP/HTTP call fails, still proceed to step 2 — the session is already logically closed.

### Step 2 — `end.py --step finalize`

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/end.py" --step finalize --session-id <SID>
```

Deletes state. Emits `ended`.

### Reason Codes

| `--reason` | When to use |
|---|---|
| `user-invoked` | Default. User ran `/teams-remote end` (or a natural-language end phrase). |
| `remote-triggered` | Idle-poll matched `end` / `/teams-remote end` / `/teams-remote-end` / `/teams-remote end` / `/teams-remote-end` in a Teams reply. |
| `session-ended` | Reserved — currently unused. |

### Reactivation

After `ended`, `/teams-remote` starts a **fresh** activation — no resume.

## Termination Matrix

| Trigger | How it's handled |
|---|---|
| User types `/teams-remote end` (or natural-language end phrase) in the CLI | End Flow with reason `user-invoked` |
| User replies `end`, `/teams-remote end`, or `/teams-remote-end` in the Teams thread | `poll.py` idle action `"terminate"` → End Flow with reason `remote-triggered` |
| CLI session exits without cleanup | Nothing; summary skipped, stale state reaped on next activation |

## Notes

- State schema version is `3`. Any mismatch is treated as "no session".
- State directory: `~/.copilot/session-state/<session-id>/plugins/general-ops/teams-remote/` (per-session, **v1.8.0+**). Files inside: `state.json`, `pending.json`, `activate-pending.json`. Hook-crash log stays machine-level at `<tempdir>/general-ops/hook-error.log`.
- `teams-ListChannelMessageReplies` caps `maxReplies` at 50. Tighten `pollIntervalSeconds` if truncation becomes a problem.
- Progress posts are **off by default**. Enable with `"auto_progress": true` in the state JSON.
- **Team/channel ambiguity is an error, not a guess.**
- Transport failures are tolerated: if `find_teams_mcp_config()` returns `None` (no MCP OAuth state on disk yet) `poll.py` logs a one-line note to stderr and emits the envelope without `http_fallback`. You stay on MCP.
- `--record-own-id` is honoured by both `--step tick` **and** `--step process` (**v1.9.1+**). Earlier builds only persisted it through `process`, which the long-poll fast path bypasses — leading to a tight loop where each just-posted ack/heartbeat/progress reply came back as a new inbound on the next tick. Pass `--record-own-id <id> [--record-own-kind heartbeat|progress|other]` on whichever step you reach next; it is idempotent.
