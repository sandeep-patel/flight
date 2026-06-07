"""Tests for the PriceMonitor use case using in-memory fakes."""

from __future__ import annotations

import pytest

from flight_tracker.application.price_monitor import PriceMonitor
from flight_tracker.domain.entities import FlightSearchQuery, SearchResult
from flight_tracker.domain.ports import FlightProviderError
from tests.conftest import FakeProvider, RecordingNotifier, make_offer


async def test_notifies_when_offer_under_target(query: FlightSearchQuery) -> None:
    result = SearchResult(query=query, offers=(make_offer(query, price=45_000),))
    notifier = RecordingNotifier()
    monitor = PriceMonitor(FakeProvider(result), notifier)

    outcome = await monitor.check_once(query)

    assert outcome.notified is True
    assert len(notifier.messages) == 1
    assert "45,000 pts" in notifier.messages[0]


async def test_silent_when_no_offer_under_target(query: FlightSearchQuery) -> None:
    result = SearchResult(query=query, offers=(make_offer(query, price=99_000),))
    notifier = RecordingNotifier()
    monitor = PriceMonitor(FakeProvider(result), notifier)

    outcome = await monitor.check_once(query)

    assert outcome.notified is False
    assert notifier.messages == []


async def test_notify_on_no_match(query: FlightSearchQuery) -> None:
    result = SearchResult(query=query, offers=(make_offer(query, price=99_000),))
    notifier = RecordingNotifier()
    monitor = PriceMonitor(FakeProvider(result), notifier, notify_on_no_match=True)

    outcome = await monitor.check_once(query)

    assert outcome.notified is True
    assert "No offers under target" in notifier.messages[0]


async def test_run_forever_stops_after_alert(query: FlightSearchQuery) -> None:
    result = SearchResult(query=query, offers=(make_offer(query, price=45_000),))
    provider = FakeProvider(result)
    notifier = RecordingNotifier()
    monitor = PriceMonitor(provider, notifier)

    await monitor.run_forever(query, interval_seconds=0, notify_once=True)

    assert provider.calls == 1
    assert len(notifier.messages) == 1


async def test_run_forever_retries_on_provider_error(query: FlightSearchQuery) -> None:
    provider = FakeProvider(error=FlightProviderError("boom"))
    notifier = RecordingNotifier()
    monitor = PriceMonitor(provider, notifier)

    # Should not raise; errors are logged and the loop stops at max_checks.
    await monitor.run_forever(query, interval_seconds=0, max_checks=2)

    assert provider.calls == 2
    assert notifier.messages == []


@pytest.mark.parametrize("max_checks", [1, 3])
async def test_run_forever_respects_max_checks(
    query: FlightSearchQuery, max_checks: int
) -> None:
    # Offers above target so it never stops early.
    result = SearchResult(query=query, offers=(make_offer(query, price=99_000),))
    provider = FakeProvider(result)
    monitor = PriceMonitor(provider, RecordingNotifier())

    await monitor.run_forever(query, interval_seconds=0, max_checks=max_checks)

    assert provider.calls == max_checks
