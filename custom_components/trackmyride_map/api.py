"""API client helpers for TrackMyRide."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER_NAME

LOGGER = logging.getLogger(LOGGER_NAME)


class TrackMyRideClient:
    """Minimal client for TrackMyRide vehicle data."""

    def __init__(self, hass: HomeAssistant, base_url: str, api_key: str) -> None:
        self._hass = hass
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    async def async_get_vehicle_positions(self) -> list[dict[str, Any]]:
        """Fetch vehicles with their latest positions."""
        url_candidates = [
            f"{self._base_url}/v1/vehicles",
            f"{self._base_url}/vehicles",
        ]
        headers = {"Authorization": f"Bearer {self._api_key}"}

        last_error: Exception | None = None
        for url in url_candidates:
            try:
                async with self._session.get(url, headers=headers, timeout=15) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    records = _extract_vehicle_records(payload)
                    if records:
                        return records
            except (ClientError, TimeoutError, ValueError) as exc:
                LOGGER.debug("TrackMyRide fetch error from %s: %s", url, exc)
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("No vehicle data returned from TrackMyRide")


def _extract_vehicle_records(payload: Any) -> list[dict[str, Any]]:
    """Normalise various TrackMyRide payload shapes to a list of dicts."""
    if payload is None:
        return []

    records: Iterable[Any] | None = None
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            records = payload["data"]
        elif isinstance(payload.get("vehicles"), list):
            records = payload["vehicles"]
        elif isinstance(payload.get("results"), list):
            records = payload["results"]
    elif isinstance(payload, list):
        records = payload

    if records is None:
        LOGGER.debug("Unexpected payload shape for vehicle list: %s", payload)
        return []

    normalised: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        coords = _extract_coordinates(item)
        if coords is None:
            LOGGER.debug("Skipping record without coordinates: %s", item)
            continue

        normalised.append(
            {
                "id": item.get("id")
                or item.get("vehicle_id")
                or item.get("uuid")
                or item.get("vin")
                or item.get("imei"),
                "name": item.get("name") or item.get("label") or item.get("display_name"),
                "latitude": coords["lat"],
                "longitude": coords["lon"],
                "gps_accuracy": _optional_float(
                    item.get("accuracy") or item.get("gps_accuracy")
                ),
                "speed": _optional_float(item.get("speed") or item.get("speed_kmh")),
                "heading": _optional_float(item.get("heading") or item.get("course")),
                "battery_level": _optional_float(
                    item.get("battery") or item.get("battery_level")
                ),
                "last_update": _parse_timestamp(
                    item.get("recorded_at")
                    or item.get("timestamp")
                    or item.get("time")
                    or item.get("updated_at")
                ),
                "raw": item,
            }
        )
    return normalised


def _extract_coordinates(item: dict[str, Any]) -> dict[str, float] | None:
    lat = item.get("latitude") or item.get("lat")
    lon = item.get("longitude") or item.get("lng") or item.get("lon")

    if lat is None or lon is None:
        return None

    try:
        return {"lat": float(lat), "lon": float(lon)}
    except (TypeError, ValueError):
        LOGGER.debug("Invalid coordinates in record: %s", item)
        return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return _ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            LOGGER.debug("Falling back to now for timestamp value: %s", value)
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
