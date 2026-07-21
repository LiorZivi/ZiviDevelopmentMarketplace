# general-ops

Bidirectional Copilot CLI **remote-control bridges**. Step away from the terminal and keep the agent running by chatting with it — over a **Microsoft Teams channel** (Teams MCP) or a **Telegram bot DM**.

## What it is

`general-ops` hosts two remote-control skills that share the same control loop (`lib/state.py`, per-session state, a `Stop` hook that keeps the agent polling while `away_mode=true`). Each has its own transport and its own isolated state subsystem, so they never collide and can even be registered side by side:

- **`teams-remote`** — bridges to a Microsoft Teams channel thread via the Teams MCP. Best when your team lives in Teams and your Copilot session is signed into M365. Needs the `teams-*` MCP tools.
- **`telegram-remote`** — bridges to a Telegram bot DM via the Bot API (stdlib HTTPS, no MCP/OAuth). Best when you want a phone-friendly bridge that **works from any repository — including Azure DevOps repos — and needs no GitHub Copilot remote-session policy**. Needs only a bot token + chat id.

### teams-remote

- **`/teams-remote [team] [channel]`** — activator. Resolves the channel via the Teams MCP, posts a root message, flips the session into `away_mode`, polls the thread for replies via `teams-ListChannelMessageReplies`, and auto-injects them back into the CLI conversation. Proactively refreshes the Teams MCP OAuth token and falls back to direct HTTP against the MCP server when the CLI's cached bearer goes stale (solves `-32001` timeouts on long-running sessions). Posts progress updates, questions, and heartbeats as threaded replies.
- **`/teams-remote end`** — terminator. Same skill, invoked with the argument `end`. Posts a session-summary reply under the root thread, deletes state.

### telegram-remote

- **`telegram-remote`** — activator. Reads a bot token + chat id (env or config file), drains the DM backlog to set a dedup baseline, posts a root announcement, flips the session into `away_mode`, long-polls the DM via `getUpdates`, and auto-injects your replies back into the CLI conversation. The skill requires progress updates at meaningful execution stages. Normal posts begin `Copilot agent message:`; successful tasks begin `TASK COMPLETE: Copilot agent message:` via `send.py --completed`; requested local files use `send_file.py`; questions use `ask.py`.
- **`telegram-remote end`** — terminator. Posts a summary to the DM, flips `away_mode` off, deletes state. You can also reply `end` (or `/telegram-remote end`) in the DM.

