"""Tests for domain entities and value-object invariants."""

from __future__ import annotations

from datetime import date

import pytest

from flight_tracker.domain.entities import (
    FareType,
    FlightSearchQuery,
    PassengerMix,
    SearchResult,
    TripType,
)
from tests.conftest import make_offer


def test_passenger_mix_requires_an_adult() -> None:
    with pytest.raises(ValueError, match="At least one adult"):
        PassengerMix(adults=0, children=2)


def test_passenger_mix_infants_need_adults() -> None:
    with pytest.raises(ValueError, match="accompanied by an adult"):
        PassengerMix(adults=1, infants=2)


def test_passenger_total() -> None:
    assert PassengerMix(adults=3, children=1).total == 4


def test_query_rejects_bad_iata() -> None:
    with pytest.raises(ValueError, match="IATA"):
        FlightSearchQuery(
            origin="SYDNEY",
            destination="ADL",
            departure_date=date(2025, 8, 8),
            passengers=PassengerMix(),
            target_price=1000,
        )


def test_query_rejects_same_origin_destination() -> None:
    with pytest.raises(ValueError, match="must differ"):
        FlightSearchQuery(
            origin="SYD",
            destination="SYD",
            departure_date=date(2025, 8, 8),
            passengers=PassengerMix(),
            target_price=1000,
        )


def test_query_rejects_return_before_departure() -> None:
    with pytest.raises(ValueError, match="Return date"):
        FlightSearchQuery(
            origin="SYD",
            destination="ADL",
            departure_date=date(2025, 8, 8),
            return_date=date(2025, 8, 1),
            passengers=PassengerMix(),
            target_price=1000,
        )


def test_trip_type_inference(query: FlightSearchQuery) -> None:
    assert query.trip_type is TripType.RETURN


def test_offers_within_target_and_cheapest(query: FlightSearchQuery) -> None:
    cheap = make_offer(query, price=45_000)
    over = make_offer(query, price=80_000)
    result = SearchResult(query=query, offers=(over, cheap))

    assert result.cheapest is cheap
    assert result.offers_within_target() == (cheap,)


def test_offer_is_within() -> None:
    query = FlightSearchQuery(
        origin="SYD",
        destination="ADL",
        departure_date=date(2025, 8, 8),
        passengers=PassengerMix(),
        target_price=50_000,
        fare_type=FareType.POINTS,
    )
    assert make_offer(query, price=50_000).is_within(50_000)
    assert not make_offer(query, price=50_001).is_within(50_000)
