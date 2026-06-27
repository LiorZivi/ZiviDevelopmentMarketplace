# TeamsMCP `-32001` Error — Root Cause & HTTP-Redirect Fix

> **TL;DR** — The Copilot CLI's Teams MCP client breaks ~5 min into a long-running session: its persistent transport gets killed by an idle middlebox, and its cached bearer never reloads. We bypass it by re-issuing the same MCP `tools/call` over fresh short-lived HTTPS requests with a freshly-refreshed bearer, against the same Teams MCP server.

## 1. The problem — what's broken in the Copilot CLI's Teams MCP client

Two things go wrong inside the CLI's MCP client during a long session:

1. **Stale in-memory bearer.** The client loads the OAuth bearer once at process startup and never reloads it. AAD bearers last ~75 min; once the cached one expires, every subsequent `tools/call` fails auth — even though a fresh token already exists on disk.
2. **Idle middlebox kills the transport.** The CLI ↔ MCP transport (`https://agent365.svc.cloud.microsoft/mcp/.../mcp_TeamsServerV1`) sits behind Azure Front Door, whose default idle timeout is **4 minutes**. After an idle window the persistent stream is silently closed; the next `tools/call` goes out on a dead socket and the CLI surfaces it as:

```
MCP server 'teams': McpError: MCP error -32001: Request timed out
```

This shows up reliably ~5 min into an idle `teams-remote` session and then repeats on every tick. Restarting the CLI is not an option for an unattended away session.

## 2. The fix — HTTP redirect + token refresh

We bypass the broken CLI MCP client and re-issue the same calls ourselves:

- **Refresh the bearer.** At the top of every poll tick, `teams_transport.ensure_fresh_token` reads `~/.copilot/mcp-oauth-config/<name>.tokens.json`, refreshes if `expiresAt - now ≤ 10 min`, and writes the new tokens back atomically with camelCase keys.
- **Flip to HTTP** (sticky for the rest of the session) on either trigger:
  - `ensure_fresh_token` actually refreshed, **or**
  - the agent reports an MCP error via `poll.py --step record-mcp-error --code -32001` (also covers `401` / `AADSTS*`).
- **Promote the envelope.** Each tick normally emits both an `mcp_call` and an `http_fallback` sibling. Once `transport == "http"`, `_promote_http_fallback` strips `mcp_call` / `mcp_args` so the agent **cannot** re-enter the broken MCP path.
- **POST directly.** The agent executes the `http_fallback` — a JSON-RPC `tools/call` against the same MCP `serverUrl`, with our own fresh bearer attached.

Once on HTTP, **stay on HTTP** for the rest of the session. The CLI's cached bearer never catches up; flipping back just reproduces the bug.

## 3. The two HTTP-redirect shapes

| Discovery | `auth` | URL | Tool name | `Authorization` header |
|---|---|---|---|---|
| User OAuth disk config | `bearer` | `serverUrl` from the config | Fully-qualified, e.g. `teams-ListChannelMessageReplies` | `Bearer <accessToken from <name>.tokens.json>` |
| Agency-hosted loopback proxy (`%TEMP%\copilot-mcp-*.json`) | `none` | `http://127.0.0.1:<port>` | Prefix stripped, e.g. `ListChannelMessageReplies` | (none — proxy injects M365 auth upstream) |

Both always send `Content-Type: application/json` and `Accept: application/json, text/event-stream`. The response body is **SSE-formatted with triple-nested JSON** — parse via `teams_transport.parse_sse_response`, never regex (Unicode escapes silently break a regex parser). An SSE parse failure is treated as an **error**, never as "no replies".

## 4. Common misconception — "are we bypassing MCP and calling Graph directly?"

No. We are **not** calling Microsoft Graph directly. We are calling the **same Teams MCP server**, just bypassing the **Copilot CLI's MCP client**.

The normal chain looks like:

```
agent → CLI's MCP client (cached bearer) → Teams MCP server → Microsoft Graph
                       ^^^^^^^^^^^^^^^^
                       this is what breaks
```

Two things go wrong inside the CLI's MCP client:

1. It holds an **in-memory bearer** loaded once at process startup and never reloaded — so once the cached token expires, every subsequent call fails auth even though a fresh token exists on disk.
2. Its CLI ↔ MCP transport sits behind Azure Front Door, whose 4-minute idle timeout silently kills the persistent stream — so even within the bearer's lifetime, the next `tools/call` after an idle window goes out on a dead socket and times out.

The HTTP redirect bypasses **only the CLI's MCP client**:

```
agent → POST JSON-RPC tools/call directly to MCP serverUrl (fresh bearer) → Teams MCP server → Graph
```

So:

- **Same endpoint** (`https://agent365.svc.cloud.microsoft/mcp/.../mcp_TeamsServerV1`), **same JSON-RPC `tools/call` shape**, **same `teams-…` tools** (e.g. `teams-ListChannelMessageReplies`).
- **What changes**: we attach a freshly-refreshed `Authorization: Bearer <token>` ourselves (read from the on-disk tokens file that `ensure_fresh_token` keeps current), and we open a fresh short-lived HTTPS request per call instead of reusing the dead persistent stream.
- We never touch Graph directly — the MCP server is still the one translating to Graph upstream.

The only exception is the **agency-hosted** variant: there we POST to the **local loopback proxy** (`http://127.0.0.1:<port>`) without an `Authorization` header, and the proxy injects M365 auth on its way upstream to the same Teams MCP server.

In one line: *we bypass the CLI's broken MCP client by re-issuing the same MCP `tools/call` over fresh, short-lived HTTPS requests with our own freshly-refreshed bearer.*

## 5. Not in scope

- `activate.py`, `ask.py`, and `end.py` still emit MCP-only envelopes (one-shot calls, rare on the long-running hot path); HTTP-fallback siblings are a follow-up PR.
- Recovery from HTTP back to MCP within a single session is intentionally unsupported — only a fresh CLI launch resets the cached bearer.
- If neither OAuth disk config nor agency proxy is discoverable, MCP-only operation continues without `http_fallback`. A long enough idle window in that state will hit the `-32001` cliff with no recovery path.
