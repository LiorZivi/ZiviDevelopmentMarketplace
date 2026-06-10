# general-ops

Bidirectional Copilot CLI ↔ Microsoft Teams bridge. Step away from the terminal and keep the agent running by chatting with it through a Teams channel.

## What it is

`general-ops` hosts a single skill:

- **`/teams-remote [team] [channel]`** — activator. Resolves the channel via the Teams MCP, posts a root message, flips the session into `away_mode`, polls the thread for replies via `teams-ListChannelMessageReplies`, and auto-injects them back into the CLI conversation. Proactively refreshes the Teams MCP OAuth token and falls back to direct HTTP against the MCP server when the CLI's cached bearer goes stale (solves `-32001` timeouts on long-running sessions). Posts progress updates, questions, and heartbeats as threaded replies.
- **`/teams-remote end`** — terminator. Same skill, invoked with the argument `end`. Posts a session-summary reply under the root thread, deletes state.

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
