from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class VehiclePosition(BaseModel):
    vehicle_id: str
    latitude: float
    longitude: float
    recorded_at: datetime
    speed_kmh: float | None = None
    heading: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TrackMyRideClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "TrackMyRideClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers)
            LOGGER.debug("TrackMyRide client connected to %s", self._base_url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_position(self, vehicle_id: str) -> VehiclePosition:
        """Fetch the latest position for a single vehicle."""
        if self._client is None:
            await self.connect()
        assert self._client  # for type-checking

        endpoint = f"/v1/vehicles/{vehicle_id}/location"
        response = await self._client.get(endpoint, timeout=15)
        response.raise_for_status()

        payload = response.json()
        data = _extract_location_payload(payload)

        return VehiclePosition(
            vehicle_id=vehicle_id,
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            speed_kmh=_optional_float(data.get("speed_kmh")),
            heading=_optional_float(data.get("heading")),
            recorded_at=_parse_timestamp(data.get("recorded_at")),
            raw=payload,
        )


def _extract_location_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Coerce several likely payload shapes into a consistent structure.

    This method is defensive to account for variations in TrackMyRide API
    responses and mock data used during development.
    """
    if not isinstance(payload, dict):
        raise ValueError("Unexpected location payload format")

    data = payload.get("data") or payload
    # Common TrackMyRide-style fields
    latitude = data.get("latitude") or data.get("lat")
    longitude = data.get("longitude") or data.get("lng") or data.get("lon")

    if latitude is None or longitude is None:
        raise ValueError("Payload missing latitude/longitude fields")

    recorded_at = (
        data.get("recorded_at")
        or data.get("timestamp")
        or data.get("time")
        or datetime.utcnow().isoformat()
    )

    normalized = {
        "latitude": latitude,
        "longitude": longitude,
        "recorded_at": recorded_at,
        "speed_kmh": data.get("speed") or data.get("speed_kmh"),
        "heading": data.get("heading") or data.get("course"),
    }

    return normalized


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            LOGGER.debug("Falling back to raw timestamp for %s", value)
            return datetime.utcnow()
    return datetime.utcnow()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
