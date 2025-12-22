"""Config flow for TrackMyRide Map."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_IDENTITY_FIELD,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    POLL_INTERVAL_OPTIONS,
)


class TrackMyRideConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrackMyRide Map."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = f"{user_input[CONF_API_BASE_URL].rstrip('/')}"
            account_id = user_input.get(CONF_ACCOUNT_ID)
            if account_id:
                unique_id = f"{unique_id}:{account_id}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="TrackMyRide Map",
                data={
                    CONF_API_BASE_URL: user_input[CONF_API_BASE_URL],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_ACCOUNT_ID: user_input.get(CONF_ACCOUNT_ID),
                    CONF_IDENTITY_FIELD: user_input.get(CONF_IDENTITY_FIELD),
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_BASE_URL): str,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_ACCOUNT_ID): str,
                vol.Optional(CONF_IDENTITY_FIELD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return TrackMyRideOptionsFlowHandler(config_entry)


class TrackMyRideOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle TrackMyRide Map options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_options(user_input)

    async def async_step_options(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=current_interval,
                ): vol.In(POLL_INTERVAL_OPTIONS),
                vol.Optional(
                    CONF_IDENTITY_FIELD,
                    default=self.config_entry.options.get(
                        CONF_IDENTITY_FIELD,
                        self.config_entry.data.get(CONF_IDENTITY_FIELD, ""),
                    ),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="options", data_schema=data_schema, errors=errors
        )
