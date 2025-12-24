"""TrackMyRide Map custom integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType

from .api import TrackMyRideClient, normalize_endpoint
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_IDENTITY_FIELD,
    CONF_MINUTES_WINDOW,
    CONF_USER_KEY,
    COORDINATOR,
    DEFAULT_API_ENDPOINT,
    DEFAULT_MINUTES,
    DOMAIN,
    LOGGER_NAME,
)
from .coordinator import TrackMyRideDataCoordinator

LOGGER = logging.getLogger(LOGGER_NAME)

_ENTITY_LABELS = {
    "odometer": "Odometer",
    "volts": "External Voltage",
    "acc_counter": "Engine On Time",
    "internal_battery": "Internal Battery",
    "zone": "Zone",
    "external_power": "External Power",
    "engine": "Engine",
}

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the latest version."""
    if entry.version < 2:
        LOGGER.info("Migrating TrackMyRide entry from version %s", entry.version)
        new_data = {**entry.data}
        new_data.setdefault(CONF_MINUTES_WINDOW, DEFAULT_MINUTES)
        # Require users to re-enter the user_key if it is missing.
        new_data.setdefault(CONF_USER_KEY, "")
        entry.version = 2
        hass.config_entries.async_update_entry(entry, data=new_data)
        LOGGER.info(
            "Migration to version 2 complete; reconfigure if authentication fails"
        )
    if entry.version < 3:
        LOGGER.info("Migrating TrackMyRide entry from version %s", entry.version)
        new_data = {**entry.data}
        try:
            new_data[CONF_API_BASE_URL] = normalize_endpoint(
                entry.data.get(CONF_API_BASE_URL) or DEFAULT_API_ENDPOINT
            )
        except Exception:  # pylint: disable=broad-except
            LOGGER.warning(
                "Failed to normalize TrackMyRide API endpoint for entry %s; keeping original",
                entry.entry_id,
            )
        entry.version = 3
        hass.config_entries.async_update_entry(entry, data=new_data)
        LOGGER.info("Migration to version 3 complete")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TrackMyRide Map from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config: dict[str, Any] = {
        CONF_API_BASE_URL: entry.data[CONF_API_BASE_URL],
        CONF_API_KEY: entry.options.get(CONF_API_KEY, entry.data[CONF_API_KEY]),
        CONF_USER_KEY: entry.options.get(CONF_USER_KEY, entry.data.get(CONF_USER_KEY)),
        CONF_ACCOUNT_ID: entry.data.get(CONF_ACCOUNT_ID),
        CONF_IDENTITY_FIELD: entry.options.get(CONF_IDENTITY_FIELD)
        or entry.data.get(CONF_IDENTITY_FIELD),
        CONF_MINUTES_WINDOW: entry.options.get(CONF_MINUTES_WINDOW)
        or entry.data.get(CONF_MINUTES_WINDOW, DEFAULT_MINUTES),
    }

    if not config[CONF_USER_KEY]:
        raise ConfigEntryAuthFailed("TrackMyRide user key missing; please reconfigure")

    client = TrackMyRideClient(
        hass,
        config[CONF_API_BASE_URL],
        config[CONF_API_KEY],
        config[CONF_USER_KEY],
    )
    coordinator = TrackMyRideDataCoordinator(hass, client, config)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {COORDINATOR: coordinator}
    await _migrate_registries(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _migrate_registries(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: TrackMyRideDataCoordinator,
) -> None:
    """Fix existing registry entries for devices and entities."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    for vehicle_id in coordinator.data or {}:
        device = device_registry.async_get_device(identifiers={(DOMAIN, vehicle_id)})
        if device and device.entry_type == DeviceEntryType.SERVICE:
            device_registry.async_update_device(device.id, entry_type=None)

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        vehicle_id, short_name = _derive_entity_parts(entity_entry.unique_id)
        if not short_name:
            continue

        vehicle_name = (
            (coordinator.data or {}).get(vehicle_id, {}).get("name") if vehicle_id else None
        )
        current_name = entity_entry.name
        default_like_name = current_name in (None, entity_entry.original_name)
        if (
            not default_like_name
            and vehicle_name
            and current_name == f"{vehicle_name} {short_name}"
        ):
            default_like_name = True

        if not default_like_name:
            continue

        updates: dict[str, Any] = {}
        if entity_entry.original_name != short_name:
            updates["original_name"] = short_name
        if current_name not in (None, short_name):
            updates["name"] = None

        if updates:
            entity_registry.async_update_entity(entity_entry.entity_id, **updates)


def _derive_entity_parts(unique_id: str | None) -> tuple[str | None, str | None]:
    """Return the vehicle id and short entity label from the known suffix map."""

    if not unique_id:
        return None, None
    for suffix, label in _ENTITY_LABELS.items():
        if unique_id.endswith(f"_{suffix}"):
            return unique_id[: -(len(suffix) + 1)], label
    return None, None
