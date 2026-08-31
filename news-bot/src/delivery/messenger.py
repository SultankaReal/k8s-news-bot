"""
Delivery module — Yandex Messenger Bot API + optional Telegram fallback.

Yandex Messenger Bot API docs:
  https://yandex.ru/dev/messenger/doc/ru/api-requests/message-send-text
"""
import logging
from typing import Optional

import requests

from ..config import get_config

log = logging.getLogger(__name__)

MESSENGER_API = "https://botapi.messenger.yandex.net/bot/v1"
MAX_MESSAGE_LEN = 4096  # Messenger limit per message


def _split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Split long text into chunks, preferring newline boundaries."""
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        # find last newline within limit
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


def send_to_messenger(text: str, chat_id: Optional[str] = None) -> bool:
    """Send text message to Yandex Messenger channel/chat via bot."""
    cfg = get_config()
    token = cfg.messenger_token
    target_chat_id = chat_id or cfg.messenger_chat_id

    if not token or not target_chat_id:
        log.error("Messenger: token or chat_id not configured")
        return False

    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
    }

    chunks = _split_message(text)
    success = True

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": target_chat_id,
            "text": chunk,
        }
        try:
            resp = requests.post(
                f"{MESSENGER_API}/messages/sendText/",
                json=payload,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                log.error(
                    "Messenger API error (chunk %d/%d): %s",
                    i + 1, len(chunks), data
                )
                success = False
            else:
                log.info("Messenger: sent chunk %d/%d to %s", i + 1, len(chunks), target_chat_id)
        except Exception as exc:
            log.error("Messenger send failed (chunk %d/%d): %s", i + 1, len(chunks), exc)
            success = False

    return success


def send_to_telegram(text: str, chat_id: Optional[str] = None) -> bool:
    """Optional Telegram fallback."""
    cfg = get_config()
    token = cfg.telegram_token
    target = chat_id or cfg.telegram_chat_id

    if not token or not target:
        return False

    chunks = _split_message(text)
    success = True

    for chunk in chunks:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": target, "text": chunk, "parse_mode": "Markdown"},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.error("Telegram send failed: %s", exc)
            success = False

    return success


def deliver(text: str) -> bool:
    """Send to all configured channels."""
    ok = False
    if get_config().messenger_token:
        ok = send_to_messenger(text) or ok
    if get_config().telegram_token:
        ok = send_to_telegram(text) or ok
    return ok
