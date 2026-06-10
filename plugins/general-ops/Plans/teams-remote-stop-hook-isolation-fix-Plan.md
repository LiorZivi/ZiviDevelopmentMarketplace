# Fix: `teams-remote` Stop hook leaks across CLI sessions

**Plugin**: `zivi-development-marketplace/general-ops`
**Component**: `teams-remote` skill — `Stop` hook
**Severity**: High (functional defect; pollutes every concurrent CLI session belonging to the same user)
**Type**: Isolation / scoping bug
**Owner**: zivi-development-marketplace · general-ops · teams-remote subsystem

---

## TL;DR for the implementing agent

The `Stop` hook at `scripts/hooks/teams_remote_stop.py` is registered globally (per `hooks/hooks.json`) and fires on **every** Copilot CLI session's `Stop` event for the user — not just the session that activated `teams-remote --away-mode`. When it fires in a foreign session, it picks the *first* state file it finds with `away_mode=true` and injects a `decision: "block"` reason that drags that foreign session into the idle-poll loop on behalf of someone else's session ID.

**Fix**: Read the current session's `session_id` from the hook's stdin payload and only return `block` when it equals the away-mode session's `session_id`. Otherwise return `0` with no decision (silent no-op).

This is the plugin-layer realization of "session-scoped event bus" — Claude Code's hook schema does not support session-scoped subscriptions, so the plugin must self-gate.

---

## Evidence: the bug in action

In a CLI session whose own ID is `bbd8febd-a37d-4e97-b08f-6ae2a985aeb6` (NOT in away mode, never invoked teams-remote), every assistant turn was followed by an auto-injected user message:

```
teams-remote is active for session 47a89b09-961c-42f9-bc7c-872aee6d4cf8 (away_mode=true).
Before ending this turn, run the idle-poll cycle so Teams replies are not missed.
Prefer long-poll mode — it blocks inside the subprocess for up to 10 minutes ...
  1. python "${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py" --step tick --mode idle --long-poll --session-id 47a89b09-961c-42f9-bc7c-872aee6d4cf8
  2. ...
```

This message was injected ~80 times in a single working session, costing real LLM turns/tokens, every time the foreign session ended a turn. Worse: had the foreign agent obediently run `poll.py --step tick`, **two pollers** would have been racing on the same Teams replies queue for session `47a89b09…`, causing duplicate processing or dropped messages.

---

## Root cause analysis

### 1. Hook is registered globally with no matcher

`hooks/hooks.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/teams_remote_stop.py\""
          }
        ]
      }
    ]
  }
}
```

The `Stop` hook fires on every CLI session's stop event for the user. The `matcher` field in Claude-Code-style hooks does not support session scoping (it's used for tool-name filtering on `PreToolUse`/`PostToolUse`). So we cannot prevent the hook from firing — we have to make it a no-op when it fires in the wrong session.

### 2. Hook discards the current `session_id`

`scripts/hooks/teams_remote_stop.py` (current behavior, lines 26–36, 83–98):

```python
def _read_stdin_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

# ...

def main() -> int:
    try:
        _ = _read_stdin_payload()      # <-- payload read, then DISCARDED
        session_id = _active_away_session()
        if session_id is None:
            return 0
        response = {
            "decision": "block",
            "reason": _block_reason(session_id),
        }
        sys.stdout.write(json.dumps(response))
        sys.stdout.flush()
        return 0
    except Exception as exc:
        log_hook_error(f"stop-hook/teams-remote: unexpected error: {exc!r}")
        return 0
```

The Claude Code hook contract delivers a JSON payload on stdin that includes `session_id` (the ID of the session firing the event). The current code reads it, assigns to `_`, and never uses it.

### 3. `_active_away_session()` picks the first match by directory scan

```python
def _active_away_session() -> str | None:
    state_dir = get_state_dir()
    for path in state_dir.glob("*.json"):
        ...
        state = load_state(session_id)
        if state.get("away_mode") is True:
            return session_id
    return None
```

This scans `${state_dir}/*.json` and returns the **first** session with `away_mode=true` — completely independent of which session triggered the hook. So every CLI session for the user that ends a turn picks up that same away-session ID and gets nudged to poll on its behalf.

---

## Required fix (Method 2 — session-scoped behavior, plugin-layer realization)

Make the hook a **no-op** unless the current session is itself the away-mode session.

### Patch — `scripts/hooks/teams_remote_stop.py`

```python
def main() -> int:
    try:
        payload = _read_stdin_payload()
        current_session_id = payload.get("session_id")  # <-- NEW: identify the firing session

        away_session_id = _active_away_session()
        if away_session_id is None:
            return 0

        # Session-scoped guard: only block when the firing session IS the away session.
        # Foreign sessions must never see a `decision: "block"` response, otherwise
        # they get spammed with idle-poll reminders that don't belong to them.
        if not current_session_id or current_session_id != away_session_id:
            return 0

        response = {
            "decision": "block",
            "reason": _block_reason(away_session_id),
        }
        sys.stdout.write(json.dumps(response))
        sys.stdout.flush()
        return 0
    except Exception as exc:
        log_hook_error(f"stop-hook/teams-remote: unexpected error: {exc!r}")
        return 0
```

### Why this realizes "method 2" rather than "method 3"

Three options were on the table:

| # | Approach | Verdict |
|---|----------|---------|
| 1 | Hook self-checks `session_id` against away session, no-ops on mismatch | ✅ Implementable; what this patch does |
| 2 | Register hook on a session-scoped event bus | ❌ Not supported by current Claude Code hooks schema (no per-session matcher) |
| 3 | Reminder text says "skip if not your session", trust the LLM to comply | ❌ Already in effect today and verifiably failing — every reminder still costs a full LLM turn, and one obedient model could double-poll |

