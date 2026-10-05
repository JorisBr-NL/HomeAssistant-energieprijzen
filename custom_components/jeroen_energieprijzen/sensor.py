"""Sensors for Jeroen.nl energieprijzen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import JeroenConfigEntry
from .api import PricePoint
from .const import (
    CONF_ENERGY_TAX,
    CONF_MARKUP,
    CONF_VAT,
    DEFAULT_ENERGY_TAX,
    DEFAULT_MARKUP,
    DEFAULT_VAT,
    DOMAIN,
    UNIT,
)
from .coordinator import JeroenCoordinator, PriceData

PriceFn = Callable[[float], float]


@dataclass(frozen=True, kw_only=True)
class JeroenSensorDescription(SensorEntityDescription):
    """Describes a price or timestamp sensor."""

    value_fn: Callable[[PriceData, datetime, PriceFn], float | datetime | None]
    native_unit_of_measurement: str | None = UNIT
    state_class: SensorStateClass | str | None = SensorStateClass.MEASUREMENT
    suggested_display_precision: int | None = 2
    icon: str | None = "mdi:currency-eur"
    attrs_fn: Callable[[PriceData, datetime, PriceFn], dict[str, Any]] | None = None


def _pt_price(point: PricePoint | None, fn: PriceFn) -> float | None:
    return None if point is None else round(fn(point.price), 5)


def _extreme(points: list[PricePoint], fn: PriceFn, lowest: bool) -> PricePoint | None:
    if not points:
        return None
    return (min if lowest else max)(points, key=lambda p: p.price)


def _avg(points: list[PricePoint], fn: PriceFn) -> float | None:
    if not points:
        return None
    return round(sum(fn(p.price) for p in points) / len(points), 5)


def _extreme_attrs(points: list[PricePoint], lowest: bool) -> dict[str, Any]:
    point = _extreme(points, lambda x: x, lowest)
    if point is None:
        return {}
    return {
        "start": dt_util.as_local(point.start).isoformat(),
        "end": dt_util.as_local(point.end).isoformat(),
    }


def _list(points: list[PricePoint], fn: PriceFn) -> list[dict[str, Any]]:
    return [
        {
            "start": dt_util.as_local(p.start).isoformat(),
            "end": dt_util.as_local(p.end).isoformat(),
            "price": round(fn(p.price), 5),
        }
        for p in points
    ]


def _current_attrs(data: PriceData, now: datetime, fn: PriceFn) -> dict[str, Any]:
    return {
        "prices_today": _list(data.today, fn),
        "prices_tomorrow": _list(data.tomorrow, fn),
        "tomorrow_available": bool(data.tomorrow),
    }


def _lowest_start(points: list[PricePoint]) -> datetime | None:
    point = _extreme(points, lambda x: x, True)
    return None if point is None else point.start


def _lowest_moment_attrs(points: list[PricePoint], fn: PriceFn) -> dict[str, Any]:
    point = _extreme(points, fn, True)
    if point is None:
        return {}
    return {
        "end": dt_util.as_local(point.end).isoformat(),
        "price": round(fn(point.price), 5),
    }


def _excl(x: float) -> float:
    return x


SENSORS: tuple[JeroenSensorDescription, ...] = (
    JeroenSensorDescription(
        key="huidige_prijs",
        name="Huidige prijs",
        value_fn=lambda d, now, fn: _pt_price(d.current(now), fn),
        attrs_fn=_current_attrs,
    ),
    JeroenSensorDescription(
        key="huidige_prijs_excl",
        name="Huidige prijs excl. belastingen",
        value_fn=lambda d, now, fn: _pt_price(d.current(now), _excl),
    ),
    JeroenSensorDescription(
        key="volgende_prijs",
        name="Volgende prijs",
        value_fn=lambda d, now, fn: _pt_price(d.next(now), fn),
        attrs_fn=lambda d, now, fn: (
            {"start": dt_util.as_local(p.start).isoformat()} if (p := d.next(now)) else {}
        ),
    ),
    JeroenSensorDescription(
        key="laagste_prijs_vandaag",
        name="Laagste prijs vandaag",
        value_fn=lambda d, now, fn: _pt_price(_extreme(d.today, fn, True), fn),
        attrs_fn=lambda d, now, fn: _extreme_attrs(d.today, True),
    ),
    JeroenSensorDescription(
        key="goedkoopste_moment_vandaag",
        name="Goedkoopste moment vandaag",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        state_class=None,
        suggested_display_precision=None,
        icon="mdi:clock-check-outline",
        value_fn=lambda d, now, fn: _lowest_start(d.today),
        attrs_fn=lambda d, now, fn: _lowest_moment_attrs(d.today, fn),
    ),
    JeroenSensorDescription(
        key="hoogste_prijs_vandaag",
        name="Hoogste prijs vandaag",
        value_fn=lambda d, now, fn: _pt_price(_extreme(d.today, fn, False), fn),
        attrs_fn=lambda d, now, fn: _extreme_attrs(d.today, False),
    ),
    JeroenSensorDescription(
        key="gemiddelde_prijs_vandaag",
        name="Gemiddelde prijs vandaag",
        value_fn=lambda d, now, fn: _avg(d.today, fn),
    ),
    JeroenSensorDescription(
        key="laagste_prijs_morgen",
        name="Laagste prijs morgen",
        value_fn=lambda d, now, fn: _pt_price(_extreme(d.tomorrow, fn, True), fn),
        attrs_fn=lambda d, now, fn: _extreme_attrs(d.tomorrow, True),
    ),
    JeroenSensorDescription(
        key="goedkoopste_moment_morgen",
        name="Goedkoopste moment morgen",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        state_class=None,
        suggested_display_precision=None,
        icon="mdi:clock-check-outline",
        value_fn=lambda d, now, fn: _lowest_start(d.tomorrow),
        attrs_fn=lambda d, now, fn: _lowest_moment_attrs(d.tomorrow, fn),
    ),
    JeroenSensorDescription(
        key="gemiddelde_prijs_morgen",
        name="Gemiddelde prijs morgen",
        value_fn=lambda d, now, fn: _avg(d.tomorrow, fn),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JeroenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    entities = [JeroenPriceSensor(coordinator, entry, desc) for desc in SENSORS]
    async_add_entities(entities)

    @callback
    def _tick(_now: datetime) -> None:
        # Prices change per 15 minutes; refresh states without calling the API.
        for entity in entities:
            if entity.hass is not None:
                entity.async_write_ha_state()

    entry.async_on_unload(
        async_track_time_change(hass, _tick, minute=[0, 15, 30, 45], second=1)
    )


class JeroenPriceSensor(CoordinatorEntity[JeroenCoordinator], SensorEntity):
    """A price sensor."""

    entity_description: JeroenSensorDescription
    _attr_has_entity_name = True
    # The price lists are large; keep them out of the database.
    _unrecorded_attributes = frozenset({"prices_today", "prices_tomorrow", "start", "end", "price"})

    def __init__(
        self,
        coordinator: JeroenCoordinator,
        entry: JeroenConfigEntry,
        description: JeroenSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Jeroen.nl energieprijzen",
            manufacturer="Jeroen.nl",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://jeroen.nl",
        )

    def _price_fn(self) -> PriceFn:
        opts = self._entry.options
        markup = float(opts.get(CONF_MARKUP, DEFAULT_MARKUP))
        tax = float(opts.get(CONF_ENERGY_TAX, DEFAULT_ENERGY_TAX))
        vat = float(opts.get(CONF_VAT, DEFAULT_VAT))
        return lambda price: (price + markup + tax) * (1 + vat / 100)

    @property
    def native_value(self) -> float | datetime | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data, dt_util.utcnow(), self._price_fn()
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(
            self.coordinator.data, dt_util.utcnow(), self._price_fn()
        )
