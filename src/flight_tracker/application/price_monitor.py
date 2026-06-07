"""The price-monitoring use case.

Runs a single check (search → filter → notify) and, optionally, a polling
loop. It depends only on the :class:`FlightProvider` and :class:`Notifier`
ports, so it can be unit-tested with fakes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from flight_tracker.application.formatting import describe_query, format_alert, format_offer
from flight_tracker.domain.entities import FlightSearchQuery, SearchResult
from flight_tracker.domain.ports import FlightProvider, FlightProviderError, Notifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """The result of a single monitoring check."""

    result: SearchResult
    notified: bool


class PriceMonitor:
    """Coordinates a flight provider and a notifier around a query."""

    def __init__(
        self,
        provider: FlightProvider,
        notifier: Notifier,
        *,
        notify_on_no_match: bool = False,
    ) -> None:
        self._provider = provider
        self._notifier = notifier
        self._notify_on_no_match = notify_on_no_match

    async def check_once(self, query: FlightSearchQuery) -> CheckOutcome:
        """Run one search and notify if any offer beats the target."""

        logger.info("Searching: %s", describe_query(query))
        result = await self._provider.search(query)
        matches = result.offers_within_target()

        cheapest = result.cheapest
        if cheapest is not None:
            logger.info(
                "Found %d offer(s); cheapest = %s",
                len(result.offers),
                format_offer(cheapest),
            )
        else:
            logger.info("No offers returned for this query.")

        if matches:
            logger.info("%d offer(s) at/below target — notifying.", len(matches))
            await self._notifier.send(format_alert(result))
            return CheckOutcome(result=result, notified=True)

        if self._notify_on_no_match:
            await self._notifier.send(
                f"No offers under target yet for {describe_query(query)}."
                + (f" Cheapest: {format_offer(cheapest)}." if cheapest else "")
            )
            return CheckOutcome(result=result, notified=True)

        return CheckOutcome(result=result, notified=False)

    async def run_forever(
        self,
        query: FlightSearchQuery,
        *,
        interval_seconds: int,
        max_checks: int | None = None,
        notify_once: bool = True,
    ) -> None:
        """Poll on a fixed interval until cancelled or ``max_checks`` hit.

        If ``notify_once`` is True the loop stops after the first
        successful alert (useful for a one-shot "tell me when it drops"
        watch). Provider errors are logged and retried on the next tick.
        """

        checks = 0
        while max_checks is None or checks < max_checks:
            checks += 1
            try:
                outcome = await self.check_once(query)
            except FlightProviderError:
                logger.exception("Provider failed on check %d; will retry.", checks)
            else:
                if outcome.notified and notify_once:
                    logger.info("Target met and alert sent — stopping watch.")
                    return

            if max_checks is not None and checks >= max_checks:
                break

            logger.info("Sleeping %ds before next check (#%d).", interval_seconds, checks + 1)
            await asyncio.sleep(interval_seconds)
