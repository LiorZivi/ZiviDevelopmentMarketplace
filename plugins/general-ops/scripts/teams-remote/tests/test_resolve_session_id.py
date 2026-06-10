"""Unit tests for ``state.resolve_session_id`` (v1.9.0).

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/teams-remote/tests
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "lib"))

import state  # noqa: E402


def _ns(session_id):
    return argparse.Namespace(session_id=session_id)


class ResolveSessionIdTests(unittest.TestCase):
    def test_env_wins_over_args_and_payload(self) -> None:
        env = {state.SESSION_ID_ENV: "env-guid"}
        out = state.resolve_session_id(
            _ns("arg-guid"),
            stdin_payload={"session_id": "payload-guid"},
            env=env,
        )
        self.assertEqual(out, "env-guid")

    def test_env_wins_even_when_args_is_placeholder(self) -> None:
        env = {state.SESSION_ID_ENV: "env-guid"}
        out = state.resolve_session_id(_ns("<SID>"), env=env)
        self.assertEqual(out, "env-guid")

    def test_env_unset_args_returned(self) -> None:
        out = state.resolve_session_id(_ns("abc"), env={})
        self.assertEqual(out, "abc")

    def test_env_unset_payload_returned_when_no_args(self) -> None:
        out = state.resolve_session_id(
            stdin_payload={"session_id": "xyz"}, env={}
        )
        self.assertEqual(out, "xyz")

    def test_placeholder_args_falls_through_to_payload(self) -> None:
        out = state.resolve_session_id(
            _ns("<SID>"),
            stdin_payload={"session_id": "xyz"},
            env={},
        )
        self.assertEqual(out, "xyz")

    def test_no_source_exits(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            state.resolve_session_id(env={})
        self.assertEqual(cm.exception.code, 2)

    def test_no_args_no_payload_no_env_exits(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            state.resolve_session_id(_ns(None), stdin_payload={}, env={})
        self.assertEqual(cm.exception.code, 2)

    def test_empty_env_value_treated_as_unset(self) -> None:
        out = state.resolve_session_id(
            _ns("arg-guid"),
            env={state.SESSION_ID_ENV: ""},
        )
        self.assertEqual(out, "arg-guid")


if __name__ == "__main__":
    unittest.main()
