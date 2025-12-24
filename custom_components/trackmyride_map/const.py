"""Constants for the TrackMyRide Map custom integration."""

from __future__ import annotations

DOMAIN = "trackmyride_map"
DEFAULT_NAME = "Track My Ride"

CONF_API_BASE_URL = "api_base_url"
CONF_API_KEY = "api_key"
CONF_USER_KEY = "user_key"
CONF_ACCOUNT_ID = "account_id"
CONF_IDENTITY_FIELD = "identity_field"
CONF_MINUTES_WINDOW = "minutes_window"

DEFAULT_API_ENDPOINT = "https://app.trackmyride.com.au/v2/php/api.php"

MIN_MINUTES = 0
MAX_MINUTES = 4320
DEFAULT_MINUTES = 60
THROTTLE_BACKOFF_INITIAL = 5
THROTTLE_BACKOFF_MAX = 300

COORDINATOR = "coordinator"

LOGGER_NAME = "custom_components.trackmyride_map"
