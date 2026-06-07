"""Factory that builds a configured ``FlightProvider`` by name.

Keeps the composition root (``cli.py``) free of per-provider wiring and
makes it trivial to add new airlines: implement the port, then register
the builder here.
"""

from __future__ import annotations

from enum import StrEnum

from flight_tracker.domain.ports import FlightProvider
from flight_tracker.infrastructure.config import AppSettings, QantasSettings
from flight_tracker.infrastructure.providers.google_flights_playwright import (
    GoogleFlightsProvider,
)
from flight_tracker.infrastructure.providers.qantas_playwright import QantasFlightProvider


class ProviderName(StrEnum):
    """Supported flight data sources."""

    GOOGLE = "google"
    QANTAS = "qantas"


def build_provider(
    name: ProviderName,
    app: AppSettings,
    qantas: QantasSettings,
) -> FlightProvider:
    """Construct the requested provider with runtime settings applied."""

    if name is ProviderName.GOOGLE:
        return GoogleFlightsProvider(
            headless=app.headless,
            timeout_ms=app.request_timeout_ms,
            screenshot_dir=qantas.screenshot_dir,
        )
    if name is ProviderName.QANTAS:
        return QantasFlightProvider(
            headless=app.headless,
            timeout_ms=app.request_timeout_ms,
            storage_state_path=qantas.storage_state,
            screenshot_dir=qantas.screenshot_dir,
        )
    raise ValueError(f"Unknown provider: {name}")  # pragma: no cover
