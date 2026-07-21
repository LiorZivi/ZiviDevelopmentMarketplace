"""Upload a local file to the active telegram-remote DM."""

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

from send import _normalize_newlines, _prefixed  # noqa: E402
from telegram_transport import (  # noqa: E402
    TelegramError,
    load_credentials,
    send_document,
)


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="telegram-remote file upload")
    parser.add_argument("--file", required=True)
    parser.add_argument("--caption", default="")
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

    caption = _normalize_newlines(args.caption)
    if caption:
        caption = _prefixed(caption)

    try:
        posted = send_document(token, chat_id, args.file, caption=caption)
    except TelegramError as exc:
        _emit({"action": "error", "error": f"file upload failed: {exc}"})
        return 1

    state["message_count"] = int(state.get("message_count", 0)) + 1
    save_state(session_id, state)
    _emit({
        "action": "sent_file",
        "message_id": str(posted.get("message_id", "")),
        "file": str(Path(args.file).expanduser().resolve()),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
