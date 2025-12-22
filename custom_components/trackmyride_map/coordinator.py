"""Data coordinator for TrackMyRide Map."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TrackMyRideClient
from .const import (
    CONF_ACCOUNT_ID,
    CONF_IDENTITY_FIELD,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    LOGGER_NAME,
    MAX_BACKOFF_SECONDS,
)

LOGGER = logging.getLogger(LOGGER_NAME)


@dataclass(slots=True)
class VehicleData:
    """Normalised vehicle data for a device tracker entity."""

    vehicle_id: str
    name: str
    latitude: float
    longitude: float
    gps_accuracy: float | None
    speed: float | None
    heading: float | None
    battery_level: float | None
    last_update: datetime
    raw: dict[str, Any]
    stable_identifier: str


class TrackMyRideDataCoordinator(DataUpdateCoordinator[dict[str, VehicleData]]):
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
        self._account_id = config.get(CONF_ACCOUNT_ID) or "default"
        self._identity_field = (config.get(CONF_IDENTITY_FIELD) or "").strip() or None

        super().__init__(
            hass,
            LOGGER,
            name="TrackMyRide Map Coordinator",
            update_interval=self._base_interval,
        )

    async def _async_update_data(self) -> dict[str, VehicleData]:
        try:
            vehicles = await self.client.async_get_vehicle_positions()
        except Exception as exc:
            self._apply_backoff()
            raise UpdateFailed(f"Error fetching TrackMyRide data: {exc}") from exc

        self._reset_interval()
        now = datetime.now(timezone.utc)
        normalized: dict[str, VehicleData] = {}

        for vehicle in vehicles:
            vehicle_id = self._derive_vehicle_id(vehicle)
            if vehicle_id is None:
                LOGGER.warning(
                    "Skipping vehicle without a usable identifier: %s", vehicle
                )
                continue

            name = vehicle.get("name") or f"Vehicle {vehicle_id}"
            last_update = vehicle.get("last_update") or now
            normalized[vehicle_id] = VehicleData(
                vehicle_id=vehicle_id,
                name=name,
                latitude=float(vehicle["latitude"]),
                longitude=float(vehicle["longitude"]),
                gps_accuracy=vehicle.get("gps_accuracy"),
                speed=vehicle.get("speed"),
                heading=vehicle.get("heading"),
                battery_level=vehicle.get("battery_level"),
                last_update=_as_utc(last_update),
                raw=vehicle.get("raw") or {},
                stable_identifier=self._derive_stable_identifier(vehicle, vehicle_id),
            )
        return normalized

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

    def _derive_vehicle_id(self, vehicle: dict[str, Any]) -> str | None:
        preferred_fields = [
            "id",
            "vehicle_id",
            "uuid",
            "vin",
            "imei",
            "deviceId",
            "device_id",
        ]
        if self._identity_field and vehicle.get(self._identity_field):
            return str(vehicle[self._identity_field])
        for field in preferred_fields:
            if vehicle.get(field):
                return str(vehicle[field])
        if vehicle.get("name"):
            return _hash_identifier(self._account_id, str(vehicle["name"]))
        if vehicle.get("raw"):
            return _hash_identifier(self._account_id, str(vehicle["raw"]))
        return None

    def _derive_stable_identifier(
        self, vehicle: dict[str, Any], derived_id: str
    ) -> str:
        if self._identity_field and vehicle.get(self._identity_field):
            return str(vehicle[self._identity_field])
        preferred_fields = [
            "id",
            "vehicle_id",
            "uuid",
            "vin",
            "imei",
            "deviceId",
            "device_id",
        ]
        for field in preferred_fields:
            if vehicle.get(field):
                return str(vehicle[field])
        warning_msg = (
            "TrackMyRide API lacks a stable identifier; falling back to hashed values."
        )
        LOGGER.debug(warning_msg)
        return _hash_identifier(self._account_id, derived_id)


def _hash_identifier(*parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()[:12]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
