"""Unit tests for ``teams_transport`` — teams-remote skill.

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Make the sibling module importable without installing anything.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import teams_transport as tt  # noqa: E402


def _build_sse_body(graph_payload: dict) -> str:
    """Build a realistic triple-nested SSE response body.

    Mirrors what the Teams MCP server emits: an ``event: message``
    block whose ``data:`` payload is a JSON-RPC envelope whose
    ``result.content[0].text`` field is a JSON-encoded wrapper whose
    ``response`` field is a JSON-encoded Graph payload.
    """
    graph_json = json.dumps(graph_payload)
    wrapper_json = json.dumps({"message": "ok", "response": graph_json})
    envelope = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": wrapper_json}]},
    }
    envelope_json = json.dumps(envelope)
    return f"event: message\ndata: {envelope_json}\n\n"


class ParseSseResponseTests(unittest.TestCase):
    def test_success_returns_graph_payload(self):
        payload = {
            "value": [
                {"id": "1700000000001", "body": {"content": "hi"}},
                {"id": "1700000000002", "body": {"content": "there"}},
            ]
        }
        raw = _build_sse_body(payload)
        parsed = tt.parse_sse_response(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["value"][0]["id"], "1700000000001")
        self.assertEqual(len(parsed["value"]), 2)

    def test_success_with_prelude_block(self):
        # Some servers emit a handshake block before the real result.
        prelude = "event: message\ndata: {\"jsonrpc\":\"2.0\",\"method\":\"ping\"}\n\n"
        raw = prelude + _build_sse_body({"value": []})
        parsed = tt.parse_sse_response(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed, {"value": []})

    def test_malformed_body_returns_none(self):
        self.assertIsNone(tt.parse_sse_response("event: message\ndata: {not json}\n"))

    def test_missing_jsonrpc_marker_returns_none(self):
        raw = "event: message\ndata: {\"hello\": \"world\"}\n\n"
        self.assertIsNone(tt.parse_sse_response(raw))

    def test_empty_body_returns_none(self):
        self.assertIsNone(tt.parse_sse_response(""))
        self.assertIsNone(tt.parse_sse_response(None))  # type: ignore[arg-type]

    def test_wrapper_without_response_returned_as_is(self):
        # Some tool responses skip the inner JSON-encoded "response" and
        # inline the payload. parse_sse_response returns the wrapper.
        wrapper = {"message": "ok", "data": {"foo": "bar"}}
        envelope = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(wrapper)}]},
        }
        raw = f"event: message\ndata: {json.dumps(envelope)}\n\n"
        parsed = tt.parse_sse_response(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["data"]["foo"], "bar")

    def test_unparseable_inner_response_returns_none(self):
        wrapper = {"message": "ok", "response": "this is not json"}
        envelope = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(wrapper)}]},
        }
        raw = f"event: message\ndata: {json.dumps(envelope)}\n\n"
        self.assertIsNone(tt.parse_sse_response(raw))


class EnsureFreshTokenTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base = Path(self.tmpdir.name)
        self.tokens_path = self.base / "test.tokens.json"
        self.config_path = self.base / "test.json"
        self.config_path.write_text(json.dumps({
            "clientId": "client-abc",
            "serverUrl": "https://example.invalid/mcp_TeamsServerV1",
        }), encoding="utf-8")

    def _write_tokens(self, *, expires_in_seconds: int):
        tokens = {
            "accessToken": "old-access",
            "refreshToken": "old-refresh",
            "expiresAt": int(time.time()) + expires_in_seconds,
            "scope": "https://graph.microsoft.com/.default offline_access",
        }
        self.tokens_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
        return tokens

    def test_fresh_token_does_not_refresh(self):
        tokens = self._write_tokens(expires_in_seconds=3600)  # 1 h out
        calls = []

        def fake_transport(url, body):
            calls.append((url, body))
            raise AssertionError("refresh should not be called when token is fresh")

        result = tt.ensure_fresh_token(
            self.tokens_path,
            now=time.time(),
            transport=fake_transport,
            config_path=self.config_path,
        )
        self.assertFalse(result["refreshed"])
        self.assertEqual(result["accessToken"], "old-access")
        self.assertEqual(calls, [])
        # File unchanged.
        on_disk = json.loads(self.tokens_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["accessToken"], "old-access")
        self.assertEqual(on_disk["refreshToken"], "old-refresh")

    def test_within_skew_refreshes(self):
        self._write_tokens(expires_in_seconds=60)  # 1 min out — well within 10 min skew
        captured = {}

        def fake_transport(url, body):
            captured["url"] = url
            captured["body"] = body
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 4500,
            }

        now = time.time()
        result = tt.ensure_fresh_token(
            self.tokens_path,
            now=now,
            transport=fake_transport,
            config_path=self.config_path,
        )
        self.assertTrue(result["refreshed"])
        self.assertEqual(result["accessToken"], "new-access")
        self.assertEqual(result["refreshToken"], "new-refresh")
        self.assertEqual(result["expiresAt"], int(now) + 4500)

        # Verify token endpoint URL + that client_id & grant_type were in the form body.
        self.assertIn("login.microsoftonline.com", captured["url"])
        body_str = captured["body"].decode("utf-8")
        self.assertIn("grant_type=refresh_token", body_str)
        self.assertIn("client_id=client-abc", body_str)
        self.assertIn("refresh_token=old-refresh", body_str)

        # Tokens file rewritten with camelCase keys.
        on_disk = json.loads(self.tokens_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["accessToken"], "new-access")
        self.assertEqual(on_disk["refreshToken"], "new-refresh")
        self.assertEqual(on_disk["expiresAt"], int(now) + 4500)
        # Must NOT contain snake_case keys from the OAuth response.
        self.assertNotIn("access_token", on_disk)
        self.assertNotIn("refresh_token", on_disk)
        self.assertNotIn("expires_in", on_disk)

    def test_expired_refreshes(self):
        self._write_tokens(expires_in_seconds=-120)  # expired 2 min ago

        def fake_transport(url, body):
            return {
                "access_token": "recovered",
                "refresh_token": "next-refresh",
                "expires_in": 3600,
            }

        now = time.time()
        result = tt.ensure_fresh_token(
            self.tokens_path,
            now=now,
            transport=fake_transport,
            config_path=self.config_path,
        )
        self.assertTrue(result["refreshed"])
        self.assertEqual(result["accessToken"], "recovered")
        on_disk = json.loads(self.tokens_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["accessToken"], "recovered")
        # File is still valid JSON after the rewrite.
        self.assertIsInstance(on_disk, dict)

    def test_refresh_preserves_missing_new_refresh_token(self):
        # Some AAD responses don't return a new refresh_token; we must
        # preserve the old one.
        self._write_tokens(expires_in_seconds=30)

        def fake_transport(url, body):
            return {"access_token": "renewed", "expires_in": 1000}

        result = tt.ensure_fresh_token(
            self.tokens_path,
            now=time.time(),
            transport=fake_transport,
            config_path=self.config_path,
        )
        self.assertEqual(result["refreshToken"], "old-refresh")
        on_disk = json.loads(self.tokens_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["refreshToken"], "old-refresh")


class FindTeamsMcpConfigTests(unittest.TestCase):
    def test_returns_none_for_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            self.assertIsNone(tt.find_teams_mcp_config(base_dir=missing))

    def test_matches_teams_server_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # A noise config that should be skipped.
            (base / "other.json").write_text(json.dumps({
                "serverUrl": "https://example.com/other",
            }), encoding="utf-8")
            # The Teams config.
            (base / "teams.json").write_text(json.dumps({
                "serverUrl": "https://api.agency/mcp_TeamsServerV1",
                "clientId": "c",
            }), encoding="utf-8")
            (base / "teams.tokens.json").write_text("{}", encoding="utf-8")
            found = tt.find_teams_mcp_config(base_dir=base)
            self.assertIsNotNone(found)
            cfg_path, tok_path, url = found
            self.assertEqual(cfg_path.name, "teams.json")
            self.assertEqual(tok_path.name, "teams.tokens.json")
            self.assertIn("mcp_TeamsServerV1", url)


class FindAgencyTeamsProxyTests(unittest.TestCase):
    def test_discovers_loopback_proxy_from_copilot_mcp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "copilot-mcp-abc123.json"
            cfg.write_text(json.dumps({
                "mcpServers": {
                    "teams": {
                        "type": "http",
                        "url": "http://127.0.0.1:55244",
                    },
                    "workiq": {
                        "type": "http",
                        "url": "http://127.0.0.1:55243",
                    },
                },
            }), encoding="utf-8")
            old_temp = os.environ.get("TEMP")
            os.environ["TEMP"] = tmp
            try:
                found = tt.find_agency_teams_proxy()
            finally:
                if old_temp is not None:
                    os.environ["TEMP"] = old_temp
                else:
                    os.environ.pop("TEMP", None)
            self.assertIsNotNone(found)
            self.assertEqual(found.url, "http://127.0.0.1:55244")

    def test_rejects_non_loopback_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "copilot-mcp-xyz.json"
            cfg.write_text(json.dumps({
                "mcpServers": {
                    "teams": {"type": "http", "url": "https://evil.example/mcp"},
                },
            }), encoding="utf-8")
            old_temp = os.environ.get("TEMP")
            os.environ["TEMP"] = tmp
            try:
                found = tt.find_agency_teams_proxy()
            finally:
                if old_temp is not None:
                    os.environ["TEMP"] = old_temp
                else:
                    os.environ.pop("TEMP", None)
            self.assertIsNone(found)


class BuildHttpFallbackTests(unittest.TestCase):
    def test_oauth_shape_preserves_teams_prefix_and_attaches_auth_bearer(self):
        cfg = (Path("x/cfg.json"), Path("x/cfg.tokens.json"),
               "https://api.agency/mcp_TeamsServerV1")
        fb = tt.build_http_fallback(
            "teams-ReplyToChannelMessage", {"a": 1}, config=cfg)
        self.assertEqual(fb["url"], "https://api.agency/mcp_TeamsServerV1")
        self.assertEqual(fb["auth"], "bearer")
        self.assertIn("tokens_path", fb)
        self.assertEqual(fb["body"]["params"]["name"],
                         "teams-ReplyToChannelMessage")

    def test_proxy_shape_strips_teams_prefix_and_omits_auth(self):
        proxy = tt.AgencyTeamsProxy(
            url="http://127.0.0.1:55244",
            source_path=Path("x/copilot-mcp-1.json"),
        )
        fb = tt.build_http_fallback(
            "teams-ReplyToChannelMessage", {"a": 1}, proxy=proxy)
        self.assertEqual(fb["url"], "http://127.0.0.1:55244")
        self.assertEqual(fb["auth"], "none")
        self.assertNotIn("tokens_path", fb)
        self.assertEqual(fb["body"]["params"]["name"],
                         "ReplyToChannelMessage")
        self.assertEqual(fb["body"]["params"]["arguments"], {"a": 1})


class LongPollRepliesTests(unittest.TestCase):
    """Tests for ``long_poll_replies`` — the core of the idle-drain fix."""

    def _proxy(self) -> "tt.AgencyTeamsProxy":
        return tt.AgencyTeamsProxy(
            url="http://127.0.0.1:55244",
            source_path=Path("x/copilot-mcp-1.json"),
        )

    def _fake_clock(self, ticks):
        """Return a monotonic clock stub driven by ``ticks`` — each call
        advances the clock by the next value; sleeps do nothing."""
        state = {"t": 0.0}
        it = iter(ticks)

        def now():
            return state["t"]

        def sleep(secs):
            state["t"] += float(secs)
            # If the scenario wants an out-of-band advance, apply it.
            try:
                state["t"] += float(next(it))
            except StopIteration:
                pass

        return now, sleep

    def _sse_body_for_replies(self, replies: list) -> str:
        return _build_sse_body({"replies": replies})

    def test_returns_replies_when_new_one_appears(self):
        """Single fetch returns a fresh reply → long-poll unblocks."""
        proxy = self._proxy()
        fresh_reply = {
            "id": "1776900000002",
            "createdDateTime": "2026-04-23T12:00:05Z",
            "body": {"contentType": "Text", "content": "hi"},
        }
        old_reply = {
            "id": "1776900000001",
            "createdDateTime": "2026-04-23T11:00:00Z",
            "body": {"contentType": "Text", "content": "old"},
        }
        body = self._sse_body_for_replies([old_reply, fresh_reply])

        calls = []

        def http(url, body_bytes, headers):
            calls.append(url)
            return body

        # Monkey-patch the default http transport used by proxy call.
        orig = tt._default_http_transport
        tt._default_http_transport = http  # type: ignore[assignment]
        try:
            now, sleep = self._fake_clock([])
            replies, timed_out = tt.long_poll_replies(
                team_id="T",
                channel_id="C",
                message_id="M",
                after_iso="2026-04-23T11:59:00+00:00",
                own_ids=set(),
                timeout_seconds=60,
                internal_interval=1,
                heartbeat_interval=30,
                proxy=proxy,
                now=now,
                sleep=sleep,
                stderr=io.StringIO(),
            )
        finally:
            tt._default_http_transport = orig  # type: ignore[assignment]

        self.assertFalse(timed_out)
        # Returns the full batch so the caller can dedupe; caller's
        # filter discards the old reply.
        self.assertEqual(len(replies), 2)
        ids = {r["id"] for r in replies}
        self.assertIn("1776900000002", ids)

    def test_times_out_when_no_new_reply_arrives(self):
        """Ceiling reached without a new reply → returns (empty, True)."""
        proxy = self._proxy()
        # Only contains a pre-existing reply (older than after_iso).
        old = {
            "id": "1776900000001",
            "createdDateTime": "2026-04-23T11:00:00Z",
            "body": {"contentType": "Text", "content": "old"},
        }
        body = self._sse_body_for_replies([old])

        def http(url, body_bytes, headers):
            return body

        orig = tt._default_http_transport
        tt._default_http_transport = http  # type: ignore[assignment]

        # Deterministic clock: we manually advance through 30s of wall-clock
        # with a 5s internal_interval and a 30s timeout.
        state = {"t": 0.0}

        def now():
            return state["t"]

        def sleep(secs):
            state["t"] += float(secs)

        try:
            replies, timed_out = tt.long_poll_replies(
                team_id="T",
                channel_id="C",
                message_id="M",
                after_iso="2026-04-23T11:59:00+00:00",
                own_ids=set(),
                timeout_seconds=30,
                internal_interval=5,
                heartbeat_interval=60,
                proxy=proxy,
                now=now,
                sleep=sleep,
                stderr=io.StringIO(),
            )
        finally:
            tt._default_http_transport = orig  # type: ignore[assignment]

        self.assertTrue(timed_out)
        self.assertEqual(replies, [])

    def test_ignores_own_message_ids(self):
        """A reply whose id is in own_ids does NOT unblock the poll."""
        proxy = self._proxy()
        own_reply = {
            "id": "1776900000003",
            "createdDateTime": "2026-04-23T12:00:05Z",
            "body": {"contentType": "Text", "content": "self-post"},
        }
        body = self._sse_body_for_replies([own_reply])

        def http(url, body_bytes, headers):
            return body

        orig = tt._default_http_transport
        tt._default_http_transport = http  # type: ignore[assignment]
        state = {"t": 0.0}

        def now():
            return state["t"]

        def sleep(secs):
            state["t"] += float(secs)

        try:
            replies, timed_out = tt.long_poll_replies(
                team_id="T",
                channel_id="C",
                message_id="M",
                after_iso="2026-04-23T11:59:00+00:00",
                own_ids={"1776900000003"},
                timeout_seconds=20,
                internal_interval=5,
                heartbeat_interval=60,
                proxy=proxy,
                now=now,
                sleep=sleep,
                stderr=io.StringIO(),
            )
        finally:
            tt._default_http_transport = orig  # type: ignore[assignment]

        self.assertTrue(timed_out, "own-posted reply must not unblock")
        self.assertEqual(replies, [])

    def test_no_transport_returns_immediately(self):
        """Without a discoverable transport, long-poll must not block."""
        # Neither config nor proxy passed; and scanning will find
        # nothing in a clean temp TEMP.
        with tempfile.TemporaryDirectory() as tmp:
            old_temp = os.environ.get("TEMP")
            os.environ["TEMP"] = tmp
            try:
                replies, timed_out = tt.long_poll_replies(
                    team_id="T",
                    channel_id="C",
                    message_id="M",
                    after_iso=None,
                    own_ids=set(),
                    timeout_seconds=300,
                    internal_interval=5,
                    heartbeat_interval=60,
                    stderr=io.StringIO(),
                )
            finally:
                if old_temp is not None:
                    os.environ["TEMP"] = old_temp
                else:
                    os.environ.pop("TEMP", None)

        self.assertTrue(timed_out)
        self.assertEqual(replies, [])

    def test_emits_heartbeat_to_stderr(self):
        """Every heartbeat_interval seconds a line is written to stderr
        so the Copilot CLI sees the subprocess is still alive (mitigates
        Issue 5 — silent-subprocess termination)."""
        proxy = self._proxy()
        old = {
            "id": "1776900000001",
            "createdDateTime": "2026-04-23T11:00:00Z",
            "body": {"contentType": "Text", "content": "old"},
        }
        body = self._sse_body_for_replies([old])

        def http(url, body_bytes, headers):
            return body

        orig = tt._default_http_transport
        tt._default_http_transport = http  # type: ignore[assignment]
        err = io.StringIO()
        state = {"t": 0.0}

        def now():
            return state["t"]

        def sleep(secs):
            state["t"] += float(secs)

        try:
            tt.long_poll_replies(
                team_id="T",
                channel_id="C",
                message_id="M",
                after_iso="2026-04-23T11:59:00+00:00",
                own_ids=set(),
                timeout_seconds=120,
                internal_interval=5,
                heartbeat_interval=30,
                proxy=proxy,
                now=now,
                sleep=sleep,
                stderr=err,
            )
        finally:
            tt._default_http_transport = orig  # type: ignore[assignment]

        text = err.getvalue()
        # 120s window / 30s heartbeat → at least 3 alive markers.
        self.assertGreaterEqual(text.count("[long-poll] alive"), 3,
                                f"expected multiple alive lines, got:\n{text}")


# imports used by LongPollRepliesTests live at top-level for clarity.
import io  # noqa: E402


if __name__ == "__main__":
    unittest.main()
