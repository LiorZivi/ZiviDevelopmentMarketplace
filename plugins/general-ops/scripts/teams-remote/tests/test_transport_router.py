"""Unit tests for ``transport_router`` (v1.9.0).

Covers:
* ``attach_http_fallback`` — oauth tuple branch + nested ``progress_post``.
* ``promote_http_fallback`` — strips ``mcp_call``/``mcp_args`` only when
  ``http_fallback`` is present, including nested envelopes; idempotent.
* ``refresh_and_route`` — stubbed token refresh flips ``state["transport"]``.
* ``dispatch_teams_call`` — all three return shapes with stubbed
  ``direct_http_call``.
* Ordering regression — canonical ``attach`` then ``promote`` sequence.

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import transport_router as tr  # noqa: E402
import teams_transport  # noqa: E402


def _make_oauth_descriptor(tmp: Path) -> tuple:
    cfg = tmp / "cfg.json"
    tok = tmp / "tok.json"
    cfg.write_text("{}")
    tok.write_text("{}")
    return (cfg, tok, "https://teams-mcp.example/Production")


class AttachHttpFallbackTests(unittest.TestCase):
    def test_oauth_branch_attaches_to_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            descriptor = _make_oauth_descriptor(Path(d))
            env = {"mcp_call": "teams-PostChannelMessage",
                   "mcp_args": {"team": "T1", "channel": "C1"}}
            tr.attach_http_fallback(env, descriptor)
            self.assertIn("http_fallback", env)
            self.assertIn("url", env["http_fallback"])

    def test_handles_nested_progress_post(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            descriptor = _make_oauth_descriptor(Path(d))
            env = {
                "mcp_call": "teams-PostChannelMessage",
                "mcp_args": {"team": "T1", "channel": "C1"},
                "progress_post": {
                    "mcp_call": "teams-ReplyToChannelMessage",
                    "mcp_args": {"team": "T1", "channel": "C1",
                                 "messageId": "X"},
                },
            }
            tr.attach_http_fallback(env, descriptor)
            self.assertIn("http_fallback", env)
            self.assertIn("http_fallback", env["progress_post"])

    def test_no_descriptor_is_noop(self) -> None:
        env = {"mcp_call": "x", "mcp_args": {}}
        tr.attach_http_fallback(env, None)
        self.assertNotIn("http_fallback", env)

    def test_envelope_without_mcp_call_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            descriptor = _make_oauth_descriptor(Path(d))
            env = {"action": "ping"}
            tr.attach_http_fallback(env, descriptor)
            self.assertNotIn("http_fallback", env)


class PromoteHttpFallbackTests(unittest.TestCase):
    def test_strips_mcp_when_fallback_present(self) -> None:
        env = {"mcp_call": "X", "mcp_args": {"a": 1},
               "http_fallback": {"url": "u", "body": {}}, "keep": True}
        tr.promote_http_fallback(env)
        self.assertNotIn("mcp_call", env)
        self.assertNotIn("mcp_args", env)
        self.assertIn("http_fallback", env)
        self.assertTrue(env["keep"])

    def test_noop_without_fallback(self) -> None:
        env = {"mcp_call": "X", "mcp_args": {"a": 1}}
        tr.promote_http_fallback(env)
        self.assertEqual(env["mcp_call"], "X")

    def test_strips_nested_progress_post(self) -> None:
        env = {
            "mcp_call": "X", "mcp_args": {},
            "http_fallback": {"url": "u", "body": {}},
            "progress_post": {
                "mcp_call": "Y", "mcp_args": {},
                "http_fallback": {"url": "v", "body": {}},
            },
        }
        tr.promote_http_fallback(env)
        self.assertNotIn("mcp_call", env)
        self.assertNotIn("mcp_call", env["progress_post"])
        self.assertIn("http_fallback", env["progress_post"])

    def test_idempotent(self) -> None:
        env = {"mcp_call": "X", "mcp_args": {},
               "http_fallback": {"url": "u", "body": {}}}
        tr.promote_http_fallback(env)
        tr.promote_http_fallback(env)
        self.assertNotIn("mcp_call", env)


class RefreshAndRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self._orig_resolve = tr.resolve_transport
        self._orig_ensure = tr.ensure_fresh_token

    def tearDown(self) -> None:
        tr.resolve_transport = self._orig_resolve
        tr.ensure_fresh_token = self._orig_ensure

    def test_refresh_fired_flips_to_http(self) -> None:
        descriptor = _make_oauth_descriptor(self.tmp)
        tr.resolve_transport = lambda: descriptor
        tr.ensure_fresh_token = lambda *a, **k: {"refreshed": True,
                                                  "accessToken": "tok"}
        state = {"transport": "mcp"}
        out = tr.refresh_and_route(state)
        self.assertEqual(state["transport"], "http")
        self.assertEqual(out, descriptor)

    def test_refresh_not_fired_keeps_mcp(self) -> None:
        descriptor = _make_oauth_descriptor(self.tmp)
        tr.resolve_transport = lambda: descriptor
        tr.ensure_fresh_token = lambda *a, **k: {"refreshed": False,
                                                  "accessToken": "tok"}
        state = {"transport": "mcp"}
        tr.refresh_and_route(state)
        self.assertEqual(state["transport"], "mcp")

    def test_proxy_descriptor_does_not_refresh(self) -> None:
        proxy = SimpleNamespace(
            url="http://127.0.0.1:5555/", server_name="teams-proxy"
        )
        tr.resolve_transport = lambda: proxy
        called = {"n": 0}

        def boom(*a, **k):
            called["n"] += 1
            raise AssertionError("must not be called for proxy")

        tr.ensure_fresh_token = boom
        state = {"transport": "mcp"}
        out = tr.refresh_and_route(state)
        self.assertEqual(out, proxy)
        self.assertEqual(state["transport"], "mcp")
        self.assertEqual(called["n"], 0)

    def test_no_transport_returns_none(self) -> None:
        tr.resolve_transport = lambda: None
        state = {"transport": "mcp"}
        out = tr.refresh_and_route(state)
        self.assertIsNone(out)
        self.assertEqual(state["transport"], "mcp")


class DispatchTeamsCallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self._orig_direct = tr.direct_http_call

    def tearDown(self) -> None:
        tr.direct_http_call = self._orig_direct

    def test_mcp_branch_returns_descriptor_with_fallback(self) -> None:
        descriptor = _make_oauth_descriptor(self.tmp)
        state = {"transport": "mcp"}
        out = tr.dispatch_teams_call(
            state, "teams-PostChannelMessage", {"team": "T", "channel": "C"},
            transport_descriptor=descriptor,
        )
        self.assertEqual(out["mode"], "mcp")
        self.assertEqual(out["mcp_call"], "teams-PostChannelMessage")
        self.assertIsNotNone(out["http_fallback"])

    def test_mcp_branch_no_descriptor_no_fallback(self) -> None:
        state = {"transport": "mcp"}
        out = tr.dispatch_teams_call(
            state, "teams-PostChannelMessage", {},
            transport_descriptor=None,
        )
        self.assertEqual(out["mode"], "mcp")
        self.assertIsNone(out["http_fallback"])

    def test_http_branch_success(self) -> None:
        descriptor = _make_oauth_descriptor(self.tmp)
        tr.direct_http_call = lambda *a, **k: teams_transport.TransportResult(
            True, None, {"id": "msg-123"}
        )
        state = {"transport": "http"}
        out = tr.dispatch_teams_call(
            state, "teams-PostChannelMessage", {"team": "T", "channel": "C"},
            transport_descriptor=descriptor,
        )
        self.assertEqual(out["mode"], "http")
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"], {"id": "msg-123"})

    def test_http_branch_failure(self) -> None:
        descriptor = _make_oauth_descriptor(self.tmp)
        tr.direct_http_call = lambda *a, **k: teams_transport.TransportResult(
            False, "http-error: boom", None
        )
        state = {"transport": "http"}
        out = tr.dispatch_teams_call(
            state, "teams-PostChannelMessage", {},
            transport_descriptor=descriptor,
        )
        self.assertEqual(out["mode"], "http")
        self.assertFalse(out["ok"])
        self.assertIn("http-error", out["error"])

    def test_http_branch_without_oauth_descriptor_errors(self) -> None:
        state = {"transport": "http"}
        out = tr.dispatch_teams_call(
            state, "teams-PostChannelMessage", {},
            transport_descriptor=None,
        )
        self.assertEqual(out["mode"], "http")
        self.assertFalse(out["ok"])


class AttachThenPromoteOrderingTests(unittest.TestCase):
    """Pin the canonical ordering for the poll.py call sites."""

    def test_http_session_strips_mcp_after_attach_then_promote(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            descriptor = _make_oauth_descriptor(Path(d))
            env = {"mcp_call": "teams-PostChannelMessage",
                   "mcp_args": {"team": "T", "channel": "C"}}
            state = {"transport": "http"}

            tr.attach_http_fallback(env, descriptor)
            if state.get("transport") == "http":
                tr.promote_http_fallback(env)

            self.assertNotIn("mcp_call", env)
            self.assertNotIn("mcp_args", env)
            self.assertIn("http_fallback", env)

    def test_mcp_session_keeps_both_after_attach_then_promote(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            descriptor = _make_oauth_descriptor(Path(d))
            env = {"mcp_call": "teams-PostChannelMessage",
                   "mcp_args": {"team": "T", "channel": "C"}}
            state = {"transport": "mcp"}

            tr.attach_http_fallback(env, descriptor)
            if state.get("transport") == "http":
                tr.promote_http_fallback(env)

            self.assertIn("mcp_call", env)
            self.assertIn("mcp_args", env)
            self.assertIn("http_fallback", env)


if __name__ == "__main__":
    unittest.main()
