"""Stop hook for /teams-remote (schema v3, Teams MCP architecture).

Its sole job when the **current** session has ``away_mode=true`` is to
block the stop and nudge the agent to re-enter the idle-poll loop before
terminating.

Per-session storage (v1.8.0+) makes cross-session contamination
impossible by construction: each CLI session has its own
``~/.copilot/session-state/<sid>/plugins/general-ops/teams-remote/state.json``
file, so the hook can only ever see its own session's away state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import (  # noqa: E402  (sys.path tweak above)
    load_state,
    log_hook_error,
    resolve_session_id,
    set_subsystem,
)

set_subsystem("teams-remote")


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


def _block_reason(session_id: str) -> str:
    return (
        "teams-remote is active for session "
        f"{session_id} (away_mode=true). Before ending this turn, run the "
        "idle-poll cycle so Teams replies are not missed. Prefer long-poll "
        "mode — it blocks inside the subprocess for up to 10 minutes and "
        "collapses ~60 forced turns per idle window down to ~1:\n"
        "  1. python \"${CLAUDE_PLUGIN_ROOT}/scripts/teams-remote/poll.py\" "
        f"--step tick --mode idle --long-poll --session-id {session_id}\n"
        "  2. The envelope's action is \"poll_result\" with inline "
        "`replies` (already fetched). No separate MCP call needed.\n"
        "  3. python poll.py --step process --mode idle --session-id "
        f"{session_id} --replies-json '<poll_result-envelope-as-json>' "
        "and act on the returned action (inject | terminate | heartbeat | "
        "continue). Loop until the user interacts locally or terminates.\n"
        "  Fallback (short-poll, only if --long-poll transport is "
        "unavailable): drop --long-poll, add --with-sleep, execute the "
        "envelope's mcp_call to fetch replies, then --step process. If "
        "the envelope's transport==\"http\" or you hit a -32001/401/AADSTS "
        "error, switch to the envelope's http_fallback sibling and stay "
        "on HTTP for the rest of this session."
    )


def main() -> int:
    try:
        payload = _read_stdin_payload()
        try:
            session_id = resolve_session_id(stdin_payload=payload)
        except SystemExit:
            # Resolver couldn't determine a session id (no env var, no
            # payload). Fail-open: hook always exits 0 so it never blocks
            # an unrelated session's Stop event.
            return 0

        try:
            state = load_state(session_id)
        except Exception as exc:
            log_hook_error(
                f"stop-hook/teams-remote: load_state {session_id[:8]} {exc!r}"
            )
            return 0

        if state is None or state.get("away_mode") is not True:
            # The current session either never activated /teams-remote or has
            # since ended away mode → no block. With per-session storage there
            # is no other session whose state we could pick up by accident.
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


if __name__ == "__main__":
    raise SystemExit(main())
