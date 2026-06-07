"""Build Google Flights ``tfs`` deep-link query parameters.

Google Flights encodes its search (route, dates, passengers, cabin) into a
base64-encoded protobuf passed as ``?tfs=``. Navigating straight to that
URL returns the results list directly, which is far more robust than
driving the search form (no autocomplete, calendars or overlays).

This module hand-encodes the handful of protobuf fields we need, so there
is no protobuf runtime dependency. Field numbers were reverse-engineered
from the public Google Flights URLs and match the widely-used schema:

    Airport    { string code = 2; }
    FlightData { string date = 2; Airport from = 13; Airport to = 14; }
    Info       { int trip = 1; repeated FlightData data = 3;
                 repeated int passengers = 8; int seat = 9; }

Enums: trip 1=round/2=one-way; seat 1=economy/2=premium/3=business/4=first;
passenger 1=adult/2=child/3=infant-in-seat/4=infant-on-lap.
"""

from __future__ import annotations

import base64
from urllib.parse import quote, urlencode

from flight_tracker.domain.entities import CabinClass, FlightSearchQuery

GOOGLE_FLIGHTS_URL = "https://www.google.com/travel/flights"

# ``tfu`` forces the "all flights" list view rather than the summary card.
_TFU_SHOW_LIST = "EgYIABABGAA"

_CABIN_TO_SEAT = {
    CabinClass.ECONOMY: 1,
    CabinClass.PREMIUM_ECONOMY: 2,
    CabinClass.BUSINESS: 3,
    CabinClass.FIRST: 4,
}

_TRIP_ROUND = 1
_TRIP_ONE_WAY = 2

_PASSENGER_ADULT = 1
_PASSENGER_CHILD = 2
_PASSENGER_INFANT_LAP = 4


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _key(field: int, wire_type: int) -> bytes:
    return _varint((field << 3) | wire_type)


def _string_field(field: int, value: str) -> bytes:
    raw = value.encode()
    return _key(field, 2) + _varint(len(raw)) + raw


def _message_field(field: int, message: bytes) -> bytes:
    return _key(field, 2) + _varint(len(message)) + message


def _int_field(field: int, value: int) -> bytes:
    return _key(field, 0) + _varint(value)


def _airport(code: str) -> bytes:
    return _string_field(2, code.upper())


def _leg(date_iso: str, origin: str, destination: str) -> bytes:
    return (
        _string_field(2, date_iso)
        + _message_field(13, _airport(origin))
        + _message_field(14, _airport(destination))
    )


def _passenger_codes(query: FlightSearchQuery) -> list[int]:
    pax = query.passengers
    codes = [_PASSENGER_ADULT] * pax.adults
    codes += [_PASSENGER_CHILD] * pax.children
    codes += [_PASSENGER_INFANT_LAP] * pax.infants
    return codes


def build_tfs(query: FlightSearchQuery) -> str:
    """Return the base64-encoded ``tfs`` protobuf for ``query``."""

    trip = _TRIP_ROUND if query.return_date is not None else _TRIP_ONE_WAY
    seat = _CABIN_TO_SEAT[query.cabin]

    info = _int_field(1, trip)
    info += _message_field(
        3, _leg(query.departure_date.isoformat(), query.origin, query.destination)
    )
    if query.return_date is not None:
        info += _message_field(
            3, _leg(query.return_date.isoformat(), query.destination, query.origin)
        )
    for code in _passenger_codes(query):
        info += _int_field(8, code)
    info += _int_field(9, seat)

    return base64.b64encode(info).decode()


def build_results_url(query: FlightSearchQuery, *, currency: str = "AUD") -> str:
    """Return the full Google Flights results URL for ``query``."""

    params = {
        "tfs": build_tfs(query),
        "hl": "en",
        "gl": "AU",
        "curr": currency,
        "tfu": _TFU_SHOW_LIST,
    }
    return f"{GOOGLE_FLIGHTS_URL}?{urlencode(params, quote_via=quote)}"
