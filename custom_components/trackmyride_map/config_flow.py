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


async def _async_validate_credentials(
    hass,
    base_url: str,
    api_key: str,
    user_key: str,
) -> TrackMyRideClient:
    """Validate credentials and return an initialised client."""
    try:
        client = TrackMyRideClient(hass, base_url, api_key, user_key)
        await client.async_test_connection()
        return client
    except TrackMyRideEndpointError as err:
        raise ValueError("invalid_endpoint") from err
    except TrackMyRideAuthError as err:
        raise ValueError("invalid_auth") from err
    except ClientError as err:
        raise ValueError("cannot_connect") from err
    except Exception as err:  # pylint: disable=broad-except
        raise ValueError("unknown") from err


def _field_default(
    key: str, config_entry: config_entries.ConfigEntry, fallback
) -> str | int | None:
    """Return the default value, preferring options over data."""
    return config_entry.options.get(key, config_entry.data.get(key, fallback))


class TrackMyRideConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrackMyRide Map."""

    VERSION = 3
    _reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input.get(CONF_API_BASE_URL) or DEFAULT_API_ENDPOINT
            api_key = user_input[CONF_API_KEY]
            user_key = user_input[CONF_USER_KEY]
            poll_interval = int(user_input[CONF_POLL_INTERVAL])
            minutes_window = int(user_input[CONF_MINUTES_WINDOW])

            try:
                client = await _async_validate_credentials(
                    self.hass, base_url, api_key, user_key
                )
            except ValueError as err:
                errors["base"] = str(err)
            else:
                account_id = user_input.get(CONF_ACCOUNT_ID)
                unique_id = f"{client.endpoint}"
                if account_id:
                    unique_id = f"{unique_id}:{account_id}"

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Track My Ride",
                    data={
                        CONF_API_BASE_URL: client.endpoint,
                        CONF_API_KEY: api_key,
                        CONF_USER_KEY: user_key,
                        CONF_ACCOUNT_ID: account_id,
                        CONF_IDENTITY_FIELD: user_input.get(CONF_IDENTITY_FIELD),
                        CONF_POLL_INTERVAL: poll_interval,
                        CONF_MINUTES_WINDOW: minutes_window,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_API_BASE_URL, default=DEFAULT_API_ENDPOINT): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_USER_KEY): str,
                vol.Optional(CONF_ACCOUNT_ID): str,
                vol.Optional(CONF_IDENTITY_FIELD): str,
                vol.Required(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): vol.In(POLL_INTERVAL_OPTIONS),
                vol.Required(
                    CONF_MINUTES_WINDOW, default=DEFAULT_MINUTES
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_MINUTES, max=MAX_MINUTES)),
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

    async def async_step_reauth(self, entry_data: dict | None = None):
        """Handle initiation of re-authentication."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None):
        """Handle the re-auth step where the user provides updated credentials."""

        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        entry = self._reauth_entry

        if user_input is not None:
            base_url = user_input.get(CONF_API_BASE_URL) or entry.data.get(
                CONF_API_BASE_URL, DEFAULT_API_ENDPOINT
            )
            api_key = user_input.get(CONF_API_KEY) or entry.options.get(
                CONF_API_KEY, entry.data[CONF_API_KEY]
            )
            user_key = user_input[CONF_USER_KEY]

            try:
                client = await _async_validate_credentials(
                    self.hass, base_url, api_key, user_key
                )
            except ValueError as err:
                errors["base"] = str(err)
            else:
                new_data = {
                    **entry.data,
                    CONF_API_BASE_URL: client.endpoint,
                    CONF_API_KEY: api_key,
                    CONF_USER_KEY: user_key,
                }
                new_options = {
                    **entry.options,
                    CONF_API_KEY: api_key,
                    CONF_USER_KEY: user_key,
                }
                self.hass.config_entries.async_update_entry(
                    entry, data=new_data, options=new_options
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_BASE_URL,
                    default=entry.data.get(CONF_API_BASE_URL, DEFAULT_API_ENDPOINT),
                ): str,
                vol.Optional(
                    CONF_API_KEY,
                    default=entry.options.get(CONF_API_KEY, entry.data.get(CONF_API_KEY)),
                ): str,
                vol.Required(CONF_USER_KEY): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=data_schema, errors=errors
        )


class TrackMyRideOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle TrackMyRide Map options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_options(user_input)

    async def async_step_options(self, user_input=None):
        errors: dict[str, str] = {}
        base_url = self.config_entry.data.get(CONF_API_BASE_URL, DEFAULT_API_ENDPOINT)
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            user_key = user_input[CONF_USER_KEY]
            try:
                await _async_validate_credentials(
                    self.hass, base_url, api_key, user_key
                )
            except ValueError as err:
                errors["base"] = str(err)
            else:
                options = {
                    CONF_API_KEY: api_key,
                    CONF_USER_KEY: user_key,
                    CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                    CONF_MINUTES_WINDOW: int(user_input[CONF_MINUTES_WINDOW]),
                    CONF_IDENTITY_FIELD: user_input.get(CONF_IDENTITY_FIELD, ""),
                }
                if getattr(self.hass, "config_entries", None):
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, options=options
                    )
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                return self.async_create_entry(title="", data=options)

        current_interval = _field_default(
            CONF_POLL_INTERVAL, self.config_entry, DEFAULT_POLL_INTERVAL
        )
        current_minutes = _field_default(
            CONF_MINUTES_WINDOW, self.config_entry, DEFAULT_MINUTES
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY,
                    default=_field_default(CONF_API_KEY, self.config_entry, ""),
                ): str,
                vol.Required(
                    CONF_USER_KEY,
                    default=_field_default(CONF_USER_KEY, self.config_entry, ""),
                ): str,
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
                    default=_field_default(CONF_IDENTITY_FIELD, self.config_entry, ""),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="options", data_schema=data_schema, errors=errors
        )
