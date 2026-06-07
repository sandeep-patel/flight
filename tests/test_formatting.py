"""Tests for alert/offer formatting."""

from __future__ import annotations

from flight_tracker.application.formatting import (
    describe_query,
    format_alert,
    format_offer,
    format_price,
)
from flight_tracker.domain.entities import (
    FareType,
    FlightSearchQuery,
    SearchResult,
)
from tests.conftest import make_offer


def test_format_price_points_and_cash() -> None:
    assert format_price(45000, FareType.POINTS) == "45,000 pts"
    assert format_price(199.5, FareType.CASH) == "$199.50 AUD"


def test_describe_query(query: FlightSearchQuery) -> None:
    text = describe_query(query)
    assert "SYD→ADL" in text
    assert "3 adults" in text
    assert "1 child" in text
    assert "points" in text


def test_format_offer_includes_taxes(query: FlightSearchQuery) -> None:
    offer = make_offer(
        query,
        price=45_000,
        taxes_aud=121.30,
        flight_number="QF741",
        departure_time="06:00",
        arrival_time="08:05",
        seats_remaining=4,
    )
    text = format_offer(offer)
    assert "45,000 pts" in text
    assert "121.30 taxes" in text
    assert "QF741" in text
    assert "06:00–08:05" in text
    assert "4 seat(s) left" in text


def test_format_alert_lists_matches(query: FlightSearchQuery) -> None:
    offers = (make_offer(query, price=45_000), make_offer(query, price=99_000))
    alert = format_alert(SearchResult(query=query, offers=offers))
    assert "Flight price alert" in alert
    assert "Found *1* offer" in alert
    assert "45,000 pts" in alert
