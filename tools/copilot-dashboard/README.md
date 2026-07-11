# Copilot Dashboard

A desktop app (Electron) for watching your **GitHub Copilot CLI** sessions live and
inspecting the raw LLM requests behind each round-trip. It reads the CLI's own
per-session transcripts under `~/.copilot/session-state/<id>/events.jsonl` — read-only,
nothing is ever written or truncated.

## Run

```powershell
cd tools/copilot-dashboard
npm install      # first time only
npm start
```

## Build a standalone .exe

```powershell
npm run dist
```

Produces `dist/CopilotDashboard.exe` (portable, no install).

## Navigation

- **Home** → two entry points: **Workspaces** and **Tracked sessions**.
- **Workspaces** — every session grouped by working directory, so each git *worktree*
  is its own card (with its full path). Repo, session count, last-active.
- **Workspace → sessions** — each session shows its title (first prompt), active/idle,
  turn count, and a **track** toggle.
- **Session → round-trips** — the turns stream (grouped by prompt). Tracking a session
  replays its history and then streams new turns live. **Clear** empties the list.
- **Click a round-trip → Request** — the full outgoing LLM request as navigable HTML:
  **Metadata · System · Request messages · Response · Tools**, with jump links,
  collapsible per-message blocks, and JSON-highlighted tool-call arguments.
- **Tracked sessions** — jump straight to the sessions you are watching.

## Notes

- "Active" = the session's `events.jsonl` changed in the last 120 minutes.
- The CLI does not persist input tokens, cache, cost, duration, or the full tool schema;
  those are omitted. Everything else (system prompt, full message history, response, and
  the tools the model *called*) is reconstructed faithfully.
- Override the source root with the `COPILOT_SESSION_STATE_ROOT` env var.
