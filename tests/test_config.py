"""Tests for environment-driven configuration."""

from __future__ import annotations

from datetime import date

from flight_tracker.domain.entities import FareType
from flight_tracker.infrastructure.config import AppSettings, SearchSettings, TelegramSettings


def test_default_search_matches_requested_trip(monkeypatch) -> None:
    # Ensure no stray env vars influence defaults.
    for var in (
        "SEARCH_ORIGIN",
        "SEARCH_DESTINATION",
        "SEARCH_ADULTS",
        "SEARCH_CHILDREN",
    ):
        monkeypatch.delenv(var, raising=False)

    search = SearchSettings(_env_file=None)
    query = search.to_query()

    assert query.origin == "SYD"
    assert query.destination == "ADL"
    assert query.departure_date.month == 8 and query.departure_date.day == 8
    assert query.return_date is not None
    assert query.return_date.month == 8 and query.return_date.day == 11
    assert query.passengers.adults == 3
    assert query.passengers.children == 1
    assert query.fare_type is FareType.CASH


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("SEARCH_ORIGIN", "mel")
    monkeypatch.setenv("SEARCH_DESTINATION", "bne")
    monkeypatch.setenv("SEARCH_ADULTS", "2")
    monkeypatch.setenv("SEARCH_DEPARTURE_DATE", "2025-09-01")

    search = SearchSettings(_env_file=None)

    assert search.origin == "MEL"
    assert search.destination == "BNE"
    assert search.adults == 2
    assert search.departure_date == date(2025, 9, 1)


def test_telegram_is_configured(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert TelegramSettings(_env_file=None).is_configured is False

    configured = TelegramSettings(_env_file=None, bot_token="t", chat_id="c")
    assert configured.is_configured is True


def test_blank_optionals_become_none(monkeypatch) -> None:
    # Blank values from a .env line like `APP_MAX_CHECKS=` must not crash.
    monkeypatch.setenv("APP_MAX_CHECKS", "")
    monkeypatch.setenv("SEARCH_RETURN_DATE", "")

    app = AppSettings(_env_file=None)
    search = SearchSettings(_env_file=None)

    assert app.max_checks is None
    assert search.return_date is None
