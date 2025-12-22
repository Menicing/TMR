"""Device tracker platform for TrackMyRide Map."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR, DOMAIN, LOGGER_NAME
from .coordinator import TrackMyRideDataCoordinator, VehicleData

LOGGER = logging.getLogger(LOGGER_NAME)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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


class TrackMyRideDeviceTracker(CoordinatorEntity[DataUpdateCoordinator], TrackerEntity):
    """Representation of a TrackMyRide vehicle."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:car-connected"

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

    @property
    def _vehicle(self) -> VehicleData | None:
        return self.coordinator.data.get(self._vehicle_id) if self.coordinator.data else None

    @property
    def latitude(self) -> float | None:
        return self._vehicle.latitude if self._vehicle else None

    @property
    def longitude(self) -> float | None:
        return self._vehicle.longitude if self._vehicle else None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def gps_accuracy(self) -> float | None:
        return self._vehicle.gps_accuracy if self._vehicle else None

    @property
    def extra_state_attributes(self) -> dict:
        if not self._vehicle:
            return {}
        return {
            "stable_id": self._vehicle.stable_identifier,
            "speed_kmh": self._vehicle.speed,
            "heading": self._vehicle.heading,
            "battery_level": self._vehicle.battery_level,
            "last_update": self._vehicle.last_update.isoformat(),
        }

    @property
    def available(self) -> bool:
        return self._vehicle is not None

    @property
    def name(self) -> str | None:
        if not self._vehicle:
            return "TrackMyRide Vehicle"
        return self._vehicle.name

    @property
    def device_info(self) -> DeviceInfo | None:
        if not self._vehicle:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._vehicle.stable_identifier)},
            name=self._vehicle.name,
            manufacturer="TrackMyRide",
            entry_type=DeviceEntryType.SERVICE,
        )
