"""Config flow for TrackMyRide Map."""

from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.core import callback

from .api import TrackMyRideAuthError, TrackMyRideClient, TrackMyRideEndpointError
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_IDENTITY_FIELD,
    CONF_MINUTES_WINDOW,
    CONF_POLL_INTERVAL,
    CONF_USER_KEY,
    DEFAULT_API_ENDPOINT,
    DEFAULT_MINUTES,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_MINUTES,
    MIN_MINUTES,
    POLL_INTERVAL_OPTIONS,
)


class TrackMyRideConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrackMyRide Map."""

    VERSION = 2

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input.get(CONF_API_BASE_URL) or DEFAULT_API_ENDPOINT
            api_key = user_input[CONF_API_KEY]
            user_key = user_input[CONF_USER_KEY]

            try:
                client = TrackMyRideClient(self.hass, base_url, api_key, user_key)
                await client.async_test_connection()
            except TrackMyRideEndpointError:
                errors["base"] = "invalid_endpoint"
            except TrackMyRideAuthError:
                errors["base"] = "invalid_auth"
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if not errors:
                account_id = user_input.get(CONF_ACCOUNT_ID)
                unique_id = f"{client.endpoint}"
                if account_id:
                    unique_id = f"{unique_id}:{account_id}"

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="TrackMyRide Map",
                    data={
                        CONF_API_BASE_URL: client.endpoint,
                        CONF_API_KEY: api_key,
                        CONF_USER_KEY: user_key,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_IDENTITY_FIELD: user_input.get(CONF_IDENTITY_FIELD),
                        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                        CONF_MINUTES_WINDOW: DEFAULT_MINUTES,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_BASE_URL, default=DEFAULT_API_ENDPOINT
                ): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_USER_KEY): str,
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
        current_minutes = self.config_entry.options.get(
            CONF_MINUTES_WINDOW,
            self.config_entry.data.get(CONF_MINUTES_WINDOW, DEFAULT_MINUTES),
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=current_interval,
                ): vol.In(POLL_INTERVAL_OPTIONS),
                vol.Required(
                    CONF_MINUTES_WINDOW,
                    default=current_minutes,
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_MINUTES, max=MAX_MINUTES)
                ),
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
