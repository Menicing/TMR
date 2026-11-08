"""Device tracker platform for TrackMyRide Map."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, LOGGER_NAME
from .coordinator import TrackMyRideDataCoordinator

LOGGER = logging.getLogger(LOGGER_NAME)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities from config entry."""
    coordinator: TrackMyRideDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    tracked: set[str] = set()

    @callback
    def _process_new_data() -> None:
        new_entities: list[TrackMyRideDeviceTracker] = []
        for vehicle_id in coordinator.data or {}:
            if vehicle_id in tracked:
                continue
            tracked.add(vehicle_id)
            new_entities.append(
                TrackMyRideDeviceTracker(
                    coordinator=coordinator,
                    entry=entry,
                    vehicle_id=vehicle_id,
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_process_new_data)
    _process_new_data()


class TrackMyRideDeviceTracker(
    CoordinatorEntity[TrackMyRideDataCoordinator], TrackerEntity
):
    """Representation of a TrackMyRide vehicle."""

    _attr_entity_category = None
    _attr_has_entity_name = True
    _attr_icon = "mdi:car-connected"
    _attr_location_accuracy = 0.0
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._entry = entry
        self._attr_unique_id = vehicle_id
        self._attr_name = None
        self._attr_icon = "mdi:car-connected"
        self._last_snapshot: tuple | None = None
        self._update_from_latest_data()

    @property
    def _vehicle(self) -> dict | None:
        return (
            self.coordinator.data.get(self._vehicle_id)
            if self.coordinator.data
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._vehicle:
            return {}
        attrs: dict[str, Any] = {}
        speed_kmh = self._vehicle.get("speed_kmh")
        if speed_kmh is not None:
            # Match the Companion App's standard location attribute (m/s) while
            # retaining the API-native km/h value for existing automations.
            attrs["speed"] = speed_kmh / 3.6
            attrs["speed_kmh"] = speed_kmh
        if (last_update := self._vehicle.get("timestamp_dt_utc")) is not None:
            attrs["last_gps_update"] = last_update
        if (rego := self._vehicle.get("rego")):
            attrs["rego"] = rego
        return attrs

    def _update_from_latest_data(self) -> None:
        """Update native Home Assistant GPS properties from coordinator data."""
        vehicle = self._vehicle
        if not vehicle:
            self._attr_latitude = None
            self._attr_longitude = None
            return

        self._attr_latitude = vehicle.get("lat")
        self._attr_longitude = vehicle.get("lon")

    @property
    def available(self) -> bool:
        return self._vehicle is not None

    @property
    def device_info(self) -> DeviceInfo | None:
        if not self._vehicle:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._vehicle_id)},
            name=self._vehicle.get("name") or f"TrackMyRide {self._vehicle_id}",
            manufacturer="TrackMyRide",
            model="Tracker",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write state only when values change."""
        self._update_from_latest_data()
        snapshot = (
            self.latitude,
            self.longitude,
            self.location_accuracy,
            self.extra_state_attributes,
        )
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        self.async_write_ha_state()
