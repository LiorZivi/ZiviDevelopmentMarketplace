"""Polling helper for /teams-remote — Teams MCP flow with direct-HTTP fallback.

Fork of ``teams-remote/poll.py`` with three upgrades (per
``plan.md`` Phase 3):

1. **Proactive token refresh.** At the top of every ``--step tick``,
   locate the Teams MCP tokens file via
   :func:`teams_transport.find_teams_mcp_config` and call
   :func:`teams_transport.ensure_fresh_token`. If it fires a refresh
   the state's ``transport`` flag is flipped to ``"http"`` for the
   rest of the session (the CLI caches the old bearer in memory;
   MCP tool calls will keep failing with ``-32001`` until restart).
   Missing config is tolerated — we log a one-line stderr note and
   keep the envelope unchanged.

2. **http_fallback sibling** on every outbound envelope (``tick``
   poll, ``heartbeat``, ``progress_post``, ``inject`` ack). Agents
   attempt ``mcp_call`` first; on ``-32001`` / 401 / ``AADSTS*`` they
   switch to ``http_fallback`` and stay on HTTP for the session.

3. **Numeric id defensive check** on top of ``own_message_ids`` dedup.
   ``last_processed_id`` is tracked as a decimal string in state and
   compared numerically (``int(reply_id) > int(last_processed_id)``)
   so clock skew / duplicate timestamps can't smuggle an old reply
   back into the stream.

Everything else (reply normalisation, timestamp boundary, HTML→text,
``own_message_ids`` self-filter) is unchanged from the teams-remote
version.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import html.parser
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from state import load_state, resolve_session_id, save_state, set_subsystem  # noqa: E402

set_subsystem("teams-remote")

from html_templates import render_awaiting, render_progress  # noqa: E402

# Local import — teams_transport lives alongside this file.
sys.path.insert(0, str(HERE))
try:
    from teams_transport import long_poll_replies  # noqa: E402
    _TRANSPORT_OK = True
except Exception as _exc:  # noqa: BLE001 — defensive: never block polling
    _TRANSPORT_OK = False
    _TRANSPORT_IMPORT_ERROR = _exc  # type: ignore[assignment]

from transport_router import (  # noqa: E402
    attach_http_fallback,
    promote_http_fallback,
    refresh_and_route,
    resolve_transport,
)

_TERM_RE = re.compile(r"^\s*(end|/teams-remote\s+end|/teams-remote-end)\s*$", re.IGNORECASE)
_MAX_REPLIES = 50


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(d: dt.datetime) -> str:
    return d.isoformat()


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


def _seen_ids(state: dict) -> list:
    return [s for s in (state.get("seen_reply_ids") or "").split(",") if s]


def _set_seen_ids(state: dict, ids: list) -> None:
    state["seen_reply_ids"] = ",".join(ids)


def _own_ids(state: dict) -> set:
    return set(state.get("own_message_ids") or [])


def _last_processed_id(state: dict) -> int:
    raw = state.get("last_processed_id")
    if raw is None or raw == "":
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _bump_last_processed_id(state: dict, reply_id: str) -> None:
    try:
        candidate = int(reply_id)
    except (TypeError, ValueError):
        return
    current = _last_processed_id(state)
    if candidate > current:
        state["last_processed_id"] = str(candidate)


def _after_iso_for_mode(state: dict, mode: str) -> Optional[str]:
    if mode == "input":
        return state.get("last_question_time")
    return (
        state.get("last_idle_heartbeat_time")
        or state.get("root_created_iso")
        or state.get("session_start_time")
    )


class _TextExtractor(html.parser.HTMLParser):
    """Minimal HTML → plain text. Drops tags, preserves text, unescapes entities."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in ("br", "p", "div", "li"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in ("p", "div", "li"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    try:
        parser = _TextExtractor()
        parser.feed(value)
        parser.close()
        return parser.get_text()
    except Exception:
        stripped = re.sub(r"<[^>]+>", " ", value)
        return html.unescape(re.sub(r"\s+", " ", stripped)).strip()


