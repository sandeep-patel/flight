"""Tests for the Google Flights provider's pure helpers."""

from __future__ import annotations

import base64
from datetime import date

import pytest

from flight_tracker.domain.entities import (
    CabinClass,
    FareType,
    FlightSearchQuery,
    PassengerMix,
)
from flight_tracker.infrastructure.providers.google_flights_playwright import (
    _parse_price,
    _parse_row_text,
)
from flight_tracker.infrastructure.providers.google_flights_tfs import (
    build_results_url,
    build_tfs,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A$890", 890.0),
        ("$1,234.50", 1234.50),
        ("AU$\xa0249", 249.0),
        ("from A$1,012 round trip", 1012.0),
        ("Price unavailable", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_price(text: str | None, expected: float | None) -> None:
    assert _parse_price(text) == expected


def test_parse_row_text_nonstop() -> None:
    row = "6:25 AM\n–\n8:10 AM\nJetstar\n2 hr 15 min\nSYD–ADL\nNonstop\nA$890\nround trip"
    parsed = _parse_row_text(row)
    assert parsed["price"] == 890.0
    assert parsed["departure_time"] == "6:25 AM"
    assert parsed["arrival_time"] == "8:10 AM"
    assert parsed["label"] == "Jetstar · Nonstop"


def test_parse_row_text_with_stop() -> None:
    row = "6:00 AM – 10:35 AM Qantas 5 hr 5 min SYD–ADL 1 stop 2 hr MEL A$1,375 round trip"
    parsed = _parse_row_text(row)
    assert parsed["price"] == 1375.0
    assert parsed["label"] == "Qantas · 1 stop"


def test_parse_row_text_without_price_returns_none_price() -> None:
    parsed = _parse_row_text("Select flight to see price")
    assert parsed["price"] is None


def _query(**overrides: object) -> FlightSearchQuery:
    base = {
        "origin": "SYD",
        "destination": "ADL",
        "departure_date": date(2026, 8, 8),
        "return_date": date(2026, 8, 11),
        "passengers": PassengerMix(adults=3, children=1),
        "target_price": 300,
        "fare_type": FareType.CASH,
        "cabin": CabinClass.ECONOMY,
    }
    base.update(overrides)
    return FlightSearchQuery(**base)  # type: ignore[arg-type]


def test_build_tfs_is_decodable_and_contains_codes() -> None:
    encoded = build_tfs(_query())
    raw = base64.b64decode(encoded)
    # Airport codes are embedded as UTF-8 strings in the protobuf.
    assert b"SYD" in raw
    assert b"ADL" in raw
    # Both legs encode the ISO dates.
    assert b"2026-08-08" in raw
    assert b"2026-08-11" in raw


def test_build_tfs_one_way_has_single_date() -> None:
    raw = base64.b64decode(build_tfs(_query(return_date=None)))
    assert raw.count(b"2026-08-08") == 1
    assert b"2026-08-11" not in raw


def test_build_results_url_has_expected_params() -> None:
    url = build_results_url(_query())
    assert url.startswith("https://www.google.com/travel/flights?")
    assert "tfs=" in url
    assert "curr=AUD" in url
    assert "hl=en" in url
