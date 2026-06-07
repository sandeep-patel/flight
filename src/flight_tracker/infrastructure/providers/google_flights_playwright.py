"""Google Flights provider backed by Playwright.

Reads **cash fares** from Google Flights for a given route, dates and
passenger mix. Instead of driving the fragile search form (autocomplete,
calendars, overlays), it navigates directly to a results page built from
Google's ``tfs`` deep-link parameter (see :mod:`google_flights_tfs`) and
parses the rendered flight rows.

Caveats
-------
* Google renders client-side and localises aggressively. We pin
  ``hl=en``, ``gl=AU`` and ``curr=AUD`` so prices come back in Australian
  dollars.
* Google does **not** expose airline reward points, so this provider only
  supports :class:`FareType.CASH`.
* Selectors live in :mod:`google_flights_selectors`. On a parse failure a
  screenshot is written to ``screenshots/`` for debugging.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from flight_tracker.domain.entities import (
    FareType,
    FlightOffer,
    FlightSearchQuery,
    SearchResult,
)
from flight_tracker.domain.ports import FlightProviderError
from flight_tracker.infrastructure.providers.google_flights_selectors import (
    DEFAULT_SELECTORS,
    GoogleFlightsSelectors,
)
from flight_tracker.infrastructure.providers.google_flights_tfs import build_results_url

logger = logging.getLogger(__name__)

_PRICE = re.compile(r"(?:A\$|AU\$|\$)\s*([\d,]+)(?:\.(\d{2}))?")
_TIME = re.compile(r"\b(\d{1,2}:\d{2})\s?([AP]M)\b", re.IGNORECASE)
# Airline(s) sit between the arrival time and the journey duration, e.g.
# "8:10 AM Jetstar 2 hr 15 min" -> "Jetstar".
_AIRLINE = re.compile(
    r"[AP]M\s*[|\s]*([A-Za-z][A-Za-z0-9 ,&'-]+?)\s*\d+\s*hr", re.IGNORECASE
)
_STOPS = re.compile(r"\b(Nonstop|\d+\s+stop(?:s)?)\b", re.IGNORECASE)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _parse_price(text: str | None) -> float | None:
    """Extract the first dollar amount from arbitrary price text."""

    if not text:
        return None
    match = _PRICE.search(text.replace("\xa0", " "))
    if not match:
        return None
    whole = match.group(1).replace(",", "")
    cents = match.group(2) or "0"
    try:
        return float(f"{whole}.{cents}")
    except ValueError:
        return None


def _parse_row_text(text: str) -> dict[str, str | float | None]:
    """Parse a Google Flights row's visible text into structured fields."""

    flat = " ".join(text.replace("\xa0", " ").split())
    price = _parse_price(flat)

    times = _TIME.findall(flat)
    departure_time = f"{times[0][0]} {times[0][1].upper()}" if times else None
    arrival_time = f"{times[1][0]} {times[1][1].upper()}" if len(times) > 1 else None

    airline_match = _AIRLINE.search(flat)
    airline = airline_match.group(1).strip() if airline_match else None

    stops_match = _STOPS.search(flat)
    stops = stops_match.group(1) if stops_match else None
    label = " · ".join(p for p in (airline, stops) if p) or None

    return {
        "price": price,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "label": label,
    }


