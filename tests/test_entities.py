"""Entity and coordinator normalisation tests."""

from __future__ import annotations

import pytest

from custom_components.trackmyride_map.binary_sensor import (
    TrackMyRideEngineBinarySensor,
    TrackMyRideExternalPowerBinarySensor,
)
from custom_components.trackmyride_map.coordinator import (
    _normalize_device,
    _parse_zone_ids,
)
from custom_components.trackmyride_map.sensor import (
    TrackMyRideAccCounterSensor,
    TrackMyRideInternalBatterySensor,
    TrackMyRideOdometerSensor,
    TrackMyRideVoltsSensor,
    TrackMyRideZoneSensor,
)
from tests.conftest import _FakeConfigEntry  # noqa: PLC2701

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


def _make_coordinator(data: dict) -> DataUpdateCoordinator:
    coordinator = DataUpdateCoordinator()
    coordinator.data = data
    return coordinator


def test_normalisation_includes_new_fields():
    """Ensure coordinator normalises new fields and zone parsing."""
    raw_device = {
        "unique_id": "veh123",
        "name": "Truck 1",
        "acc_counter": "12.3",
        "external_power": 1,
        "engine": 0,
        "internal_battery": "Charging",
        "odometer": "456.7",
        "volts": "12.5",
        "zone": "zone-a, zone-b,",
        "rego": "ABC123",
        "comms_delta": 10,
        "aaData": [{"lat": "1.23", "lng": "4.56", "speed": "78", "epoch": 1700000000}],
    }

    normalized = _normalize_device(raw_device, {})
    assert normalized is not None
    unique_id, data = normalized

    assert unique_id == "veh123"
    assert data["odometer"] == pytest.approx(456.7)
    assert data["acc_counter"] == pytest.approx(12.3)
    assert data["external_power"] == 1
    assert data["engine"] == 0
    assert data["internal_battery"] == "Charging"
    assert data["zone"] == "zone-a, zone-b,"
    assert data["zone_ids"] == ["zone-a", "zone-b"]
    assert data["zone_count"] == 2
    assert data["volts"] == pytest.approx(12.5)
    assert data["lat"] == pytest.approx(1.23)
    assert data["lon"] == pytest.approx(4.56)
    assert data["speed_kmh"] == pytest.approx(78)
    assert data["timestamp_epoch"] == 1700000000


def test_zone_parsing():
    """Zone strings are split, trimmed, and empties removed."""
    zone_ids = _parse_zone_ids("abc, def,,ghi ")
    assert zone_ids == ["abc", "def", "ghi"]
    assert len(zone_ids) == 3


def test_entity_unique_ids_stable():
    """Ensure entity unique_id values follow the expected suffix scheme."""
    coordinator = _make_coordinator({"veh999": {"name": "Vehicle 999"}})
    entry = _FakeConfigEntry()

    sensors = [
        TrackMyRideOdometerSensor(coordinator, entry, "veh999"),
        TrackMyRideVoltsSensor(coordinator, entry, "veh999"),
        TrackMyRideAccCounterSensor(coordinator, entry, "veh999"),
        TrackMyRideInternalBatterySensor(coordinator, entry, "veh999"),
        TrackMyRideZoneSensor(coordinator, entry, "veh999"),
        TrackMyRideExternalPowerBinarySensor(coordinator, entry, "veh999"),
        TrackMyRideEngineBinarySensor(coordinator, entry, "veh999"),
    ]

    expected_suffixes = [
        "odometer",
        "volts",
        "acc_counter",
        "internal_battery",
        "zone",
        "external_power",
        "engine",
    ]
    assert [sensor.unique_id for sensor in sensors] == [
        f"veh999_{suffix}" for suffix in expected_suffixes
    ]


def test_boolean_fields_map_to_binary_state():
    """Binary sensor on/off mapping for boolean fields."""
    coordinator = _make_coordinator(
        {
            "veh42": {
                "name": "Vehicle 42",
                "external_power": 0,
                "engine": 1,
            }
        }
    )
    entry = _FakeConfigEntry()
    external_power = TrackMyRideExternalPowerBinarySensor(coordinator, entry, "veh42")
    engine = TrackMyRideEngineBinarySensor(coordinator, entry, "veh42")

    assert external_power.is_on is False
    assert engine.is_on is True

    coordinator.data["veh42"]["external_power"] = 1
    coordinator.data["veh42"]["engine"] = 0

    assert external_power.is_on is True
    assert engine.is_on is False
