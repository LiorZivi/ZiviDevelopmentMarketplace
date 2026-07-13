---
name: telegram-remote
description: "Activate, operate, and tear down a bidirectional bridge between this Copilot CLI session and a Telegram bot DM so the user can step away from the terminal. Works from any repository (including Azure DevOps repos) and needs no GitHub Copilot remote-session policy — it only needs a Telegram bot token + chat id. Progress and questions are posted to the DM; the user's replies auto-inject back into the session as prompts. Invoke with no args to activate; invoke with the literal argument 'end' to close an active session (posts a summary, flips away_mode off, deletes state). Activation triggers: 'telegram-remote', 'i'm stepping away', 'ping me on telegram', 'post progress to telegram', 'afk mode', 'continue on telegram', 'headed into a meeting'. End triggers: 'telegram-remote end', 'end-telegram-remote', 'stop-telegram-remote', 'i'm back at the terminal', 'back from afk', 'stop posting to telegram', 'disable remote mode'."
argument-hint: "end | [chat-id]"
user-invocable: true
---

# telegram-remote — Activation, Core Loop & End

You are the Copilot CLI ↔ Telegram bridge. You keep a Telegram bot DM in sync
with this CLI session while the user is away from the terminal.

Unlike `teams-remote`, this transport is trivial: the Telegram Bot API is a
single HTTPS endpoint with the bot token in the URL. There is **no OAuth, no
token refresh, no MCP, no SSE, and no self-filtering** — the bot never receives
its own outbound messages, so de-duplication is a monotonic `update_id` offset.
Every outbound/inbound call goes straight through
`scripts/telegram-remote/telegram_transport.py` (Python stdlib only).

## Dispatch — which mode am I in?

- **End mode** — the user invoked `telegram-remote end`, or the request is
  clearly about tearing down an existing remote session. **Skip to the
  [End Flow](#end-flow).**
- **Activation mode** — anything else. Continue with prerequisites.

## Prerequisites — check FIRST (activation mode only)

| Capability | Provider | Used for |
|---|---|---|
| **Bot token + chat id** | env `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`, or `~/.copilot/telegram-remote.json` (`botToken` + `chatId`), or `.github/telegram-remote.json` | All posts + polling |
| **Python 3.9+** on `PATH` as `python` | stdlib only — no `pip install` | Running the scripts |

The chat id is the user's **1:1 DM with the bot** (a bot cannot read Telegram
"Saved Messages"). To discover it, the user messages the bot once, then:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/telegram_transport.py" discover
```

**Single-consumer rule:** `getUpdates` is single-consumer per bot token.
Reusing a bot that only *sends* (e.g. a notifier) is fine; running two
`telegram-remote` sessions on the same token at once causes HTTP 409 conflicts.

If activation emits `need_input` (missing token/chat) or `error` with
`conflict: true`, relay the message to the user and stop — do not start the
loop.

## Plugin Paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`
- **Scripts**: `${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/{activate,poll,send,ask,end}.py`
- **Transport**: `${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/telegram_transport.py`
- **State**: `~/.copilot/session-state/<session-id>/plugins/general-ops/telegram-remote/state.json`

Every script accepts an optional `--session-id`; in production the session id is
read from the `COPILOT_AGENT_SESSION_ID` env var, so you normally omit it.

## Envelope Contract

Each script prints one JSON envelope on stdout. If it has `next_step`, act on it
before ending your turn. Only `ended` is terminal.

| `action` | Meaning / what to do |
|---|---|
| `ready` (activate) | Session live. Start the idle loop (`poll.py --mode idle`). |
| `ready` (ask) | Question posted. Switch to input poll (`poll.py --mode input`). |
| `need_input` / `error` | Relay to the user and stop. |
| `already_active` | A session is already running for this CLI session. |
| `inject` | Each item in `replies` is a new user prompt. Post an ack, do the work, tick again. |
| `answer` | The user's answer to your pending question. Continue the task. |
| `continue` | Nothing new in the poll window. Tick again. |
| `terminate` | User replied `end`. Run the [End Flow](#end-flow) (reason `remote-triggered`). |
| `timeout` | The question window elapsed. Decide how to proceed without the answer. |
| `sent` | An ad-hoc `send.py` post succeeded. |
| `ended` | Session closed (terminal). |

## Activation Flow

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/activate.py" --step run
```

It resolves credentials, drains the DM backlog to set the dedup baseline, posts
a root announcement, writes state with `away_mode=true`, and emits `ready`
(`next_step: poll_idle`). Then enter the idle loop.

## Behaviour While Away (`away_mode=true`)

A **Stop hook** blocks the end of every turn while `away_mode=true` and reminds
you to run the idle poll. Treat its block reason as an imperative.

### Rule 1 — Idle polling between tasks

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/poll.py" --step tick --mode idle
```

This **long-polls internally** (blocks up to ~8 minutes, issuing back-to-back
`getUpdates` calls) — the blocking wait *is* the idle sleep, so one turn covers
a long idle window instead of hundreds. Branch on the returned action:

- `inject` — each `replies[i].text` becomes a new user prompt. Post a short ack
  **in parallel** with starting the first real-work tool call (see Rule 2).
- `terminate` — run the `end_hint` command → [End Flow](#end-flow).
- `continue` — loop (tick again).

### Rule 2 — Acknowledge injected messages in parallel with starting work

The `inject` envelope carries an `ack_hint`. Post the ack and your first
real-work tool call as **parallel** tool calls in one response, so nothing
blocks progress:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/send.py" --text "<one-sentence ack>"
```

`send.py` auto-prefixes `Copilot agent message:` so the user can tell your posts
from their own.

### Rule 3 — Asking the user a question

Route every question you'd normally ask locally through `ask.py`:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/ask.py" --question "<text>"
```

Then enter the **input poll** until it returns `answer` (or `timeout` /
`terminate`):

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/poll.py" --step tick --mode input
```

### Rule 4 — Posting progress

Optional. Use `send.py` for meaningful milestones or before slow work. Keep it
brief; don't narrate every tool call.

### Rule 5 — Every post is plain text

All posts are plain text (no Markdown/HTML). Use `\n` for line breaks and `- `
for bullets. Do not author Telegram markup.

## End Flow

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/telegram-remote/end.py" --reason <reason>
```

`--reason` is one of `user-invoked` | `remote-triggered` | `session-ended`.
It posts a summary, flips `away_mode` off, deletes state, and emits `ended`
(terminal). After that, the Stop hook stops blocking.

| Trigger | Reason |
|---|---|
| User types `telegram-remote end` (or a natural-language end phrase) locally | `user-invoked` |
| User replies `end` / `/end` / `/telegram-remote end` in the DM (poll returns `terminate`) | `remote-triggered` |

## Reactivation

After `ended`, `telegram-remote` starts a **fresh** activation — there is no
resume.

## Notes

- State schema version is `3` (shared with `general-ops`); the
  `telegram-remote` subsystem directory isolates it from a concurrent
  `teams-remote` session.
- If the CLI exits without `end`, the summary is skipped and stale state is
  reaped on next activation.
- **Trust model:** invoking `telegram-remote` opts every message in the bot DM
  into auto-injection as a prompt. Only you can DM your bot, but treat the bot
  token as a credential.
