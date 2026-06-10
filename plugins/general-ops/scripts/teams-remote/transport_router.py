"""Transport routing helpers for teams-remote (extracted from poll.py).

This module owns the discovery, refresh, and envelope-shaping logic for
the two Teams MCP transports (oauth-authenticated MCP and the agency-hosted
loopback proxy). The four-script entrypoints (activate / ask / end / poll)
import only the public names defined here — there are no underscore-aliased
re-exports.

Public surface:

* :func:`resolve_transport` — discover the active transport, return either an
  oauth 3-tuple ``(config_path, tokens_path, server_url)`` or the
  :class:`teams_transport.AgencyTeamsProxy` dataclass, or ``None`` if neither
  is available.
* :func:`refresh_and_route` — proactively refresh the oauth token and flip
  ``state["transport"]`` to ``"http"`` if the refresh fired (signal that the
  CLI's cached bearer is stale). No-op for the agency proxy.
* :func:`attach_http_fallback` — append an ``http_fallback`` sibling to an
  outbound envelope (and any nested ``progress_post``) so the agent can switch
  away from a broken MCP path mid-flight.
* :func:`promote_http_fallback` — once a session is on HTTP, strip the
  ``mcp_call`` / ``mcp_args`` keys from any envelope that still has both the
  primary call and the fallback so the agent cannot accidentally re-enter the
  broken MCP path.
* :func:`dispatch_teams_call` — unifying helper for activate/ask/end. Either
  performs an in-process :func:`teams_transport.direct_http_call` (when the
  session has flipped to HTTP) and returns the parsed result, or returns the
  raw mcp call descriptor + an optional fallback for the caller to embed.

**Single-call invariant**: scripts are single-shot subprocesses. Each
invocation must call :func:`refresh_and_route` exactly once at the top, then
make at most one :func:`dispatch_teams_call`. The transport value captured at
``refresh_and_route`` time is the value emitted in the resulting envelope —
within-process flip races are impossible by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from teams_transport import (  # noqa: E402
        build_http_fallback,
        direct_http_call,
        ensure_fresh_token,
        find_agency_teams_proxy,
        find_teams_mcp_config,
    )
    _TRANSPORT_OK = True
except Exception as _exc:  # noqa: BLE001 — defensive
    _TRANSPORT_OK = False
    _TRANSPORT_IMPORT_ERROR = _exc  # type: ignore[assignment]


def resolve_transport() -> Optional[object]:
    """Return the discovered transport descriptor for building fallbacks.

    Preference order:
      1. Disk OAuth config (``find_teams_mcp_config``) — required for
         proactive token refresh. Works for user-authorised Teams MCPs.
      2. Agency-hosted loopback proxy (``find_agency_teams_proxy``) —
         no token refresh needed (proxy handles auth internally); agent
         POSTs unauthenticated to ``127.0.0.1:<port>``.

    Returns either:
      * the 3-tuple ``(config_path, tokens_path, server_url)`` for oauth, or
      * the :class:`AgencyTeamsProxy` dataclass instance, or
      * ``None`` if neither transport is discoverable.

    Callers type-switch with ``isinstance``.
    """
    if not _TRANSPORT_OK:
        return None
    try:
        oauth = find_teams_mcp_config()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[teams-remote/transport] find_teams_mcp_config failed: {exc!r}\n"
        )
        oauth = None
    if oauth is not None:
        return oauth
    try:
        proxy = find_agency_teams_proxy()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[teams-remote/transport] find_agency_teams_proxy failed: {exc!r}\n"
        )
        proxy = None
    if proxy is not None:
        return proxy
    sys.stderr.write(
        "[teams-remote/transport] no Teams MCP transport discoverable (neither "
        "~/.copilot/mcp-oauth-config/ nor %TEMP%\\copilot-mcp-*.json) — "
        "http_fallback will be omitted\n"
    )
    return None


def refresh_and_route(state: dict) -> Optional[object]:
    """Run a proactive token refresh when an oauth transport is present.

    Returns the transport descriptor (tuple for oauth, ``AgencyTeamsProxy``
    for proxy, or ``None``).

    Side effect: if a refresh fired this tick, flips ``state["transport"]``
    to ``"http"`` so subsequent outbound envelopes signal the switch.
    Missing config is tolerated — we log a single line to stderr.
    """
    transport = resolve_transport()
    if transport is None:
        return None
    # Agency proxy: no token refresh — the proxy handles auth.
    if not isinstance(transport, tuple):
        return transport
    cfg_path, tokens_path, _server_url = transport
    if not tokens_path.exists():
        sys.stderr.write(
            f"[teams-remote/transport] tokens file missing at {tokens_path} — "
            "skipping refresh\n"
        )
        return transport
    try:
        fresh = ensure_fresh_token(tokens_path, config_path=cfg_path)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"[teams-remote/transport] token refresh failed: {exc!r}\n"
        )
        return transport
    if fresh.get("refreshed"):
        state["transport"] = "http"
    return transport


def attach_http_fallback(envelope: dict, transport: Optional[object]) -> None:
    """Add an ``http_fallback`` sibling to ``envelope`` mirroring mcp_call.

    ``transport`` is either the oauth 3-tuple from
    :func:`teams_transport.find_teams_mcp_config` or an
    :class:`AgencyTeamsProxy` dataclass from
    :func:`teams_transport.find_agency_teams_proxy`. Handles the nested
    ``progress_post`` sub-envelope too. No-op if transport lookup
    already failed or the envelope has no ``mcp_call``.
    """
    if transport is None or not _TRANSPORT_OK:
        return

    is_tuple = isinstance(transport, tuple)

    def _inject(env: dict) -> None:
        call = env.get("mcp_call")
        args = env.get("mcp_args")
        if not call or not isinstance(args, dict):
            return
        if is_tuple:
            fallback = build_http_fallback(call, args, config=transport)
        else:
            fallback = build_http_fallback(call, args, proxy=transport)
        if fallback is not None:
            env["http_fallback"] = fallback

    _inject(envelope)
    progress = envelope.get("progress_post")
    if isinstance(progress, dict):
        _inject(progress)


def promote_http_fallback(envelope: dict) -> None:
    """When the session has flipped to HTTP transport, strip the MCP primary
    call so the agent cannot re-enter the broken MCP path and re-stall.

    ``http_fallback`` stays under its existing key — SKILL.md instructs the
    agent to execute that sibling directly. Applies to nested envelopes too
    (``progress_post``). Inner closure ``_strip`` is intentionally lexically
    nested — module-level public surface only.
    """
    def _strip(env: dict) -> None:
        if "http_fallback" in env:
            env.pop("mcp_call", None)
            env.pop("mcp_args", None)

    _strip(envelope)
    progress = envelope.get("progress_post")
    if isinstance(progress, dict):
        _strip(progress)


def dispatch_teams_call(
    state: dict,
    tool_name: str,
    mcp_args: dict,
    *,
    transport_descriptor: Optional[object],
) -> dict:
    """Route a Teams MCP call through HTTP (in-process) or hand back the
    descriptor for the agent to execute over MCP.

    Single-call invariant: caller must invoke this at most once per
    subprocess; ``transport_descriptor`` is the value captured by a single
    prior :func:`refresh_and_route`.

    Returns one of three shapes:

    * ``{"mode": "http", "ok": True, "result": <parsed-jsonrpc-result>}`` —
      ``state["transport"] == "http"`` and the in-process call succeeded.
    * ``{"mode": "http", "ok": False, "error": "<reason>"}`` —
      ``state["transport"] == "http"`` but the call failed. Caller emits a
      ``transport_error`` envelope with ``next_step: "investigate_or_end"``.
      Sessions stay on http; no auto-flip back to mcp.
    * ``{"mode": "mcp", "mcp_call": tool_name, "mcp_args": mcp_args,
      "http_fallback": <fallback-or-None>}`` — caller merges into outbound
      envelope so the agent executes the MCP tool itself.
    """
    if state.get("transport") == "http":
        if not _TRANSPORT_OK:
            return {"mode": "http", "ok": False, "error": "transport-unavailable"}
        # Only oauth tuples carry a real transport here; the agency proxy
        # uses a different code path (build_http_fallback returns the
        # localhost POST descriptor for the agent to execute).
        if not isinstance(transport_descriptor, tuple):
            return {
                "mode": "http",
                "ok": False,
                "error": "no-oauth-config-for-direct-call",
            }
        result = direct_http_call(tool_name, mcp_args, config=transport_descriptor)
        if not result.success:
            return {"mode": "http", "ok": False, "error": result.error or "unknown"}
        return {"mode": "http", "ok": True, "result": result.data}

    fallback = None
    if _TRANSPORT_OK and transport_descriptor is not None:
        if isinstance(transport_descriptor, tuple):
            fallback = build_http_fallback(
                tool_name, mcp_args, config=transport_descriptor
            )
        else:
            fallback = build_http_fallback(
                tool_name, mcp_args, proxy=transport_descriptor
            )
    return {
        "mode": "mcp",
        "mcp_call": tool_name,
        "mcp_args": mcp_args,
        "http_fallback": fallback,
    }
