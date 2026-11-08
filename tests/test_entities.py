"""Entity and coordinator normalisation tests."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.trackmyride_map.binary_sensor import (
    TrackMyRideEngineBinarySensor,
    TrackMyRideExternalPowerBinarySensor,
)
from custom_components.trackmyride_map.coordinator import (
    _as_datetime_from_epoch,
    _as_valid_coordinates,
    _minutes_to_timedelta,
    _normalize_device,
    _parse_zone_ids,
    _parse_zone_map,
)
from custom_components.trackmyride_map.sensor import (
    TrackMyRideAccCounterSensor,
    TrackMyRideGpsLocationSensor,
    TrackMyRideInternalBatterySensor,
    TrackMyRideOdometerSensor,
    TrackMyRideVoltsSensor,
    TrackMyRideZoneSensor,
)
from custom_components.trackmyride_map.device_tracker import (
    TrackMyRideDeviceTracker,
    async_setup_entry as async_setup_tracker_entry,
)
from custom_components.trackmyride_map.const import COORDINATOR, DOMAIN
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
        TrackMyRideGpsLocationSensor(coordinator, entry, "veh999"),
        TrackMyRideExternalPowerBinarySensor(coordinator, entry, "veh999"),
        TrackMyRideEngineBinarySensor(coordinator, entry, "veh999"),
    ]

    expected_suffixes = [
        "odometer",
        "volts",
        "acc_counter",
        "internal_battery",
        "zone",
        "gps_location",
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
    assert "latitude" not in attrs
    assert "longitude" not in attrs
    assert "volts" not in attrs
    assert "last_comms" not in attrs
    assert attrs["last_gps_update"] == "2023-01-01T00:00:00+00:00"
    assert attrs["speed"] == pytest.approx(12 / 3.6)
    assert attrs["speed_kmh"] == 12


def test_tracker_leaves_zone_state_to_home_assistant():
    """Coordinates, rather than an API location name, drive native HA zones."""
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "speed_kmh": 5,
                "zone_state": "Depot",
                "lat": -37.8,
                "lon": 144.9,
            }
        }
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")

    assert tracker.location_name is None
    assert tracker.latitude == pytest.approx(-37.8)
    assert tracker.longitude == pytest.approx(144.9)


def test_tracker_writes_state_when_coordinates_change():
    """A coordinate-only update is written for Recorder and map history."""
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "lat": -33.8688,
                "lon": 151.2093,
                "timestamp_dt_utc": "2026-01-01T00:00:00+00:00",
            }
        }
    )
    tracker = TrackMyRideDeviceTracker(coordinator, _FakeConfigEntry(), "veh1")
    writes: list[tuple[float | None, float | None]] = []
    tracker.async_write_ha_state = lambda: writes.append(  # type: ignore[assignment]
        (tracker.latitude, tracker.longitude)
    )

    tracker._handle_coordinator_update()
    coordinator.data["veh1"].update(
        {
            "lat": -33.8699,
            "lon": 151.2104,
            "timestamp_dt_utc": "2026-01-01T00:00:10+00:00",
        }
    )
    tracker._handle_coordinator_update()

    assert writes[-1] == pytest.approx((-33.8699, 151.2104))
    assert len(writes) == 2


def test_tracker_platform_creates_one_stable_entity_per_device():
    """The platform exposes every API vehicle as one native tracker."""
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "lat": -33.8688,
                "lon": 151.2093,
            },
            "veh2": {"name": "Vehicle 2", "lat": -37.8136, "lon": 144.9631},
        }
    )
    entry = _FakeConfigEntry(entry_id="entry-1")
    hass = type(
        "FakeHass",
        (),
        {"data": {DOMAIN: {entry.entry_id: {COORDINATOR: coordinator}}}},
    )()
    added: list[TrackMyRideDeviceTracker] = []

    asyncio.run(async_setup_tracker_entry(hass, entry, added.extend))

    assert [tracker.unique_id for tracker in added] == ["veh1", "veh2"]
    assert all(
        tracker.device_info.identifiers == {(DOMAIN, tracker.unique_id)}
        for tracker in added
    )


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91, 10),
        (-91, 10),
        (10, 181),
        (10, -181),
        ("nan", 10),
        (10, "inf"),
        (None, 10),
        (True, 10),
    ],
)
def test_invalid_coordinate_pairs_are_rejected(latitude, longitude):
    """Invalid or partial GPS fixes cannot move a tracker."""
    assert _as_valid_coordinates(latitude, longitude) is None


def test_invalid_new_fix_preserves_last_valid_location():
    """A malformed API point cannot replace a previously valid GPS fix."""
    previous = {
        "veh1": {
            "lat": -33.8688,
            "lon": 151.2093,
            "speed_kmh": 25.0,
            "timestamp_epoch": 1_700_000_000,
            "timestamp_dt_utc": _as_datetime_from_epoch(1_700_000_000),
        }
    }
    normalized = _normalize_device(
        {
            "unique_id": "veh1",
            "aaData": [
                {
                    "lat": 999,
                    "lng": 151.5,
                    "speed": 80,
                    "epoch": 1_800_000_000,
                }
            ],
        },
        previous,
    )

    assert normalized is not None
    _, data = normalized
    assert data["lat"] == pytest.approx(-33.8688)
    assert data["lon"] == pytest.approx(151.2093)
    assert data["speed_kmh"] == pytest.approx(25.0)
    assert data["timestamp_epoch"] == 1_700_000_000


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


def test_tracker_delays_travelling_to_away(monkeypatch):
    """A routine traffic stop does not immediately end a trip."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "speed_kmh": 5,
                "zone_state": "",
                "lat": -33.8688,
                "lon": 151.2093,
            }
        }
    )
    tracker = TrackMyRideDeviceTracker(coordinator, _FakeConfigEntry(), "veh1")
    assert tracker.location_name == "travelling"

    coordinator.data["veh1"]["speed_kmh"] = 0
    monkeypatch.setattr(tracker, "_utcnow", lambda: start)
    tracker._handle_coordinator_update()
    assert tracker.location_name == "travelling"

    monkeypatch.setattr(
        tracker, "_utcnow", lambda: start + timedelta(seconds=179)
    )
    tracker._handle_coordinator_update()
    assert tracker.location_name == "travelling"

    monkeypatch.setattr(
        tracker, "_utcnow", lambda: start + timedelta(seconds=180)
    )
    tracker._handle_coordinator_update()
    assert tracker.location_name == "away"


def test_gps_location_is_available_on_tracker_and_sensor():
    """Coordinates are available through both tracking entity types."""
    coordinator = _make_coordinator(
        {
            "veh1": {
                "name": "Vehicle 1",
                "speed_kmh": 0,
                "zone_state": "Home",
                "lat": -33.8688,
                "lon": 151.2093,
            }
        }
    )
    entry = _FakeConfigEntry()
    tracker = TrackMyRideDeviceTracker(coordinator, entry, "veh1")
    sensor = TrackMyRideGpsLocationSensor(coordinator, entry, "veh1")

    assert tracker.latitude == pytest.approx(-33.8688)
    assert tracker.longitude == pytest.approx(151.2093)
    assert tracker.extra_state_attributes["latitude"] == pytest.approx(-33.8688)
    assert tracker.extra_state_attributes["longitude"] == pytest.approx(151.2093)
    assert sensor.native_value == "-33.868800, 151.209300"
    assert sensor.extra_state_attributes == {
        "latitude": -33.8688,
        "longitude": 151.2093,
    }


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