The sections below document **teams-remote**; **telegram-remote** is documented under [telegram-remote — details](#telegram-remote--details).

## Architecture at a glance

| Path | Mechanism |
|---|---|
| **Write** (root, progress, question, heartbeat, summary) | Teams MCP — `teams-PostChannelMessage` (root) and `teams-ReplyToChannelMessage` (everything else). Each call returns a Graph message id that is recorded in `own_message_ids` so polling never re-reads our own posts. |
| **Read** (poll replies) | Teams MCP `teams-ListChannelMessageReplies(teamId, channelId, messageId=root_message_id, maxReplies=50)`. Python `poll.py` dedupes by id, filters by `createdDateTime`, and classifies replies into `inject` / `answer` / `terminate` / `heartbeat`. |
| **Thread anchor** | `root_message_id` returned by the root `PostChannelMessage`. A correlation token (`CORR-<sid8>-<uuid8>`) is still embedded in every outbound post's footer for traceability, but the MCP read path no longer needs it for lookup. |

Schema version: **3**. Schemas 1/2 (webhook + `ask_work_iq`) are orphaned on sight.

## Prerequisites

- **Teams MCP server.** Agency-hosted Copilot CLI sessions auto-provision the `teams-*` MCP tools (signed into M365). Required tools:
  - `teams-ListTeams`, `teams-ListChannels` — resolve names → GUIDs at activation.
  - `teams-PostChannelMessage` — creates the root thread.
  - `teams-ReplyToChannelMessage` — appends progress, questions, heartbeats, and the final summary.
  - `teams-ListChannelMessageReplies` — polls the thread.
  If any of these are not registered, the skill refuses to activate and tells the user to relaunch with `agency copilot --mcp teams`.
- **Python 3.9+** on `PATH` as `python`. Uses only the standard library — no `pip install`, no `requirements.txt`.
- This repo's marketplace is `.claude-plugin/marketplace.json`.

## Install

The plugin registers itself via the marketplace manifest. After the registration entry is present, re-run your marketplace refresh per `docs/INSTALL.md`.

## Usage

### Activate a remote session

Pass the team and channel names (or channel URL) inline:

```
/teams-remote LiziTestTeam LiziTestTeam_MainChannel
```

…or with a config file at `.github/teams-remote.json` (repo-local) or `~/.copilot/teams-remote.json` (user-global):

```jsonc
{
  "teamId": "38e78eec-67c6-4a2c-96be-f90d61acb764",
  "channelId": "19:HCiNN8k...@thread.tacv2",
  "team": "LiziTestTeam",
  "channel": "LiziTestTeam_MainChannel",
  "pollIntervalSeconds": 10,
  "timeoutMinutes": 300
}
```

…then simply:

```
/teams-remote
```

If only names are given, the agent resolves IDs via `teams-ListTeams` + `teams-ListChannels`. Ambiguous name matches are an error, not a guess — the agent stops and asks you to disambiguate.

### End the session

```
/teams-remote end
```

Or, from inside the Teams thread, reply with `end` or `/teams-remote end` (legacy `/teams-remote-end` is still accepted) — the idle poll picks it up and drives the termination flow itself.

## How it works (brief)

- **State**: one JSON file per CLI session at `~/.copilot/session-state/<session-id>/plugins/general-ops/teams-remote/state.json` (v1.8.0+). Atomic writes via `os.replace`. Schema gated by `schema_version: 3`.
- **Activation is two-step**: `activate.py --step run` emits a `post_root` envelope with the exact MCP call args; the agent executes `teams-PostChannelMessage`, then calls `activate.py --step finalize --root-message-id <id>` to persist state. This keeps activation atomic — a failed MCP post leaves no half-alive session.
- **Ask, end, heartbeat, progress** follow the same pattern: the script emits a `mcp_call` envelope (`teams-ReplyToChannelMessage`); the agent executes; the agent records the returned id via `poll.py --step record-own` so we don't self-read the post back.
- **Self-filter by message id, not sender.** Teams MCP attributes posts to the signed-in user, so a sender filter would also hide legitimate remote replies typed by that same human. `own_message_ids` tracks every outbound id; replies are filtered against that set.
- **Timestamp boundary** uses the Graph `createdDateTime` returned with each post (authoritative), never the local clock.
- **Stop hook** at `hooks/hooks.json` keeps the agent awake while `away_mode=true`. It cannot call MCP itself (no tool context in a hook subprocess) but it blocks the turn with `{"decision":"block","reason":"..."}`, which forces another assistant turn in which the agent *can* call MCP to tick the idle-poll. Once `/teams-remote end` flips `away_mode=false`, the hook stops blocking.
- **No SessionEnd hook.** Session teardown has no subsequent turn, so MCP is unreachable from that lifecycle event. If the CLI exits without `/teams-remote end`, the final summary is skipped and stale state is reaped on next activation.

## telegram-remote — details

A phone-friendly bridge that needs **no MCP, no OAuth, and no GitHub Copilot remote-session policy** — just a Telegram bot. Because it's independent of the git host and your Copilot seat, it works from **any** repository, including Azure DevOps checkouts where the native `/remote` command is unavailable.

### Prerequisites

- **A Telegram bot token + your DM chat id.** Reuse an existing bot (one that only *sends* is fine) or create a dedicated one via `@BotFather`. Resolve them from, in order:
  1. env `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
  2. `~/.copilot/telegram-remote.json` (user-global)
  3. `.github/telegram-remote.json` (repo-local)

  ```jsonc
  { "botToken": "123456:ABC-DEF...", "chatId": "987654321" }
  ```

  The chat id is your **1:1 DM with the bot** (a bot cannot read Telegram "Saved Messages"). To find it, message the bot once, then:

  ```
  python "<plugin>/scripts/telegram-remote/telegram_transport.py" discover
  ```

- **Python 3.9+** on `PATH` as `python`. Standard library only — no `pip install`.

### Usage

```
telegram-remote          # activate: posts a root message, enters away_mode, long-polls the DM
telegram-remote end      # end: posts a summary, deletes state
```

From your phone, just message the bot: each message is injected as a new prompt. Reply `end` / `/end` / `/telegram-remote end` to stop.

### How it works (brief)

- **State**: one JSON file per CLI session at `~/.copilot/session-state/<session-id>/plugins/general-ops/telegram-remote/state.json`, isolated from `teams-remote` by the `telegram-remote` subsystem sub-directory (`set_subsystem`). Schema gated by `schema_version: 3`; atomic writes.
- **Single-step scripts**: unlike teams-remote's two-step MCP handshakes, the Telegram scripts call the Bot API directly (`telegram_transport.py`, stdlib `urllib`), so `activate` / `send` / `ask` / `end` post-and-persist in one shot.
- **No self-filtering.** `getUpdates` only returns *incoming* messages — the bot never receives its own posts — so de-dup is a monotonic `update_id` offset, not an `own_message_ids` set.
- **Efficient idle loop.** `poll.py --step tick --mode idle` long-polls internally (blocks up to ~8 min via back-to-back `getUpdates` calls), so one forced agent turn covers a long idle window. Tune with the `long_poll_budget` / `long_poll_timeout` state fields (or `TELEGRAM_REMOTE_POLL_BUDGET` / `TELEGRAM_REMOTE_POLL_SEGMENT` for tests).
- **Visible task lifecycle.** The agent acknowledges each injected request, posts concise updates as investigation, implementation, validation, or publishing phases complete, and sends successful results with `send.py --completed --text "<outcome>"`. The final Telegram post begins `TASK COMPLETE: Copilot agent message:`.
- **Multiline text and file delivery.** `send.py` expands literal `\n` sequences into real line breaks. `send_file.py --file "<absolute path>" --caption "<text>"` uploads requested local artifacts directly to the DM.
- **Stop hook** `telegram_remote_stop.py` blocks the turn while `away_mode=true` and nudges the agent to re-tick. It coexists with the teams Stop hook — the CLI runs every registered Stop hook and each no-ops unless its own subsystem is away.

### Caveats

- **Single-consumer per bot.** `getUpdates` is single-consumer: two `telegram-remote` sessions on the same token conflict (HTTP 409). Reusing a send-only notifier bot is fine; running two remote sessions at once needs two bots.
- **409 Conflict** also occurs if the bot has a webhook set. Remove it or use a dedicated bot.
- **No summary on hard exit.** If the CLI exits without `telegram-remote end`, the summary is skipped and stale state is reaped on next activation.

### Tests

Offline integration tests (network mocked, no token needed):

```
python -m unittest discover -s plugins/general-ops/scripts/telegram-remote/tests
```

## Trust model

By invoking `/teams-remote` you opt every reply posted to the Teams thread into auto-injection as a user prompt to this CLI. There is **no sender allow-list in MVP** — anyone who can post to the channel can steer the agent. Use a private channel or restrict membership if that matters.

## Troubleshooting

| Symptom | Check |
|---|---|
| Activation prints a prerequisites message | The `teams-*` MCP tools aren't registered. Relaunch Copilot CLI with `agency copilot --mcp teams` and retry. |
| Activation emits `need_input` with `missing: [team_id, channel_id]` | Resolve via `teams-ListTeams` + `teams-ListChannels` (or save to `.github/teams-remote.json`), then retry. |
| Name resolution finds multiple candidates | Names are not guaranteed unique. Use the channel URL or saved GUIDs in the config file. |
| `poll.py` returns `truncated: true` | More than 50 replies landed between polls and the oldest may be dropped. Tighten `pollIntervalSeconds` in config. |
| Polling returns no replies | Check `own_message_ids` in the state file — every outbound post must be recorded via `poll.py --step record-own` to avoid self-filtering going wrong; also confirm the session's `root_message_id` is still reachable in Teams. |
| Corrupted state / schema mismatch | `load_state` returns `None` on any schema mismatch or JSON decode error and treats the session as inactive. Simply `/teams-remote` again. |
| Stale files from a previous run | Call `run_stale_cleanup()` from any entrypoint; it sweeps state older than 24 hours and rotates `hook-error.log` at 1 MB. |

## Future work

- **SessionEnd auto-summary** — SessionEnd hooks run at process teardown with no subsequent turn, so MCP is unreachable. A transport that survives teardown (e.g., a small subprocess daemon holding an OAuth token) could close this gap.
- `/teams-pause` + `/teams-resume` explicit middle-state pair.
- Sender allow-list (`allowedSenders` config).
- 1:1 and group-chat transport (requires `teams-CreateChat` + `teams-ListChatMessages`).
- Multi-session fan-out to the same thread.
- Adaptive-card rendering instead of inline HTML.
- `pytest` CI harness.
