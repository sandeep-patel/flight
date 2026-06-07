"""Shared test fixtures and in-memory fakes for the domain ports."""

from __future__ import annotations

from datetime import date

import pytest

from flight_tracker.domain.entities import (
    CabinClass,
    FareType,
    FlightOffer,
    FlightSearchQuery,
    PassengerMix,
    SearchResult,
)
from flight_tracker.domain.ports import FlightProviderError


class FakeProvider:
    """In-memory ``FlightProvider`` returning canned results."""

    def __init__(self, result: SearchResult | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls = 0

    async def search(self, query: FlightSearchQuery) -> SearchResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._result is not None:
            return self._result
        return SearchResult(query=query, offers=())


class RecordingNotifier:
    """In-memory ``Notifier`` that records the messages it is sent."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


@pytest.fixture
def query() -> FlightSearchQuery:
    return FlightSearchQuery(
        origin="SYD",
        destination="ADL",
        departure_date=date(2025, 8, 8),
        return_date=date(2025, 8, 11),
        passengers=PassengerMix(adults=3, children=1),
        target_price=60_000,
        fare_type=FareType.POINTS,
        cabin=CabinClass.ECONOMY,
    )


def make_offer(query: FlightSearchQuery, price: float, **kwargs: object) -> FlightOffer:
    return FlightOffer(
        origin=query.origin,
        destination=query.destination,
        departure_date=query.departure_date,
        return_date=query.return_date,
        fare_type=query.fare_type,
        cabin=query.cabin,
        price=price,
        **kwargs,  # type: ignore[arg-type]
    )


__all__ = [
    "FakeProvider",
    "RecordingNotifier",
    "FlightProviderError",
    "make_offer",
]
