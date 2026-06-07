"""Selectors and constants for the Google Flights results page.

Centralised so they can be updated in one place when Google changes its
markup. The provider navigates to a ``tfs`` deep-link results URL (see
:mod:`google_flights_tfs`), so we only need consent-dismissal and
result-row selectors here.

Run with ``APP_HEADLESS=false`` to watch the flow and inspect the failure
screenshot in ``screenshots/`` when parsing breaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GoogleFlightsSelectors:
    """CSS / role selectors for the results page."""

    # Consent / cookie interstitial (consent.google.com or inline dialog).
    consent_accept_buttons: tuple[str, ...] = field(
        default_factory=lambda: (
            "button[aria-label*='Accept all']",
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "form[action*='consent'] button",
        )
    )

    # A single flight result row. ``li.pIav2d`` is Google's current result
    # row class; the ``ul.Rk10dc`` descendant is a structural fallback.
    flight_row: str = "li.pIav2d, ul.Rk10dc > li[role='listitem']"


DEFAULT_SELECTORS = GoogleFlightsSelectors()

