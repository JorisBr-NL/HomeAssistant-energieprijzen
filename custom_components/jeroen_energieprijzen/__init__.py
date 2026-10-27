"""Jeroen.nl dynamische energieprijzen integration.

Deprecated: replaced by the Jeroen.nl integration (ha-jeroen-nl). This version
keeps working, but shows a notice under Settings > System > Repairs.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JeroenApi
from .const import DOMAIN
from .coordinator import JeroenCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

NEW_INTEGRATION_URL = "https://github.com/JorisBr-NL/ha-jeroen-nl"
DEPRECATION_ISSUE = "deprecated_integration"

type JeroenConfigEntry = ConfigEntry[JeroenCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: JeroenConfigEntry) -> bool:
    """Set up from a config entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DEPRECATION_ISSUE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=DEPRECATION_ISSUE,
        translation_placeholders={"url": NEW_INTEGRATION_URL},
        learn_more_url=NEW_INTEGRATION_URL,
    )
    _LOGGER.warning(
        "Jeroen.nl energieprijzen is deprecated and will no longer be maintained; "
        "please switch to the Jeroen.nl integration: %s",
        NEW_INTEGRATION_URL,
    )

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


async def async_remove_entry(hass: HomeAssistant, entry: JeroenConfigEntry) -> None:
    """Remove the deprecation notice once the integration is removed."""
    ir.async_delete_issue(hass, DOMAIN, DEPRECATION_ISSUE)
