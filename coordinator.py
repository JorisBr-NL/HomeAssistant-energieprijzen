"""Data update coordinator for Jeroen.nl energieprijzen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import JeroenApi, JeroenApiError, JeroenAuthError, PricePoint
from .const import (
    DOMAIN,
    PERIOD_TODAY,
    PERIOD_TOMORROW,
    TOMORROW_AVAILABLE_FROM_HOUR,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Prices for today and tomorrow (local dates)."""

    today: list[PricePoint] = field(default_factory=list)
    tomorrow: list[PricePoint] = field(default_factory=list)

    @property
    def all(self) -> list[PricePoint]:
        return [*self.today, *self.tomorrow]

    def current(self, now: datetime) -> PricePoint | None:
        for point in self.all:
            if point.start <= now < point.end:
                return point
        return None

    def next(self, now: datetime) -> PricePoint | None:
        for point in self.all:
            if point.start > now:
                return point
        return None


def _local_date(point: PricePoint) -> date:
    return dt_util.as_local(point.start).date()


def _only_date(points: list[PricePoint], day: date) -> list[PricePoint]:
    return [p for p in points if _local_date(p) == day]


class JeroenCoordinator(DataUpdateCoordinator[PriceData]):
    """Fetch and cache prices."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: JeroenApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._cache: dict[date, list[PricePoint]] = {}

    async def _fetch(self, period: str) -> list[PricePoint]:
        try:
            return await self.api.async_get_prices(period)
        except JeroenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err

    async def _async_update_data(self) -> PriceData:
        now = dt_util.now()
        today = now.date()
        tomorrow = date.fromordinal(today.toordinal() + 1)

        # Forget old days.
        self._cache = {d: p for d, p in self._cache.items() if d >= today}

        try:
            if not self._cache.get(today):
                points = await self._fetch(PERIOD_TODAY)
                self._store(points)
                if not self._cache.get(today):
                    raise UpdateFailed("Geen prijzen voor vandaag ontvangen")

            if now.hour >= TOMORROW_AVAILABLE_FROM_HOUR and not self._cache.get(tomorrow):
                try:
                    self._store(await self._fetch(PERIOD_TOMORROW))
                except JeroenApiError as err:
                    # Tomorrow is optional; keep today's data working.
                    _LOGGER.debug("Prijzen voor morgen nog niet beschikbaar: %s", err)
        except JeroenApiError as err:
            if self._cache.get(today):
                _LOGGER.warning("Ophalen mislukt, gebruik gecachte prijzen: %s", err)
            else:
                raise UpdateFailed(str(err)) from err

        return PriceData(
            today=self._cache.get(today, []),
            tomorrow=self._cache.get(tomorrow, []),
        )

    def _store(self, points: list[PricePoint]) -> None:
        """Store points per local date (an API period may span a date edge)."""
        days = {_local_date(p) for p in points}
        for day in days:
            day_points = _only_date(points, day)
            existing = self._cache.get(day, [])
            if len(day_points) >= len(existing):
                self._cache[day] = day_points
