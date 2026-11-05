"""Device tracker platform for TrackMyRide Map."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR, DOMAIN, LOGGER_NAME, TRAVELLING_STOP_DELAY
from .coordinator import TrackMyRideDataCoordinator

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

    _attr_has_entity_name = False
    _attr_icon = "mdi:car-connected"
    _attr_location_accuracy: float | None = None
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
        self._stopped_since: datetime | None = None
        self._sync_from_coordinator(self._utcnow())

    @property
    def _vehicle(self) -> dict | None:
        return (
            self.coordinator.data.get(self._vehicle_id)
            if self.coordinator.data
            else None
        )

    @property
    def extra_state_attributes(self) -> dict:
        if not self._vehicle:
            return {}
        return {
            "latitude": self._vehicle.get("lat"),
            "longitude": self._vehicle.get("lon"),
            "speed_kmh": self._vehicle.get("speed_kmh"),
            "volts": self._vehicle.get("volts"),
            "last_comms": self._vehicle.get("last_comms"),
            "rego": self._vehicle.get("rego"),
            "last_update": self._vehicle.get("timestamp_dt_utc"),
        }

    def _sync_from_coordinator(self, now: datetime) -> None:
        """Update Home Assistant's tracker attributes from coordinator data."""
        vehicle = self._vehicle
        if not vehicle:
            self._attr_latitude = None
            self._attr_longitude = None
            self._attr_location_name = None
            self._stopped_since = None
            return

        self._attr_latitude = vehicle.get("lat")
        self._attr_longitude = vehicle.get("lon")
        speed = vehicle.get("speed_kmh")
        if speed is not None and speed > 0:
            self._stopped_since = None
            self._attr_location_name = "travelling"
            return

        zone_state = vehicle.get("zone_state")
        zone_name = zone_state.strip() if isinstance(zone_state, str) else ""
        if zone_name:
            self._stopped_since = None
            self._attr_location_name = zone_name
            return

        if getattr(self, "_attr_location_name", None) == "travelling":
            self._stopped_since = self._stopped_since or now
            if now - self._stopped_since < timedelta(seconds=TRAVELLING_STOP_DELAY):
                return

        self._stopped_since = None
        self._attr_location_name = "away"

    def _utcnow(self) -> datetime:
        """Return the current UTC time; kept separate for deterministic tests."""
        return datetime.now(UTC)

    @property
    def location_name(self) -> str | None:
        if not self._vehicle:
            return None
        speed = self._vehicle.get("speed_kmh")
        if speed is not None and speed > 0:
            return "travelling"
        zone_state = self._vehicle.get("zone_state")
        if isinstance(zone_state, str):
            zone_state = zone_state.strip()
        else:
            zone_state = ""
        return zone_state or "away"

    @property
    def available(self) -> bool:
        return self._vehicle is not None

    @property
    def name(self) -> str | None:
        if not self._vehicle:
            return "Track My Ride Vehicle"
        return self._vehicle.get("name") or f"TrackMyRide {self._vehicle_id}"

    @property
    def device_info(self) -> DeviceInfo | None:
        if not self._vehicle:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._vehicle_id)},
            name=self.name,
            manufacturer="TrackMyRide",
            model="Tracker",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write state only when values change."""
        self._sync_from_coordinator(self._utcnow())
        snapshot = (
            self.latitude,
            self.longitude,
            self.extra_state_attributes,
            self.location_name,
        )
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        self.async_write_ha_state()
