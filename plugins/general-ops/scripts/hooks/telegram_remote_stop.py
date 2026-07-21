"""Stop hook for the ``telegram-remote`` skill.

Coexists with ``teams_remote_stop.py``: the Copilot CLI aggregates every Stop
hook from all sources and runs each one, so both hooks fire on every turn. Each
guards on its **own** subsystem state and no-ops otherwise — when a Telegram
away-session is active the Teams hook sees no Teams state (returns nothing,
skipped) and this hook blocks, and vice-versa.

Its sole job when the current session has ``away_mode=true`` for the
``telegram-remote`` subsystem is to block the stop and nudge the agent back
into the idle-poll loop before the turn ends. Per-session storage makes
cross-session contamination impossible: this hook only ever reads
``~/.copilot/session-state/<sid>/plugins/general-ops/telegram-remote/state.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import (  # noqa: E402
    load_state,
    log_hook_error,
    resolve_session_id,
    set_subsystem,
)

set_subsystem("telegram-remote")

_POLL = HERE.parent / "telegram-remote" / "poll.py"
_END = HERE.parent / "telegram-remote" / "end.py"


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
        f"telegram-remote is active for session {session_id} (away_mode=true). "
        "Before ending this turn, run the idle-poll cycle so Telegram replies "
        "are not missed. It long-polls internally (blocks up to ~8 min) and "
        "returns a single action:\n"
        f'  python "{_POLL}" --step tick --mode idle --session-id {session_id}\n'
        "Branch on the action:\n"
        "  - inject: treat each item in `replies` as a new user prompt. Post a "
        "short ack via send.py IN PARALLEL with starting the work (see the "
        "ack_hint in the envelope), post progress at meaningful execution "
        "stages, and finish successful work with send.py --completed so the "
        "message begins `TASK COMPLETE: Copilot agent message:`; then "
        "tick again.\n"
        "  - terminate: the user replied `end` — run the end_hint command "
        f'(python "{_END}" --reason remote-triggered --session-id {session_id}).\n'
        "  - continue: nothing new in the budget window — tick again.\n"
        "Loop until the user interacts locally or telegram-remote is ended. "
        "Only end.py flips away_mode off and lets this turn stop."
    )


def main() -> int:
    try:
        payload = _read_stdin_payload()
        try:
            session_id = resolve_session_id(stdin_payload=payload)
        except SystemExit:
            # No resolvable session id → fail open (never block an unrelated
            # session's Stop event).
            return 0

        try:
            state = load_state(session_id)
        except Exception as exc:
            log_hook_error(f"stop-hook/telegram-remote: load_state {session_id[:8]} {exc!r}")
            return 0

        if state is None or state.get("away_mode") is not True:
            return 0

        response = {"decision": "block", "reason": _block_reason(session_id)}
        sys.stdout.write(json.dumps(response))
        sys.stdout.flush()
        return 0
    except Exception as exc:
        log_hook_error(f"stop-hook/telegram-remote: unexpected error: {exc!r}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
