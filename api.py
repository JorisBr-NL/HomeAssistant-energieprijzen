"""Small API client for the Jeroen.nl dynamische energieprijzen API."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import API_URL, DEFAULT_SLOT

NL_TZ = ZoneInfo("Europe/Amsterdam")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class JeroenApiError(Exception):
    """General API error."""


class JeroenAuthError(JeroenApiError):
    """Invalid API key."""


@dataclass(frozen=True)
class PricePoint:
    """One price slot."""

    start: datetime  # timezone aware (UTC)
    end: datetime  # timezone aware (UTC)
    price: float  # EUR/kWh, excluding taxes

    def as_dict(self, price: float | None = None) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "price": round(self.price if price is None else price, 5),
        }


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def _parse_time(item: dict[str, Any]) -> datetime | None:
    raw = item.get("datum_utc")
    tz = timezone.utc
    if raw is None:
        raw = item.get("datum_nl")
        tz = NL_TZ
    if raw is None:
        return None
    raw = str(raw).strip()
    for fmt in (TIME_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=tz).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(timezone.utc)


def _price_key(item: dict[str, Any]) -> str | None:
    if "prijs_excl_belastingen" in item:
        return "prijs_excl_belastingen"
    for key in item:
        if key.startswith("prijs"):
            return key
    return None


def _extract_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("error", "fout", "message", "melding"):
            if key in data and not any(isinstance(v, list) for v in data.values()):
                raise JeroenApiError(str(data[key]))
        for value in data.values():
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    raise JeroenApiError(f"Onverwacht antwoord van de API: {str(data)[:200]}")


def parse_prices(data: Any) -> list[PricePoint]:
    """Convert the raw API response into sorted price points."""
    rows = _extract_rows(data)
    points: list[tuple[datetime, float]] = []
    for row in rows:
        start = _parse_time(row)
        key = _price_key(row)
        price = _parse_price(row.get(key)) if key else None
        if start is None or price is None:
            continue
        points.append((start, price))

    points.sort(key=lambda p: p[0])

    # Derive slot length from the data (15 min or 60 min), fall back to 15 min.
    slot = DEFAULT_SLOT
    if len(points) > 1:
        diff = points[1][0] - points[0][0]
        if timedelta(minutes=5) <= diff <= timedelta(hours=1):
            slot = diff

    result: list[PricePoint] = []
    for idx, (start, price) in enumerate(points):
        end = start + slot
        if idx + 1 < len(points) and points[idx + 1][0] - start <= timedelta(hours=1):
            end = points[idx + 1][0]
        result.append(PricePoint(start=start, end=end, price=price))
    return result


class JeroenApi:
    """API client."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def async_get_prices(self, period: str) -> list[PricePoint]:
        """Fetch prices for a period ('vandaag' or 'morgen')."""
        params = {"key": self._api_key, "period": period, "type": "json"}
        try:
            async with asyncio.timeout(30):
                resp = await self._session.get(API_URL, params=params)
                if resp.status in (401, 403):
                    raise JeroenAuthError("API-sleutel wordt geweigerd")
                if resp.status != 200:
                    raise JeroenApiError(f"HTTP-status {resp.status}")
                text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise JeroenApiError(f"Verbinding mislukt: {err}") from err

        text = text.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except ValueError as err:
            lowered = text.lower()
            if "key" in lowered or "sleutel" in lowered:
                raise JeroenAuthError(text[:200]) from err
            raise JeroenApiError(f"Geen geldige JSON: {text[:200]}") from err

        return parse_prices(data)
