"""Console notifier — a no-credentials fallback for local testing."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ConsoleNotifier:
    """Prints alerts to stdout. Implements the ``Notifier`` port."""

    async def send(self, message: str) -> None:
        print("\n" + "=" * 60)
        print(message)
        print("=" * 60 + "\n")
        logger.info("Console notification emitted.")
