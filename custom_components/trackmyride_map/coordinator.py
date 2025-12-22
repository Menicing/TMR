"""Data coordinator for TrackMyRide Map."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TrackMyRideAuthError, TrackMyRideClient, TrackMyRideEndpointError
from .const import (
    CONF_IDENTITY_FIELD,
    CONF_MINUTES_WINDOW,
    CONF_POLL_INTERVAL,
    DEFAULT_MINUTES,
    DEFAULT_POLL_INTERVAL,
    LOGGER_NAME,
    MAX_BACKOFF_SECONDS,
)

LOGGER = logging.getLogger(LOGGER_NAME)


class TrackMyRideDataCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls TrackMyRide and handles simple backoff."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TrackMyRideClient,
        config: dict[str, Any],
    ) -> None:
        self.client = client
        self._base_interval = timedelta(
            seconds=int(config.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        )
        self._failure_count = 0
        self._identity_field = (config.get(CONF_IDENTITY_FIELD) or "").strip() or None
        self._minutes = int(config.get(CONF_MINUTES_WINDOW, DEFAULT_MINUTES))

        super().__init__(
            hass,
            LOGGER,
            name="TrackMyRide Map Coordinator",
            update_interval=self._base_interval,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            payload = await self.client.async_get_devices(
                limit=1, minutes=self._minutes
            )
        except TrackMyRideEndpointError as exc:
            self._apply_backoff()
            raise UpdateFailed(f"Endpoint error: {exc}") from exc
        except TrackMyRideAuthError as exc:
            self._apply_backoff()
            raise UpdateFailed(f"Authentication error: {exc}") from exc
        except ClientError as exc:
            self._apply_backoff()
            raise UpdateFailed(f"Connection error: {exc}") from exc
        except Exception as exc:  # pylint: disable=broad-except
            self._apply_backoff()
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

        self._reset_interval()
        devices = self._extract_devices(payload)
        normalized: dict[str, dict[str, Any]] = {}
        previous = self.data or {}

        for raw_device in devices:
            normalized_entry = _normalize_device(raw_device, previous)
            if not normalized_entry:
                continue
            unique_id, normalized_device = normalized_entry
            normalized[unique_id] = normalized_device

        return normalized

    def _extract_devices(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            LOGGER.debug("Unexpected payload type (expected dict): %s", type(payload))
            return []
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            LOGGER.debug("Unexpected data container in payload: %s", type(data))
            return []
        devices: list[dict[str, Any]] = []
        for _, device in data.items():
            if not isinstance(device, dict):
                continue
            devices.append(device)
        return devices

    def _apply_backoff(self) -> None:
        self._failure_count += 1
        factor = min(self._failure_count + 1, 4)
        new_interval = min(
            self._base_interval * factor, timedelta(seconds=MAX_BACKOFF_SECONDS)
        )
        if new_interval != self.update_interval:
            LOGGER.debug(
                "Applying backoff after %s failures: %ss",
                self._failure_count,
                new_interval.total_seconds(),
            )
            self.update_interval = new_interval

    def _reset_interval(self) -> None:
        if self._failure_count:
            LOGGER.debug("Resetting backoff after successful update")
        self._failure_count = 0
        self.update_interval = self._base_interval


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_int(value: Any, fallback: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_device(
    raw_device: dict[str, Any], previous: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any]] | None:
    unique_id = str(raw_device.get("unique_id") or "").strip()
    if not unique_id:
        LOGGER.warning("Skipping device without unique_id: %s", raw_device)
        return None

    prev_entry = previous.get(unique_id, {})
    name = raw_device.get("name") or f"TrackMyRide {unique_id}"
    rego = raw_device.get("rego")
    comms_delta = raw_device.get("comms_delta")

    point = None
    aa_data = raw_device.get("aaData")
    if isinstance(aa_data, list) and aa_data:
        first = aa_data[0]
        if isinstance(first, dict):
            point = first

    lat = prev_entry.get("lat")
    lon = prev_entry.get("lon")
    speed_kmh = prev_entry.get("speed_kmh")
    volts = _as_float(raw_device.get("volts"), prev_entry.get("volts"))
    timestamp_epoch = prev_entry.get("timestamp_epoch")

    odometer = _as_float(raw_device.get("odometer"), prev_entry.get("odometer"))
    acc_counter = _as_float(
        raw_device.get("acc_counter"), prev_entry.get("acc_counter")
    )
    external_power = _as_int(
        raw_device.get("external_power"), prev_entry.get("external_power")
    )
    engine = _as_int(raw_device.get("engine"), prev_entry.get("engine"))
    internal_battery = raw_device.get("internal_battery") or prev_entry.get(
        "internal_battery"
    )
    zone_raw = raw_device.get("zone")
    zone = zone_raw if isinstance(zone_raw, str) else ""
    zone_ids = _parse_zone_ids(zone)

    if point:
        lat = _as_float(point.get("lat"), lat)
        lon = _as_float(point.get("lng") or point.get("lon"), lon)
        speed_kmh = _as_float(point.get("speed"), speed_kmh)
        volts = _as_float(point.get("volts"), volts)
        timestamp_epoch = _as_int(
            point.get("epoch") or raw_device.get("last_data_at_epoch"),
            fallback=timestamp_epoch,
        )
    else:
        timestamp_epoch = _as_int(
            raw_device.get("last_data_at_epoch"), fallback=timestamp_epoch
        )

    normalized = {
        "name": name,
        "rego": rego,
        "lat": lat,
        "lon": lon,
        "speed_kmh": speed_kmh,
        "timestamp_epoch": timestamp_epoch,
        "volts": volts,
        "comms_delta": comms_delta,
        "odometer": odometer,
        "acc_counter": acc_counter,
        "external_power": external_power,
        "engine": engine,
        "internal_battery": internal_battery,
        "zone": zone,
        "zone_ids": zone_ids,
        "zone_count": len(zone_ids),
        "raw": raw_device,
    }
    return unique_id, normalized


def _parse_zone_ids(zone: str) -> list[str]:
    if not zone:
        return []
    parts = [part.strip() for part in zone.split(",")]
    return [part for part in parts if part]
