"""Sensor platform for TrackMyRide Map."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    """Set up TrackMyRide sensors."""
    coordinator: TrackMyRideDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    tracked: set[str] = set()

    @callback
    def _process_new_data() -> None:
        new_entities: list[TrackMyRideSensorBase] = []
        for vehicle_id in coordinator.data or {}:
            if vehicle_id in tracked:
                continue
            tracked.add(vehicle_id)
            new_entities.extend(
                [
                    TrackMyRideOdometerSensor(coordinator, entry, vehicle_id),
                    TrackMyRideVoltsSensor(coordinator, entry, vehicle_id),
                    TrackMyRideAccCounterSensor(coordinator, entry, vehicle_id),
                    TrackMyRideInternalBatterySensor(coordinator, entry, vehicle_id),
                    TrackMyRideZoneSensor(coordinator, entry, vehicle_id),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_process_new_data)
    _process_new_data()


class TrackMyRideSensorBase(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Base class for TrackMyRide sensors."""

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


class TrackMyRideOdometerSensor(TrackMyRideSensorBase):
    """Odometer sensor."""

    _attr_native_unit_of_measurement = "km"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(coordinator, entry, vehicle_id, "odometer", "Odometer")

    @property
    def native_value(self) -> float | None:
        if not self._vehicle:
            return None
        return self._vehicle.get("odometer")


class TrackMyRideVoltsSensor(TrackMyRideSensorBase):
    """External power supply voltage sensor."""

    _attr_native_unit_of_measurement = "V"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(coordinator, entry, vehicle_id, "volts", "External Voltage")

    @property
    def native_value(self) -> float | None:
        if not self._vehicle:
            return None
        value = self._vehicle.get("volts")
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None


class TrackMyRideAccCounterSensor(TrackMyRideSensorBase):
    """Engine on-time accumulator in minutes (1/10 minute increments)."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(
            coordinator, entry, vehicle_id, "acc_counter", "Engine On Time"
        )

    @property
    def native_value(self) -> float | None:
        if not self._vehicle:
            return None
        return self._vehicle.get("acc_counter")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._vehicle:
            return {}
        return {
            "acc_counter_timedelta": self._vehicle.get("acc_counter_timedelta"),
            "acc_counter_str": self._vehicle.get("acc_counter_str"),
        }


class TrackMyRideInternalBatterySensor(TrackMyRideSensorBase):
    """Internal battery status sensor."""

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(
            coordinator, entry, vehicle_id, "internal_battery", "Internal Battery"
        )

    @property
    def native_value(self) -> str | None:
        if not self._vehicle:
            return None
        return self._vehicle.get("internal_battery")


class TrackMyRideZoneSensor(TrackMyRideSensorBase):
    """Zone assignment sensor."""

    def __init__(
        self,
        coordinator: TrackMyRideDataCoordinator,
        entry: ConfigEntry,
        vehicle_id: str,
    ) -> None:
        super().__init__(coordinator, entry, vehicle_id, "zone", "Zone")

    @property
    def native_value(self) -> str:
        if not self._vehicle:
            return ""
        return self._vehicle.get("zone_state") or ""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._vehicle:
            return {"zone_ids": [], "zone_names": [], "zone_count": 0}
        return {
            "zone_ids": self._vehicle.get("zone_ids", []),
            "zone_names": self._vehicle.get("zone_names", []),
            "zone_count": self._vehicle.get("zone_count", 0),
        }