The current implementation is effectively #3 (the reminder text already names the session). It's the worst option because it's non-deterministic, costs tokens on every turn, and an obedient model will break the rightful poller.

#1 is what's actually achievable at the plugin layer. From the foreign session's perspective the result is identical to "session-scoped event bus": no `block` decision, no reminder injection, no polluted context. The only cost is a tiny Python invocation per Stop event (<50 ms), which already happens.

If a future runtime version supports `"matcher": { "session_id": "<id>" }` or similar, register the hook with that matcher AND keep the in-hook guard as defense-in-depth.

---

## Acceptance criteria

1. **Foreign session no-op**: When `teams_remote_stop.py` runs with stdin `{"session_id": "AAAA"}` and a state file for session `BBBB` has `away_mode=true`, the script must exit 0 with **empty stdout** (no `decision` field).
2. **Own session block**: When stdin `session_id` equals `BBBB` and `BBBB`'s state has `away_mode=true`, the script must exit 0 with stdout containing `{"decision": "block", "reason": "..."}` referencing `BBBB`.
3. **No away mode**: When no session has `away_mode=true`, the script must exit 0 with empty stdout regardless of stdin.
4. **Missing/garbled payload**: When stdin is empty or non-JSON, behavior must be empty stdout (no block) — fail-open, since we cannot prove the firing session is the away one.
5. **Backwards compatible**: No changes to `hooks.json`, `state.py`, or any other script. The patch is confined to `scripts/hooks/teams_remote_stop.py`.

---

## Test plan

Add cases to `scripts/teams-remote/tests/` (or wherever stop-hook tests live — create if absent). Mirror the existing pytest patterns used in `tests/test_poll.py`.

```python
# tests/test_teams_remote_stop.py
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "teams_remote_stop.py"


def _run_hook(stdin_payload: dict, state_dir, monkeypatch):
    monkeypatch.setenv("TEAMS_REMOTE_STATE_DIR", str(state_dir))  # or however state_dir is overridden
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def test_foreign_session_is_silent_noop(tmp_path, monkeypatch):
    # arrange: away session BBBB exists in state dir
    (tmp_path / "BBBB.json").write_text(json.dumps({
        "schema_version": 3, "session_id": "BBBB", "away_mode": True
    }))
    # act: hook fires for session AAAA
    res = _run_hook({"session_id": "AAAA"}, tmp_path, monkeypatch)
    # assert
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_own_session_blocks(tmp_path, monkeypatch):
    (tmp_path / "BBBB.json").write_text(json.dumps({
        "schema_version": 3, "session_id": "BBBB", "away_mode": True
    }))
    res = _run_hook({"session_id": "BBBB"}, tmp_path, monkeypatch)
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["decision"] == "block"
    assert "BBBB" in payload["reason"]


def test_no_away_session_silent_noop(tmp_path, monkeypatch):
    res = _run_hook({"session_id": "AAAA"}, tmp_path, monkeypatch)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_empty_stdin_silent_noop(tmp_path, monkeypatch):
    (tmp_path / "BBBB.json").write_text(json.dumps({
        "schema_version": 3, "session_id": "BBBB", "away_mode": True
    }))
    # empty payload -> no current session_id -> must NOT block (fail-open)
    res = _run_hook({}, tmp_path, monkeypatch)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_malformed_stdin_silent_noop(tmp_path, monkeypatch):
    (tmp_path / "BBBB.json").write_text(json.dumps({
        "schema_version": 3, "session_id": "BBBB", "away_mode": True
    }))
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json{",
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""
```

> **Note for the agent**: confirm the actual mechanism `state.py` uses to locate `state_dir` (env var, fixed path under `~/.copilot`, etc.) and adjust the monkeypatch in tests accordingly. Search `scripts/lib/state.py::get_state_dir`.

---

## Manual verification

1. Open two CLI sessions (call them `A` and `B`).
2. In session `A`, run the teams-remote activate flow that sets `away_mode=true`.
3. Send any prompt in session `B`.
4. **Before fix**: session `B` receives a `Stop`-injected reminder block referencing session `A`'s ID after every assistant turn.
5. **After fix**: session `B` proceeds normally. No reminder. Session `A` still gets the reminder when it ends its own turns.
6. End away mode in session `A`. Confirm both sessions are clean.

---

## Files touched (expected)

| File | Change |
|------|--------|
| `scripts/hooks/teams_remote_stop.py` | Read `session_id` from stdin payload; gate `block` on session-id match |
| `scripts/teams-remote/tests/test_teams_remote_stop.py` (new) | Add five-case unit test as above |

No changes to `hooks.json`, `state.py`, `poll.py`, `activate.py`, `end.py`, `ask.py`, or `teams_transport.py`.

---

## Out of scope (do not change)

- The `_block_reason` text — it's correct for the rightful session and the bug is not the wording.
- The `_active_away_session()` directory-scan logic — it's still useful for finding the away session by ID; we're just gating its result by current-session match.
- The poll/process/long-poll machinery in `scripts/teams-remote/poll.py` — unaffected.
- The `hooks.json` matcher — leave as-is until the runtime supports session-scoped matchers.

---

## Reference: paths on the implementing machine

If the agent is operating directly against an installed plugin tree (e.g. for reproduction), the relevant files are at:

- Hook script: `<plugin-root>/scripts/hooks/teams_remote_stop.py`
- Hook registration: `<plugin-root>/hooks/hooks.json`
- State helpers: `<plugin-root>/scripts/lib/state.py`
- Skill definition: `<plugin-root>/skills/teams-remote/SKILL.md`
- Existing tests: `<plugin-root>/scripts/teams-remote/tests/`

Where `<plugin-root>` in the marketplace source is the `general-ops` plugin under `zivi-development-marketplace`.