def _normalise_reply(reply: dict) -> dict:
    """Normalise a Graph ``chatMessage`` reply to a flat ``{id, sender, text, timestamp}``."""
    rid = str(reply.get("id") or "")
    timestamp = str(reply.get("createdDateTime") or reply.get("timestamp") or "")

    sender = "unknown"
    frm = reply.get("from")
    if isinstance(frm, dict):
        user = frm.get("user") if isinstance(frm.get("user"), dict) else None
        app = frm.get("application") if isinstance(frm.get("application"), dict) else None
        if user and user.get("displayName"):
            sender = str(user["displayName"])
        elif app and app.get("displayName"):
            sender = str(app["displayName"])
        elif frm.get("displayName"):
            sender = str(frm["displayName"])

    body = reply.get("body")
    if isinstance(body, dict):
        content = body.get("content") or ""
        if body.get("contentType", "").lower() == "html":
            text = _html_to_text(str(content))
        else:
            text = str(content).strip()
    else:
        text = str(reply.get("text") or reply.get("content") or "").strip()

    return {"id": rid, "sender": sender, "text": text, "timestamp": timestamp}


# --------------------------------------------------------------------------- #
# Transport helpers — extracted to transport_router.py (v1.9.0). Imports above.
# --------------------------------------------------------------------------- #


def _apply_mention_hack(mcp_args: dict, state: dict) -> Optional[str]:
    """Attach a self-@mention AND the "Copilot agent message:" prefix to a
    Teams reply's mcp_args.

    Returns the mention display name (so callers can still reference it in a
    user-facing ``mention_hint``), or ``None`` if the state doesn't carry a
    ``user_mention_id``.

    Two pieces are injected into ``mcp_args`` when a mention is active:

    1. ``mentions`` — a JSON-stringified array Teams needs to raise a push
       notification for the signed-in user (who would otherwise be suppressed
       from notifying themselves; live-validated 2026-04).
    2. A prefix prepended to ``content`` of the form
       ``<p><at>DisplayName</at> Copilot agent message:</p>`` so the away user
       can visually distinguish agent-authored posts from their own replies in
       the Teams thread.

    If the caller left ``content`` empty (the ack template does this), the
    prefix is still set so the agent only needs to append their own HTML. If
    ``content`` already carries an ``<at>`` mention we don't double-prefix.
    """
    user_id = state.get("user_mention_id") or ""
    display = state.get("user_display") or ""
    if not user_id or not display:
        return None
    # Teams MCP accepts `mentions` as a JSON string (not an array).
    mcp_args.setdefault(
        "mentions",
        json.dumps([{"displayName": display, "id": user_id, "type": "user"}]),
    )
    existing = mcp_args.get("content") or ""
    prefix = f"<p><at>{display}</at> Copilot agent message:</p>"
    if "<at>" not in existing:
        mcp_args["content"] = prefix + existing
    return display


# --------------------------------------------------------------------------- #


def _build_progress_envelope(state: dict) -> Optional[dict]:
    """Return a progress-post sub-envelope if one should fire this tick, else None."""
    if not state.get("auto_progress"):
        return None
    now = _now()
    last = _parse_iso(state.get("last_auto_post_time"))
    if last is not None and (now - last).total_seconds() < int(state.get("poll_interval", 10)) * 3:
        return None

    html_body = render_progress(state, extras={
        "prefix": "[Claude]",
        "timestamp": _iso(now),
        "turn_summary": "Polling for replies…" if last else "Remote session live; awaiting instructions.",
        "files_changed_delta": [],
    })
    result = {
        "mcp_call": "teams-ReplyToChannelMessage",
        "mcp_args": {
            "teamId": state["team_id"],
            "channelId": state["channel_id"],
            "messageId": state["root_message_id"],
            "content": html_body,
            "contentType": "html",
        },
        "reason": "progress-auto",
        "note": "Post this reply BEFORE polling. Add the returned id to own_message_ids by calling poll.py --step record-own.",
    }
    mention = _apply_mention_hack(result["mcp_args"], state)
    if mention:
        result["mention_hint"] = (
            "Self-mention + 'Copilot agent message:' prefix already injected "
            "into content. For ANY ad-hoc post you compose by hand: "
            "contentType MUST be 'text', content MUST start with "
            f"'@{mention} Copilot agent message: ', AND you MUST pass the "
            "mentions arg as JSON-string "
            f"[{{\"displayName\":\"{mention}\",\"id\":\"{state.get('user_mention_id','')}\",\"type\":\"user\"}}]. "
            "Do NOT author raw HTML (<p>, <br>, <at>, etc.) in ad-hoc posts."
        )
    return result


