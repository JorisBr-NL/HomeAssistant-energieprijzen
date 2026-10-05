"""Config flow for Jeroen.nl energieprijzen."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import JeroenApi, JeroenApiError, JeroenAuthError
from .const import (
    CONF_ENERGY_TAX,
    CONF_MARKUP,
    CONF_VAT,
    DEFAULT_ENERGY_TAX,
    DEFAULT_MARKUP,
    DEFAULT_VAT,
    DOMAIN,
    PERIOD_TODAY,
)

KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


def _price_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0, max=5, step=0.00001, mode=NumberSelectorMode.BOX, unit_of_measurement="EUR/kWh")
    )


class JeroenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _validate(self, api_key: str) -> str | None:
        api = JeroenApi(async_get_clientsession(self.hass), api_key)
        try:
            points = await api.async_get_prices(PERIOD_TODAY)
        except JeroenAuthError:
            return "invalid_auth"
        except JeroenApiError:
            return "cannot_connect"
        if not points:
            return "no_data"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await self._validate(api_key)) is None:
                return self.async_create_entry(
                    title="Jeroen.nl energieprijzen",
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = error

        return self.async_show_form(step_id="user", data_schema=KEY_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if (error := await self._validate(api_key)) is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error
        return self.async_show_form(step_id="reauth_confirm", data_schema=KEY_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return JeroenOptionsFlow()


class JeroenOptionsFlow(OptionsFlow):
    """Options: surcharges and VAT for the all-in price."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_MARKUP, default=opts.get(CONF_MARKUP, DEFAULT_MARKUP)): _price_selector(),
                vol.Required(CONF_ENERGY_TAX, default=opts.get(CONF_ENERGY_TAX, DEFAULT_ENERGY_TAX)): _price_selector(),
                vol.Required(CONF_VAT, default=opts.get(CONF_VAT, DEFAULT_VAT)): NumberSelector(
                    NumberSelectorConfig(min=0, max=100, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%")
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
