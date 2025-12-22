"""TrackMyRide Map custom integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import TrackMyRideClient
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_IDENTITY_FIELD,
    CONF_POLL_INTERVAL,
    COORDINATOR,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER_NAME,
)
from .coordinator import TrackMyRideDataCoordinator

LOGGER = logging.getLogger(LOGGER_NAME)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TrackMyRide Map from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config: dict[str, Any] = {
        CONF_API_BASE_URL: entry.data[CONF_API_BASE_URL],
        CONF_API_KEY: entry.data[CONF_API_KEY],
        CONF_ACCOUNT_ID: entry.data.get(CONF_ACCOUNT_ID),
        CONF_IDENTITY_FIELD: entry.options.get(CONF_IDENTITY_FIELD)
        or entry.data.get(CONF_IDENTITY_FIELD),
        CONF_POLL_INTERVAL: entry.options.get(CONF_POLL_INTERVAL)
        or entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    }

    client = TrackMyRideClient(
        hass, config[CONF_API_BASE_URL], config[CONF_API_KEY]
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
