"""Registry migrations and formatting tests."""

from __future__ import annotations

import asyncio
import pytest

from custom_components.trackmyride_map import _migrate_registries
from custom_components.trackmyride_map.binary_sensor import TrackMyRideEngineBinarySensor
from custom_components.trackmyride_map.const import DOMAIN
from custom_components.trackmyride_map.sensor import TrackMyRideVoltsSensor
from custom_components.trackmyride_map.util import format_comms_delta
from tests.conftest import _FakeConfigEntry  # noqa: PLC2701

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


def _make_coordinator(data: dict) -> DataUpdateCoordinator:
    coordinator = DataUpdateCoordinator()
    coordinator.data = data
    return coordinator


def test_device_info_not_service_entry_type():
    """Device info should describe a device, not a service."""

    coordinator = _make_coordinator({"veh1": {"name": "Road King"}})
    entry = _FakeConfigEntry()
    sensor = TrackMyRideVoltsSensor(coordinator, entry, "veh1")
    binary = TrackMyRideEngineBinarySensor(coordinator, entry, "veh1")

    for entity in (sensor, binary):
        device_info = entity.device_info
        assert device_info is not None
        assert device_info.entry_type is None
        assert device_info.manufacturer == "TrackMyRide"
        assert device_info.model == "Tracker"
        assert device_info.identifiers == {(DOMAIN, "veh1")}


def test_entity_names_are_short_no_device_prefix():
    """Entity friendly names should not include the device name."""

    coordinator = _make_coordinator({"veh1": {"name": "Road King"}})
    entry = _FakeConfigEntry()
    sensor = TrackMyRideVoltsSensor(coordinator, entry, "veh1")
    assert sensor.name == "External Voltage"


def test_device_registry_migration_clears_service_entry_type():
    """Existing device registry entries should be flipped from service to device."""

    hass = HomeAssistant()
    entry = _FakeConfigEntry(entry_id="abc123")
    coordinator = _make_coordinator({"veh1": {"name": "Road King"}})

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create_device(
        identifiers={(DOMAIN, "veh1")},
        entry_type=DeviceEntryType.SERVICE,
        name="Road King",
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "veh1_volts",
        config_entry=entry,
        suggested_object_id="road_king_road_king_external_voltage",
        name="Road King External Voltage",
        original_name="Road King External Voltage",
        device_id=device.id,
    )

    asyncio.run(_migrate_registries(hass, entry, coordinator))

    assert device.entry_type is None
    migrated_entry = entity_registry.get("sensor.road_king_road_king_external_voltage")
    assert migrated_entry is not None
    assert migrated_entry.name is None
    assert migrated_entry.original_name == "External Voltage"
    assert migrated_entry.unique_id == "veh1_volts"


def test_entity_registry_migration_respects_user_defined_name():
    """Existing registry entries keep user friendly names."""

    hass = HomeAssistant()
    entry = _FakeConfigEntry(entry_id="abc123")
    coordinator = _make_coordinator({"veh1": {"name": "Road King"}})

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create_device(
        identifiers={(DOMAIN, "veh1")},
        entry_type=DeviceEntryType.SERVICE,
        name="Road King",
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "veh1_volts",
        config_entry=entry,
        suggested_object_id="road_king_custom_voltage",
        name="My Custom Voltage Name",
        original_name="Road King External Voltage",
        device_id=device.id,
    )

    asyncio.run(_migrate_registries(hass, entry, coordinator))

    migrated_entry = entity_registry.get("sensor.road_king_custom_voltage")
    assert migrated_entry is not None
    assert migrated_entry.name == "My Custom Voltage Name"
    assert migrated_entry.original_name == "Road King External Voltage"


def test_format_comms_delta_two_levels_and_minus_one():
    """comms_delta is adjusted by -1s and rendered with two components."""

    assert format_comms_delta(45) == "44 seconds"
    assert format_comms_delta(61) == "1 minute"
    assert format_comms_delta(119) == "1 minute 58 seconds"
    assert format_comms_delta(3700) == "1 hour 1 minute"
    assert format_comms_delta(90061) == "1 day 1 hour"
    assert format_comms_delta(31_700_000) == "1 year 2 months"
