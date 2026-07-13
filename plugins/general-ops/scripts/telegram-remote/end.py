"""Tear down a telegram-remote session.

Single shot (the script posts directly, so there is no agent-relayed step):
posts a short session summary to the DM, flips ``away_mode`` off, and deletes
state. Emitting ``ended`` is terminal — the Stop hook stops blocking once state
is gone.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from state import (  # noqa: E402
    delete_state,
    load_state,
    resolve_session_id,
    save_state,
    set_subsystem,
)

set_subsystem("telegram-remote")

from telegram_transport import TelegramError, load_credentials, send_message  # noqa: E402

AGENT_PREFIX = "Copilot agent message:"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def _duration(start_iso: str) -> str:
    try:
        start = dt.datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
    except Exception:
        return "? min"
    total = int((_now() - start).total_seconds())
    if total < 60:
        return f"{total} sec"
    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _banner(reason: str) -> str:
    return {
        "user-invoked": "Session ended from the terminal.",
        "remote-triggered": "Session ended by your `end` reply.",
        "session-ended": "Session ended (CLI exited).",
    }.get(reason, "Session ended.")


def main() -> int:
    parser = argparse.ArgumentParser(description="telegram-remote end entrypoint")
    parser.add_argument("--session-id", required=False)
    parser.add_argument("--reason", default="user-invoked",
                        choices=["user-invoked", "remote-triggered", "session-ended"])
    args = parser.parse_args()

    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({
            "action": "no_session",
            "message": "No active telegram-remote session.",
        })
        return 0

    # Flip away_mode off first so the Stop hook lets the turn end even if the
    # summary post fails.
    state["away_mode"] = False
    save_state(session_id, state)

    token, _ = load_credentials()
    chat_id = state.get("chat_id")
    summary = (
        f"\U0001f534 {AGENT_PREFIX} {_banner(args.reason)}\n"
        f"Duration: {_duration(state.get('session_start_time', ''))}  ·  "
        f"Messages exchanged: {state.get('message_count', 0)}\n"
        "Remote control is now off. Restart me with 'telegram-remote' anytime."
    )
    if token and chat_id:
        try:
            send_message(token, chat_id, summary)
        except TelegramError:
            pass  # session is logically closed regardless

    delete_state(session_id)
    _emit({"action": "ended", "session_id": session_id, "reason": args.reason})
    return 0


if __name__ == "__main__":
    sys.exit(main())
