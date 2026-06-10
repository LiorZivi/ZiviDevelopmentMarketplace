"""Teams MCP transport layer for the ``teams-remote`` skill.

This module ports the token-refresh + direct-HTTP fallback mechanism
from the ``phone-mode`` reference skill (see ``Skill-1.txt`` at the
repository root) to pure Python.

Responsibilities:

- Locate the on-disk OAuth tokens file used by the Copilot CLI's Teams
  MCP client under ``~/.copilot/mcp-oauth-config/`` by matching
  ``serverUrl`` against ``mcp_TeamsServerV1``.
- Proactively refresh the bearer a configurable window before it
  expires (default 10 minutes) and write the new tokens back using
  camelCase keys (``accessToken``/``refreshToken``/``expiresAt``).
- Build a JSON-RPC ``tools/call`` envelope, POST it directly to the MCP
  server, and robustly parse the triple-nested SSE-formatted response
  so callers never see a silently-empty result on parse failure.

Only the Python standard library is used: ``urllib.request``, ``json``,
``pathlib``, ``time``, ``dataclasses``. No third-party deps, keeping
this consistent with the rest of the ``general-ops`` plugin.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_TEAMS_MCP_URL_MARKER = "mcp_TeamsServerV1"
_JSONRPC_MARKER = re.compile(r'"jsonrpc"\s*:\s*"2\.0"')
_DEFAULT_SKEW_SECONDS = 600  # refresh within 10 min of expiry


@dataclass
class TransportResult:
    """Structured outcome of a ``direct_http_call``.

    ``success`` is ``False`` whenever anything went wrong (HTTP error,
    SSE parse failure, token refresh failure) — callers MUST check
    ``success`` before trusting ``data``.
    """

    success: bool
    error: Optional[str] = None
    data: Any = None


# --------------------------------------------------------------------------- #
# Config / token-file discovery
# --------------------------------------------------------------------------- #


def _default_config_dir() -> Path:
    return Path.home() / ".copilot" / "mcp-oauth-config"


def find_teams_mcp_config(
    base_dir: Optional[Path] = None,
) -> Optional[Tuple[Path, Path, str]]:
    """Scan ``base_dir`` for the Teams MCP config file.

    Returns ``(config_path, tokens_path, server_url)`` for the first
    ``<name>.json`` whose ``serverUrl`` contains ``mcp_TeamsServerV1``,
    or ``None`` if nothing matches (or the directory does not exist).

    The tokens path is ``<name>.tokens.json`` in the same directory —
    it may or may not exist yet; callers should handle both.
    """
    directory = Path(base_dir) if base_dir is not None else _default_config_dir()
    if not directory.exists() or not directory.is_dir():
        return None

    for candidate in sorted(directory.glob("*.json")):
        if candidate.name.endswith(".tokens.json"):
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        server_url = str(data.get("serverUrl") or "")
        if _TEAMS_MCP_URL_MARKER in server_url:
            tokens_path = candidate.with_name(candidate.stem + ".tokens.json")
            return candidate, tokens_path, server_url
    return None


# --------------------------------------------------------------------------- #
# Agency-hosted Teams MCP discovery (local loopback proxy)
# --------------------------------------------------------------------------- #


@dataclass
class AgencyTeamsProxy:
    """Discovered agency-hosted Teams MCP proxy.

    Agency-managed Copilot CLI sessions (the ``copilot.exe`` launcher
    passes ``--additional-mcp-config @<path>``) spawn a local HTTP proxy
    that forwards JSON-RPC ``tools/call`` requests to the upstream Teams
    MCP server and performs bearer-token auth internally. The proxy
    listens on ``127.0.0.1:<port>`` and accepts **unauthenticated**
    POSTs — we simply hit it without an ``Authorization`` header.

    Caveat: the proxy exposes tool names **without** the ``teams-``
    MCP-tool prefix. When building a JSON-RPC call we strip the prefix
    so the forwarded tool name (e.g. ``ListChannelMessageReplies``)
    matches the upstream server's registration.
    """

    url: str  # e.g. "http://127.0.0.1:55244"
    source_path: Path  # the discovered --additional-mcp-config JSON file


def _scan_agency_mcp_config(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    servers = (data or {}).get("mcpServers") or {}
    entry = servers.get("teams")
    if not isinstance(entry, dict):
        return None
    if str(entry.get("type") or "").lower() != "http":
        return None
    url = str(entry.get("url") or "").rstrip("/")
    # Only trust loopback — we skip auth on this channel.
    if not url.startswith("http://127.0.0.1:") and not url.startswith("http://localhost:"):
        return None
    return url


def find_agency_teams_proxy() -> Optional[AgencyTeamsProxy]:
    """Locate the agency-hosted Teams MCP loopback proxy, or ``None``.

    Scans ``%TEMP%\\copilot-mcp-*.json`` (the launcher writes one of
    these per CLI session) for an ``mcpServers.teams`` entry whose
    ``url`` is a loopback HTTP endpoint. Returns the first match —
    multiple files can exist from prior sessions; the newest mtime
    is picked so stale entries don't shadow the active session.
    """
    import os  # local import: keeps module import-time tiny
    temp_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
    if not temp_dir.exists():
        return None
    candidates = sorted(
        temp_dir.glob("copilot-mcp-*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    for candidate in candidates:
        url = _scan_agency_mcp_config(candidate)
        if url:
            return AgencyTeamsProxy(url=url, source_path=candidate)
    return None


def _strip_teams_prefix(tool_name: str) -> str:
    """Agency proxy expects unprefixed tool names (see AgencyTeamsProxy)."""
    if tool_name.startswith("teams-"):
        return tool_name[len("teams-"):]
    return tool_name


# --------------------------------------------------------------------------- #
# Token refresh
# --------------------------------------------------------------------------- #


def _default_now() -> float:
    return time.time()


def _default_refresh_transport(url: str, form_body: bytes) -> dict:
    """Default network call for the OAuth refresh. Mocked in tests."""
    req = urllib.request.Request(
        url,
        data=form_body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_tokens_atomic(path: Path, tokens: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    tmp.replace(path)


def ensure_fresh_token(
    tokens_path: Path,
    skew_seconds: int = _DEFAULT_SKEW_SECONDS,
    now: Optional[float] = None,
    transport: Optional[Callable[[str, bytes], dict]] = None,
    config_path: Optional[Path] = None,
) -> dict:
    """Return a fresh access token, refreshing it on disk if near expiry.

    Parameters
    ----------
    tokens_path :
        Path to ``<name>.tokens.json``. Must exist and contain
        camelCase ``accessToken`` / ``refreshToken`` / ``expiresAt``
        (Unix seconds).
    skew_seconds :
        If ``expiresAt - now <= skew_seconds`` a refresh is fired.
    now :
        Injectable clock for tests (seconds since epoch).
    transport :
        Injectable HTTP call for the refresh. Signature
        ``(url, form_body_bytes) -> dict`` where the returned dict is
        the JSON body of the token endpoint response
        (``access_token`` / ``refresh_token`` / ``expires_in``).
    config_path :
        Optional path to the sibling ``<name>.json`` config so we can
        read ``clientId`` from it. Defaults to the tokens path with
        the ``.tokens.json`` suffix replaced by ``.json``.

    Returns
    -------
    dict with keys ``accessToken``, ``refreshToken``, ``expiresAt``,
    ``refreshed`` (bool). On refresh, the tokens file is rewritten
    atomically with the same camelCase shape as before.
    """
    tokens_path = Path(tokens_path)
    current_now = _default_now() if now is None else float(now)
    http = transport or _default_refresh_transport

    tokens = _read_json(tokens_path)
    access_token = tokens.get("accessToken")
    refresh_token = tokens.get("refreshToken")
    expires_at = tokens.get("expiresAt")
    scope = tokens.get("scope")

    try:
        expires_at_f = float(expires_at) if expires_at is not None else 0.0
    except (TypeError, ValueError):
        expires_at_f = 0.0

    if expires_at_f - current_now > skew_seconds:
        return {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at_f if expires_at is not None else expires_at,
            "refreshed": False,
        }

    # Need a refresh. Pull client_id + scope from the sibling config.
    if config_path is not None:
        cfg_path = Path(config_path)
    else:
        cfg_path = tokens_path.with_name(
            tokens_path.name.replace(".tokens.json", ".json")
        )
    client_id: Optional[str] = None
    if cfg_path.exists():
        try:
            cfg = _read_json(cfg_path)
            client_id = cfg.get("clientId") or cfg.get("client_id")
            if not scope:
                scope = cfg.get("scope")
        except (OSError, json.JSONDecodeError):
            client_id = None
    if client_id is None:
        client_id = tokens.get("clientId") or tokens.get("client_id")

    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token or "",
        "client_id": client_id or "",
    }
    if scope:
        form["scope"] = scope if isinstance(scope, str) else " ".join(scope)
    body = urllib.parse.urlencode(form).encode("utf-8")

    resp = http(_TOKEN_URL, body)
    new_access = resp.get("access_token")
    new_refresh = resp.get("refresh_token") or refresh_token
    expires_in = resp.get("expires_in") or 0
    try:
        expires_in_i = int(expires_in)
    except (TypeError, ValueError):
        expires_in_i = 0
    new_expires_at = int(current_now) + expires_in_i

    # Preserve any extra fields (scope, tenantId, ...) the CLI left behind.
    tokens["accessToken"] = new_access
    tokens["refreshToken"] = new_refresh
    tokens["expiresAt"] = new_expires_at
    if scope and "scope" not in tokens:
        tokens["scope"] = scope
    _write_tokens_atomic(tokens_path, tokens)

    return {
        "accessToken": new_access,
        "refreshToken": new_refresh,
        "expiresAt": new_expires_at,
        "refreshed": True,
    }


# --------------------------------------------------------------------------- #
# SSE parsing
# --------------------------------------------------------------------------- #


def parse_sse_response(raw: str) -> Optional[dict]:
    """Parse an MCP server Server-Sent-Events response body.

    The MCP server returns a body shaped like::

        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{
            "content":[{"type":"text","text":"<JSON-ENCODED-WRAPPER>"}]}}

    …where ``text`` is a JSON **string** whose decoded value is a
    wrapper ``{"message": "...", "response": "<JSON-ENCODED-GRAPH>"}``
    and ``response`` is again a JSON-encoded Graph payload. Three
    levels of ``json.loads`` are therefore required.

    Returns the innermost Graph payload (a dict) on success, or
    ``None`` on any failure — callers MUST treat ``None`` as an error,
    never as "no messages".
    """
    if not raw or not isinstance(raw, str):
        return None

    # Split on `event: message` and pick the last block that looks like
    # a JSON-RPC envelope. Matching the envelope strictly avoids false
    # positives when user-visible reply content mentions "result".
    blocks = re.split(r"event:\s*message\r?\n", raw)
    result_block: Optional[str] = None
    for block in blocks:
        if _JSONRPC_MARKER.search(block):
            result_block = block  # keep the last matching block
    if result_block is None:
        return None

    data_lines = []
    for line in result_block.splitlines():
        if line.startswith("data: "):
            data_lines.append(line[len("data: "):])
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):])
    json_str = "".join(data_lines).strip()
    if len(json_str) < 10:
        return None

    try:
        envelope = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(envelope, dict):
        return None

    # Level 2: result.content[0].text is itself a JSON string.
    try:
        text = envelope["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    try:
        wrapper = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(wrapper, dict):
        return None

    # Level 3: response (if present) is itself a JSON string.
    response = wrapper.get("response")
    if response is None:
        # Some tool responses inline the Graph payload already, or
        # skip the wrapper entirely. Return what we have so callers
        # can still read it — but only if it looks like a dict.
        return wrapper
    if isinstance(response, dict):
        return response
    try:
        graph = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(graph, dict):
        return None
    return graph


# --------------------------------------------------------------------------- #
# Direct HTTP call
# --------------------------------------------------------------------------- #


def _default_http_transport(
    url: str, body: bytes, headers: dict, timeout: int = 60
) -> str:
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def direct_http_call(
    tool_name: str,
    args: dict,
    *,
    tokens_path: Optional[Path] = None,
    config: Optional[Tuple[Path, Path, str]] = None,
    now: Optional[float] = None,
    refresh_transport: Optional[Callable[[str, bytes], dict]] = None,
    http_transport: Optional[Callable[[str, bytes, dict], str]] = None,
) -> TransportResult:
    """POST a JSON-RPC ``tools/call`` to the Teams MCP server directly.

    Resolves the tokens + server URL from ``config`` (a tuple as
    returned by :func:`find_teams_mcp_config`) when provided; otherwise
    calls :func:`find_teams_mcp_config` itself. Calls
    :func:`ensure_fresh_token` before the HTTP call so the bearer is
    guaranteed to be valid for at least ``skew_seconds``.
    """
    if config is None:
        found = find_teams_mcp_config()
        if found is None:
            return TransportResult(False, "no-teams-mcp-config", None)
        config = found
    cfg_path, tok_path, server_url = config
    tokens_path = Path(tokens_path) if tokens_path is not None else tok_path

    try:
        fresh = ensure_fresh_token(
            tokens_path,
            now=now,
            transport=refresh_transport,
            config_path=cfg_path,
        )
    except Exception as exc:  # noqa: BLE001 — bubble up as structured error
        return TransportResult(False, f"token-refresh-failed: {exc!r}", None)

    access_token = fresh.get("accessToken")
    if not access_token:
        return TransportResult(False, "no-access-token", None)

    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    http = http_transport or _default_http_transport
    try:
        raw = http(server_url, body, headers)
    except Exception as exc:  # noqa: BLE001
        return TransportResult(False, f"http-error: {exc!r}", None)

    parsed = parse_sse_response(raw)
    if parsed is None:
        return TransportResult(False, "sse-parse-failed", None)
    return TransportResult(True, None, parsed)


def build_http_fallback(
    tool_name: str,
    args: dict,
    *,
    config: Optional[Tuple[Path, Path, str]] = None,
    proxy: Optional[AgencyTeamsProxy] = None,
) -> Optional[dict]:
    """Return an ``http_fallback`` envelope sibling, or ``None``.

    Two shapes depending on the discovered transport:

    * **OAuth (user-authorised disk config)** — has ``auth: "bearer"`` and
      the agent is expected to attach ``Authorization: Bearer <access_token>``
      from the sibling ``*.tokens.json`` file before POSTing::

          {"url": "<serverUrl>",
           "auth": "bearer",
           "tokens_path": "<...>.tokens.json",
           "body": {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "teams-<Verb>", "arguments": <args>}}}

    * **Agency proxy (local loopback)** — has ``auth: "none"`` and the
      agent POSTs without an ``Authorization`` header. The tool name is
      stripped of its ``teams-`` prefix because the proxy forwards to a
      server that registers unprefixed names::

          {"url": "http://127.0.0.1:<port>",
           "auth": "none",
           "body": {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "<Verb>", "arguments": <args>}}}

    If both ``config`` and ``proxy`` are omitted the function probes both
    in order (disk config first, then agency proxy). Returns ``None`` if
    neither is present.
    """
    if config is None and proxy is None:
        found_cfg = find_teams_mcp_config()
        if found_cfg is not None:
            config = found_cfg
        else:
            proxy = find_agency_teams_proxy()

    if config is not None:
        _, tokens_path, server_url = config
        return {
            "url": server_url,
            "auth": "bearer",
            "tokens_path": str(tokens_path),
            "body": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            },
        }

    if proxy is not None:
        return {
            "url": proxy.url,
            "auth": "none",
            "body": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": _strip_teams_prefix(tool_name),
                    "arguments": args,
                },
            },
        }

    return None


# --------------------------------------------------------------------------- #
# Long-poll for idle Teams replies
# --------------------------------------------------------------------------- #


def _proxy_http_call(
    proxy: AgencyTeamsProxy,
    tool_name: str,
    args: dict,
    http_transport: Optional[Callable[[str, bytes, dict], str]] = None,
) -> TransportResult:
    """POST a JSON-RPC ``tools/call`` to the agency loopback proxy.

    Mirrors :func:`direct_http_call` but without auth and with the
    ``teams-`` prefix stripped from ``tool_name``. Used by
    :func:`long_poll_replies` when the agency proxy transport is active.
    """
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": _strip_teams_prefix(tool_name),
                "arguments": args,
            },
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    http = http_transport or _default_http_transport
    try:
        raw = http(proxy.url, body, headers)
    except Exception as exc:  # noqa: BLE001
        return TransportResult(False, f"http-error: {exc!r}", None)
    parsed = parse_sse_response(raw)
    if parsed is None:
        # Proxy may return raw JSON rather than SSE — try that too.
        try:
            return TransportResult(True, None, json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            return TransportResult(False, "proxy-parse-failed", None)
    return TransportResult(True, None, parsed)


def _extract_replies(payload: Any) -> list:
    """Pull a reply list out of whatever shape the MCP/proxy returned.

    The Graph payload is normally ``{"value": [...]}``; the MCP wrapper
    sometimes re-keys it as ``{"replies": [...]}``. Accept both and any
    bare list for robustness. Returns ``[]`` on any shape mismatch.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("replies", "messages", "value"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []


def _reply_is_new(
    reply: dict, after_iso: Optional[str], own_ids: set
) -> bool:
    """True if ``reply`` should unblock the long-poll (past ``after_iso``
    timestamp and not in ``own_ids``). Replies with malformed
    ``createdDateTime`` are considered new (fail-open: better a spurious
    wake than a missed message)."""
    rid = str(reply.get("id") or "")
    if rid in own_ids:
        return False
    if not after_iso:
        return True
    ts = str(reply.get("createdDateTime") or reply.get("timestamp") or "")
    if not ts:
        return True
    try:
        ts_dt = _parse_iso_z(ts)
        after_dt = _parse_iso_z(after_iso)
    except Exception:  # noqa: BLE001
        return True
    if ts_dt is None or after_dt is None:
        return True
    return ts_dt > after_dt


def _parse_iso_z(value: str):
    """Tolerant ISO-8601 parser accepting the ``Z`` suffix."""
    import datetime as _dt

    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def long_poll_replies(
    team_id: str,
    channel_id: str,
    message_id: str,
    after_iso: Optional[str],
    own_ids: Optional[set] = None,
    *,
    timeout_seconds: int = 600,
    internal_interval: int = 5,
    heartbeat_interval: int = 60,
    max_replies: int = 50,
    config: Optional[Tuple[Path, Path, str]] = None,
    proxy: Optional[AgencyTeamsProxy] = None,
    now: Optional[Callable[[], float]] = None,
    sleep: Optional[Callable[[float], None]] = None,
    stderr=None,
) -> Tuple[list, bool]:
    """Block until a new Teams reply arrives, a cancellation is signalled,
    or ``timeout_seconds`` elapse.

    This is the core of the long-poll fix (see
    ``docs/LongPollImplementation-Measurements.md``): one subprocess
    invocation absorbs what was previously dozens of short-poll LLM
    turns. Graph does not expose a native long-poll endpoint, so we
    issue short GETs in a tight internal loop and return the first
    batch that contains any reply past ``after_iso`` and not in
    ``own_ids``.

    Parameters
    ----------
    team_id, channel_id, message_id :
        Identifiers for the Teams channel thread we're polling under.
    after_iso :
        Upper-bound timestamp of "already seen" replies (usually the
        last activity timestamp). Anything with
        ``createdDateTime > after_iso`` counts as new. ``None``
        disables the timestamp filter (rare; the ``own_ids`` set then
        does all the work).
    own_ids :
        Set of reply ids we posted ourselves — never wake for them.
    timeout_seconds :
        Ceiling on the total blocking wait. Default ``600`` (10 min) —
        chosen to stay comfortably inside the bearer's 60+ min
        lifetime so we never straddle a token refresh.
    internal_interval :
        Seconds between internal GETs. Default 5.
    heartbeat_interval :
        Seconds between stderr heartbeats. Default 60. Heartbeats
        mitigate Issue 5 — the Copilot CLI killing a silent
        subprocess. A single line ``[long-poll] alive t=<sec>`` is
        written.
    max_replies :
        Forwarded as ``maxReplies`` to Graph. Capped at 50 by the MCP
        server.
    config, proxy :
        Optional pre-discovered transport descriptors. If both
        omitted, this function calls ``find_teams_mcp_config()`` then
        ``find_agency_teams_proxy()``.
    now, sleep, stderr :
        Injectable clock / sleep / stream for tests.

    Returns
    -------
    (replies, timed_out) :
        ``replies`` is the list of chatMessage dicts as Graph returned
        them — caller normalises. Empty when the timeout elapsed with
        nothing new. ``timed_out`` is ``True`` when no new reply was
        seen within ``timeout_seconds``.
    """
    import sys as _sys

    _now = now or time.monotonic
    _sleep = sleep or time.sleep
    _stderr = stderr or _sys.stderr
    _own = set(own_ids or ())

    if config is None and proxy is None:
        cfg = find_teams_mcp_config()
        if cfg is not None:
            config = cfg
        else:
            proxy = find_agency_teams_proxy()
    if config is None and proxy is None:
        # No transport → can't long-poll. Signal timeout immediately.
        return [], True

    # Proactive token refresh at the top (oauth only). We don't refresh
    # inside the loop because timeout_seconds (10 min) is smaller than
    # the skew we refresh at (10 min before expiry), so one refresh at
    # the top covers the whole window.
    if config is not None:
        cfg_path, tokens_path, _srv = config
        if tokens_path.exists():
            try:
                ensure_fresh_token(tokens_path, config_path=cfg_path)
            except Exception as exc:  # noqa: BLE001
                _stderr.write(
                    f"[long-poll] token refresh failed: {exc!r} — continuing\n"
                )

    args = {
        "teamId": team_id,
        "channelId": channel_id,
        "messageId": message_id,
        "maxReplies": max_replies,
    }

    start = _now()
    last_heartbeat = start

    while True:
        elapsed = _now() - start
        if elapsed >= timeout_seconds:
            return [], True

        # Fetch.
        if config is not None:
            result = direct_http_call(
                "teams-ListChannelMessageReplies", args, config=config
            )
        else:
            result = _proxy_http_call(
                proxy, "teams-ListChannelMessageReplies", args
            )

        if result.success and result.data is not None:
            replies = _extract_replies(result.data)
            new = [r for r in replies if _reply_is_new(r, after_iso, _own)]
            if new:
                return replies, False
        else:
            # Log once per failure so the caller can trace silent errors.
            _stderr.write(
                f"[long-poll] fetch failed: {result.error!r} — will retry\n"
            )

        # Heartbeat.
        now_t = _now()
        if now_t - last_heartbeat >= heartbeat_interval:
            _stderr.write(f"[long-poll] alive t={int(now_t - start)}\n")
            _stderr.flush()
            last_heartbeat = now_t

        # Sleep but respect the remaining budget.
        remaining = timeout_seconds - (now_t - start)
        if remaining <= 0:
            return [], True
        _sleep(min(internal_interval, max(remaining, 0)))
