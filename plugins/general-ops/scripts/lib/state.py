"""State & pending-queue helpers for general-ops skills (teams-remote etc.).

**Storage layout (v1.8.0+):**

State lives **per-session** under the Copilot CLI session-state directory::

    ~/.copilot/session-state/<session-id>/plugins/general-ops/<subsystem>/
        state.json              # the per-session state document
        pending.json            # outbound post queue (teams-remote)
        activate-pending.json   # mid-flight activate handshake (teams-remote)

This replaces the pre-1.8 flat layout under ``%TEMP%/general-ops/<subsystem>/``
which keyed files by ``<session-id>.json``. The old layout made cross-session
hooks dangerous — a glob over the state dir could see other sessions' files.
With per-session sub-dirs that bug is impossible by construction: the Stop
hook resolves its directory from its own ``session_id`` and never touches
sibling sessions.

The ``hook-error.log`` is intentionally **NOT** session-scoped: hook crashes
that occur before we can identify a session must still log somewhere. It
lives at ``<tempdir>/general-ops/hook-error.log``.

Test override: set ``COPILOT_SESSION_ROOT`` env var (or call
``set_session_root(path)``) to redirect everything below ``session-state/``
into a tmp directory.

**Session-id resolution (v1.9.0+):**

Production source of truth for the per-session GUID is the env var
``COPILOT_AGENT_SESSION_ID`` (set by the Copilot CLI on its own process —
per-process, multi-session-safe). All entrypoint scripts and the Stop hook
must call :func:`resolve_session_id` rather than reading raw inputs. The
function is polymorphic in caller context — it accepts either an
``argparse.Namespace`` (CLI scripts) or a ``dict`` stdin payload (the Stop
hook). The literal placeholder ``"<SID>"`` is silently ignored on the args
path so stale agent prompts that pass it verbatim are harmless.

Resolution order:
  1. ``env["COPILOT_AGENT_SESSION_ID"]`` if non-empty.
  2. ``args.session_id`` if provided, non-empty, and not the literal ``"<SID>"``.
  3. ``stdin_payload["session_id"]`` if provided and non-empty.
  4. ``sys.exit(2)`` with a stderr message.

Importing from entrypoints::

    HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(HERE.parent / "lib"))
    from state import load_state, save_state, resolve_session_id, ...
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 3
_DEFAULT_SUBSYSTEM = "teams-remote"
_SUBSYSTEM = _DEFAULT_SUBSYSTEM
_LOG_NAME = "hook-error.log"
_LOG_MAX_BYTES = 1 * 1024 * 1024  # 1 MB

SESSION_ROOT_ENV = "COPILOT_SESSION_ROOT"
SESSION_ID_ENV = "COPILOT_AGENT_SESSION_ID"
SESSION_ID_PLACEHOLDER = "<SID>"
_SESSION_ROOT_OVERRIDE: Optional[Path] = None

# State-file basenames (the parent dir already encodes the session id).
_STATE_BASENAME = "state.json"
_PENDING_BASENAME = "pending.json"
_ACTIVATE_PENDING_BASENAME = "activate-pending.json"


def set_subsystem(name: str) -> None:
    """Override the subsystem sub-directory used for state files.

    Call this once at import time from scripts that want their own
    isolated state directory (e.g. ``set_subsystem("teams-remote")``).
    Defaults to ``teams-remote`` so existing callers are unchanged.
    """
    global _SUBSYSTEM
    _SUBSYSTEM = name or _DEFAULT_SUBSYSTEM


def get_subsystem() -> str:
    return _SUBSYSTEM


def set_session_root(path: Optional[Path]) -> None:
    """Override the session-state root (tests). ``None`` clears the override."""
    global _SESSION_ROOT_OVERRIDE
    _SESSION_ROOT_OVERRIDE = Path(path) if path is not None else None


def get_session_root() -> Path:
    """Return the directory that holds per-session sub-directories.

    Resolution order:
      1. ``set_session_root()`` programmatic override (tests).
      2. ``COPILOT_SESSION_ROOT`` env var (tests / CI).
      3. ``~/.copilot/session-state`` (production default — matches the
         CLI's own session-state location).
    """
    if _SESSION_ROOT_OVERRIDE is not None:
        return _SESSION_ROOT_OVERRIDE
    env = os.environ.get(SESSION_ROOT_ENV)
    if env:
        return Path(env)
    return Path.home() / ".copilot" / "session-state"


def get_state_dir(session_id: str) -> Path:
    """Return (creating if needed) the per-session state directory.

    Layout: ``<session-root>/<session-id>/plugins/general-ops/<subsystem>/``.
    """
    if not session_id:
        raise ValueError("session_id is required")
    base = (
        get_session_root()
        / session_id
        / "plugins"
        / "general-ops"
        / _SUBSYSTEM
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_state_path(session_id: str) -> Path:
    """Return the state file path for ``session_id``."""
    return get_state_dir(session_id) / _STATE_BASENAME


def get_pending_path(session_id: str) -> Path:
    """Return the pending-post queue file path for ``session_id``."""
    return get_state_dir(session_id) / _PENDING_BASENAME


def get_activate_pending_path(session_id: str) -> Path:
    """Return the activate-handshake pending file path for ``session_id``."""
    return get_state_dir(session_id) / _ACTIVATE_PENDING_BASENAME


def get_log_dir() -> Path:
    """Machine-level log directory (NOT session-scoped).

    Hook crashes that fire before we can identify a session must still
    have somewhere to log, so this stays at ``<tempdir>/general-ops/``.
    """
    base = Path(tempfile.gettempdir()) / "general-ops"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_log_path() -> Path:
    """Return the shared hook-error.log path (machine-level, not session-scoped)."""
    return get_log_dir() / _LOG_NAME


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log_hook_error(message: str) -> None:
    """Append a single line to hook-error.log. Never raises."""
    try:
        path = get_log_path()
        line = f"[{_now_iso()}] {message}\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        # Last-ditch: swallow. Logging must never crash a hook.
        pass


def _atomic_write_text(final: Path, text: str) -> None:
    """Write `text` to `final` atomically via a sibling *.tmp and os.replace."""
    tmp = final.with_suffix(final.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, final)


def load_state(session_id: str) -> Optional[dict]:
    """Load and return the state dict, or ``None`` if missing / invalid / wrong schema.

    Returns None if:
      - The state file does not exist.
      - The file is not valid JSON (a mid-write race, truncation, etc.).
      - ``schema_version`` is missing or != SCHEMA_VERSION.
    Logs a one-line warning on schema mismatch or decode errors.
    """
    path = get_state_path(session_id)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        log_hook_error(f"[load_state] {session_id[:8]} decode error: {exc}")
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        log_hook_error(
            f"[load_state] {session_id[:8]} schema mismatch "
            f"(got {data.get('schema_version') if isinstance(data, dict) else type(data).__name__})"
        )
        return None
    return data


def save_state(session_id: str, state: dict) -> None:
    """Serialise and atomically write the state dict."""
    path = get_state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(state, indent=2))


def delete_state(session_id: str) -> None:
    """Remove the state file if present. Idempotent.

    The empty per-session sub-directory is left behind for the CLI's own
    session-state cleanup to handle (it owns the parent).
    """
    try:
        get_state_path(session_id).unlink(missing_ok=True)
    except OSError as exc:
        log_hook_error(f"[delete_state] {session_id[:8]} {exc}")


def append_pending_post(session_id: str, entry: dict) -> None:
    """Atomically append an entry to the per-session pending-post queue.

    Entry shape: ``{"timestamp": ISO-UTC, "content_html": str, "source": str}``.
    """
    path = get_pending_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    queue: list = []
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                queue = parsed
        except (OSError, json.JSONDecodeError) as exc:
            log_hook_error(f"[append_pending_post] {session_id[:8]} queue reset: {exc}")
            queue = []
    queue.append(entry)
    _atomic_write_text(path, json.dumps(queue, indent=2))


def read_pending_queue(session_id: str) -> list:
    """Return the current pending queue as a list (empty if absent/invalid)."""
    path = get_pending_path(session_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def write_pending_queue(session_id: str, queue: list) -> None:
    """Atomically overwrite the pending queue file. Deletes file if queue is empty."""
    path = get_pending_path(session_id)
    if not queue:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(queue, indent=2))


def clear_pending_queue(session_id: str) -> None:
    """Remove the pending queue file if present."""
    try:
        get_pending_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


def rotate_log_if_needed() -> None:
    """Rotate hook-error.log at 1 MB. Never raises."""
    try:
        log = get_log_path()
        if log.exists() and log.stat().st_size > _LOG_MAX_BYTES:
            rotated = log.with_suffix(log.suffix + ".old")
            if rotated.exists():
                rotated.unlink()
            os.rename(log, rotated)
    except OSError:
        pass


def resolve_session_id(
    args=None,
    *,
    stdin_payload: Optional[dict] = None,
    env: Optional[dict] = None,
) -> str:
    """Return the session id with strategy A (env-var first).

    Production source of truth is the ``COPILOT_AGENT_SESSION_ID`` env var,
    set per-process by the Copilot CLI. This function is polymorphic in
    caller context:

    * Entrypoint scripts pass an ``argparse.Namespace`` as the first arg.
      ``args.session_id`` is treated as a *test/manual* fallback.
    * The Stop hook passes ``stdin_payload=<json-dict-from-stdin>``. Its
      ``session_id`` field is treated as a fallback when the env var is
      unset (e.g. older CLI builds).

    The literal placeholder ``"<SID>"`` from agent prompt templates is
    silently ignored on the args path.

    Resolution order:
      1. ``env[SESSION_ID_ENV]`` (default: ``os.environ``) if non-empty.
      2. ``args.session_id`` if non-empty and not the placeholder.
      3. ``stdin_payload["session_id"]`` if non-empty.
      4. ``sys.exit(2)`` with a stderr message.

    Both fallbacks may be combined — env wins over both, and args wins
    over payload.
    """
    source_env = env if env is not None else os.environ
    candidate = source_env.get(SESSION_ID_ENV)
    if candidate:
        return candidate

    if args is not None:
        arg_value = getattr(args, "session_id", None)
        if arg_value and arg_value != SESSION_ID_PLACEHOLDER:
            return arg_value

    if stdin_payload is not None and isinstance(stdin_payload, dict):
        payload_value = stdin_payload.get("session_id")
        if payload_value and isinstance(payload_value, str):
            return payload_value

    sys.stderr.write(
        "teams-remote: no session id (COPILOT_AGENT_SESSION_ID unset and no fallback)\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    # Tiny self-test: round-trip a dummy state dict.
    sid = "selftest-0000"
    save_state(sid, {"schema_version": SCHEMA_VERSION, "session_id": sid, "away_mode": True})
    loaded = load_state(sid)
    print(json.dumps(loaded, indent=2))
    delete_state(sid)
    sys.exit(0)
