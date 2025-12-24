"""Entity and coordinator normalisation tests."""

from __future__ import annotations

import pytest

from custom_components.trackmyride_map.binary_sensor import (
    TrackMyRideEngineBinarySensor,
    TrackMyRideExternalPowerBinarySensor,
)
from custom_components.trackmyride_map.coordinator import (
    _as_datetime_from_epoch,
    _minutes_to_timedelta,
    _normalize_device,
    _parse_zone_ids,
    _parse_zone_map,
)
from custom_components.trackmyride_map.sensor import (
    TrackMyRideAccCounterSensor,
    TrackMyRideInternalBatterySensor,
    TrackMyRideOdometerSensor,
    TrackMyRideVoltsSensor,
    TrackMyRideZoneSensor,
)
from custom_components.trackmyride_map.device_tracker import TrackMyRideDeviceTracker
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
    assert data["zone_names"] == ["zone-a", "zone-b"]
    assert data["zone_state"] == "zone-a, zone-b"
    assert data["volts"] == pytest.approx(12.5)
    assert data["lat"] == pytest.approx(1.23)
    assert data["lon"] == pytest.approx(4.56)
    assert data["speed_kmh"] == pytest.approx(78)
    assert data["timestamp_epoch"] == 1700000000
    assert data["timestamp_dt_utc"].isoformat() == "2023-11-14T22:13:20+00:00"
    assert data["acc_counter_timedelta"].total_seconds() == pytest.approx(738)
    assert data["acc_counter_str"] == "0:12:18"
    assert data["comms_delta"] == 10
    assert data["comms_delta_seconds"] == 9
    assert data["last_comms"] == "9 seconds"


def test_zone_parsing():
    """Zone strings are split, trimmed, and empties removed."""
    assert _parse_zone_ids("") == []
    assert _parse_zone_ids("abc") == ["abc"]
    zone_ids = _parse_zone_ids("abc, def,,ghi ")
    assert zone_ids == ["abc", "def", "ghi"]
    assert len(zone_ids) == 3


def test_zone_map_parsing_from_featurecollection():
    """Zones feature collection is mapped to a zone id -> name dict."""
    payload = {
        "features": [
            {"id": "Z1", "properties": {"name": "Depot"}},
            {"id": "Z2", "properties": {"name": "Mine"}},
        ]
    }
    assert _parse_zone_map(payload) == {"Z1": "Depot", "Z2": "Mine"}


def test_zone_names_rendering_with_fallback():
    """Zone names are resolved with fallback to id and rendered to state."""
    raw_device = {"unique_id": "veh123", "zone": "Z1,Z9"}
    normalized = _normalize_device(raw_device, {}, {"Z1": "Depot"})
    assert normalized is not None
    _, data = normalized
    assert data["zone_ids"] == ["Z1", "Z9"]
    assert data["zone_names"] == ["Depot", "Z9"]
    assert data["zone_state"] == "Depot, Z9"


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


def test_volts_rounding_two_decimals():
    """Voltage sensor rounds to two decimals while staying numeric."""
    coordinator = _make_coordinator({"veh1": {"name": "Vehicle", "volts": 12.3456}})
    entry = _FakeConfigEntry()
    sensor = TrackMyRideVoltsSensor(coordinator, entry, "veh1")
    assert sensor.native_value == pytest.approx(12.35)

    coordinator.data["veh1"]["volts"] = 12.3
    assert sensor.native_value == pytest.approx(12.3)

    coordinator.data["veh1"]["volts"] = None
    assert sensor.native_value is None


def test_epoch_to_utc_datetime():
    """Epoch seconds convert to aware UTC datetime."""
    dt = _as_datetime_from_epoch(1_700_000_000)
    assert dt.tzinfo is not None
    assert dt.isoformat() == "2023-11-14T22:13:20+00:00"


def test_duration_minutes_to_timedelta():
    """Minutes values convert to timedelta and readable string."""
    td = _minutes_to_timedelta(12.3)
    assert td.total_seconds() == pytest.approx(738)
    assert str(td) == "0:12:18"


def test_device_tracker_attributes_cleanup():
    """Device tracker exposes cleaned and renamed attributes."""
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "speed_kmh": 12,
                "volts": 12.3,
                "comms_delta": 10,
                "comms_delta_seconds": 9,
                "last_comms": "9 seconds",
                "rego": "ABC123",
                "timestamp_dt_utc": "2023-01-01T00:00:00+00:00",
                "timestamp_epoch": 1_672_531_200,
            }
        }
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")

    attrs = tracker.extra_state_attributes
    assert "comms_delta" not in attrs
    assert "comms_delta_seconds" not in attrs
    assert "last_update_epoch" not in attrs
    assert attrs["last_update"] == "2023-01-01T00:00:00+00:00"
    assert attrs["last_comms"] == "9 seconds"


def test_tracker_state_travelling_when_speed_gt_zero():
    """Speed above zero forces travelling state regardless of zone."""
    coordinator = _make_coordinator(
        {"veh1": {"name": "Vehicle 1", "speed_kmh": 5, "zone_state": "Home"}}
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")

    assert tracker.location_name == "travelling"


def test_tracker_state_zone_when_not_moving():
    """When stationary, zone name is used as state."""
    coordinator = _make_coordinator(
        {"veh1": {"name": "Vehicle 1", "speed_kmh": 0, "zone_state": "Home"}}
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")

    assert tracker.location_name == "Home"


def test_tracker_state_away_when_not_moving_no_zone():
    """When stationary without zone, state falls back to away."""
    coordinator = _make_coordinator(
        {"veh1": {"name": "Vehicle 1", "speed_kmh": 0, "zone_state": ""}}
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")

    assert tracker.location_name == "away"


def test_entity_skips_write_when_unchanged(monkeypatch):
    """Coordinator updates should not write when state is unchanged."""
    coordinator = _make_coordinator({"veh1": {"name": "Vehicle", "volts": 12.3}})
    entry = _FakeConfigEntry()
    sensor = TrackMyRideVoltsSensor(coordinator, entry, "veh1")

    calls: list[str] = []
    sensor.async_write_ha_state = lambda: calls.append("called")  # type: ignore[assignment]

    sensor._handle_coordinator_update()
    assert len(calls) == 1

    coordinator.data = {"veh1": {"name": "Vehicle", "volts": 12.3}}
    sensor._handle_coordinator_update()
    assert len(calls) == 1

    coordinator.data = {"veh1": {"name": "Vehicle", "volts": 13.0}}
    sensor._handle_coordinator_update()
    assert len(calls) == 2
