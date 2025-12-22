"""Test fixtures and stubs for Home Assistant dependencies."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest


class _FakeConfigEntry:
    """Minimal config entry stub."""

    def __init__(self, data=None, options=None, entry_id="test"):
        self.data = data or {}
        self.options = options or {}
        self.entry_id = entry_id


class _FakeConfigFlow:
    """Minimal ConfigFlow stub."""

    VERSION = 1

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id):
        self._unique_id = unique_id  # noqa: SLF001

    def _abort_if_unique_id_configured(self):
        return None

    def async_create_entry(self, *, title, data):
        return {"title": title, "data": data}

    def async_show_form(self, *, step_id, data_schema, errors):
        return {"step_id": step_id, "data_schema": data_schema, "errors": errors}


class _FakeOptionsFlow:
    """Minimal OptionsFlow stub."""

    def __init__(self, config_entry=None):
        self.config_entry = config_entry

    def async_show_form(self, *, step_id, data_schema, errors):
        return {"step_id": step_id, "data_schema": data_schema, "errors": errors}

    def async_create_entry(self, *, title, data):
        return {"title": title, "data": data}


class _FakeSession:
    """Minimal aiohttp client session stub."""

    def get(self, *args, **kwargs):
        raise RuntimeError("Network calls are not supported in tests")


def _prime_stub_modules():
    """Install baseline stub modules for import-time use."""

    if "homeassistant" in sys.modules:
        return

    if "aiohttp" not in sys.modules:
        aiohttp_mod = ModuleType("aiohttp")

        class ClientError(Exception):
            pass

        aiohttp_mod.ClientError = ClientError
        sys.modules["aiohttp"] = aiohttp_mod

    ha = ModuleType("homeassistant")
    ha.__path__ = []  # mark as package
    config_entries = ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = _FakeConfigFlow
    config_entries.OptionsFlow = _FakeOptionsFlow
    config_entries.ConfigEntry = _FakeConfigEntry

    const = ModuleType("homeassistant.const")

    class Platform(str):
        DEVICE_TRACKER = "device_tracker"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    const.Platform = Platform

    core = ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    core.HomeAssistant = HomeAssistant
    core.callback = lambda func: func

    exceptions = ModuleType("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        pass

    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []  # mark as package
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass):
        return _FakeSession()

    aiohttp_client.async_get_clientsession = async_get_clientsession
    helpers.aiohttp_client = aiohttp_client

    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, hass=None, logger=None, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self._listeners = []

        def __class_getitem__(cls, item):
            return cls

        def async_add_listener(self, listener):
            self._listeners.append(listener)
            return lambda: None

        def async_set_updated_data(self, data):
            self.data = data
            for listener in list(self._listeners):
                listener()

    class UpdateFailed(Exception):
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator=None):
            self.coordinator = coordinator

        def async_write_ha_state(self):
            return None

        def __class_getitem__(cls, item):
            return cls

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    helpers.update_coordinator = update_coordinator

    device_registry = ModuleType("homeassistant.helpers.device_registry")

    class DeviceEntryType:
        SERVICE = "service"

    device_registry.DeviceEntryType = DeviceEntryType
    helpers.device_registry = device_registry
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    entity_mod = ModuleType("homeassistant.helpers.entity")

    class DeviceInfo:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    entity_mod.DeviceInfo = DeviceInfo
    entity_mod.DeviceEntryType = DeviceEntryType
    helpers.entity = entity_mod
    sys.modules["homeassistant.helpers.entity"] = entity_mod

    entity_platform = ModuleType("homeassistant.helpers.entity_platform")

    def _add_entities_stub(entities, **kwargs):
        return entities

    entity_platform.AddEntitiesCallback = _add_entities_stub
    helpers.entity_platform = entity_platform
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    device_tracker_const = ModuleType("homeassistant.components.device_tracker.const")

    class SourceType(str):
        GPS = "gps"

    device_tracker_const.SourceType = SourceType
    sys.modules["homeassistant.components.device_tracker.const"] = device_tracker_const

    device_tracker_config = ModuleType(
        "homeassistant.components.device_tracker.config_entry"
    )

    class TrackerEntity:
        pass

    device_tracker_config.TrackerEntity = TrackerEntity
    sys.modules["homeassistant.components.device_tracker.config_entry"] = (
        device_tracker_config
    )

    sensor_mod = ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:
        DISTANCE = "distance"
        VOLTAGE = "voltage"

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"
        TOTAL = "total"

    class SensorEntity:
        _attr_native_unit_of_measurement = None
        _attr_device_class = None
        _attr_state_class = None

        def __init__(self):
            self._attr_native_unit_of_measurement = getattr(
                self, "_attr_native_unit_of_measurement", None
            )

    sensor_mod.SensorDeviceClass = SensorDeviceClass
    sensor_mod.SensorStateClass = SensorStateClass
    sensor_mod.SensorEntity = SensorEntity
    sys.modules["homeassistant.components.sensor"] = sensor_mod

    binary_sensor_mod = ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorDeviceClass:
        POWER = "power"
        RUNNING = "running"

    class BinarySensorEntity:
        _attr_device_class = None

    binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    ha.config_entries = config_entries
    ha.const = const
    ha.core = core
    ha.exceptions = exceptions
    ha.helpers = helpers

    if "voluptuous" not in sys.modules:
        vol = ModuleType("voluptuous")

        def Schema(value):
            return value

        def Optional(key, default=None):
            return key

        def Required(key, default=None):
            return key

        def In(options):
            def _validator(value):
                return value

            return _validator

        def All(*funcs):
            def _validator(value):
                for func in funcs:
                    if callable(func):
                        value = func(value)
                return value

            return _validator

        def Coerce(target_type):
            def _coerce(value):
                return target_type(value)

            return _coerce

        def Range(min=None, max=None):
            def _validator(value):
                return value

            return _validator

        vol.Schema = Schema
        vol.Optional = Optional
        vol.Required = Required
        vol.In = In
        vol.All = All
        vol.Coerce = Coerce
        vol.Range = Range

        sys.modules["voluptuous"] = vol


_prime_stub_modules()


@pytest.fixture(autouse=True)
def stub_homeassistant(monkeypatch):
    """Stub Home Assistant modules for import-time compatibility."""

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    _prime_stub_modules()

    # Refresh modules via monkeypatch to ensure isolation.
    monkeypatch.setitem(sys.modules, "homeassistant", sys.modules["homeassistant"])
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.config_entries",
        sys.modules["homeassistant.config_entries"],
    )
    monkeypatch.setitem(
        sys.modules, "homeassistant.const", sys.modules["homeassistant.const"]
    )
    monkeypatch.setitem(
        sys.modules, "homeassistant.core", sys.modules["homeassistant.core"]
    )
    monkeypatch.setitem(
        sys.modules, "homeassistant.exceptions", sys.modules["homeassistant.exceptions"]
    )
    monkeypatch.setitem(
        sys.modules, "homeassistant.helpers", sys.modules["homeassistant.helpers"]
    )
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.helpers.aiohttp_client",
        sys.modules["homeassistant.helpers.aiohttp_client"],
    )
