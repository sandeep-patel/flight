"""Selectors and constants for the Qantas booking flow.

These are deliberately centralised so they can be updated in one place
when Qantas changes its markup. Each selector lists a few fallbacks
(joined with ``, ``) so the scraper survives minor DOM changes.

Note: Qantas is a heavily client-rendered, anti-bot-protected site and
its DOM changes frequently. Treat these as a starting point and verify
against the live page (run with ``APP_HEADLESS=false`` to watch).
"""

from __future__ import annotations

from dataclasses import dataclass

# Public booking widget entry point.
QANTAS_BOOKING_URL = "https://www.qantas.com/au/en/book-a-trip/flights.html"


@dataclass(frozen=True, slots=True)
class QantasSelectors:
    """CSS / role selectors for the booking widget and results page."""

    # Cookie / consent banner.
    cookie_accept: str = (
        "button#cookie-banner-accept, button[data-testid='cookie-accept'], "
        "button:has-text('Accept all')"
    )

    # Trip type toggles.
    trip_return: str = "label:has-text('Return'), [data-testid='trip-type-return']"
    trip_one_way: str = "label:has-text('One way'), [data-testid='trip-type-oneway']"

    # "Use points" / classic rewards toggle.
    use_points_toggle: str = (
        "[data-testid='usePoints'], label:has-text('Use points'), "
        "input[name='payWith'][value='points']"
    )

    # Origin / destination autocomplete.
    origin_input: str = "input#flights-from, input[name='from'], [data-testid='origin-input']"
    destination_input: str = "input#flights-to, input[name='to'], [data-testid='destination-input']"
    autocomplete_option: str = "[role='option'], li[data-testid='autocomplete-option']"

    # Date pickers.
    departure_date_input: str = (
        "input#flights-departing, input[name='departureDate'], [data-testid='departure-date']"
    )
    return_date_input: str = (
        "input#flights-returning, input[name='returnDate'], [data-testid='return-date']"
    )
    date_cell: str = "td[data-date='{iso}'] button, button[aria-label*='{label}']"

    # Passenger selector.
    passenger_open: str = "[data-testid='passengers'], button:has-text('Passenger')"
    adults_increment: str = (
        "[data-testid='adults-increment'], button[aria-label*='Increase adults']"
    )
    children_increment: str = (
        "[data-testid='children-increment'], button[aria-label*='Increase children']"
    )
    infants_increment: str = (
        "[data-testid='infants-increment'], button[aria-label*='Increase infants']"
    )
    passenger_done: str = "[data-testid='passengers-done'], button:has-text('Done')"

    # Search submit.
    search_submit: str = (
        "button[type='submit']:has-text('Search'), [data-testid='search-flights']"
    )

    # Results.
    results_container: str = (
        "[data-testid='flight-results'], main:has-text('Select your flight')"
    )
    fare_card: str = "[data-testid='flight-card'], li.flight-result, article.flight-card"
    points_price: str = (
        "[data-testid='points-amount'], .points-amount, span:has-text('pts')"
    )
    cash_price: str = "[data-testid='cash-amount'], .cash-amount, span:has-text('$')"
    taxes_amount: str = "[data-testid='taxes-amount'], .taxes, span:has-text('taxes')"
    flight_number: str = "[data-testid='flight-number'], .flight-number"
    departure_time: str = "[data-testid='departure-time'], .departure-time"
    arrival_time: str = "[data-testid='arrival-time'], .arrival-time"
    seats_remaining: str = "[data-testid='seats-remaining'], .seats-left"


DEFAULT_SELECTORS = QantasSelectors()
