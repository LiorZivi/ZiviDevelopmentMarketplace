"""/teams-remote end entrypoint — Teams MCP flow (schema v3).

Fork of ``teams-remote/end.py`` isolated to the ``teams-remote`` subsystem.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import (  # noqa: E402
    clear_pending_queue,
    delete_state,
    load_state,
    resolve_session_id,
    save_state,
    set_subsystem,
)

set_subsystem("teams-remote")

from html_templates import render_summary  # noqa: E402
from transport_router import (  # noqa: E402
    attach_http_fallback,
    promote_http_fallback,
    refresh_and_route,
)


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


def _banner_for_reason(reason: str) -> str:
    return {
        "user-invoked": "Session ended by /teams-remote end.",
        "remote-triggered": "Session ended by remote `end` reply.",
        "session-ended": "Session ended (CLI exited).",
    }.get(reason, "Session ended.")


def cmd_run(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)
    state = load_state(session_id)
    if state is None:
        _emit({
            "action": "no_session",
            "message": "No active teams-remote session. Run /teams-remote to start one.",
        })
        return 0

    duration_human = _duration(state.get("session_start_time", ""))
    banner = _banner_for_reason(args.reason or "user-invoked")
    html_body = render_summary(state, extras={
        "banner": banner,
        "duration_human": duration_human,
    })

    # Self-mention on the end summary so Teams raises a push notification
    # (symmetric with the activate root post). Noop unless the session was
    # activated with --user-id + --user-display.
    user_id = state.get("user_mention_id") or ""
    user_display = state.get("user_display") or ""
    mentions_json = ""
    if user_id and user_display:
        html_body = f"<p><at>{user_display}</at> Copilot agent message:</p>" + html_body
        mentions_json = json.dumps([{
            "displayName": user_display,
            "id": user_id,
            "type": "user",
        }])

    state["away_mode"] = False
    save_state(session_id, state)

    mcp_args = {
        "teamId": state["team_id"],
        "channelId": state["channel_id"],
        "messageId": state["root_message_id"],
        "content": html_body,
        "contentType": "html",
    }
    if mentions_json:
        mcp_args["mentions"] = mentions_json

    transport_config = refresh_and_route(state)
    post_summary_env = {
        "action": "post_summary",
        "session_id": session_id,
        "reason": args.reason,
        "transport": state.get("transport", "mcp"),
        "mcp_call": "teams-ReplyToChannelMessage",
        "mcp_args": mcp_args,
        "next_step": "finalize",
        "hint": "Post the summary via MCP, then invoke end.py --step finalize to delete state.",
    }
    attach_http_fallback(post_summary_env, transport_config)
    if state.get("transport") == "http":
        promote_http_fallback(post_summary_env)
    _emit(post_summary_env)
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    session_id = resolve_session_id(args)
    delete_state(session_id)
    clear_pending_queue(session_id)
    _emit({"action": "ended", "session_id": session_id})
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="/teams-remote end entrypoint")
    parser.add_argument("--step", required=True, choices=["run", "finalize"])
    parser.add_argument(
        "--session-id",
        required=False,
        help="optional; for tests and manual runs only — production reads "
             "COPILOT_AGENT_SESSION_ID.",
    )
    parser.add_argument("--reason", default="user-invoked",
                        choices=["user-invoked", "remote-triggered", "session-ended"])
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.step == "run":
        return cmd_run(args)
    return cmd_finalize(args)


if __name__ == "__main__":
    sys.exit(main())
