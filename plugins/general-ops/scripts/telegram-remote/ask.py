"""Ask the away user a question over Telegram, then switch to input-poll mode.

Posts the question to the DM and stamps ``last_question_time`` so the input
poll can enforce the answer-timeout window. After this, run
``poll.py --step tick --mode input`` until it returns ``answer`` (or ``timeout``
/ ``terminate``).
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

from state import load_state, resolve_session_id, save_state, set_subsystem  # noqa: E402

set_subsystem("telegram-remote")

from telegram_transport import TelegramError, load_credentials, send_message  # noqa: E402

AGENT_PREFIX = "Copilot agent message:"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="telegram-remote ask entrypoint")
    parser.add_argument("--question", required=True)
    parser.add_argument("--session-id", required=False)
    args = parser.parse_args()

    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({"action": "error", "error": "no active telegram-remote session"})
        return 1

    token, _ = load_credentials()
    chat_id = state.get("chat_id")
    if not token or not chat_id:
        _emit({"action": "error", "error": "missing bot token or chat id"})
        return 1

    body = f"\u2753 {AGENT_PREFIX} {args.question}"
    try:
        send_message(token, chat_id, body)
    except TelegramError as exc:
        _emit({"action": "error", "error": f"failed to post question: {exc}"})
        return 1

    state["last_question_time"] = _now_iso()
    state["message_count"] = int(state.get("message_count", 0)) + 1
    save_state(session_id, state)

    _emit({
        "action": "ready",
        "session_id": session_id,
        "last_question_time": state["last_question_time"],
        "timeout_seconds": state["timeout_seconds"],
        "next": "run input poll via poll.py --step tick --mode input",
        "next_step": "poll_input",
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
