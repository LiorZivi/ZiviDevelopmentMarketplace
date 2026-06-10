"""Unit tests for ``teams-remote/poll.py`` auto-flip behaviour (v1.5.1).

Covers:

* ``--step record-mcp-error`` against a missing session → ``no_session``.
* First error flips ``transport`` to ``"http"`` and sets streak=1.
* Second error bumps streak to 2 but does NOT re-flip.
* Post-flip ``--step tick`` envelope drops ``mcp_call``/``mcp_args`` and
  preserves ``http_fallback`` (when transport config is available).

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
# Make the sibling ``poll`` and ``lib/state`` modules importable without
# needing any packaging.
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "lib"))

import state as _state  # noqa: E402
import poll  # noqa: E402
import transport_router  # noqa: E402


def _isolated_subsystem() -> str:
    """Point state at a unique sub-dir so tests can't collide with each other
    or with a live teams-remote session on the same machine."""
    name = "teams-remote-test-" + uuid.uuid4().hex[:8]
    _state.set_subsystem(name)
    return name


def _isolate(testcase: unittest.TestCase) -> str:
    """Per-test isolation: redirect session_root to a tmp dir and pin a
    unique subsystem. Cleans up on test teardown. Also clears
    ``COPILOT_AGENT_SESSION_ID`` so :func:`state.resolve_session_id`
    falls back to the test's ``args.session_id`` deterministically."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    testcase.addCleanup(_state.set_session_root, None)
    _state.set_session_root(Path(tmp.name))

    prior = os.environ.pop(_state.SESSION_ID_ENV, None)
    if prior is not None:
        testcase.addCleanup(os.environ.__setitem__, _state.SESSION_ID_ENV, prior)
    return _isolated_subsystem()


def _seed_state(session_id: str) -> dict:
    """Minimal state sufficient for cmd_tick + record-mcp-error."""
    state = {
        "schema_version": _state.SCHEMA_VERSION,
        "session_id": session_id,
        "team_id": "team-guid",
        "channel_id": "channel-thread",
        "root_message_id": "root-msg-id",
        "correlation_token": "corr-token",
        "poll_interval": 10,
        "timeout_seconds": 600,
        "away_mode": True,
        "transport": "mcp",
        "last_processed_id": "0",
        "seen_reply_ids": "",
        "own_message_ids": [],
        "message_count": 0,
    }
    _state.save_state(session_id, state)
    return state


class _CapturedEmit:
    """Capture ``poll._emit`` output while a block runs."""

    def __init__(self) -> None:
        self.buf = io.StringIO()
        self._orig = None

    def __enter__(self):
        self._orig = poll._emit

        def _capture(action: dict) -> None:
            self.buf.write(json.dumps(action) + "\n")
        poll._emit = _capture  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        poll._emit = self._orig  # type: ignore[assignment]

    def payloads(self) -> list[dict]:
        out = []
        for line in self.buf.getvalue().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def last(self) -> dict:
        payloads = self.payloads()
        assert payloads, "no emit captured"
        return payloads[-1]


def _record_args(session_id: str, code: int, message: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(session_id=session_id, code=code, message=message)


def _tick_args(session_id: str) -> argparse.Namespace:
    return argparse.Namespace(
        session_id=session_id,
        mode="idle",
        with_sleep=False,
    )


class RecordMcpErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def test_no_session(self) -> None:
        with _CapturedEmit() as cap:
            rc = poll.cmd_record_mcp_error(_record_args("nonexistent-" + uuid.uuid4().hex, -32001))
        self.assertEqual(rc, 1)
        self.assertEqual(cap.last()["error"], "no_session")

    def test_first_error_flips_to_http(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)

        with _CapturedEmit() as cap:
            rc = poll.cmd_record_mcp_error(_record_args(sid, -32001, "Request timed out"))

        self.assertEqual(rc, 0)
        emitted = cap.last()
        self.assertEqual(emitted["action"], "mcp_error_recorded")
        self.assertEqual(emitted["transport"], "http")
        self.assertEqual(emitted["mcp_timeout_streak"], 1)
        self.assertTrue(emitted["flipped"])
        self.assertEqual(emitted["next_step"], "tick")

        state = _state.load_state(sid)
        self.assertEqual(state["transport"], "http")
        self.assertEqual(state["mcp_timeout_streak"], 1)
        self.assertIn("transport_flipped_at", state)
        self.assertEqual(state["transport_flip_reason"], "mcp-error:-32001")
        err = state["last_mcp_error"]
        self.assertEqual(err["code"], -32001)
        self.assertEqual(err["message"], "Request timed out")
        self.assertIn("at", err)

    def test_second_error_bumps_streak_but_does_not_reflip(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)

        with _CapturedEmit():
            poll.cmd_record_mcp_error(_record_args(sid, -32001))
        state_after_1 = _state.load_state(sid)
        flipped_at_1 = state_after_1["transport_flipped_at"]

        with _CapturedEmit() as cap:
            poll.cmd_record_mcp_error(_record_args(sid, -32001, "again"))
        emitted = cap.last()
        self.assertEqual(emitted["mcp_timeout_streak"], 2)
        self.assertFalse(emitted["flipped"])

        state_after_2 = _state.load_state(sid)
        self.assertEqual(state_after_2["mcp_timeout_streak"], 2)
        # Flip timestamp must not move once we're on HTTP.
        self.assertEqual(state_after_2["transport_flipped_at"], flipped_at_1)

    def test_missing_code_returns_error(self) -> None:
        # Routed through main() so we exercise the dispatcher's --code guard.
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)
        old_argv = sys.argv
        try:
            sys.argv = [
                "poll.py", "--step", "record-mcp-error",
                "--session-id", sid,
            ]
            with _CapturedEmit() as cap:
                rc = poll.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 1)
        self.assertEqual(cap.last()["error"], "missing --code")


class PostFlipTickEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        _isolate(self)

    def test_tick_on_mcp_transport_keeps_mcp_call(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)

        with _CapturedEmit() as cap:
            rc = poll.cmd_tick(_tick_args(sid))
        self.assertEqual(rc, 0)
        env = cap.last()
        # Baseline sanity: MCP still primary when transport=="mcp".
        self.assertEqual(env["transport"], "mcp")
        self.assertEqual(env["mcp_call"], "teams-ListChannelMessageReplies")
        self.assertIn("mcp_args", env)

    def test_tick_after_flip_strips_mcp_call(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)
        # Flip the session.
        with _CapturedEmit():
            poll.cmd_record_mcp_error(_record_args(sid, -32001))

        with _CapturedEmit() as cap:
            rc = poll.cmd_tick(_tick_args(sid))
        self.assertEqual(rc, 0)
        env = cap.last()
        self.assertEqual(env["transport"], "http")
        # If the transport module + config are available, http_fallback
        # is attached AND mcp_call/mcp_args are promoted away. If config
        # is not locatable on this box, _attach_http_fallback is a no-op,
        # in which case the envelope still has mcp_call — we don't fail
        # the test: the agent-side contract only requires that *when*
        # http_fallback exists, mcp_call is absent.
        if "http_fallback" in env:
            self.assertNotIn("mcp_call", env)
            self.assertNotIn("mcp_args", env)
            # oauth transport preserves the `teams-` prefix; agency
            # loopback proxy strips it to match the upstream server's
            # unprefixed tool registration.
            name = env["http_fallback"]["body"]["params"]["name"]
            self.assertIn(name, {"teams-ListChannelMessageReplies",
                                 "ListChannelMessageReplies"})

    def test_promote_helper_is_idempotent_and_scoped(self) -> None:
        env = {
            "mcp_call": "teams-X",
            "mcp_args": {"a": 1},
            "http_fallback": {"url": "https://x", "body": {}},
            "progress_post": {
                "mcp_call": "teams-Y",
                "mcp_args": {"b": 2},
                "http_fallback": {"url": "https://y", "body": {}},
            },
            "other_key": "kept",
        }
        transport_router.promote_http_fallback(env)
        self.assertNotIn("mcp_call", env)
        self.assertNotIn("mcp_args", env)
        self.assertIn("http_fallback", env)
        self.assertEqual(env["other_key"], "kept")
        self.assertNotIn("mcp_call", env["progress_post"])
        self.assertNotIn("mcp_args", env["progress_post"])
        self.assertIn("http_fallback", env["progress_post"])

        # Idempotent re-run: no KeyError, no spurious changes.
        transport_router.promote_http_fallback(env)
        self.assertNotIn("mcp_call", env)

    def test_promote_helper_noop_without_fallback(self) -> None:
        env = {"mcp_call": "teams-X", "mcp_args": {"a": 1}}
        transport_router.promote_http_fallback(env)
        # No http_fallback ⇒ nothing stripped (agent still has a path).
        self.assertEqual(env["mcp_call"], "teams-X")
        self.assertEqual(env["mcp_args"], {"a": 1})


class TickRecordOwnIdTests(unittest.TestCase):
    """`--record-own-id` on tick must persist before polling so the
    long-poll filter (and subsequent process step) skips the just-posted
    message instead of treating it as a new inbound reply."""

    def setUp(self) -> None:
        _isolate(self)

    def _tick_args_with_record(
        self, session_id: str, msg_id: str, kind: str = "other"
    ) -> argparse.Namespace:
        return argparse.Namespace(
            session_id=session_id,
            mode="idle",
            with_sleep=False,
            long_poll=False,
            record_own_id=msg_id,
            record_own_kind=kind,
            record_own_created=None,
        )

    def test_record_own_id_persists_to_state(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)
        with _CapturedEmit():
            rc = poll.cmd_tick(self._tick_args_with_record(sid, "999000111"))
        self.assertEqual(rc, 0)
        state = _state.load_state(sid)
        self.assertIn("999000111", state.get("own_message_ids") or [])

    def test_record_own_id_progress_kind_bumps_message_count(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)
        before = int((_state.load_state(sid) or {}).get("message_count", 0))
        with _CapturedEmit():
            rc = poll.cmd_tick(
                self._tick_args_with_record(sid, "999000222", kind="progress")
            )
        self.assertEqual(rc, 0)
        state = _state.load_state(sid)
        self.assertIn("999000222", state.get("own_message_ids") or [])
        self.assertEqual(int(state.get("message_count", 0)), before + 1)
        self.assertIsNotNone(state.get("last_auto_post_time"))

    def test_record_own_id_idempotent(self) -> None:
        sid = "sess-" + uuid.uuid4().hex[:8]
        _seed_state(sid)
        with _CapturedEmit():
            poll.cmd_tick(self._tick_args_with_record(sid, "999000333"))
            poll.cmd_tick(self._tick_args_with_record(sid, "999000333"))
        state = _state.load_state(sid)
        own = state.get("own_message_ids") or []
        self.assertEqual(own.count("999000333"), 1)


if __name__ == "__main__":
    unittest.main()
