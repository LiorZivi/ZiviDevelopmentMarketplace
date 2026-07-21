"""Post an ad-hoc plain-text message to the telegram-remote DM.

Used for acknowledgements, progress notes, answers, and status updates — any
free-form post the agent composes by hand. The ``Copilot agent message:``
prefix is added automatically (so the user can distinguish agent posts from
their own messages, which matters when the bot is shared with other notifiers).
"""

from __future__ import annotations

import argparse
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
COMPLETION_PREFIX = "TASK COMPLETE:"


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def _prefixed(text: str) -> str:
    text = text or ""
    if text.lstrip().lower().startswith(AGENT_PREFIX.lower()):
        return text
    return f"{AGENT_PREFIX} {text}"


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\\r\\n", "\n").replace("\\n", "\n")


def _completed(text: str) -> str:
    text = _normalize_newlines(text).strip()
    if text.lower().startswith(COMPLETION_PREFIX.lower()):
        remainder = text[len(COMPLETION_PREFIX):].strip()
        text = remainder
    outcome = _prefixed(text)
    return f"{COMPLETION_PREFIX} {outcome}"


def main() -> int:
    parser = argparse.ArgumentParser(description="telegram-remote ad-hoc send")
    parser.add_argument("--text", required=True)
    parser.add_argument("--session-id", required=False)
    parser.add_argument("--no-prefix", action="store_true",
                        help="Send text verbatim without the agent prefix.")
    parser.add_argument(
        "--completed",
        action="store_true",
        help="Prefix a successful task result with the fixed completion marker.",
    )
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

    normalized_text = _normalize_newlines(args.text)
    if args.completed:
        body = _completed(normalized_text)
    elif args.no_prefix:
        body = normalized_text
    else:
        body = _prefixed(normalized_text)
    try:
        posted = send_message(token, chat_id, body)
    except TelegramError as exc:
        _emit({"action": "error", "error": f"send failed: {exc}"})
        return 1

    state["message_count"] = int(state.get("message_count", 0)) + 1
    save_state(session_id, state)
    _emit({
        "action": "sent",
        "message_id": str(posted.get("message_id", "")),
        "completed": args.completed,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
