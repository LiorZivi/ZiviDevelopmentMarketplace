"""Tests for self-mention injection on the activate root post and the
end summary post — teams-remote skill.

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "lib"))

import tempfile

import os

import state as _state  # noqa: E402
import activate  # noqa: E402
import end  # noqa: E402
import transport_router as _tr  # noqa: E402


def _isolate(testcase: unittest.TestCase = None) -> str:
    """Per-test isolation: redirect session_root to a tmp dir and pin a
    unique subsystem. When called with a TestCase, registers cleanups —
    including clearing ``COPILOT_AGENT_SESSION_ID`` so the resolver
    deterministically falls back to the test's ``args.session_id``, and
    stubbing ``resolve_transport`` to ``None`` so envelopes don't pick up
    a real on-disk Teams MCP config from the developer machine."""
    name = "teams-remote-test-" + uuid.uuid4().hex[:8]
    if testcase is not None:
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
    return name


class _Capture:
    def __init__(self, module) -> None:
        self.module = module
        self.buf = io.StringIO()
        self._orig = None

    def __enter__(self):
        self._orig = self.module._emit
        self.module._emit = lambda action: self.buf.write(json.dumps(action) + "\n")
        return self

    def __exit__(self, *a):
        self.module._emit = self._orig

    def payloads(self):
        return [json.loads(l) for l in self.buf.getvalue().splitlines() if l.strip()]


class ActivateMentionTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def _args(self, **extra):
        base = dict(
            step="run",
            session_id="sess-" + uuid.uuid4().hex[:8],
            team_id="team-guid",
            channel_id="channel-thread",
            team="LiziTestTeam",
            channel="Lizi_Copilot_Teams_Interactions",
            user_display="Lior Zivi",
            user_id=None,
            root_message_id=None,
            created_iso=None,
        )
        base.update(extra)
        return argparse.Namespace(**base)

    def test_no_user_id_means_no_mentions_and_no_at_tag(self):
        with _Capture(activate) as cap:
            activate.cmd_run(self._args(user_id=None))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_root")
        self.assertNotIn("mentions", env["mcp_args"])
        self.assertNotIn("<at>", env["mcp_args"]["content"])

    def test_user_id_and_display_inject_mention_tag_and_mentions_field(self):
        with _Capture(activate) as cap:
            activate.cmd_run(self._args(
                user_id="2f626221-0548-428f-838a-647ae111b73d",
                user_display="Lior Zivi",
            ))
        env = cap.payloads()[-1]
        self.assertIn("mentions", env["mcp_args"])
        mentions = json.loads(env["mcp_args"]["mentions"])
        self.assertEqual(mentions[0]["id"], "2f626221-0548-428f-838a-647ae111b73d")
        self.assertEqual(mentions[0]["displayName"], "Lior Zivi")
        self.assertTrue(env["mcp_args"]["content"].startswith("<p><at>Lior Zivi</at> Copilot agent message:</p>"))


class EndMentionTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def _seed(self, *, user_id="", user_display=""):
        sid = "sess-" + uuid.uuid4().hex[:8]
        st = {
            "schema_version": _state.SCHEMA_VERSION,
            "session_id": sid,
            "team_id": "team-guid",
            "channel_id": "channel-thread",
            "root_message_id": "root-msg-id",
            "correlation_token": "corr-token",
            "poll_interval": 10,
            "timeout_seconds": 600,
            "away_mode": True,
            "transport": "http",
            "last_processed_id": "0",
            "seen_reply_ids": "",
            "own_message_ids": [],
            "message_count": 0,
            "user_mention_id": user_id,
            "user_display": user_display,
            "session_start_time": "2026-04-22T20:31:38+00:00",
        }
        _state.save_state(sid, st)
        return sid

    def _args(self, sid):
        return argparse.Namespace(session_id=sid, reason="user-invoked")

    def test_no_mention_when_user_id_missing(self):
        sid = self._seed()
        with _Capture(end) as cap:
            end.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertEqual(env["action"], "post_summary")
        self.assertNotIn("mentions", env["mcp_args"])
        self.assertNotIn("<at>", env["mcp_args"]["content"])

    def test_mention_injected_when_state_carries_user_id(self):
        sid = self._seed(user_id="2f626221-0548-428f-838a-647ae111b73d",
                         user_display="Lior Zivi")
        with _Capture(end) as cap:
            end.cmd_run(self._args(sid))
        env = cap.payloads()[-1]
        self.assertIn("mentions", env["mcp_args"])
        mentions = json.loads(env["mcp_args"]["mentions"])
        self.assertEqual(mentions[0]["id"], "2f626221-0548-428f-838a-647ae111b73d")
        self.assertTrue(env["mcp_args"]["content"].startswith("<p><at>Lior Zivi</at> Copilot agent message:</p>"))


if __name__ == "__main__":
    unittest.main()
