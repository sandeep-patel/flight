"""Command-line entry point and composition root.

This module is the only place that wires concrete adapters to the
application use case. It parses CLI flags (which override ``.env``
defaults), builds the dependency graph, and runs the monitor.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime

from flight_tracker.application.price_monitor import PriceMonitor
from flight_tracker.domain.entities import (
    CabinClass,
    FareType,
    FlightSearchQuery,
    PassengerMix,
)
from flight_tracker.domain.ports import Notifier
from flight_tracker.infrastructure.config import (
    AppSettings,
    SearchSettings,
    TelegramSettings,
    load_settings,
)
from flight_tracker.infrastructure.logging_config import configure_logging
from flight_tracker.infrastructure.notifications.console import ConsoleNotifier
from flight_tracker.infrastructure.notifications.telegram import TelegramNotifier
from flight_tracker.infrastructure.providers.factory import ProviderName, build_provider

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - argparse surfaces this
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM-DD."
        ) from exc


def _build_arg_parser(search: SearchSettings, app: AppSettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flight-tracker",
        description="Watch flight fares (Google Flights / Qantas) and alert via Telegram.",
    )
    parser.add_argument(
        "--provider",
        type=ProviderName,
        choices=list(ProviderName),
        default=ProviderName.GOOGLE,
        help="Data source: 'google' (cash, default) or 'qantas' (reward points).",
    )
    parser.add_argument("--origin", default=search.origin, help="3-letter IATA, e.g. SYD.")
    parser.add_argument(
        "--destination", default=search.destination, help="3-letter IATA, e.g. ADL."
    )
    parser.add_argument(
        "--depart",
        type=_parse_date,
        default=search.departure_date,
        help="Departure date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--return",
        dest="return_date",
        type=_parse_date,
        default=search.return_date,
        help="Return date YYYY-MM-DD (omit for one-way).",
    )
    parser.add_argument("--adults", type=int, default=search.adults)
    parser.add_argument("--children", type=int, default=search.children)
    parser.add_argument("--infants", type=int, default=search.infants)
    parser.add_argument(
        "--cabin",
        type=CabinClass,
        choices=list(CabinClass),
        default=search.cabin,
    )
    parser.add_argument(
        "--fare-type",
        type=FareType,
        choices=list(FareType),
        default=search.fare_type,
        help="'cash' (Google Flights) or 'points' (Qantas Classic Rewards).",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=search.target_price,
        help="Alert threshold: points if fare-type=points, else AUD.",
    )
    parser.add_argument("--once", action="store_true", help="Run a single check and exit.")
    parser.add_argument(
        "--interval",
        type=int,
        default=app.poll_interval_seconds,
        help="Seconds between checks when polling.",
    )
    parser.add_argument(
        "--max-checks",
        type=int,
        default=app.max_checks,
        help="Stop after this many checks (default: unlimited).",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        default=app.headless,
        help="Show the browser window (useful for debugging selectors).",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Print alerts to the console instead of Telegram.",
    )
    return parser


def _build_query(args: argparse.Namespace) -> FlightSearchQuery:
    return FlightSearchQuery(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.depart,
        return_date=args.return_date,
        passengers=PassengerMix(
            adults=args.adults, children=args.children, infants=args.infants
        ),
        target_price=args.target,
        fare_type=args.fare_type,
        cabin=args.cabin,
    )


def _build_notifier(args: argparse.Namespace, telegram: TelegramSettings) -> Notifier:
    if args.console or not telegram.is_configured:
        if not args.console:
            logger.warning(
                "Telegram is not configured — falling back to console output. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable alerts."
            )
        return ConsoleNotifier()
    return TelegramNotifier(telegram.bot_token, telegram.chat_id)


async def _run(args: argparse.Namespace) -> None:
    app, _, telegram, qantas = load_settings()

    query = _build_query(args)
    notifier = _build_notifier(args, telegram)
    provider = build_provider(args.provider, app, qantas)
    monitor = PriceMonitor(
        provider,
        notifier,
        notify_on_no_match=app.notify_on_no_match,
    )

    if args.once:
        await monitor.check_once(query)
        return

    await monitor.run_forever(
        query,
        interval_seconds=args.interval,
        max_checks=args.max_checks,
    )


def main() -> None:
    app, search, telegram, _ = load_settings()
    configure_logging(app.log_level)

    parser = _build_arg_parser(search, app)
    args = parser.parse_args()

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        logger.info("Interrupted — exiting.")


if __name__ == "__main__":
    main()
