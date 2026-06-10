"""Activation entrypoint for ``/teams-remote`` (Teams MCP flow, schema v3).

This is a fork of the ``teams-remote`` ``activate.py`` with its
session-state directory rebased under ``<tempdir>/general-ops/teams-remote/``
so both skills can coexist on the same machine without clobbering each
other's state. Functionally identical to the original apart from that
isolation.

The two-step handshake is unchanged — see ``teams-remote/activate.py``
for the rationale. Dual-transport (``http_fallback`` sibling on
outbound envelopes) is deferred to a later PR per ``plan.md``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import (  # noqa: E402
    SCHEMA_VERSION,
    load_state,
    log_hook_error,
    resolve_session_id,
    save_state,
    set_subsystem,
)

set_subsystem("teams-remote")

from html_templates import render_root  # noqa: E402
from transport_router import (  # noqa: E402
    attach_http_fallback,
    promote_http_fallback,
    refresh_and_route,
)

DEFAULT_POLL_INTERVAL = 10
DEFAULT_TIMEOUT_MINUTES = 300


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _emit(action: dict) -> None:
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()


def _load_config() -> dict:
    candidates = [
        Path(os.getcwd()) / ".github" / "teams-remote.json",
        Path(os.getcwd()) / ".github" / "teams-remote.json",
        Path.home() / ".copilot" / "teams-remote.json",
        Path.home() / ".copilot" / "teams-remote.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log_hook_error(f"[activate/teams-remote] config parse error {candidate}: {exc}")
    return {}


def _mint_correlation_token(session_id: str) -> str:
    sid_short = (session_id or "sess")[:8]
    uuid_short = uuid.uuid4().hex[:8]
    return f"CORR-{sid_short}-{uuid_short}"


def _pending_path(session_id: str) -> Path:
    from state import get_activate_pending_path
    return get_activate_pending_path(session_id)


def _save_pending(session_id: str, payload: dict) -> None:
    path = _pending_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_pending(session_id: str) -> dict | None:
    path = _pending_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _clear_pending(session_id: str) -> None:
    try:
        _pending_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


def cmd_run(args: argparse.Namespace) -> int:
    """Step 1: validate, render, emit post_root envelope. Defer state."""
    session_id = resolve_session_id(args)

    existing = load_state(session_id)
    if existing and existing.get("away_mode"):
        _emit({
            "action": "already_active",
            "team_name": existing.get("team_name"),
            "channel_name": existing.get("channel_name"),
            "team_id": existing.get("team_id"),
            "channel_id": existing.get("channel_id"),
            "root_message_id": existing.get("root_message_id"),
            "correlation_token": existing.get("correlation_token"),
        })
        return 0

    config = _load_config()
    team_id = args.team_id or config.get("teamId") or config.get("team_id")
    channel_id = args.channel_id or config.get("channelId") or config.get("channel_id")

    missing = []
    if not team_id:
        missing.append("team_id")
    if not channel_id:
        missing.append("channel_id")
    if missing:
        _emit({
            "action": "need_input",
            "missing": missing,
            "message": (
                "Teams MCP team_id and channel_id are required. Resolve them "
                "via teams-ListTeams + teams-ListChannels (match the user's "
                "team/channel name exactly; fail if multiple matches). Then "
                "re-run with --team-id / --channel-id, or save them in "
                ".github/teams-remote.json as \"teamId\" / \"channelId\"."
            ),
        })
        return 0

    team_name = args.team or config.get("team") or "(unspecified)"
    channel_name = args.channel or config.get("channel") or "(unspecified)"
    correlation_token = _mint_correlation_token(session_id)

    provisional = {
        "correlation_token": correlation_token,
        "session_id_short": session_id[:8],
        "session_start_time": _now_iso(),
    }
    user_display_resolved = (
        args.user_display
        or os.environ.get("USER")
        or os.environ.get("USERNAME") or ""
    )
    root_html = render_root(provisional, extras={
        "workspace_path": os.getcwd(),
        "user_display": user_display_resolved,
    })
    # Self-mention on the root post so Teams raises a push notification
    # for the user (messages authored by the signed-in user are otherwise
    # suppressed). Noop when --user-id / display missing.
    root_mentions = ""
    if args.user_id and user_display_resolved:
        root_html = (
            f"<p><at>{user_display_resolved}</at> Copilot agent message:</p>" + root_html
        )
        root_mentions = json.dumps([{
            "displayName": user_display_resolved,
            "id": args.user_id,
            "type": "user",
        }])

    pending = {
        "session_id": session_id,
        "team_id": team_id,
        "channel_id": channel_id,
        "team_name": team_name,
        "channel_name": channel_name,
        "correlation_token": correlation_token,
        "session_start_time": provisional["session_start_time"],
        "user_display": args.user_display
                         or os.environ.get("USER")
                         or os.environ.get("USERNAME") or "",
        "user_mention_id": args.user_id or "",
        "workspace_path": os.getcwd(),
        "poll_interval": int(config.get("pollIntervalSeconds", DEFAULT_POLL_INTERVAL)),
        "timeout_seconds": int(config.get("timeoutMinutes", DEFAULT_TIMEOUT_MINUTES)) * 60,
        "root_html": root_html,
    }
    _save_pending(session_id, pending)

    mcp_args = {
        "teamId": team_id,
        "channelId": channel_id,
        "content": root_html,
        "contentType": "html",
        "subject": "Copilot CLI — teams-remote Session",
    }
    if root_mentions:
        mcp_args["mentions"] = root_mentions

    # Single-call invariant: refresh_and_route is invoked once per
    # subprocess; the captured transport_config is the value used by the
    # attach/promote pair below. No async transport flip is possible
    # within this single-shot script.
    transport_config = refresh_and_route({"transport": "mcp"})

    post_root_env = {
        "action": "post_root",
        "session_id": session_id,
        "transport": "mcp",
        "mcp_call": "teams-PostChannelMessage",
        "mcp_args": mcp_args,
        "correlation_token": correlation_token,
        "next_step": "finalize",
        "hint": (
            "Call the MCP tool with mcp_args. The response contains "
            "`id` (the root message id). Then re-invoke activate.py "
            "--step finalize --root-message-id <id> [--created-iso <createdDateTime>]."
        ),
    }
    attach_http_fallback(post_root_env, transport_config)
    # post_root has no next_step beyond `finalize` because the activation
    # handshake constrains the agent's next call (must pass message-id to
    # --step finalize). Do not add a duplicate next_step here.
    _emit(post_root_env)
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    """Step 2: write state after the MCP post succeeded."""
    session_id = resolve_session_id(args)
    pending = _load_pending(session_id)
    if pending is None:
        _emit({"action": "error",
               "error": "no pending activation found; call --step run first"})
        return 1
    if not args.root_message_id:
        _emit({"action": "error", "error": "missing --root-message-id"})
        return 1

    created_iso = args.created_iso or _now_iso()

    state = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "session_id_short": session_id[:8],
        "session_start_time": pending["session_start_time"],
        "away_mode": True,
        "chat_kind": "channel",
        "team_id": pending["team_id"],
        "channel_id": pending["channel_id"],
        "team_name": pending["team_name"],
        "channel_name": pending["channel_name"],
        "root_message_id": args.root_message_id,
        "root_created_iso": created_iso,
        "correlation_token": pending["correlation_token"],
        "poll_interval": pending["poll_interval"],
        "timeout_seconds": pending["timeout_seconds"],
        "workspace_path": pending["workspace_path"],
        "user_display": pending["user_display"],
        "user_mention_id": pending.get("user_mention_id", ""),
        "last_question_time": None,
        "seen_reply_ids": "",
        "own_message_ids": [args.root_message_id],
        "last_auto_post_time": None,
        "last_idle_heartbeat_time": None,
        "message_count": 0,
        "tasks_completed": [],
        "files_changed": [],
        "decisions_made": [],
        # teams-remote additions: transport routing. "mcp" by default; poll.py
        # flips to "http" once a token refresh has fired (signalling that
        # the CLI's cached bearer is stale).
        "transport": "mcp",
        "last_processed_id": "0",
    }
    save_state(session_id, state)
    _clear_pending(session_id)

    _emit({
        "action": "ready",
        "session_id": session_id,
        "team_id": state["team_id"],
        "channel_id": state["channel_id"],
        "team_name": state["team_name"],
        "channel_name": state["channel_name"],
        "root_message_id": state["root_message_id"],
        "correlation_token": state["correlation_token"],
        "poll_interval": state["poll_interval"],
        "timeout_seconds": state["timeout_seconds"],
        "transport": state["transport"],
        "next": "run idle poll via poll.py --step tick --mode idle",
        "next_step": "poll_idle",
    })
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="/teams-remote activation entrypoint")
    parser.add_argument("--step", required=True, choices=["run", "finalize"])
    parser.add_argument(
        "--session-id",
        required=False,
        help="optional; for tests and manual runs only — production reads "
             "COPILOT_AGENT_SESSION_ID.",
    )
    parser.add_argument("--team-id", default=None,
                        help="Graph team GUID (resolve via teams-ListTeams).")
    parser.add_argument("--channel-id", default=None,
                        help="Graph channel id, thread.tacv2 form (resolve via teams-ListChannels).")
    parser.add_argument("--team", default=None, help="Team display name (for rendering).")
    parser.add_argument("--channel", default=None, help="Channel display name (for rendering).")
    parser.add_argument("--user-display", default=None)
    parser.add_argument("--user-id", default=None,
                        help="Graph user GUID of the away user. When provided, "
                             "teams-remote replies will carry importance=urgent and "
                             "a self-@mention so Teams raises a notification "
                             "even though the message is authored on behalf of "
                             "the signed-in user.")
    parser.add_argument("--root-message-id", default=None,
                        help="Root message id returned by teams-PostChannelMessage.")
    parser.add_argument("--created-iso", default=None,
                        help="createdDateTime of the root message (authoritative boundary).")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.step == "run":
        return cmd_run(args)
    return cmd_finalize(args)


if __name__ == "__main__":
    sys.exit(main())
