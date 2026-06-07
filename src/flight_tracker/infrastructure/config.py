"""Application configuration loaded from environment variables.

Secrets (Telegram token, chat id) are never hard-coded; they are read
from the environment or an optional local ``.env`` file. See
``.env.example`` for the full list.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from flight_tracker.domain.entities import (
    CabinClass,
    FareType,
    FlightSearchQuery,
    PassengerMix,
)


def _empty_to_none(value: object) -> object:
    """Treat blank env-var values as unset.

    A line like ``APP_MAX_CHECKS=`` in ``.env`` yields an empty string,
    which would otherwise fail to parse into ``int | None``.
    """

    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class TelegramSettings(BaseSettings):
    """Telegram Bot API credentials."""

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(default="", description="Telegram bot token from @BotFather.")
    chat_id: str = Field(default="", description="Target chat id (user or group).")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class SearchSettings(BaseSettings):
    """Default search parameters, overridable by CLI flags.

    Defaults are seeded with the requested trip:
    SYD → ADL, 8 Aug, return 11 Aug, 3 adults + 1 child, cash fares.
    """

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    origin: str = "SYD"
    destination: str = "ADL"
    departure_date: date = date(date.today().year, 8, 8)
    return_date: date | None = date(date.today().year, 8, 11)
    adults: int = 3
    children: int = 1
    infants: int = 0
    cabin: CabinClass = CabinClass.ECONOMY
    fare_type: FareType = FareType.CASH
    target_price: float = 300.0

    _blank_return_date = field_validator("return_date", mode="before")(_empty_to_none)

    @model_validator(mode="after")
    def _normalise(self) -> SearchSettings:
        object.__setattr__(self, "origin", self.origin.upper())
        object.__setattr__(self, "destination", self.destination.upper())
        return self

    def to_query(self) -> FlightSearchQuery:
        return FlightSearchQuery(
            origin=self.origin,
            destination=self.destination,
            departure_date=self.departure_date,
            return_date=self.return_date,
            passengers=PassengerMix(
                adults=self.adults,
                children=self.children,
                infants=self.infants,
            ),
            target_price=self.target_price,
            fare_type=self.fare_type,
            cabin=self.cabin,
        )


class QantasSettings(BaseSettings):
    """Qantas provider settings."""

    model_config = SettingsConfigDict(
        env_prefix="QANTAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Path to a Playwright storage_state JSON captured after logging in to
    # Qantas Frequent Flyer once. Reused so reward pricing is visible.
    storage_state: str | None = None
    screenshot_dir: str = "screenshots"

    _blank_storage_state = field_validator("storage_state", mode="before")(_empty_to_none)


class AppSettings(BaseSettings):
    """Top-level runtime settings."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"
    headless: bool = True
    request_timeout_ms: int = 45_000
    poll_interval_seconds: int = 1_800
    max_checks: int | None = None
    notify_on_no_match: bool = False

    _blank_max_checks = field_validator("max_checks", mode="before")(_empty_to_none)


def load_settings() -> tuple[AppSettings, SearchSettings, TelegramSettings, QantasSettings]:
    """Load all settings groups from the environment / ``.env``."""

    return AppSettings(), SearchSettings(), TelegramSettings(), QantasSettings()
