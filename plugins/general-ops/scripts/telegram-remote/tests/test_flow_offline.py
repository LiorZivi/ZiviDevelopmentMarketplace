"""Offline integration tests for the telegram-remote flow (network mocked).

Exercises the full control loop — activate → stop-hook block → idle inject →
foreign-chat drop → send ack → ask/answer → terminate → end → stop-hook silent
— by monkeypatching the single ``telegram_transport._api_call`` choke point, so
no bot token or network is required.

Run with::

    python -m unittest discover -s plugins/general-ops/scripts/telegram-remote/tests
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TR = HERE.parent                       # scripts/telegram-remote
SCRIPTS = TR.parent                    # scripts
for p in (str(TR), str(SCRIPTS / "hooks"), str(SCRIPTS / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

SID = "test-sid-1234"


class TelegramRemoteFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self._root = tempfile.mkdtemp(prefix="tgremote-test-")
        os.environ["COPILOT_SESSION_ROOT"] = self._root
        os.environ["COPILOT_AGENT_SESSION_ID"] = SID
        os.environ["TELEGRAM_BOT_TOKEN"] = "TESTTOKEN"
        os.environ["TELEGRAM_CHAT_ID"] = "999"
        os.environ["TELEGRAM_REMOTE_POLL_BUDGET"] = "0"
        os.environ["TELEGRAM_REMOTE_POLL_SEGMENT"] = "0"

        import telegram_transport as tt
        self.tt = tt
        self.update_queue: list = []
        self.sent: list = []
        self.sent_documents: list = []

        def fake_api(token, method, params, timeout):
            if method == "sendMessage":
                self.sent.append(params["text"])
                return {"message_id": 100 + len(self.sent)}
            if method == "getUpdates":
                return self.update_queue.pop(0) if self.update_queue else []
            if method == "deleteWebhook":
                return True
            raise AssertionError("unexpected method " + method)

        self._orig_api = tt._api_call
        tt._api_call = fake_api

    def tearDown(self) -> None:
        self.tt._api_call = self._orig_api

    @staticmethod
    def _run(fn, *a, **k):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fn(*a, **k)
        text = buf.getvalue().strip()
        env = json.loads(text.splitlines()[-1]) if text else None
        return rc, env, buf.getvalue()

    @staticmethod
    def _msg(update_id, message_id, text, chat_id=999):
        return {"update_id": update_id, "message": {
            "message_id": message_id, "date": 1700000000 + update_id,
            "from": {"username": "LiorZivi"}, "chat": {"id": chat_id}, "text": text}}

    def test_full_flow(self) -> None:
        import activate
        import poll
        import end
        import send
        import send_file
        import ask
        import telegram_remote_stop as hook
        from state import load_state

        # 1) activate
        self.update_queue.append([])  # empty backlog drain
        rc, env, _ = self._run(activate.cmd_run, SimpleNamespace(
            step="run", session_id=None, chat_id=None, user_display="Lior"))
        self.assertEqual((rc, env["action"]), (0, "ready"))
        st = load_state(SID)
        self.assertTrue(st["away_mode"])
        self.assertEqual(st["chat_id"], "999")
        self.assertEqual(st["root_message_id"], "101")
        self.assertIn("telegram-remote is now active", self.sent[-1])

        # 2) stop-hook blocks while away
        _stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"session_id": SID}))
        _, _, hout = self._run(hook.main)
        sys.stdin = _stdin
        self.assertTrue(hout.strip())
        self.assertEqual(json.loads(hout)["decision"], "block")

        # 3) idle inject
        self.update_queue.append([self._msg(5001, 7, "add logging to main")])
        rc, env, _ = self._run(poll.cmd_tick, SimpleNamespace(
            step="tick", mode="idle", session_id=None, long_poll=True, with_sleep=False))
        self.assertEqual(env["action"], "inject")
        self.assertEqual(env["replies"][0]["text"], "add logging to main")
        self.assertEqual(load_state(SID)["last_update_id"], 5001)
        self.assertIn("progress updates", env["ack_hint"])
        self.assertIn("--completed", env["ack_hint"])

        # 4) foreign-chat message consumed but not injected
        self.update_queue.append([self._msg(5002, 8, "not for us", chat_id=777)])
        rc, env, _ = self._run(poll.cmd_tick, SimpleNamespace(
            step="tick", mode="idle", session_id=None, long_poll=True, with_sleep=False))
        self.assertEqual(env["action"], "continue")
        self.assertEqual(load_state(SID)["last_update_id"], 5002)

        # 5) send.py ad-hoc ack prefixed
        old = sys.argv
        sys.argv = ["send.py", "--text", "on it"]
        rc, env, _ = self._run(send.main)
        sys.argv = old
        self.assertEqual(env["action"], "sent")
        self.assertTrue(self.sent[-1].startswith("Copilot agent message: on it"))

        # 6) send.py expands literal newline escapes
        old = sys.argv
        sys.argv = ["send.py", "--text", r"line one\nline two"]
        rc, env, _ = self._run(send.main)
        sys.argv = old
        self.assertEqual(env["action"], "sent")
        self.assertEqual(
            self.sent[-1],
            "Copilot agent message: line one\nline two",
        )

        # 7) send.py successful completion gets both ordered prefixes
        old = sys.argv
        sys.argv = ["send.py", "--completed", "--text", "All tests passed."]
        rc, env, _ = self._run(send.main)
        sys.argv = old
        self.assertEqual(env["action"], "sent")
        self.assertTrue(env["completed"])
        self.assertTrue(self.sent[-1].startswith(
            "TASK COMPLETE: Copilot agent message:"))
        self.assertIn("All tests passed.", self.sent[-1])
        self.assertEqual(
            send._completed("task complete: Already summarized."),
            "TASK COMPLETE: Copilot agent message: Already summarized.",
        )
        self.assertEqual(
            send._completed(r"One line\nSecond line"),
            "TASK COMPLETE: Copilot agent message: One line\nSecond line",
        )
        self.assertEqual(
            send._completed(""),
            "TASK COMPLETE: Copilot agent message: ",
        )

        # 8) send_file.py uploads a local document with an agent-prefixed caption
        def fake_send_document(token, chat_id, file_path, *, caption, timeout=60.0):
            self.sent_documents.append({
                "token": token,
                "chat_id": chat_id,
                "file_path": file_path,
                "caption": caption,
            })
            return {"message_id": 222}

        send_file.send_document = fake_send_document
        document = Path(self._root) / "comparison.html"
        document.write_text("<html></html>", encoding="utf-8")
        old = sys.argv
        sys.argv = [
            "send_file.py",
            "--file",
            str(document),
            "--caption",
            r"Comparison report\nOpen locally if needed.",
        ]
        rc, env, _ = self._run(send_file.main)
        sys.argv = old
        self.assertEqual(env["action"], "sent_file")
        self.assertEqual(
            self.sent_documents[-1]["caption"],
            "Copilot agent message: Comparison report\nOpen locally if needed.",
        )

        # 9) ask.py expands literal newline escapes + input poll -> answer
        old = sys.argv
        sys.argv = [
            "ask.py",
            "--question",
            r"Deploy to production?\nA: Yes\nB: No",
        ]
        rc, env, _ = self._run(ask.main)
        sys.argv = old
        self.assertEqual(env["next_step"], "poll_input")
        self.assertEqual(
            self.sent[-1],
            "\u2753 Copilot agent message: Deploy to production?\nA: Yes\nB: No",
        )
        self.update_queue.append([self._msg(5003, 9, "yes go")])
        rc, env, _ = self._run(poll.cmd_tick, SimpleNamespace(
            step="tick", mode="input", session_id=None, long_poll=True, with_sleep=False))
        self.assertEqual((env["action"], env["text"]), ("answer", "yes go"))

        # 10) idle terminate keyword
        self.update_queue.append([self._msg(5004, 10, "end")])
        rc, env, _ = self._run(poll.cmd_tick, SimpleNamespace(
            step="tick", mode="idle", session_id=None, long_poll=True, with_sleep=False))
        self.assertEqual(env["action"], "terminate")

        # 11) end.py deletes state
        old = sys.argv
        sys.argv = ["end.py", "--reason", "remote-triggered"]
        rc, env, _ = self._run(end.main)
        sys.argv = old
        self.assertEqual(env["action"], "ended")
        self.assertIsNone(load_state(SID))

        # 12) stop-hook silent after end
        sys.stdin = io.StringIO(json.dumps({"session_id": SID}))
        _, _, hout = self._run(hook.main)
        sys.stdin = _stdin
        self.assertEqual(hout.strip(), "")


if __name__ == "__main__":
    unittest.main()
