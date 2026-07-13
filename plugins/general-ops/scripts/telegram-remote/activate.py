"""Activation entrypoint for the ``telegram-remote`` skill.

Unlike ``teams-remote`` (whose two-step handshake exists because the *agent*
must invoke the MCP tools), the Telegram scripts call the Bot API directly, so
activation is a single shot:

  1. Resolve credentials (bot token + chat id).
  2. Drain any existing backlog so old DM messages are not injected, recording
     the baseline ``last_update_id``.
  3. POST the root announcement to the DM.
  4. Persist state with ``away_mode = True``.
  5. Emit ``ready`` (``next_step: poll_idle``).

State is shared with the rest of ``general-ops`` via ``lib/state.py``; the
``set_subsystem("telegram-remote")`` call isolates it under
``.../plugins/general-ops/telegram-remote/`` so it never collides with a
concurrent ``teams-remote`` session.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from state import (  # noqa: E402
    SCHEMA_VERSION,
    load_state,
    resolve_session_id,
    save_state,
    set_subsystem,
)

set_subsystem("telegram-remote")

from telegram_transport import (  # noqa: E402
    TelegramError,
    get_updates,
    load_credentials,
    send_message,
)

AGENT_PREFIX = "Copilot agent message:"
DEFAULT_LONG_POLL_TIMEOUT = 50
DEFAULT_LONG_POLL_BUDGET = 480  # seconds the idle tick blocks before returning
DEFAULT_QUESTION_TIMEOUT_MINUTES = 300


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def _drain_baseline(token: str) -> int:
    """Return the highest pending ``update_id`` (0 if none), consuming nothing.

    We poll with ``timeout=0`` (short poll) and take the max id. The first real
    idle tick then polls with ``offset = baseline + 1``, which confirms/drops
    everything at or below the baseline — so pre-existing DM history (including
    messages the reused bot previously sent to itself, or stale user chatter)
    is never injected.
    """
    updates = get_updates(token, None, timeout=0)
    ids = [u.get("update_id") for u in updates if isinstance(u.get("update_id"), int)]
    return max(ids) if ids else 0


def cmd_run(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)

    existing = load_state(session_id)
    if existing and existing.get("away_mode"):
        _emit({
            "action": "already_active",
            "chat_id": existing.get("chat_id"),
            "root_message_id": existing.get("root_message_id"),
        })
        return 0

    token, chat_id = load_credentials()
    if args.chat_id:
        chat_id = args.chat_id
    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        _emit({
            "action": "need_input",
            "missing": missing,
            "message": (
                "Telegram bot token and chat id are required. Set env "
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, or create "
                "~/.copilot/telegram-remote.json with keys botToken + chatId. "
                "To find your DM chat id, message your bot in Telegram then run: "
                'python "'
                + str(HERE / "telegram_transport.py")
                + '" discover'
            ),
        })
        return 0

    # Drain backlog to establish the dedup baseline.
    try:
        baseline = _drain_baseline(token)
    except TelegramError as exc:
        _emit({
            "action": "error",
            "error": str(exc),
            "conflict": exc.is_conflict,
            "hint": (
                "409 Conflict means the bot has a webhook set or another "
                "getUpdates consumer (e.g. a second telegram-remote session) "
                "is running. Use a dedicated bot, stop the other poller, or "
                "remove the webhook."
            ) if exc.is_conflict else "Check the bot token and network access.",
        })
        return 1

    workspace = os.getcwd()
    user_display = (
        args.user_display
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or ""
    )
    root_text = (
        f"\U0001f535 {AGENT_PREFIX} telegram-remote is now active.\n"
        f"Working directory: {workspace}\n"
        "I'll relay progress here and treat your replies as instructions.\n"
        "Reply `end` (or `/telegram-remote end`) to stop remote control."
    )
    try:
        posted = send_message(token, chat_id, root_text)
    except TelegramError as exc:
        _emit({"action": "error", "error": f"failed to post root message: {exc}"})
        return 1

    now = _now_iso()
    state = {
        "schema_version": SCHEMA_VERSION,
        "subsystem": "telegram-remote",
        "session_id": session_id,
        "session_id_short": session_id[:8],
        "session_start_time": now,
        "away_mode": True,
        "transport": "telegram",
        "chat_id": str(chat_id),
        "root_message_id": str(posted.get("message_id", "")),
        "last_update_id": int(baseline),
        "long_poll_timeout": DEFAULT_LONG_POLL_TIMEOUT,
        "long_poll_budget": DEFAULT_LONG_POLL_BUDGET,
        "timeout_seconds": DEFAULT_QUESTION_TIMEOUT_MINUTES * 60,
        "workspace_path": workspace,
        "user_display": user_display,
        "last_question_time": None,
        "last_idle_heartbeat_time": now,
        "message_count": 1,
    }
    save_state(session_id, state)

    _emit({
        "action": "ready",
        "session_id": session_id,
        "chat_id": state["chat_id"],
        "root_message_id": state["root_message_id"],
        "last_update_id": state["last_update_id"],
        "transport": "telegram",
        "next": "run idle poll via poll.py --step tick --mode idle",
        "next_step": "poll_idle",
    })
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="telegram-remote activation entrypoint")
    parser.add_argument("--step", required=True, choices=["run"])
    parser.add_argument(
        "--session-id",
        required=False,
        help="optional; tests/manual runs only — production reads "
             "COPILOT_AGENT_SESSION_ID.",
    )
    parser.add_argument("--chat-id", default=None,
                        help="Override the configured Telegram chat id.")
    parser.add_argument("--user-display", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
