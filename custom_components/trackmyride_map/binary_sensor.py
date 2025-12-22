"""Binary sensor platform for TrackMyRide Map."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR, DOMAIN
from .coordinator import TrackMyRideDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TrackMyRide binary sensors."""
    coordinator: TrackMyRideDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    tracked: set[str] = set()

    @callback
    def _process_new_data() -> None:
        new_entities: list[TrackMyRideBinarySensorBase] = []
        for vehicle_id in coordinator.data or {}:
            if vehicle_id in tracked:
                continue
            tracked.add(vehicle_id)
            new_entities.extend(
                [
                    TrackMyRideExternalPowerBinarySensor(
                        coordinator, entry, vehicle_id
                    ),
                    TrackMyRideEngineBinarySensor(coordinator, entry, vehicle_id),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_process_new_data)
    _process_new_data()


class TrackMyRideBinarySensorBase(
    CoordinatorEntity[DataUpdateCoordinator], BinarySensorEntity
):
    """Base class for TrackMyRide binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
        metric_key: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._metric_key = metric_key
        self._label = label
        self._attr_unique_id = f"{vehicle_id}_{metric_key}"
        self._entry = entry
        self._attr_name = label

    @property
    def _vehicle(self) -> dict[str, Any] | None:
        return (
            self.coordinator.data.get(self._vehicle_id)
            if self.coordinator.data
            else None
        )

    @property
    def available(self) -> bool:
        return self._vehicle is not None

    @property
    def name(self) -> str | None:
        return self._attr_name

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        if not self._vehicle:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._vehicle_id)},
            name=self._vehicle.get("name")
            or f"TrackMyRide {self._vehicle_id}",
            manufacturer="TrackMyRide",
            model="Tracker",
        )


class TrackMyRideExternalPowerBinarySensor(TrackMyRideBinarySensorBase):
    """External power state (1/0)."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(
            coordinator, entry, vehicle_id, "external_power", "External Power"
        )

    @property
    def is_on(self) -> bool | None:
        if not self._vehicle:
            return None
        value = self._vehicle.get("external_power")
        if value is None:
            return None
        return value == 1


class TrackMyRideEngineBinarySensor(TrackMyRideBinarySensorBase):
    """Engine running state (1/0)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(coordinator, entry, vehicle_id, "engine", "Engine")

    @property
    def is_on(self) -> bool | None:
        if not self._vehicle:
            return None
        value = self._vehicle.get("engine")
        if value is None:
            return None
        return value == 1
