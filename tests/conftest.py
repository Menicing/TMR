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
        def __class_getitem__(cls, item):
            return cls

    class UpdateFailed(Exception):
        pass

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    helpers.update_coordinator = update_coordinator

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
        sys.modules, "homeassistant.config_entries", sys.modules["homeassistant.config_entries"]
    )
    monkeypatch.setitem(sys.modules, "homeassistant.const", sys.modules["homeassistant.const"])
    monkeypatch.setitem(sys.modules, "homeassistant.core", sys.modules["homeassistant.core"])
    monkeypatch.setitem(
        sys.modules, "homeassistant.exceptions", sys.modules["homeassistant.exceptions"]
    )
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", sys.modules["homeassistant.helpers"])
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.helpers.aiohttp_client",
        sys.modules["homeassistant.helpers.aiohttp_client"],
    )
