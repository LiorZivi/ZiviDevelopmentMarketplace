"""Ask-question entrypoint — /teams-remote (Teams MCP flow, schema v3).

Fork of ``teams-remote/ask.py`` isolated to the ``teams-remote`` subsystem
so both skills can coexist. Two-step handshake unchanged; see the
original for rationale.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import load_state, resolve_session_id, save_state, set_subsystem  # noqa: E402

set_subsystem("teams-remote")

from html_templates import render_input_needed  # noqa: E402
from transport_router import (  # noqa: E402
    attach_http_fallback,
    promote_http_fallback,
    refresh_and_route,
)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def cmd_run(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1
    if not args.question:
        _emit({"action": "error", "error": "missing --question"})
        return 1

    html_body = render_input_needed(state, extras={
        "timestamp": _now_iso(),
        "question": args.question,
    })

    transport_config = refresh_and_route(state)
    post_question_env = {
        "action": "post_question",
        "session_id": session_id,
        "transport": state.get("transport", "mcp"),
        "mcp_call": "teams-ReplyToChannelMessage",
        "mcp_args": {
            "teamId": state["team_id"],
            "channelId": state["channel_id"],
            "messageId": state["root_message_id"],
            "content": html_body,
            "contentType": "html",
        },
        "next_step": "finalize",
        "hint": (
            "Call the MCP tool; the response has `id` and `createdDateTime`. "
            "Then re-invoke ask.py --step finalize --message-id <id> "
            "--created-iso <createdDateTime>."
        ),
    }
    attach_http_fallback(post_question_env, transport_config)
    if state.get("transport") == "http":
        promote_http_fallback(post_question_env)
    _emit(post_question_env)
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1
    if not args.message_id:
        _emit({"action": "error", "error": "missing --message-id"})
        return 1

    state["last_question_time"] = args.created_iso or _now_iso()
    own = list(state.get("own_message_ids") or [])
    if args.message_id not in own:
        own.append(args.message_id)
    state["own_message_ids"] = own
    save_state(session_id, state)

    _emit({
        "action": "ready",
        "session_id": session_id,
        "last_question_time": state["last_question_time"],
        "poll_interval": state["poll_interval"],
        "timeout_seconds": state["timeout_seconds"],
        "correlation_token": state["correlation_token"],
        "next": "run input poll via poll.py --mode input",
        "next_step": "poll_input",
    })
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ask a question via Teams MCP (teams-remote)")
    parser.add_argument("--step", required=True, choices=["run", "finalize"])
    parser.add_argument(
        "--session-id",
        required=False,
        help="optional; for tests and manual runs only — production reads "
             "COPILOT_AGENT_SESSION_ID.",
    )
    parser.add_argument("--question", default=None)
    parser.add_argument("--message-id", default=None,
                        help="Message id returned by teams-ReplyToChannelMessage.")
    parser.add_argument("--created-iso", default=None,
                        help="createdDateTime from the MCP response.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.step == "run":
        return cmd_run(args)
    return cmd_finalize(args)


if __name__ == "__main__":
    sys.exit(main())
