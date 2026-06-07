"""Tests for the numeric parser used by the Qantas provider."""

from __future__ import annotations

import pytest

from flight_tracker.infrastructure.providers.qantas_playwright import _parse_number


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("45,000 pts", 45000.0),
        ("From 12,500 points", 12500.0),
        ("$121.30 taxes & carrier charges", 121.30),
        ("\xa099,800\xa0pts", 99800.0),
        ("4 seats left", 4.0),
        (None, None),
        ("Sold out", None),
        ("", None),
    ],
)
def test_parse_number(text: str | None, expected: float | None) -> None:
    assert _parse_number(text) == expected