class GoogleFlightsProvider:
    """Implements the ``FlightProvider`` port for Google Flights."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 45_000,
        screenshot_dir: str = "screenshots",
        selectors: GoogleFlightsSelectors = DEFAULT_SELECTORS,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._screenshot_dir = Path(screenshot_dir)
        self._selectors = selectors

    async def search(self, query: FlightSearchQuery) -> SearchResult:
        if query.fare_type is not FareType.CASH:
            raise FlightProviderError(
                "Google Flights only supports cash fares. Use --fare-type cash "
                "(it does not expose airline reward points)."
            )
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await self._new_context(browser)
                page = await context.new_page()
                page.set_default_timeout(self._timeout_ms)
                try:
                    offers = await self._run_flow(page, query)
                finally:
                    await context.close()
                    await browser.close()
            return SearchResult(query=query, offers=tuple(offers))
        except PlaywrightTimeoutError as exc:
            raise FlightProviderError(f"Timed out driving Google Flights: {exc}") from exc
        except FlightProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a provider error
            raise FlightProviderError(f"Google Flights search failed: {exc}") from exc

    # -- browser setup -----------------------------------------------------

    async def _new_context(self, browser: Browser) -> BrowserContext:
        return await browser.new_context(
            user_agent=_USER_AGENT,
            locale="en-AU",
            timezone_id="Australia/Sydney",
            viewport={"width": 1366, "height": 900},
        )

    # -- the flow ----------------------------------------------------------

    async def _run_flow(self, page: Page, query: FlightSearchQuery) -> list[FlightOffer]:
        url = build_results_url(query)
        logger.info(
            "Opening Google Flights results for %s→%s.", query.origin, query.destination
        )
        await page.goto(url, wait_until="domcontentloaded")
        await self._dismiss_consent(page)
        await self._wait_for_results(page)

        offers = await self._parse_results(page, query)
        if not offers:
            await self._capture_failure(page, "no-offers-parsed")
            raise FlightProviderError(
                "No offers parsed. Google Flights' markup likely changed or a "
                "consent wall appeared — see screenshots/ and update selectors."
            )
        logger.info("Parsed %d offer(s).", len(offers))
        return offers

    async def _dismiss_consent(self, page: Page) -> None:
        # Google sometimes interstitials a consent page (consent.google.com).
        for selector in self._selectors.consent_accept_buttons:
            try:
                await page.click(selector, timeout=4_000)
                logger.debug("Dismissed consent via %s", selector)
                await page.wait_for_load_state("domcontentloaded")
                return
            except PlaywrightTimeoutError:
                continue
        logger.debug("No consent dialog to dismiss.")

    async def _wait_for_results(self, page: Page) -> None:
        logger.info("Waiting for results to render.")
        try:
            await page.wait_for_selector(
                self._selectors.flight_row, timeout=self._timeout_ms
            )
        except PlaywrightTimeoutError as exc:
            await self._capture_failure(page, "results-timeout")
            raise FlightProviderError(
                "Results did not load. Google may be showing a consent wall or "
                "blocking automation — see the failure screenshot."
            ) from exc

    # -- parsing -----------------------------------------------------------

    async def _parse_results(
        self, page: Page, query: FlightSearchQuery
    ) -> list[FlightOffer]:
        rows = page.locator(self._selectors.flight_row)
        count = await rows.count()
        logger.info("Found %d result row(s).", count)

        offers: list[FlightOffer] = []
        for i in range(count):
            offer = await self._parse_row(rows.nth(i), query)
            if offer is not None:
                offers.append(offer)
        return offers

    async def _parse_row(
        self, row: Locator, query: FlightSearchQuery
    ) -> FlightOffer | None:
        try:
            text = await row.inner_text()
        except PlaywrightTimeoutError:
            return None

        parsed = _parse_row_text(text)
        price = parsed["price"]
        if not isinstance(price, float):
            return None

        label = parsed["label"]
        departure_time = parsed["departure_time"]
        arrival_time = parsed["arrival_time"]

        return FlightOffer(
            origin=query.origin,
            destination=query.destination,
            departure_date=query.departure_date,
            return_date=query.return_date,
            fare_type=FareType.CASH,
            cabin=query.cabin,
            price=price,
            currency="AUD",
            flight_number=label if isinstance(label, str) else None,
            departure_time=departure_time if isinstance(departure_time, str) else None,
            arrival_time=arrival_time if isinstance(arrival_time, str) else None,
        )

    # -- low-level helpers -------------------------------------------------

    async def _capture_failure(self, page: Page, label: str) -> None:
        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
            path = self._screenshot_dir / f"google-flights-{label}.png"
            await page.screenshot(path=str(path), full_page=True)
            logger.warning("Saved failure screenshot: %s", path)
        except Exception as exc:  # noqa: BLE001 - best-effort diagnostics
            logger.debug("Could not capture screenshot: %s", exc)
