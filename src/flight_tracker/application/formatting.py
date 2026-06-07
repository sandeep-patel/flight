"""Human-readable formatting for offers and alerts.

Kept in the application layer because it expresses *what* we tell the
user, independent of the delivery channel (Telegram, console, e-mail).
"""

from __future__ import annotations

from flight_tracker.domain.entities import (
    FareType,
    FlightOffer,
    FlightSearchQuery,
    SearchResult,
)


def _unit(fare_type: FareType) -> str:
    return "pts" if fare_type is FareType.POINTS else "AUD"


def format_price(value: float, fare_type: FareType) -> str:
    if fare_type is FareType.POINTS:
        return f"{int(round(value)):,} pts"
    return f"${value:,.2f} AUD"


def describe_query(query: FlightSearchQuery) -> str:
    pax = query.passengers
    pax_parts = [f"{pax.adults} adult{'s' if pax.adults != 1 else ''}"]
    if pax.children:
        pax_parts.append(f"{pax.children} child{'ren' if pax.children != 1 else ''}")
    if pax.infants:
        pax_parts.append(f"{pax.infants} infant{'s' if pax.infants != 1 else ''}")

    when = query.departure_date.strftime("%d %b %Y")
    if query.return_date is not None:
        when += f" → {query.return_date.strftime('%d %b %Y')}"

    return (
        f"{query.origin}→{query.destination} ({query.trip_type.value}) "
        f"{when} · {', '.join(pax_parts)} · {query.cabin.value} · "
        f"{query.fare_type.value}"
    )


def format_offer(offer: FlightOffer) -> str:
    bits = [format_price(offer.price, offer.fare_type)]
    if offer.taxes_aud is not None and offer.fare_type is FareType.POINTS:
        bits.append(f"+ ${offer.taxes_aud:,.2f} taxes")
    if offer.flight_number:
        bits.append(offer.flight_number)
    if offer.departure_time:
        time_range = offer.departure_time
        if offer.arrival_time:
            time_range += f"–{offer.arrival_time}"
        bits.append(time_range)
    if offer.seats_remaining is not None:
        bits.append(f"{offer.seats_remaining} seat(s) left")
    return " · ".join(bits)


def format_alert(result: SearchResult) -> str:
    """Build the Telegram alert body for offers under the target."""

    query = result.query
    matches = result.offers_within_target()
    target = format_price(query.target_price, query.fare_type)

    lines = [
        "✈️ *Flight price alert*",
        f"`{describe_query(query)}`",
        f"Target: *{target}*",
        "",
        f"Found *{len(matches)}* offer(s) at or below target:",
    ]
    for offer in sorted(matches, key=lambda o: o.price)[:10]:
        lines.append(f"• {format_offer(offer)}")

    cheapest = result.cheapest
    if cheapest is not None:
        lines.append("")
        lines.append(f"Cheapest overall: {format_offer(cheapest)}")
    return "\n".join(lines)