def _cmd_tick_long_poll(
    args: argparse.Namespace, state: dict, transport_config: object
) -> int:
    """Block inline on ``long_poll_replies`` and emit a ``poll_result``
    envelope with replies inline.

    The returned envelope deliberately omits ``mcp_call`` / ``mcp_args``
    — the agent doesn't need to make a Teams API call, it just pipes
    the ``replies`` array straight into ``--step process --replies-json``.

    Falls back to the classic short-poll envelope (by returning 1 from
    this function's caller path) only when the long-poll itself cannot
    run; that's handled by the guard in ``cmd_tick`` before we get here.
    """
    after_iso = _after_iso_for_mode(state, "idle")
    own_ids = _own_ids(state)
    timeout = int(state.get("long_poll_timeout_seconds", 600))
    interval = int(state.get("long_poll_internal_interval", 5))

    # Pass the discovered transport descriptor directly so the helper
    # doesn't re-probe the filesystem on every call.
    kwargs: dict = {
        "timeout_seconds": timeout,
        "internal_interval": interval,
    }
    if isinstance(transport_config, tuple):
        kwargs["config"] = transport_config
    else:
        kwargs["proxy"] = transport_config

    replies, timed_out = long_poll_replies(
        team_id=state["team_id"],
        channel_id=state["channel_id"],
        message_id=state["root_message_id"],
        after_iso=after_iso,
        own_ids=own_ids,
        **kwargs,
    )

    last_activity = (
        _parse_iso(state.get("last_idle_heartbeat_time"))
        or _parse_iso(state.get("root_created_iso"))
        or _parse_iso(state.get("session_start_time"))
        or _now()
    )
    idle_sec = int((_now() - last_activity).total_seconds())

    envelope = {
        "action": "poll_result",
        "mode": "idle",
        "transport": state.get("transport", "mcp"),
        "replies": replies,
        "timed_out": timed_out,
        "correlation_token": state["correlation_token"],
        "after_timestamp": after_iso,
        "next_step": "process",
        "session_id": resolve_session_id(args),
        "idle_seconds": idle_sec,
        "long_poll_timeout_seconds": timeout,
    }
    _emit(envelope)
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    state = load_state(resolve_session_id(args))
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1

    # Record any prior outbound message id BEFORE polling so the long-poll
    # filter (and short-poll filter on the next process step) skips it.
    # The skill contract says agents may pass --record-own-id on tick after
    # an ack/heartbeat/progress post; without this branch the id was only
    # picked up by cmd_process, which the long-poll path bypasses.
    if getattr(args, "record_own_id", None):
        own = list(state.get("own_message_ids") or [])
        if args.record_own_id not in own:
            own.append(args.record_own_id)
            state["own_message_ids"] = own
        if getattr(args, "record_own_kind", "other") == "progress":
            state["last_auto_post_time"] = (
                getattr(args, "record_own_created", None) or _iso(_now())
            )
            state["message_count"] = int(state.get("message_count", 0)) + 1
        save_state(resolve_session_id(args), state)

    # --- teams-remote: proactive token refresh + transport routing.
    transport_config = refresh_and_route(state)
    save_state(resolve_session_id(args), state)  # persist any transport=http flip

    # --- Long-poll fast path (idle mode only).
    # See docs/LongPollImplementation-Measurements.md. When --long-poll is set
    # we block inside THIS subprocess for up to `long_poll_timeout_seconds`
    # (default 600s), doing short internal GETs, and return a
    # `poll_result` envelope carrying the replies inline. This collapses
    # ~60 forced LLM turns in a 10-min idle window down to ~1.
    if (
        args.mode == "idle"
        and getattr(args, "long_poll", False)
        and transport_config is not None
        and _TRANSPORT_OK
    ):
        return _cmd_tick_long_poll(args, state, transport_config)

    if args.with_sleep:
        try:
            time.sleep(int(state.get("poll_interval", 10)))
        except (ValueError, TypeError):
            time.sleep(10)

    after_iso = _after_iso_for_mode(state, args.mode)

    envelope = {
        "action": "poll",
        "mode": args.mode,
        "sleep_seconds": state["poll_interval"],
        "transport": state.get("transport", "mcp"),
        "mcp_call": "teams-ListChannelMessageReplies",
        "mcp_args": {
            "teamId": state["team_id"],
            "channelId": state["channel_id"],
            "messageId": state["root_message_id"],
            "maxReplies": _MAX_REPLIES,
        },
        "correlation_token": state["correlation_token"],
        "after_timestamp": after_iso,
        "next_step": "process",
        "session_id": resolve_session_id(args),
    }

    if args.mode == "input":
        last_q = _parse_iso(state.get("last_question_time"))
        if last_q is None:
            _emit({"action": "error",
                   "error": "input-mode tick without last_question_time; call ask.py first"})
            return 1
        deadline = last_q + dt.timedelta(seconds=int(state["timeout_seconds"]))
        envelope["deadline"] = _iso(deadline)
        envelope["timed_out"] = _now() >= deadline
    else:
        last_activity = (
            _parse_iso(state.get("last_idle_heartbeat_time"))
            or _parse_iso(state.get("root_created_iso"))
            or _parse_iso(state.get("session_start_time"))
            or _now()
        )
        idle_sec = (_now() - last_activity).total_seconds()
        envelope["idle_seconds"] = int(idle_sec)
        envelope["heartbeat_due"] = idle_sec >= int(state["timeout_seconds"])
        progress = _build_progress_envelope(state)
        if progress is not None:
            envelope["progress_post"] = progress

    attach_http_fallback(envelope, transport_config)
    if state.get("transport") == "http":
        promote_http_fallback(envelope)
    _emit(envelope)
    return 0


