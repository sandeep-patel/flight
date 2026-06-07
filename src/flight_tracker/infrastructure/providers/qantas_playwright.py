"""Qantas flight provider backed by Playwright.

Drives the public Qantas booking widget to read **Classic Flight Reward
points** (or cash fares) for a given route, dates and passenger mix.

Important caveats
-----------------
* Qantas renders client-side and employs bot mitigation. Selectors live
  in :mod:`qantas_selectors` and may need tuning against the live DOM.
  Run with ``APP_HEADLESS=false`` to watch the flow, and inspect the
  failure screenshot written to ``screenshots/`` when parsing fails.
* Full Classic Reward availability/pricing is shown to logged-in
  Frequent Flyer members. Provide a saved Playwright ``storage_state``
  JSON (env ``QANTAS_STORAGE_STATE``) captured after logging in once, so
  the scraper reuses an authenticated session.
* This tool automates a site you are entitled to use for your own
  bookings. Respect Qantas's Terms of Use and keep polling intervals
  conservative.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
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
from flight_tracker.infrastructure.providers.qantas_selectors import (
    DEFAULT_SELECTORS,
    QANTAS_BOOKING_URL,
    QantasSelectors,
)

logger = logging.getLogger(__name__)

_NUMERIC = re.compile(r"[\d,]+(?:\.\d+)?")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _parse_number(text: str | None) -> float | None:
    """Extract the first numeric value from arbitrary price text."""

    if not text:
        return None
    match = _NUMERIC.search(text.replace("\xa0", " "))
    if not match:
        return None
    return float(match.group().replace(",", ""))


class QantasFlightProvider:
    """Implements the ``FlightProvider`` port for Qantas."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 45_000,
        storage_state_path: str | None = None,
        screenshot_dir: str = "screenshots",
        selectors: QantasSelectors = DEFAULT_SELECTORS,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._screenshot_dir = Path(screenshot_dir)
        self._selectors = selectors
        # Resolve up-front (sync) so the async flow performs no FS probing.
        self._storage_state_path: str | None = None
        if storage_state_path and Path(storage_state_path).exists():
            self._storage_state_path = storage_state_path

    async def search(self, query: FlightSearchQuery) -> SearchResult:
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
            raise FlightProviderError(f"Timed out driving Qantas: {exc}") from exc
        except FlightProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a provider error
            raise FlightProviderError(f"Qantas search failed: {exc}") from exc

    # -- browser setup -----------------------------------------------------

    async def _new_context(self, browser: Browser) -> BrowserContext:
        if self._storage_state_path:
            logger.info("Reusing authenticated session: %s", self._storage_state_path)
            return await browser.new_context(
                user_agent=_USER_AGENT,
                locale="en-AU",
                viewport={"width": 1366, "height": 900},
                storage_state=self._storage_state_path,
            )
        return await browser.new_context(
            user_agent=_USER_AGENT,
            locale="en-AU",
            viewport={"width": 1366, "height": 900},
        )

    # -- the booking flow --------------------------------------------------

    async def _run_flow(self, page: Page, query: FlightSearchQuery) -> list[FlightOffer]:
        sel = self._selectors
        logger.info("Opening Qantas booking page.")
        await page.goto(QANTAS_BOOKING_URL, wait_until="domcontentloaded")
        await self._dismiss_cookies(page)

        await self._select_trip_type(page, query)
        if query.fare_type is FareType.POINTS:
            await self._enable_points(page)

        await self._fill_place(page, sel.origin_input, query.origin)
        await self._fill_place(page, sel.destination_input, query.destination)

        await self._fill_date(page, sel.departure_date_input, query.departure_date)
        if query.return_date is not None:
            await self._fill_date(page, sel.return_date_input, query.return_date)

        await self._set_passengers(page, query)

        logger.info("Submitting search.")
        await self._click_first(page, sel.search_submit)
        await self._wait_for_results(page)

        offers = await self._parse_results(page, query)
        if not offers:
            await self._capture_failure(page, "no-offers-parsed")
            raise FlightProviderError(
                "No offers parsed. The DOM likely changed or results need an "
                "authenticated session — see screenshots/ and update selectors."
            )
        return offers

    async def _dismiss_cookies(self, page: Page) -> None:
        try:
            await page.click(self._selectors.cookie_accept, timeout=5_000)
            logger.debug("Dismissed cookie banner.")
        except PlaywrightTimeoutError:
            logger.debug("No cookie banner to dismiss.")

    async def _select_trip_type(self, page: Page, query: FlightSearchQuery) -> None:
        target = (
            self._selectors.trip_return
            if query.return_date is not None
            else self._selectors.trip_one_way
        )
        await self._click_first(page, target, optional=True)

    async def _enable_points(self, page: Page) -> None:
        logger.info("Enabling 'Use points'.")
        await self._click_first(page, self._selectors.use_points_toggle, optional=True)

    async def _fill_place(self, page: Page, selector: str, code: str) -> None:
        locator = page.locator(selector).first
        await locator.click()
        await locator.fill("")
        await locator.type(code, delay=80)
        try:
            await page.locator(self._selectors.autocomplete_option).first.click(
                timeout=8_000
            )
        except PlaywrightTimeoutError:
            # Fall back to committing the typed value.
            await locator.press("Enter")

    async def _fill_date(self, page: Page, selector: str, value: date) -> None:
        iso = value.isoformat()
        label = value.strftime("%d %B %Y")
        locator = page.locator(selector).first
        await locator.click()
        # Try a calendar cell first; fall back to typing into the input.
        cell = self._selectors.date_cell.format(iso=iso, label=label)
        try:
            await page.locator(cell).first.click(timeout=6_000)
            return
        except PlaywrightTimeoutError:
            logger.debug("Calendar cell not found for %s; typing instead.", iso)
        await locator.fill(value.strftime("%d/%m/%Y"))
        await locator.press("Enter")

    async def _set_passengers(self, page: Page, query: FlightSearchQuery) -> None:
        sel = self._selectors
        pax = query.passengers
        await self._click_first(page, sel.passenger_open, optional=True)

        # The widget defaults to 1 adult, 0 children, 0 infants.
        await self._click_n(page, sel.adults_increment, pax.adults - 1)
        await self._click_n(page, sel.children_increment, pax.children)
        await self._click_n(page, sel.infants_increment, pax.infants)

        await self._click_first(page, sel.passenger_done, optional=True)

    async def _wait_for_results(self, page: Page) -> None:
        logger.info("Waiting for results to render.")
        try:
            await page.wait_for_selector(
                self._selectors.results_container, timeout=self._timeout_ms
            )
            await page.wait_for_selector(self._selectors.fare_card, timeout=self._timeout_ms)
        except PlaywrightTimeoutError as exc:
            await self._capture_failure(page, "results-timeout")
            raise FlightProviderError(
                "Results did not load. Qantas may be blocking automation or "
                "requires login — see the failure screenshot."
            ) from exc

    # -- parsing -----------------------------------------------------------

    async def _parse_results(
        self, page: Page, query: FlightSearchQuery
    ) -> list[FlightOffer]:
        sel = self._selectors
        cards = page.locator(sel.fare_card)
        count = await cards.count()
        logger.info("Parsing %d result card(s).", count)

        offers: list[FlightOffer] = []
        for i in range(count):
            card = cards.nth(i)
            if query.fare_type is FareType.POINTS:
                price = _parse_number(await self._text(card, sel.points_price))
            else:
                price = _parse_number(await self._text(card, sel.cash_price))
            if price is None:
                continue

            taxes = _parse_number(await self._text(card, sel.taxes_amount))
            seats = _parse_number(await self._text(card, sel.seats_remaining))

            offers.append(
                FlightOffer(
                    origin=query.origin,
                    destination=query.destination,
                    departure_date=query.departure_date,
                    return_date=query.return_date,
                    fare_type=query.fare_type,
                    cabin=query.cabin,
                    price=price,
                    taxes_aud=taxes,
                    flight_number=await self._text(card, sel.flight_number),
                    departure_time=await self._text(card, sel.departure_time),
                    arrival_time=await self._text(card, sel.arrival_time),
                    seats_remaining=int(seats) if seats is not None else None,
                )
            )
        return offers

    # -- low-level helpers -------------------------------------------------

    async def _text(self, scope: object, selector: str) -> str | None:
        try:
            locator = scope.locator(selector).first  # type: ignore[attr-defined]
            if await locator.count() == 0:
                return None
            value = (await locator.inner_text()).strip()
            return value or None
        except PlaywrightTimeoutError:
            return None

    async def _click_first(self, page: Page, selector: str, *, optional: bool = False) -> None:
        try:
            await page.locator(selector).first.click(timeout=self._timeout_ms)
        except PlaywrightTimeoutError:
            if not optional:
                await self._capture_failure(page, "click-failed")
                raise FlightProviderError(f"Could not click selector: {selector}") from None
            logger.debug("Optional click skipped: %s", selector)

    async def _click_n(self, page: Page, selector: str, times: int) -> None:
        for _ in range(max(0, times)):
            await self._click_first(page, selector, optional=True)

    async def _capture_failure(self, page: Page, label: str) -> None:
        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
            path = self._screenshot_dir / f"qantas-{label}.png"
            await page.screenshot(path=str(path), full_page=True)
            logger.warning("Saved failure screenshot: %s", path)
        except Exception as exc:  # noqa: BLE001 - best-effort diagnostics
            logger.debug("Could not capture screenshot: %s", exc)
