"""Core domain entities and value objects.

These are plain, immutable dataclasses with no dependency on any
framework. They model *what* the application reasons about, independent
of *how* data is fetched or notifications are delivered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class TripType(StrEnum):
    """Whether the journey is one-way or return."""

    ONE_WAY = "one_way"
    RETURN = "return"


class FareType(StrEnum):
    """How the fare is paid for.

    ``POINTS`` searches Qantas Classic/Reward seat availability and the
    application treats the target threshold as a number of points.
    ``CASH`` searches paid fares and treats the threshold as AUD.
    """

    POINTS = "points"
    CASH = "cash"


class CabinClass(StrEnum):
    """Cabin to search for."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


@dataclass(frozen=True, slots=True)
class PassengerMix:
    """Number of passengers by age bracket.

    ``infants`` are lap infants (under 2). ``children`` are 2-11 years.
    """

    adults: int = 1
    children: int = 0
    infants: int = 0

    def __post_init__(self) -> None:
        if self.adults < 1:
            raise ValueError("At least one adult is required.")
        for label, value in (
            ("adults", self.adults),
            ("children", self.children),
            ("infants", self.infants),
        ):
            if value < 0:
                raise ValueError(f"Passenger count '{label}' cannot be negative.")
        if self.infants > self.adults:
            raise ValueError("Each infant must be accompanied by an adult.")

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


@dataclass(frozen=True, slots=True)
class FlightSearchQuery:
    """An immutable description of the search to run.

    ``target_price`` is expressed in points when ``fare_type`` is
    ``FareType.POINTS`` and in AUD when it is ``FareType.CASH``.
    """

    origin: str
    destination: str
    departure_date: date
    passengers: PassengerMix
    target_price: float
    fare_type: FareType = FareType.POINTS
    cabin: CabinClass = CabinClass.ECONOMY
    return_date: date | None = None

    def __post_init__(self) -> None:
        if len(self.origin) != 3 or len(self.destination) != 3:
            raise ValueError("Origin and destination must be 3-letter IATA codes.")
        if self.origin.upper() == self.destination.upper():
            raise ValueError("Origin and destination must differ.")
        if self.target_price <= 0:
            raise ValueError("Target price must be positive.")
        if self.return_date is not None and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")

    @property
    def trip_type(self) -> TripType:
        return TripType.RETURN if self.return_date is not None else TripType.ONE_WAY


@dataclass(frozen=True, slots=True)
class FlightOffer:
    """A single bookable option returned by a provider.

    ``price`` carries points when ``fare_type`` is ``POINTS`` and AUD
    when it is ``CASH``. ``taxes_aud`` is the cash component payable on a
    points booking (carrier charges + taxes), when known.
    """

    origin: str
    destination: str
    departure_date: date
    fare_type: FareType
    cabin: CabinClass
    price: float
    currency: str = "AUD"
    taxes_aud: float | None = None
    flight_number: str | None = None
    departure_time: str | None = None
    arrival_time: str | None = None
    seats_remaining: int | None = None
    return_date: date | None = None

    def is_within(self, target_price: float) -> bool:
        """Return True when this offer is at or below the target."""

        return self.price <= target_price


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The full set of offers produced for a query."""

    query: FlightSearchQuery
    offers: tuple[FlightOffer, ...] = field(default_factory=tuple)

    @property
    def cheapest(self) -> FlightOffer | None:
        return min(self.offers, key=lambda offer: offer.price, default=None)

    def offers_within_target(self) -> tuple[FlightOffer, ...]:
        return tuple(o for o in self.offers if o.is_within(self.query.target_price))
