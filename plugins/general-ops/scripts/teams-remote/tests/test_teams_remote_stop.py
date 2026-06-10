"""Unit tests for ``scripts/hooks/teams_remote_stop.py`` (Stop hook).

Verifies the session-scoped guard added to fix cross-session contamination:
the hook is registered globally (no per-session matcher in the hook schema),
so it fires on every CLI session's Stop event. It must only emit a
``decision: "block"`` when the firing session IS the away-mode session.

Mirrors the test patterns in ``test_poll.py`` (isolated subsystem, no
real state-dir collisions).

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Make ``state`` importable from ``../../lib`` and ``teams_remote_stop``
# importable from ``../../hooks``.
sys.path.insert(0, str(HERE.parent.parent / "lib"))
sys.path.insert(0, str(HERE.parent.parent / "hooks"))

import state as _state  # noqa: E402
import teams_remote_stop as hook  # noqa: E402


def _isolate(testcase: unittest.TestCase) -> str:
    """Per-test isolation: redirect session_root to a tmp dir and pin a
    unique subsystem. Cleans up on test teardown. Also clears the
    ``COPILOT_AGENT_SESSION_ID`` env var so tests deterministically use
    their stdin payload as the resolution source unless they explicitly
    set the env var via :func:`_set_env_session_id`."""
    name = "teams-remote-stop-test-" + uuid.uuid4().hex[:8]
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    testcase.addCleanup(_state.set_session_root, None)
    _state.set_session_root(Path(tmp.name))
    _state.set_subsystem(name)

    prior = os.environ.pop(_state.SESSION_ID_ENV, None)
    if prior is not None:
        testcase.addCleanup(os.environ.__setitem__, _state.SESSION_ID_ENV, prior)
    return name


def _set_env_session_id(testcase: unittest.TestCase, value: str) -> None:
    prior = os.environ.get(_state.SESSION_ID_ENV)
    os.environ[_state.SESSION_ID_ENV] = value
    if prior is None:
        testcase.addCleanup(os.environ.pop, _state.SESSION_ID_ENV, None)
    else:
        testcase.addCleanup(os.environ.__setitem__, _state.SESSION_ID_ENV, prior)


def _seed_state(session_id: str, *, away: bool) -> None:
    _state.save_state(session_id, {
        "schema_version": _state.SCHEMA_VERSION,
        "session_id": session_id,
        "team_id": "team-guid",
        "channel_id": "channel-thread",
        "root_message_id": "root-msg-id",
        "correlation_token": "corr-token",
        "poll_interval": 10,
        "timeout_seconds": 600,
        "away_mode": away,
        "transport": "mcp",
        "last_processed_id": "0",
        "seen_reply_ids": "",
        "own_message_ids": [],
        "message_count": 0,
    })


class _CapturedIO:
    """Replace stdin/stdout with in-memory streams for a single hook run."""

    def __init__(self, stdin_payload: str) -> None:
        self._stdin_payload = stdin_payload
        self._orig_stdin = None
        self._orig_stdout = None
        self.stdout_buf = io.StringIO()

    def __enter__(self):
        self._orig_stdin = sys.stdin
        self._orig_stdout = sys.stdout
        sys.stdin = io.StringIO(self._stdin_payload)
        sys.stdout = self.stdout_buf
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        sys.stdin = self._orig_stdin
        sys.stdout = self._orig_stdout

    def stdout_text(self) -> str:
        return self.stdout_buf.getvalue()


class StopHookSessionIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def _run_with(self, stdin_payload: str) -> str:
        with _CapturedIO(stdin_payload) as cap:
            rc = hook.main()
        self.assertEqual(rc, 0, "hook must always exit 0")
        return cap.stdout_text()

    # ---- Acceptance criteria from the plan ------------------------------------

    def test_foreign_session_is_silent_noop(self) -> None:
        """Plan AC #1: stdin session_id=AAAA, away state for BBBB → empty stdout."""
        _seed_state("BBBB", away=True)
        out = self._run_with(json.dumps({"session_id": "AAAA"}))
        self.assertEqual(out, "")

    def test_own_session_blocks(self) -> None:
        """Plan AC #2: stdin session_id=BBBB, away state for BBBB → block referencing BBBB."""
        _seed_state("BBBB", away=True)
        out = self._run_with(json.dumps({"session_id": "BBBB"}))
        body = json.loads(out)
        self.assertEqual(body["decision"], "block")
        self.assertIn("BBBB", body["reason"])

    def test_no_away_session_silent_noop(self) -> None:
        """Plan AC #3: no state at all → empty stdout."""
        out = self._run_with(json.dumps({"session_id": "AAAA"}))
        self.assertEqual(out, "")

    def test_empty_stdin_silent_noop(self) -> None:
        """Plan AC #4: empty payload, BBBB is away → fail-open, no block."""
        _seed_state("BBBB", away=True)
        out = self._run_with(json.dumps({}))
        self.assertEqual(out, "")

    def test_malformed_stdin_silent_noop(self) -> None:
        """Plan AC #4: garbled stdin, BBBB is away → fail-open, no block."""
        _seed_state("BBBB", away=True)
        out = self._run_with("not json{")
        self.assertEqual(out, "")

    # ---- Extra coverage --------------------------------------------------------

    def test_away_false_does_not_block_self(self) -> None:
        """A session that ran teams-remote but ended away mode must not block itself."""
        _seed_state("CCCC", away=False)
        out = self._run_with(json.dumps({"session_id": "CCCC"}))
        self.assertEqual(out, "")

    # ---- Env-var resolver wiring (v1.9.0) -------------------------------------

    def test_env_var_wins_over_payload(self) -> None:
        """Plan AC: env=AAA and payload session_id=BBB → hook reads state for AAA."""
        _seed_state("AAA", away=True)
        _seed_state("BBB", away=True)
        _set_env_session_id(self, "AAA")
        out = self._run_with(json.dumps({"session_id": "BBB"}))
        body = json.loads(out)
        self.assertEqual(body["decision"], "block")
        # Block reason references the env-resolved id, not the payload one.
        self.assertIn("AAA", body["reason"])
        self.assertNotIn("BBB", body["reason"])

    def test_env_unset_falls_back_to_payload(self) -> None:
        """Plan AC: env unset, payload session_id=BBB → hook loads state for BBB."""
        _seed_state("BBB", away=True)
        # _isolate() already clears the env var.
        out = self._run_with(json.dumps({"session_id": "BBB"}))
        body = json.loads(out)
        self.assertEqual(body["decision"], "block")
        self.assertIn("BBB", body["reason"])


if __name__ == "__main__":
    unittest.main()
