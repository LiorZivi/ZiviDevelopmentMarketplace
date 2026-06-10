"""Phase 5: HTTP-fallback integration tests for activate/ask/end ``cmd_run``.

Verifies that each entrypoint:

* On ``transport == "mcp"``: emits ``mcp_call`` + ``http_fallback`` siblings.
* On ``transport == "http"``: promotes — strips ``mcp_call``/``mcp_args`` and
  leaves only ``http_fallback``.
* When no transport is discoverable: emits the ``mcp_call`` envelope without
  ``http_fallback`` (graceful degradation).

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
import end  # noqa: E402
import transport_router as _tr  # noqa: E402


_FAKE_FALLBACK = {
    "url": "https://example.invalid/mcp",
    "auth": "bearer",
    "tokens_path": "C:/fake/tokens.json",
    "body": {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "teams-Stub", "arguments": {}}},
}


def _isolate(testcase: unittest.TestCase, *, transport_descriptor=None) -> None:
    name = "teams-remote-tx-" + uuid.uuid4().hex[:8]
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
    _tr.resolve_transport = lambda: transport_descriptor
    testcase.addCleanup(setattr, _tr, "resolve_transport", orig_resolve)

    if transport_descriptor is not None:
        orig_build = _tr.build_http_fallback
        _tr.build_http_fallback = (
            lambda tool, args, **kw: dict(_FAKE_FALLBACK, body={
                **_FAKE_FALLBACK["body"],
                "params": {"name": tool, "arguments": args},
            })
        )
        testcase.addCleanup(setattr, _tr, "build_http_fallback", orig_build)

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


def _seed_active_state(sid: str, *, transport: str = "mcp") -> dict:
    st = {
        "schema_version": _state.SCHEMA_VERSION,
        "session_id": sid,
        "team_id": "team-1",
        "channel_id": "chan-1",
        "root_message_id": "root-1",
        "correlation_token": "tok-1",
        "poll_interval": 30,
        "timeout_seconds": 600,
        "away_mode": True,
        "transport": transport,
        "last_processed_id": "0",
        "seen_reply_ids": "",
        "own_message_ids": [],
        "message_count": 0,
        "user_mention_id": "",
        "user_display": "Tester",
        "session_start_time": "2026-01-01T00:00:00Z",
    }
    _state.save_state(sid, st)
    return st


# ---------------------------------------------------------------------------
# activate.py — only cmd_run issues an MCP call. State doesn't exist yet at
# that point, so transport is implicitly "mcp" on first activation.
# ---------------------------------------------------------------------------
class ActivateTransportTests(unittest.TestCase):
    def _args(self, sid):
        return argparse.Namespace(
            step="run",
            session_id=sid,
            team_id="team-1",
            channel_id="chan-1",
            team="T",
            channel="C",
            user_display="Tester",
            user_id=None,
            root_message_id=None,
            created_iso=None,
        )

    def test_no_transport_emits_post_root_without_fallback(self):
        _isolate(self, transport_descriptor=None)
        sid = "sess-" + uuid.uuid4().hex[:8]
        with _Capture(activate) as cap:
            activate.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_root")
        self.assertEqual(env["mcp_call"], "teams-PostChannelMessage")
        self.assertNotIn("http_fallback", env)

    def test_oauth_transport_attaches_fallback_on_mcp(self):
        # Activation always starts on transport="mcp" (no prior state),
        # so attach should fire but promote should not.
        _isolate(self, transport_descriptor=("cfg.json", Path("tok.json"), "https://x"))
        sid = "sess-" + uuid.uuid4().hex[:8]
        with _Capture(activate) as cap:
            activate.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_root")
        self.assertIn("mcp_call", env)
        self.assertIn("mcp_args", env)
        self.assertIn("http_fallback", env)


# ---------------------------------------------------------------------------
# ask.py — cmd_run loads existing state, so transport may be "mcp" or "http".
# ---------------------------------------------------------------------------
class AskTransportTests(unittest.TestCase):
    def _args(self, sid):
        return argparse.Namespace(
            step="run",
            session_id=sid,
            question="how is it going?",
            message_id=None,
            created_iso=None,
        )

    def test_mcp_transport_emits_both_siblings(self):
        _isolate(self, transport_descriptor=("cfg.json", Path("tok.json"), "https://x"))
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_active_state(sid, transport="mcp")
        with _Capture(ask) as cap:
            ask.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_question")
        self.assertEqual(env["transport"], "mcp")
        self.assertIn("mcp_call", env)
        self.assertIn("http_fallback", env)

    def test_http_transport_promotes_strips_mcp(self):
        _isolate(self, transport_descriptor=("cfg.json", Path("tok.json"), "https://x"))
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_active_state(sid, transport="http")
        with _Capture(ask) as cap:
            ask.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_question")
        self.assertEqual(env["transport"], "http")
        self.assertNotIn("mcp_call", env)
        self.assertNotIn("mcp_args", env)
        self.assertIn("http_fallback", env)

    def test_no_transport_keeps_mcp_only(self):
        _isolate(self, transport_descriptor=None)
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_active_state(sid, transport="http")
        with _Capture(ask) as cap:
            ask.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        # promote_http_fallback only strips when http_fallback is attached;
        # with no transport discoverable, attach is a no-op so mcp_call
        # remains as the only descriptor (graceful degradation).
        self.assertEqual(env["action"], "post_question")
        self.assertIn("mcp_call", env)
        self.assertNotIn("http_fallback", env)


# ---------------------------------------------------------------------------
# end.py — same dual-transport contract as ask.
# ---------------------------------------------------------------------------
class EndTransportTests(unittest.TestCase):
    def _args(self, sid):
        return argparse.Namespace(
            step="run",
            session_id=sid,
            reason="user-invoked",
        )

    def test_mcp_transport_emits_both_siblings(self):
        _isolate(self, transport_descriptor=("cfg.json", Path("tok.json"), "https://x"))
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_active_state(sid, transport="mcp")
        with _Capture(end) as cap:
            end.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_summary")
        self.assertIn("mcp_call", env)
        self.assertIn("http_fallback", env)

    def test_http_transport_promotes(self):
        _isolate(self, transport_descriptor=("cfg.json", Path("tok.json"), "https://x"))
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_active_state(sid, transport="http")
        with _Capture(end) as cap:
            end.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_summary")
        self.assertEqual(env["transport"], "http")
        self.assertNotIn("mcp_call", env)
        self.assertIn("http_fallback", env)


if __name__ == "__main__":
    unittest.main()
