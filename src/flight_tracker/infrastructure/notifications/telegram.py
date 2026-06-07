"""Telegram notifier using the Bot HTTP API.

Uses ``httpx`` directly (no heavy SDK) and retries transient failures.
The bot token and chat id come from configuration, never from code.
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends Markdown messages to a Telegram chat."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot_token and chat_id are required.")
        self._chat_id = chat_id
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._timeout = timeout_seconds

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def send(self, message: str) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
            body = response.json()
            if not body.get("ok", False):
                raise httpx.HTTPError(f"Telegram API error: {body}")
        logger.info("Telegram notification sent.")
