"""Jeroen.nl dynamische energieprijzen integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JeroenApi
from .coordinator import JeroenCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type JeroenConfigEntry = ConfigEntry[JeroenCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: JeroenConfigEntry) -> bool:
    """Set up from a config entry."""
    api = JeroenApi(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = JeroenCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: JeroenConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: JeroenConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
