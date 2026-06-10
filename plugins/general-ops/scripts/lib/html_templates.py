"""HTML message templates for the teams-remote skill.

Six ``render_*`` functions return HTML strings that are sent as the
``content`` field of a Teams MCP ``PostChannelMessage`` /
``ReplyToChannelMessage`` call (contentType=html). Every interpolated
user-supplied value is escaped with ``html.escape(value, quote=True)``.
File paths are pre-sanitised (``\\`` → ``/``) before interpolation.

All functions take ``state: dict`` and an optional ``extras: dict | None``
that carries per-call values the state dict does not hold (timestamps,
truncated turn summaries, error text, list deltas, etc.).

**Correlation-token footer**: Every render_* appends a tiny footer
containing ``state["correlation_token"]``. In schema v3 we locate
threads by ``root_message_id``, not the token — so the footer is kept
purely for traceability / debugging / grep-ability of posts in a
channel, not for lookup.
"""

from __future__ import annotations

import html
from typing import Optional


def _esc(value) -> str:
    """HTML-escape a value (None → empty string, non-str → str())."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _corr_footer(state: dict) -> str:
    """Return a small, grep-able correlation footer. Empty string if no token."""
    token = state.get("correlation_token") if isinstance(state, dict) else None
    if not token:
        return ""
    return (
        f"\n<p><span style=\"color:#999;font-size:11px\">"
        f"corr: <code>{_esc(token)}</code></span></p>"
    )


def _path(value) -> str:
    """Sanitise a file path for HTML: backslashes → forward slashes, then escape."""
    if value is None:
        return ""
    return html.escape(str(value).replace("\\", "/"), quote=True)


def _render_list_items(items, as_code: bool = False) -> str:
    """Render a list of strings as ``<li>...</li>`` lines; paths use ``<code>``."""
    if not items:
        return ""
    out = []
    for item in items:
        rendered = _path(item) if as_code else _esc(item)
        if as_code:
            out.append(f"<li><code>{rendered}</code></li>")
        else:
            out.append(f"<li>{rendered}</li>")
    return "".join(out)


def render_root(state: dict, extras: Optional[dict] = None) -> str:
    """Render the root message posted once at activation."""
    extras = extras or {}
    session_id_short = _esc(state.get("session_id_short"))
    session_start = _esc(state.get("session_start_time"))
    workspace_path = _path(extras.get("workspace_path", ""))
    user_display = _esc(extras.get("user_display", ""))
    return (
        f"<h2>🤖 Copilot CLI — Remote Session <code>{session_id_short}</code></h2>\n"
        f"<p><b>Started:</b> {session_start}<br>\n"
        f"<b>Workspace:</b> <code>{workspace_path}</code><br>\n"
        f"<b>User:</b> {user_display}</p>\n"
        f"<p>The agent is now <b>remote</b>. Reply in this thread to answer questions or send instructions.\n"
        f"Reply with <code>/teams-remote end</code> (or <code>end</code>) to close the session.</p>\n"
        f"<hr>"
        + _corr_footer(state)
    )


def render_progress(state: dict, extras: Optional[dict] = None) -> str:
    """Render a progress-update reply (posted every assistant turn while away).

    ``extras``: ``prefix`` (``"[Claude - auto]"`` from hook, ``"[Claude]"`` from
    skill), ``timestamp``, ``turn_summary``, ``files_changed_delta`` (list).
    """
    extras = extras or {}
    prefix = _esc(extras.get("prefix", "[Claude - auto]"))
    timestamp = _esc(extras.get("timestamp", ""))
    turn_summary = _esc(extras.get("turn_summary", ""))
    files = extras.get("files_changed_delta") or []
    items = _render_list_items(files, as_code=True)
    return (
        f"<p><b>{prefix} · Progress update</b> · {timestamp}</p>\n"
        f"<p>{turn_summary}</p>\n"
        f"<details><summary>Changes this cycle</summary>\n"
        f"  <ul>\n"
        f"    {items}\n"
        f"  </ul>\n"
        f"</details>"
        + _corr_footer(state)
    )


def render_input_needed(state: dict, extras: Optional[dict] = None) -> str:
    """Render the InputNeeded reply posted by ask.py."""
    extras = extras or {}
    timestamp = _esc(extras.get("timestamp", ""))
    question = _esc(extras.get("question", ""))
    return (
        f"<p><b>❓ Input needed</b> · {timestamp}</p>\n"
        f"<blockquote>{question}</blockquote>\n"
        f"<p><i>Reply in this thread. Auto-injecting your reply into the CLI conversation.</i></p>"
        + _corr_footer(state)
    )


def render_awaiting(state: dict, extras: Optional[dict] = None) -> str:
    """Render the idle-poll heartbeat reply."""
    extras = extras or {}
    idle_minutes = _esc(extras.get("idle_minutes", 0))
    timestamp = _esc(extras.get("timestamp", ""))
    return (
        f"<p>💤 <b>Awaiting instructions</b> · idle for {idle_minutes} min · {timestamp}</p>\n"
        f"<p>Reply with instructions, a new task, or <code>end</code> / <code>/teams-remote end</code> to close.</p>"
        + _corr_footer(state)
    )


def render_error(state: dict, extras: Optional[dict] = None) -> str:
    """Render the Error / Blocked reply."""
    extras = extras or {}
    timestamp = _esc(extras.get("timestamp", ""))
    error_text = _esc(extras.get("error", ""))
    return (
        f"<p>⚠️ <b>Error / blocked</b> · {timestamp}</p>\n"
        f"<pre>{error_text}</pre>\n"
        f"<p>Falling back to terminal. Re-run <code>/teams-remote</code> to reactivate.</p>"
        + _corr_footer(state)
    )


def render_summary(state: dict, extras: Optional[dict] = None) -> str:
    """Render the final session-summary reply.

    ``extras``: ``banner`` (variant text), ``duration_human``.
    """
    extras = extras or {}
    session_id_short = _esc(state.get("session_id_short"))
    duration = _esc(extras.get("duration_human", ""))
    message_count = _esc(state.get("message_count", 0))
    banner = _esc(extras.get("banner", ""))
    tasks = _render_list_items(state.get("tasks_completed") or [], as_code=False)
    files = _render_list_items(state.get("files_changed") or [], as_code=True)
    decisions = _render_list_items(state.get("decisions_made") or [], as_code=False)
    return (
        f"<h3>✅ Session summary · <code>{session_id_short}</code></h3>\n"
        f"<p><b>Duration:</b> {duration} · <b>Messages:</b> {message_count}</p>\n"
        f"<p><i>{banner}</i></p>\n"
        f"<h4>Tasks completed</h4>\n"
        f"<ul>{tasks}</ul>\n"
        f"<h4>Files changed</h4>\n"
        f"<ul>{files}</ul>\n"
        f"<h4>Decisions made</h4>\n"
        f"<ul>{decisions}</ul>\n"
        f"<hr>"
        + _corr_footer(state)
    )
