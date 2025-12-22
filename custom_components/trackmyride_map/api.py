"""API client helpers for TrackMyRide."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_API_ENDPOINT, LOGGER_NAME

LOGGER = logging.getLogger(LOGGER_NAME)


class TrackMyRideEndpointError(Exception):
    """Raised when the endpoint is invalid or unreachable."""


class TrackMyRideAuthError(Exception):
    """Raised when authentication fails."""


def _redact(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def normalize_endpoint(url: str) -> str:
    """Ensure the URL uses the documented API endpoint."""

    if not url:
        raise TrackMyRideEndpointError("Empty endpoint")

    normalized = url.strip()
    if normalized.endswith("/v2/php/api.php"):
        return normalized

    trimmed = normalized.rstrip("/")
    if trimmed.endswith("/v2/php/api.php"):
        return trimmed

    return f"{trimmed}/v2/php/api.php"


def _validate_endpoint(url: str) -> str:
    """Normalise the URL to the documented API endpoint."""

    normalized = normalize_endpoint(url)
    if not normalized.endswith("/v2/php/api.php"):
        raise TrackMyRideEndpointError("Endpoint must end with /v2/php/api.php")
    return normalized


class TrackMyRideClient:
    """Client for TrackMyRide devices API."""

    def __init__(
        self, hass: HomeAssistant, base_url: str, api_key: str, user_key: str
    ) -> None:
        self._hass = hass
        self._endpoint = _validate_endpoint(base_url or DEFAULT_API_ENDPOINT)
        self._api_key = api_key
        self._user_key = user_key
        self._session = async_get_clientsession(hass)

    @property
    def endpoint(self) -> str:
        """Return the validated endpoint."""
        return self._endpoint

    async def async_get_devices(
        self, *, limit: int = 1, minutes: int = 60, filter_vehicle: str | None = None
    ) -> dict[str, Any]:
        """Fetch device data from TrackMyRide."""
        params: dict[str, Any] = {
            "limit": limit,
            "minutes": minutes,
        }
        if filter_vehicle:
            params["filter_vehicle"] = filter_vehicle
        return await self._async_request("devices", "get", params=params)

    async def async_get_zones(self) -> dict[str, Any]:
        """Fetch zones data from TrackMyRide."""

        return await self._async_request("zones", "get")

    async def async_test_connection(self) -> dict[str, Any]:
        """Perform a lightweight connection test."""
        return await self._async_request(
            "devices", "get", params={"limit": 1, "minutes": 60}
        )

    async def _async_request(
        self, module: str, action: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a request to TrackMyRide."""
        query: dict[str, Any] = {
            "api_key": self._api_key,
            "user_key": self._user_key,
            "module": module,
            "action": action,
            "json": 1,
        }
        if params:
            query.update(params)

        redacted_query = {
            **{k: v for k, v in query.items() if k not in {"api_key", "user_key"}},
            "api_key": _redact(str(self._api_key)),
            "user_key": _redact(str(self._user_key)),
        }
        LOGGER.debug(
            "TrackMyRide request: endpoint=%s module=%s action=%s params=%s",
            self._endpoint,
            module,
            action,
            redacted_query,
        )

        try:
            async with self._session.get(
                self._endpoint, params=query, timeout=15
            ) as resp:
                status = resp.status
                text = await resp.text()
                if status == 404:
                    raise TrackMyRideEndpointError("Endpoint returned 404")
                if status in (401, 403):
                    raise TrackMyRideAuthError(f"Authentication failed: {status}")
                if status >= 500:
                    raise ClientError(f"Server error {status}")

                try:
                    payload = await resp.json()
                except Exception:
                    LOGGER.debug(
                        "TrackMyRide response was not JSON (status=%s): %s",
                        status,
                        text[:200],
                    )
                    raise

                self._log_shape(module, action, status, payload)
        except TrackMyRideEndpointError:
            raise
        except TrackMyRideAuthError:
            raise
        except ClientError as err:
            raise err
        except Exception as err:  # pylint: disable=broad-except
            raise ClientError(err) from err

        if isinstance(payload, dict) and _has_invalid_key_message(payload):
            raise TrackMyRideAuthError("TrackMyRide API reported invalid keys")

        return payload if isinstance(payload, dict) else {"data": payload}

    def _log_shape(self, module: str, action: str, status: int, payload: Any) -> None:
        """Log a brief shape summary without secrets."""
        summary = ""
        if isinstance(payload, dict):
            summary = f"keys={list(payload.keys())}"
        elif isinstance(payload, list):
            summary = f"list_items={len(payload)}"
        else:
            summary = f"type={type(payload).__name__}"

        LOGGER.debug(
            "TrackMyRide response: endpoint=%s module=%s action=%s status=%s shape=%s",
            self._endpoint,
            module,
            action,
            status,
            summary,
        )


def _has_invalid_key_message(payload: dict[str, Any]) -> bool:
    message = str(payload).lower()
    return "invalid key" in message or "invalid api" in message