def _parse_replies_json(raw: Optional[str]) -> list:
    """Accepts a bare array, ``{messages:[...]}`` (MCP envelope), or ``{replies:[...]}``."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("messages", "replies", "value"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def _filter_candidates(state: dict, replies: list, after_iso: Optional[str]) -> list:
    """Apply seen-ID dedupe, own-ID self-filter, numeric id floor, and timestamp boundary."""
    seen = set(_seen_ids(state))
    own = _own_ids(state)
    after_dt = _parse_iso(after_iso)
    last_processed = _last_processed_id(state)

    candidates = []
    for r in replies:
        norm = _normalise_reply(r)
        if not norm["id"] or not norm["text"]:
            continue
        if norm["id"] in seen or norm["id"] in own:
            continue
        # Defensive numeric floor: even if clocks or dedup slipped,
        # refuse to re-surface an id we've already advanced past.
        try:
            rid_int = int(norm["id"])
        except (TypeError, ValueError):
            rid_int = None
        if rid_int is not None and last_processed and rid_int <= last_processed:
            continue
        if after_dt is not None:
            ts = _parse_iso(norm["timestamp"])
            if ts is not None and ts <= after_dt:
                continue
        candidates.append(norm)

    candidates.sort(key=lambda r: r["timestamp"] or "")
    return candidates


def cmd_process_input(args: argparse.Namespace, state: dict,
                      replies: list, transport_config: Optional[tuple]) -> int:
    last_q = _parse_iso(state.get("last_question_time"))
    if last_q is None:
        _emit({"action": "error", "error": "input-mode process without last_question_time"})
        return 1

    if _now() - last_q >= dt.timedelta(seconds=int(state["timeout_seconds"])):
        _emit({"action": "timeout",
               "message": f"Question timed out after {state['timeout_seconds']}s"})
        return 0

    candidates = _filter_candidates(state, replies, state.get("last_question_time"))
    if not candidates:
        truncated = len(replies) >= _MAX_REPLIES
        _emit({"action": "continue", "reason": "no-new-replies",
               "truncated": truncated,
               "next": "tick again",
               "next_step": "tick"})
        return 0

    answer = candidates[0]
    seen = _seen_ids(state)
    seen.append(answer["id"])
    _set_seen_ids(state, seen)
    _bump_last_processed_id(state, answer["id"])
    save_state(resolve_session_id(args), state)

    _emit({
        "action": "answer",
        "text": answer["text"],
        "sender": answer["sender"],
        "reply_id": answer["id"],
    })
    return 0


def cmd_process_idle(args: argparse.Namespace, state: dict,
                     replies: list, transport_config: Optional[tuple]) -> int:
    after_iso = _after_iso_for_mode(state, "idle")
    candidates = _filter_candidates(state, replies, after_iso)

    events: list = []
    seen = _seen_ids(state)

    for reply in candidates:
        seen.append(reply["id"])
        _set_seen_ids(state, seen)
        _bump_last_processed_id(state, reply["id"])

        if _TERM_RE.match(reply["text"] or ""):
            save_state(resolve_session_id(args), state)
            _emit({
                "action": "terminate",
                "reason": "remote-triggered",
                "sender": reply["sender"],
                "text": reply["text"],
                "reply_id": reply["id"],
            })
            return 0

        state["last_idle_heartbeat_time"] = _iso(_now())
        events.append(reply)

    if events:
        save_state(resolve_session_id(args), state)
        # Provide an ack envelope so the caller can post acknowledgement
        # in parallel with starting the work — mirrors Rule 2a from SKILL.md.
        inject_envelope = {
            "action": "inject",
            "replies": events,
            "transport": state.get("transport", "mcp"),
            "ack_template": {
                "mcp_call": "teams-ReplyToChannelMessage",
                "mcp_args": {
                    "teamId": state["team_id"],
                    "channelId": state["channel_id"],
                    "messageId": state["root_message_id"],
                    "content": "",  # agent fills this with a short ack
                    "contentType": "html",
                },
            },
        }
        mention = _apply_mention_hack(
            inject_envelope["ack_template"]["mcp_args"], state)
        if mention:
            inject_envelope["mention_hint"] = (
                "Self-mention + 'Copilot agent message:' prefix already injected "
                "into ack_template.mcp_args.content; append your ack text as "
                "PLAIN TEXT after the prefix (do NOT overwrite content, do NOT "
                "add raw HTML like <p>/<br>/<ul>). For separate ad-hoc posts "
                f"(answers, status updates), use contentType='text', start with '@{mention} "
                f"Copilot agent message: ', and pass mentions=[{{\"displayName\":\"{mention}\","
                f"\"id\":\"{state.get('user_mention_id','')}\",\"type\":\"user\"}}]."
            )
        attach_http_fallback(inject_envelope["ack_template"], transport_config)
        if state.get("transport") == "http":
            promote_http_fallback(inject_envelope["ack_template"])
        _emit(inject_envelope)
        return 0

    last_activity = (
        _parse_iso(state.get("last_idle_heartbeat_time"))
        or _parse_iso(state.get("root_created_iso"))
        or _parse_iso(state.get("session_start_time"))
        or _now()
    )
    idle_sec = (_now() - last_activity).total_seconds()
    if idle_sec >= int(state["timeout_seconds"]):
        html_body = render_awaiting(state, extras={
            "idle_minutes": int(idle_sec / 60),
            "timestamp": _iso(_now()),
        })
        state["last_idle_heartbeat_time"] = _iso(_now())
        save_state(resolve_session_id(args), state)
        heartbeat_env = {
            "action": "heartbeat",
            "transport": state.get("transport", "mcp"),
            "next_step": "tick",
            "mcp_call": "teams-ReplyToChannelMessage",
            "mcp_args": {
                "teamId": state["team_id"],
                "channelId": state["channel_id"],
                "messageId": state["root_message_id"],
                "content": html_body,
                "contentType": "html",
            },
            "note": "Post the heartbeat; then call poll.py --step record-own --message-id <id> so we don't re-read it.",
        }
        mention = _apply_mention_hack(heartbeat_env["mcp_args"], state)
        if mention:
            heartbeat_env["mention_hint"] = (
                "Self-mention + 'Copilot agent message:' prefix already injected "
                "into heartbeat content. Reminder: any ad-hoc post you compose "
                f"separately MUST use contentType='text', start with '@{mention} "
                f"Copilot agent message: ', and pass mentions=[{{\"displayName\":\"{mention}\","
                f"\"id\":\"{state.get('user_mention_id','')}\",\"type\":\"user\"}}]. "
                "No hand-rolled HTML."
            )
        attach_http_fallback(heartbeat_env, transport_config)
        if state.get("transport") == "http":
            promote_http_fallback(heartbeat_env)
        _emit(heartbeat_env)
        return 0

    truncated = len(replies) >= _MAX_REPLIES
    _emit({"action": "continue", "reason": "no-new-replies",
           "idle_seconds": int(idle_sec), "truncated": truncated,
           "next": "tick again",
           "next_step": "tick"})
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    state = load_state(resolve_session_id(args))
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1

    # Locate transport once so process-time envelopes (ack, heartbeat)
    # can carry http_fallback too — prefers oauth disk config, falls
    # back to agency-hosted loopback proxy.
    transport_config = resolve_transport()

    if args.record_own_id:
        own = list(state.get("own_message_ids") or [])
        if args.record_own_id not in own:
            own.append(args.record_own_id)
        state["own_message_ids"] = own
        if args.record_own_kind == "progress":
            state["last_auto_post_time"] = args.record_own_created or _iso(_now())
            state["message_count"] = int(state.get("message_count", 0)) + 1
        save_state(resolve_session_id(args), state)

    replies = _parse_replies_json(args.replies_json)
    if args.mode == "input":
        return cmd_process_input(args, state, replies, transport_config)
    return cmd_process_idle(args, state, replies, transport_config)


def cmd_record_own(args: argparse.Namespace) -> int:
    state = load_state(resolve_session_id(args))
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1
    if not args.message_id:
        _emit({"action": "error", "error": "missing --message-id"})
        return 1
    own = list(state.get("own_message_ids") or [])
    if args.message_id not in own:
        own.append(args.message_id)
    state["own_message_ids"] = own
    if args.kind == "progress":
        state["last_auto_post_time"] = args.created_iso or _iso(_now())
        state["message_count"] = int(state.get("message_count", 0)) + 1
    save_state(resolve_session_id(args), state)
    _emit({"action": "recorded", "message_id": args.message_id,
           "own_count": len(own)})
    return 0


def cmd_record_mcp_error(args: argparse.Namespace) -> int:
    """Record an MCP call failure and, on the first hit, flip the session
    to the HTTP transport for the remainder of its lifetime.

    Agents call this after observing a ``McpError`` / ``-32001 Request timed
    out`` on a ``teams-*`` MCP tool invocation, then immediately re-run
    ``--step tick``. The next tick envelope will carry ``transport: "http"``
    and will have had its ``mcp_call``/``mcp_args`` stripped so the HTTP
    fallback is the only available path.
    """
    state = load_state(resolve_session_id(args))
    if state is None:
        _emit({"action": "error", "error": "no_session"})
        return 1

    streak = int(state.get("mcp_timeout_streak", 0)) + 1
    state["mcp_timeout_streak"] = streak
    state["last_mcp_error"] = {
        "code": int(args.code),
        "message": args.message or "",
        "at": _iso(_now()),
    }

    flipped = False
    if state.get("transport") != "http":
        state["transport"] = "http"
        state["transport_flipped_at"] = _iso(_now())
        state["transport_flip_reason"] = f"mcp-error:{int(args.code)}"
        flipped = True

    save_state(resolve_session_id(args), state)
    _emit({
        "action": "mcp_error_recorded",
        "transport": state["transport"],
        "mcp_timeout_streak": streak,
        "flipped": flipped,
        "next_step": "tick",
    })
    return 0


def cmd_set_user_mention(args: argparse.Namespace) -> int:
    """Patch an existing session's ``user_mention_id`` / ``user_display``.

    Enables the self-@mention + ``importance=urgent`` hack on subsequent
    envelopes without requiring a full re-activation. No-op fields are
    preserved if not passed.
    """
    state = load_state(resolve_session_id(args))
    if state is None:
        _emit({"action": "error", "error": "no active teams-remote session"})
        return 1
    if args.user_id is not None:
        state["user_mention_id"] = args.user_id
    if args.user_display is not None:
        state["user_display"] = args.user_display
    save_state(resolve_session_id(args), state)
    _emit({
        "action": "user_mention_updated",
        "user_mention_id": state.get("user_mention_id", ""),
        "user_display": state.get("user_display", ""),
    })
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="teams-remote polling helper")
    parser.add_argument("--step", required=True,
                        choices=["tick", "process", "record-own",
                                 "record-mcp-error", "set-user-mention"])
    parser.add_argument("--mode", choices=["input", "idle"], default="idle")
    parser.add_argument("--session-id", required=False, help="optional; for tests and manual runs only - production reads COPILOT_AGENT_SESSION_ID.")
    parser.add_argument("--replies-json", default=None,
                        help="JSON array from teams-ListChannelMessageReplies, "
                             "or {messages:[...]} envelope as returned by MCP.")
    parser.add_argument("--message-id", default=None,
                        help="For --step record-own: the id of an outbound post.")
    parser.add_argument("--created-iso", default=None,
                        help="For --step record-own --kind progress: createdDateTime.")
    parser.add_argument("--kind", default="other",
                        choices=["other", "progress", "heartbeat"],
                        help="For --step record-own: bookkeeping category.")
    parser.add_argument("--with-sleep", action="store_true",
                        help="For --step tick: sleep poll_interval seconds "
                             "internally before emitting the envelope.")
    parser.add_argument("--long-poll", action="store_true",
                        help="For --step tick --mode idle: block inside this "
                             "subprocess for up to long_poll_timeout_seconds "
                             "(default 600s), doing short internal HTTP GETs. "
                             "Emits a 'poll_result' envelope with replies "
                             "inline when a new reply arrives or the ceiling "
                             "elapses. Collapses ~60 forced LLM turns per "
                             "10-min idle window down to ~1. See "
                             "docs/LongPollImplementation-Measurements.md.")
    parser.add_argument("--record-own-id", default=None,
                        help="For --step process: id of a just-posted outbound "
                             "message to register before processing replies.")
    parser.add_argument("--record-own-created", default=None,
                        help="For --step process: createdDateTime of the "
                             "record-own-id post (used when kind=progress).")
    parser.add_argument("--record-own-kind", default="other",
                        choices=["other", "progress", "heartbeat"],
                        help="For --step process: kind of the recorded own id.")
    parser.add_argument("--code", type=int, default=None,
                        help="For --step record-mcp-error: MCP error code "
                             "(e.g. -32001 for 'Request timed out').")
    parser.add_argument("--message", default=None,
                        help="For --step record-mcp-error: error message text.")
    parser.add_argument("--user-id", default=None,
                        help="For --step set-user-mention: Graph user GUID "
                             "of the away user (enables notification hack).")
    parser.add_argument("--user-display", default=None,
                        help="For --step set-user-mention: display name "
                             "used inside the <at>...</at> mention tag.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.step == "tick":
        return cmd_tick(args)
    if args.step == "record-own":
        return cmd_record_own(args)
    if args.step == "record-mcp-error":
        if args.code is None:
            _emit({"action": "error", "error": "missing --code"})
            return 1
        return cmd_record_mcp_error(args)
    if args.step == "set-user-mention":
        return cmd_set_user_mention(args)
    return cmd_process(args)


if __name__ == "__main__":
    sys.exit(main())
