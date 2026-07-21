"""Idle/input polling for the ``telegram-remote`` skill.

A single ``--step tick`` does everything (there is no separate ``process`` step
— the script owns the HTTP, so nothing is delegated back to the agent):

* It **long-polls internally** for up to ``long_poll_budget`` seconds (default
  480), issuing back-to-back ``getUpdates`` calls of ``long_poll_timeout``
  seconds each. The blocking wait *is* the idle sleep, so one forced agent turn
  covers ~8 minutes of idle instead of ~500 — the same token-drain collapse
  ``teams-remote`` gets from its long-poll fast path.
* When the user replies, it classifies and emits a branch action:

  | mode  | action     | meaning                                             |
  |-------|------------|-----------------------------------------------------|
  | idle  | ``inject`` | replies become new user prompts (+ post an ack)     |
  | idle  | ``terminate`` | user said ``end`` → run end.py                    |
  | idle  | ``continue`` | budget elapsed, nothing new → tick again          |
  | input | ``answer`` | first reply answers the pending ask.py question     |
  | input | ``timeout``| question window elapsed with no answer              |
  | input | ``continue``/``terminate`` | as above                            |

De-dup is a monotonic ``update_id`` offset — the bot never receives its own
outbound messages, so no self-filtering is required.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from state import (  # noqa: E402
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
    parse_message,
)

_TERM_RE = re.compile(
    r"^\s*(end|/end|/telegram-remote\s+end|/telegram-remote-end)\s*$",
    re.IGNORECASE,
)
_SEND_SCRIPT = str(HERE / "send.py")
_END_SCRIPT = str(HERE / "end.py")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def _budget(state: dict) -> int:
    env = os.environ.get("TELEGRAM_REMOTE_POLL_BUDGET")
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return int(state.get("long_poll_budget", 480))


def _segment(state: dict) -> int:
    env = os.environ.get("TELEGRAM_REMOTE_POLL_SEGMENT")
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return int(state.get("long_poll_timeout", 50))


def _long_poll(state: dict, token: str) -> Optional[list]:
    """Block up to the budget, returning the first non-empty update batch.

    Returns ``[]`` when the budget elapses with nothing new. Returns ``None``
    after emitting an ``error`` envelope for a non-recoverable failure (409
    conflict). Transient network errors are retried within the budget.
    """
    offset = int(state.get("last_update_id", 0)) + 1
    segment = _segment(state)
    deadline = time.monotonic() + _budget(state)
    transient = 0
    # Always make at least one attempt, even if the budget is 0 (test mode).
    first = True
    while first or time.monotonic() < deadline:
        first = False
        remaining = deadline - time.monotonic()
        seg = segment if segment <= 0 else max(1, min(segment, int(remaining) or 1))
        try:
            updates = get_updates(token, offset, timeout=seg)
        except TelegramError as exc:
            if exc.is_conflict:
                _emit({
                    "action": "error",
                    "error": str(exc),
                    "conflict": True,
                    "hint": (
                        "409 Conflict: a webhook is set on this bot or another "
                        "getUpdates consumer (a second telegram-remote session) "
                        "is polling the same token. Stop the other poller or use "
                        "a dedicated bot, then re-activate."
                    ),
                })
                return None
            transient += 1
            if transient >= 5:
                # Give up this tick; the caller will re-tick.
                return []
            time.sleep(min(5, 2 * transient))
            continue
        if updates:
            return updates
        if segment <= 0:
            break
    return []


def _collect(state: dict, updates: list) -> list:
    """Advance the offset past the whole batch, return in-chat text messages."""
    ids = [u.get("update_id") for u in updates if isinstance(u.get("update_id"), int)]
    if ids:
        state["last_update_id"] = max(max(ids), int(state.get("last_update_id", 0)))
    chat_id = str(state.get("chat_id", ""))
    msgs = []
    for up in updates:
        norm = parse_message(up)
        if norm and norm["text"] and norm["chat_id"] == chat_id:
            msgs.append(norm)
    msgs.sort(key=lambda m: m["timestamp"] or "")
    return msgs


def _handle_idle(session_id: str, state: dict, msgs: list) -> int:
    if not msgs:
        save_state(session_id, state)
        _emit({"action": "continue", "reason": "no-new-replies", "next_step": "tick"})
        return 0

    events = []
    for m in msgs:
        if _TERM_RE.match(m["text"] or ""):
            state["last_idle_heartbeat_time"] = _now_iso()
            save_state(session_id, state)
            _emit({
                "action": "terminate",
                "reason": "remote-triggered",
                "sender": m["sender"],
                "text": m["text"],
                "reply_id": m["id"],
                "end_hint": (
                    f'python "{_END_SCRIPT}" --reason remote-triggered '
                    f"--session-id {session_id}"
                ),
            })
            return 0
        events.append(m)

    state["last_idle_heartbeat_time"] = _now_iso()
    state["message_count"] = int(state.get("message_count", 0)) + len(events)
    save_state(session_id, state)
    _emit({
        "action": "inject",
        "replies": events,
        "ack_hint": (
            "Post a short acknowledgement IN PARALLEL with starting the work "
            "(one sentence, paraphrase what you understood), then do the task:\n"
            f'  python "{_SEND_SCRIPT}" --text "<ack>" --session-id {session_id}\n'
            "Post concise progress updates at meaningful execution stages. "
            "After successful completion, send the fixed completion marker:\n"
            f'  python "{_SEND_SCRIPT}" --completed --text "<outcome>" '
            f"--session-id {session_id}\n"
            "Then tick the idle poll again."
        ),
        "send_script": _SEND_SCRIPT,
        "next_step": "tick",
    })
    return 0


def _handle_input(session_id: str, state: dict, msgs: list) -> int:
    last_q = _parse_iso(state.get("last_question_time"))
    if last_q is None:
        _emit({"action": "error",
               "error": "input-mode tick without last_question_time; call ask.py first"})
        return 1

    if _now() - last_q >= dt.timedelta(seconds=int(state["timeout_seconds"])):
        save_state(session_id, state)
        _emit({"action": "timeout",
               "message": f"Question timed out after {state['timeout_seconds']}s"})
        return 0

    if not msgs:
        save_state(session_id, state)
        _emit({"action": "continue", "reason": "no-new-replies", "next_step": "tick"})
        return 0

    for m in msgs:
        if _TERM_RE.match(m["text"] or ""):
            save_state(session_id, state)
            _emit({
                "action": "terminate",
                "reason": "remote-triggered",
                "sender": m["sender"],
                "text": m["text"],
                "reply_id": m["id"],
                "end_hint": (
                    f'python "{_END_SCRIPT}" --reason remote-triggered '
                    f"--session-id {session_id}"
                ),
            })
            return 0

    answer = msgs[0]
    state["message_count"] = int(state.get("message_count", 0)) + 1
    save_state(session_id, state)
    _emit({
        "action": "answer",
        "text": answer["text"],
        "sender": answer["sender"],
        "reply_id": answer["id"],
    })
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({"action": "error", "error": "no active telegram-remote session"})
        return 1

    token, _ = load_credentials()
    if not token:
        _emit({"action": "error", "error": "no bot token configured"})
        return 1

    updates = _long_poll(state, token)
    if updates is None:
        return 1  # error already emitted (conflict)

    msgs = _collect(state, updates)
    if args.mode == "input":
        return _handle_input(session_id, state, msgs)
    return _handle_idle(session_id, state, msgs)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="telegram-remote polling entrypoint")
    parser.add_argument("--step", required=True, choices=["tick"])
    parser.add_argument("--mode", default="idle", choices=["idle", "input"])
    parser.add_argument(
        "--session-id",
        required=False,
        help="optional; tests/manual runs only — production reads "
             "COPILOT_AGENT_SESSION_ID.",
    )
    # Accepted for parity with the teams-remote invocation shape; the Telegram
    # long-poll blocks internally, so these are advisory no-ops.
    parser.add_argument("--long-poll", action="store_true")
    parser.add_argument("--with-sleep", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    return cmd_tick(args)


if __name__ == "__main__":
    sys.exit(main())
