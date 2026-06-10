"""Phase 3: Envelope Contract — every steady-state envelope carries
``next_step`` so the agent never reads a non-terminal envelope as terminal.

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "lib"))

import state as _state  # noqa: E402
import activate  # noqa: E402
import ask  # noqa: E402
import poll  # noqa: E402
import transport_router as _tr  # noqa: E402


def _isolate(testcase: unittest.TestCase) -> None:
    name = "teams-remote-next-" + uuid.uuid4().hex[:8]
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    testcase.addCleanup(_state.set_session_root, None)
    _state.set_session_root(Path(tmp.name))
    prior = os.environ.pop(_state.SESSION_ID_ENV, None)
    if prior is not None:
        testcase.addCleanup(
            os.environ.__setitem__, _state.SESSION_ID_ENV, prior
        )
    orig_resolve = _tr.resolve_transport
    _tr.resolve_transport = lambda: None
    testcase.addCleanup(setattr, _tr, "resolve_transport", orig_resolve)
    _state.set_subsystem(name)


class _Capture:
    def __init__(self, module) -> None:
        self.module = module
        self.buf = io.StringIO()
        self._orig = None

    def __enter__(self):
        self._orig = self.module._emit
        self.module._emit = lambda env: self.buf.write(json.dumps(env) + "\n")
        return self

    def __exit__(self, *a):
        self.module._emit = self._orig

    def payloads(self):
        return [json.loads(l) for l in self.buf.getvalue().splitlines() if l.strip()]


def _seed_pending(session_id: str) -> dict:
    """Create a pending activation file so cmd_finalize has data to load."""
    pending = {
        "session_start_time": "2026-01-01T00:00:00Z",
        "team_id": "team-1",
        "channel_id": "chan-1",
        "team_name": "T",
        "channel_name": "C",
        "correlation_token": "tok-1",
        "poll_interval": 30,
        "timeout_seconds": 600,
        "workspace_path": "C:/tmp",
        "user_display": "Tester",
        "user_mention_id": "",
    }
    activate._save_pending(session_id, pending)
    return pending


class ActivateReadyEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def test_finalize_ready_envelope_has_next_and_next_step(self):
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_pending(sid)
        ns = argparse.Namespace(
            step="finalize",
            session_id=sid,
            root_message_id="m-root-1",
            created_iso="2026-01-01T00:00:01Z",
        )
        with _Capture(activate) as cap:
            rc = activate.cmd_finalize(ns)
        self.assertEqual(rc, 0)
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "ready")
        self.assertEqual(env["next_step"], "poll_idle")
        self.assertIn("next", env)
        self.assertIn("idle", env["next"])


class AskReadyEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def test_finalize_ready_envelope_has_next_step_poll_input(self):
        sid = "sess-" + uuid.uuid4().hex[:8]
        # Seed a minimal active state so cmd_finalize loads something.
        st = {
            "schema_version": _state.SCHEMA_VERSION if hasattr(_state, "SCHEMA_VERSION") else 1,
            "session_id": sid,
            "team_id": "t",
            "channel_id": "c",
            "root_message_id": "r",
            "correlation_token": "tok",
            "poll_interval": 30,
            "timeout_seconds": 600,
            "own_message_ids": [],
            "pending_question": {
                "question": "?",
                "asked_iso": "2026-01-01T00:00:00Z",
                "correlation_token": "tok",
            },
        }
        _state.save_state(sid, st)
        ns = argparse.Namespace(
            step="finalize",
            session_id=sid,
            message_id="m-q-1",
            created_iso="2026-01-01T00:00:01Z",
        )
        with _Capture(ask) as cap:
            rc = ask.cmd_finalize(ns)
        self.assertEqual(rc, 0)
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "ready")
        self.assertEqual(env["next_step"], "poll_input")


class PollContinueEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def _seed_idle_state(self, sid: str) -> None:
        st = {
            "schema_version": _state.SCHEMA_VERSION,
            "session_id": sid,
            "team_id": "t",
            "channel_id": "c",
            "root_message_id": "r",
            "transport": "mcp",
            "poll_interval": 30,
            "timeout_seconds": 600,
            "last_processed_id": "0",
            "last_idle_heartbeat_time": "2026-01-01T00:00:00Z",
            "own_message_ids": [],
            "seen_reply_ids": "",
            "user_display": "Tester",
            "user_mention_id": "",
            "session_start_time": "2026-01-01T00:00:00Z",
        }
        _state.save_state(sid, st)

    def test_idle_continue_envelope_has_next_step_tick(self):
        sid = "sess-" + uuid.uuid4().hex[:8]
        self._seed_idle_state(sid)
        ns = argparse.Namespace(
            step="process",
            mode="idle",
            session_id=sid,
            replies_json="[]",
            message_id=None,
            created_iso=None,
            kind="other",
            with_sleep=False,
            long_poll=False,
            code=None,
            user_id=None,
            user_display=None,
        )
        state = _state.load_state(sid)
        with _Capture(poll) as cap:
            rc = poll.cmd_process_idle(ns, state, [], None)
        self.assertEqual(rc, 0)
        env = cap.payloads()[-1]
        # Either "continue" (no heartbeat due) or "heartbeat" — both must
        # carry next_step: "tick".
        self.assertIn(env["action"], ("continue", "heartbeat"))
        self.assertEqual(env["next_step"], "tick")


if __name__ == "__main__":
    unittest.main()
