"""Constants for the Jeroen.nl energieprijzen integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "jeroen_energieprijzen"

API_URL = "https://jeroen.nl/api/dynamische-energieprijzen/v2/"
PERIOD_TODAY = "vandaag"
PERIOD_TOMORROW = "morgen"

CONF_MARKUP = "opslag"
CONF_ENERGY_TAX = "energiebelasting"
CONF_VAT = "btw"

# Defaults (2026, excl. btw): average supplier markup (Zonneplan/ANWB/Frank),
# energiebelasting 2026 and Dutch VAT.
DEFAULT_MARKUP = 0.016
DEFAULT_ENERGY_TAX = 0.09161
DEFAULT_VAT = 21.0

# How often the coordinator checks whether new data must be fetched.
# Data that is already complete is cached, so the API is only called
# when today's or tomorrow's prices are still missing.
UPDATE_INTERVAL = timedelta(minutes=30)

# Prices for tomorrow are usually published in the early afternoon.
TOMORROW_AVAILABLE_FROM_HOUR = 13

DEFAULT_SLOT = timedelta(minutes=15)

UNIT = "EUR/kWh"
