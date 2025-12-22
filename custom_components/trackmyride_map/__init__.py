"""TrackMyRide Map custom integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import TrackMyRideClient, normalize_endpoint
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_IDENTITY_FIELD,
    CONF_MINUTES_WINDOW,
    CONF_POLL_INTERVAL,
    CONF_USER_KEY,
    COORDINATOR,
    DEFAULT_MINUTES,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER_NAME,
)
from .coordinator import TrackMyRideDataCoordinator

LOGGER = logging.getLogger(LOGGER_NAME)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


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
        LOGGER.info("Migration to version 2 complete; reconfigure if authentication fails")
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
        CONF_API_KEY: entry.data[CONF_API_KEY],
        CONF_USER_KEY: entry.data.get(CONF_USER_KEY),
        CONF_ACCOUNT_ID: entry.data.get(CONF_ACCOUNT_ID),
        CONF_IDENTITY_FIELD: entry.options.get(CONF_IDENTITY_FIELD)
        or entry.data.get(CONF_IDENTITY_FIELD),
        CONF_POLL_INTERVAL: entry.options.get(CONF_POLL_INTERVAL)
        or entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
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
