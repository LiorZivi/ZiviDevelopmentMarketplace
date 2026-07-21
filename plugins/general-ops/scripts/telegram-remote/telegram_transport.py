"""Telegram Bot API transport for the ``telegram-remote`` skill.

Pure standard library (``urllib``) — no third-party deps, no ``pip install``.
This is deliberately much smaller than the ``teams-remote`` transport: the
Telegram Bot API is a single bearer-in-URL HTTPS endpoint with no OAuth, no
token refresh, and no SSE. Two primitives cover the whole skill:

* :func:`send_message` — ``POST /sendMessage`` (outbound: root post, acks,
  questions, progress, summary). Plain text, chunked at Telegram's 4096 limit.
* :func:`send_document` — multipart ``POST /sendDocument`` for requested local
  files up to Telegram's 50 MB bot limit.
* :func:`get_updates` — ``GET /getUpdates?offset&timeout`` long-poll (inbound:
  the user's replies in the bot DM).

**Why there is no self-filtering.** ``getUpdates`` only ever returns *incoming*
updates (messages sent *to* the bot). The bot's own outbound ``sendMessage``
calls never come back through ``getUpdates``. So — unlike the Teams MCP path,
which attributes the agent's own posts to the signed-in user — de-duplication
here is purely a monotonic ``update_id`` offset. No ``own_message_ids`` set is
needed.

**Single-consumer caveat.** ``getUpdates`` is a single-consumer model per bot
token: two pollers on the same token steal each other's updates (HTTP 409
``Conflict``). Reusing a bot that only ever *sends* (e.g. the BDV notifier) is
fine because it never calls ``getUpdates``; running two ``telegram-remote``
sessions on the same token at once is not.

Credential resolution (first hit wins):
  1. env ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID``
  2. ``<cwd>/.github/telegram-remote.json``
  3. ``~/.copilot/telegram-remote.json``
  keys: ``botToken``/``bot_token`` and ``chatId``/``chat_id``.

CLI helpers (for setup / smoke tests):
  ``python telegram_transport.py discover``  — list chats that have recently
      messaged the bot, so you can copy your DM ``chat_id``.
  ``python telegram_transport.py send "text"`` — send one message to the
      configured chat.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

API_BASE = "https://api.telegram.org"
TELEGRAM_LIMIT = 4096
DEFAULT_LONG_POLL_TIMEOUT = 50  # seconds, server-side long-poll per request
_NETWORK_SLACK = 15  # urlopen timeout must exceed the long-poll timeout


class TelegramError(Exception):
    """Any Bot API failure (transport error or ``ok: false`` response)."""

    def __init__(self, message: str, *, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code

    @property
    def is_conflict(self) -> bool:
        """True for HTTP 409 — a webhook is set or another poller is running.

        This does not self-resolve, so callers should surface it to the user
        rather than silently retrying.
        """
        if self.code == 409:
            return True
        return "conflict" in str(self).lower()


# --------------------------------------------------------------------------- #
# Credential resolution
# --------------------------------------------------------------------------- #
def _read_config_file() -> dict:
    candidates = [
        Path(os.getcwd()) / ".github" / "telegram-remote.json",
        Path.home() / ".copilot" / "telegram-remote.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
    return {}


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """Return ``(bot_token, chat_id)`` from env then config file. Either may be None."""
    cfg = _read_config_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or cfg.get("botToken") or cfg.get("bot_token")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or cfg.get("chatId") or cfg.get("chat_id")
    token = token.strip() if isinstance(token, str) else token
    chat = str(chat).strip() if chat is not None else None
    return (token or None), (chat or None)


# --------------------------------------------------------------------------- #
# Low-level API call
# --------------------------------------------------------------------------- #
def _api_call(token: str, method: str, params: dict, timeout: float):
    if not token:
        raise TelegramError("no bot token configured")
    url = f"{API_BASE}/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)  # POST
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Telegram returns a JSON body with `description` even on 4xx.
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            raise TelegramError(f"HTTP {exc.code}", code=exc.code) from exc
        raise TelegramError(
            body.get("description", f"HTTP {exc.code}"), code=exc.code
        )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise TelegramError(str(exc)) from exc
    if not isinstance(body, dict) or not body.get("ok"):
        desc = body.get("description") if isinstance(body, dict) else "malformed response"
        raise TelegramError(desc or "unknown Bot API error")
    return body.get("result")


def _chunk(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    text = text or ""
    if len(text) <= limit:
        return [text] if text else [""]
    parts: list[str] = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


def send_message(token: str, chat_id: str, text: str, *, timeout: float = 15.0) -> dict:
    """Send ``text`` to ``chat_id`` as plain text. Returns the LAST message dict.

    Plain text (no ``parse_mode``) is intentional: control messages contain
    file paths, code, and punctuation that MarkdownV2 would force us to escape.
    Long messages are split across the 4096-char limit.
    """
    result: dict = {}
    for chunk in _chunk(text):
        result = _api_call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": "true",
            },
            timeout,
        )
    return result or {}


def send_document(
    token: str,
    chat_id: str,
    file_path: str,
    *,
    caption: str = "",
    timeout: float = 60.0,
) -> dict:
    """Upload one local file to ``chat_id`` through Telegram ``sendDocument``."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise TelegramError(f"document not found: {path}")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise TelegramError("document exceeds Telegram's 50 MB bot upload limit")

    boundary = f"----telegram-remote-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
            str(value).encode("utf-8"),
            b"\r\n",
        ])

    add_field("chat_id", chat_id)
    if caption:
        add_field("caption", caption[:1024])

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode("ascii"),
        (
            f'Content-Disposition: form-data; name="document"; '
            f'filename="{path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
        path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ])

    url = f"{API_BASE}/bot{token}/sendDocument"
    request = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            raise TelegramError(f"HTTP {exc.code}", code=exc.code) from exc
        raise TelegramError(
            body.get("description", f"HTTP {exc.code}"), code=exc.code
        )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise TelegramError(str(exc)) from exc

    if not isinstance(body, dict) or not body.get("ok"):
        description = body.get("description") if isinstance(body, dict) else "malformed response"
        raise TelegramError(description or "unknown Bot API error")
    result = body.get("result")
    return result if isinstance(result, dict) else {}


