"""Coordinator zone cache behaviour tests."""

from __future__ import annotations

import asyncio

from custom_components.trackmyride_map.coordinator import TrackMyRideDataCoordinator
from homeassistant.core import HomeAssistant


class _FakeClient:
    def __init__(self) -> None:
        self.devices_calls = 0
        self.zones_calls = 0

    async def async_get_devices(self, *, limit=1, minutes=60, filter_vehicle=None):
        self.devices_calls += 1
        return {
            "data": {
                "veh1": {
                    "unique_id": "veh1",
                    "zone": "Z1,Z2",
                }
            }
        }

    async def async_get_zones(self):
        self.zones_calls += 1
        return {
            "features": [
                {"id": "Z1", "properties": {"name": "Depot"}},
                {"id": "Z2", "properties": {"name": "Mine"}},
            ]
        }


def test_zones_cache_throttles_requests(monkeypatch):
    """Zones endpoint is not called more than once within cache window."""

    client = _FakeClient()
    coordinator = TrackMyRideDataCoordinator(HomeAssistant(), client, {})

    # First update populates cache.
    data_first = asyncio.run(coordinator._async_update_data())
    assert client.zones_calls == 1
    assert data_first["veh1"]["zone_state"] == "Depot, Mine"

    # Second update within TTL uses cache and does not refetch.
    data_second = asyncio.run(coordinator._async_update_data())
    assert client.zones_calls == 1
    assert data_second["veh1"]["zone_names"] == ["Depot", "Mine"]
