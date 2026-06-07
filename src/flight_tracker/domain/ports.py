"""Ports: the abstract interfaces the application depends on.

Infrastructure adapters implement these. The application layer depends
only on these abstractions, never on concrete adapters, keeping the
core testable and provider-agnostic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flight_tracker.domain.entities import FlightSearchQuery, SearchResult


class FlightProviderError(RuntimeError):
    """Raised when a provider fails to produce a result."""


@runtime_checkable
class FlightProvider(Protocol):
    """Source of flight offers (e.g. a Qantas Playwright scraper)."""

    async def search(self, query: FlightSearchQuery) -> SearchResult:
        """Return all offers matching ``query``.

        Implementations should raise :class:`FlightProviderError` on an
        unrecoverable failure rather than returning partial data.
        """
        ...


@runtime_checkable
class Notifier(Protocol):
    """Delivers a message to the user (e.g. Telegram)."""

    async def send(self, message: str) -> None:
        """Deliver ``message``. May raise on transport failure."""
        ...