def get_updates(
    token: str,
    offset: Optional[int],
    *,
    timeout: int = DEFAULT_LONG_POLL_TIMEOUT,
) -> list[dict]:
    """Long-poll for new updates. Returns a list of raw update dicts.

    ``offset`` should be ``last_update_id + 1``. Passing it confirms (drops)
    every update with a smaller id, so we never re-receive processed messages.
    ``allowed_updates`` is restricted to ``message`` — we only care about the
    user typing in the DM.
    """
    params: dict = {
        "timeout": int(timeout),
        "allowed_updates": json.dumps(["message"]),
    }
    if offset is not None:
        params["offset"] = int(offset)
    # The socket timeout must outlast the server-side long-poll window.
    result = _api_call(token, "getUpdates", params, timeout + _NETWORK_SLACK)
    return result if isinstance(result, list) else []


def delete_webhook(token: str, *, timeout: float = 15.0) -> None:
    """Best-effort ``deleteWebhook`` so ``getUpdates`` can be used.

    Only call this when the caller has confirmed the bot is not relying on a
    webhook elsewhere. Not used automatically by the skill.
    """
    _api_call(token, "deleteWebhook", {"drop_pending_updates": "false"}, timeout)


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def parse_message(update: dict) -> Optional[dict]:
    """Normalise a raw update into ``{update_id, id, text, sender, timestamp}``.

    Returns None for updates that are not plain text messages. ``id`` is the
    string ``message_id`` (parallels teams-remote's reply id); ``timestamp`` is
    the ISO-8601 form of the Telegram ``date`` (unix seconds).
    """
    if not isinstance(update, dict):
        return None
    msg = update.get("message")
    if not isinstance(msg, dict):
        return None
    text = msg.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    frm = msg.get("from") or {}
    sender = (
        frm.get("username")
        or " ".join(p for p in (frm.get("first_name"), frm.get("last_name")) if p)
        or str(frm.get("id", "unknown"))
    )
    import datetime as _dt

    ts = msg.get("date")
    iso = ""
    if isinstance(ts, (int, float)):
        iso = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat()
    return {
        "update_id": update.get("update_id"),
        "id": str(msg.get("message_id", "")),
        "text": text,
        "sender": sender,
        "timestamp": iso,
        "chat_id": str((msg.get("chat") or {}).get("id", "")),
    }


# --------------------------------------------------------------------------- #
# CLI helpers (setup / smoke test)
# --------------------------------------------------------------------------- #
def _cli_discover() -> int:
    token, _ = load_credentials()
    if not token:
        sys.stderr.write("No TELEGRAM_BOT_TOKEN configured.\n")
        return 2
    try:
        updates = get_updates(token, None, timeout=0)
    except TelegramError as exc:
        sys.stderr.write(f"getUpdates failed: {exc}\n")
        if exc.is_conflict:
            sys.stderr.write(
                "409 Conflict: the bot has a webhook set or another getUpdates "
                "consumer is running. Remove the webhook or stop the other poller.\n"
            )
        return 1
    chats: dict[str, dict] = {}
    for up in updates:
        norm = parse_message(up)
        if not norm or not norm["chat_id"]:
            continue
        chats[norm["chat_id"]] = {"sender": norm["sender"], "last_text": norm["text"][:40]}
    if not chats:
        print("No recent messages. Send a message to your bot in Telegram, then re-run.")
        return 0
    print("Chats that recently messaged this bot:")
    for cid, info in chats.items():
        print(f"  chat_id={cid}  from={info['sender']}  last={info['last_text']!r}")
    print("\nCopy your DM chat_id into TELEGRAM_CHAT_ID or ~/.copilot/telegram-remote.json.")
    return 0


def _cli_send(text: str) -> int:
    token, chat = load_credentials()
    if not token or not chat:
        sys.stderr.write("Need both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.\n")
        return 2
    try:
        res = send_message(token, chat, text)
    except TelegramError as exc:
        sys.stderr.write(f"send failed: {exc}\n")
        return 1
    print(f"sent message_id={res.get('message_id')}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "discover":
        raise SystemExit(_cli_discover())
    if len(sys.argv) >= 3 and sys.argv[1] == "send":
        raise SystemExit(_cli_send(sys.argv[2]))
    sys.stderr.write(
        "usage:\n"
        "  python telegram_transport.py discover\n"
        '  python telegram_transport.py send "text"\n'
    )
    raise SystemExit(2)
