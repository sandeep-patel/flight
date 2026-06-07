"""Logging configuration."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with a concise, timestamped format."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Playwright's internal logging is noisy at DEBUG; keep it at WARNING.
    logging.getLogger("playwright").setLevel(logging.WARNING)
