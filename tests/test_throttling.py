"""Throttle handling and polling behaviour tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from custom_components.trackmyride_map.api import TrackMyRideClient
from custom_components.trackmyride_map.const import (
    CONF_MINUTES_WINDOW,
    DEFAULT_API_ENDPOINT,
)
from custom_components.trackmyride_map.config_flow import TrackMyRideOptionsFlowHandler
from custom_components.trackmyride_map.coordinator import TrackMyRideDataCoordinator
from tests.conftest import _FakeConfigEntry  # noqa: PLC2701

from homeassistant.core import HomeAssistant


class _FakeResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.headers = headers or {}

    async def text(self) -> str:
        return "{}"

    async def json(self):
        return {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def _make_client(session: _FakeSession) -> TrackMyRideClient:
    hass = HomeAssistant()
    client = TrackMyRideClient(hass, DEFAULT_API_ENDPOINT, "api", "user")
    client._session = session  # noqa: SLF001
    return client


def test_retry_after_seconds_header_sets_next_allowed(monkeypatch):
    """Retry-After seconds header sets next_allowed_at and skips early refresh."""

    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    session = _FakeSession([_FakeResponse(429, headers={"Retry-After": "10"})])
    client = _make_client(session)
    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(), client, {CONF_MINUTES_WINDOW: 60}
    )
    coordinator.data = {"veh1": {"name": "Unit Test"}}

    monkeypatch.setattr(coordinator, "_utcnow", lambda: now)
    data = asyncio.run(coordinator._async_update_data())

    assert session.calls == 1
    assert data == coordinator.data
    assert coordinator._next_allowed_at == now + timedelta(seconds=10)

    monkeypatch.setattr(coordinator, "_utcnow", lambda: now + timedelta(seconds=5))
    data_second = asyncio.run(coordinator._async_update_data())
    assert session.calls == 1
    assert data_second == coordinator.data


def test_throttle_next_allowed_uses_response_time_not_pre_request_now(monkeypatch):
    """Throttle handling uses the response time when calculating next_allowed_at."""

    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=2)
    session = _FakeSession([_FakeResponse(429, headers={"Retry-After": "10"})])
    client = _make_client(session)
    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(), client, {CONF_MINUTES_WINDOW: 60}
    )
    coordinator.data = {"veh1": {"name": "Unit Test"}}

    times = [t0, t1]

    def _fake_utcnow():
        return times.pop(0) if times else t1

    monkeypatch.setattr(coordinator, "_utcnow", _fake_utcnow)
    asyncio.run(coordinator._async_update_data())

    assert coordinator._next_allowed_at == t1 + timedelta(seconds=10)


def test_retry_after_http_date_header_sets_next_allowed(monkeypatch):
    """HTTP-date Retry-After header sets next_allowed_at correctly."""

    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    retry_at = now + timedelta(seconds=10)
    retry_after = format_datetime(retry_at, usegmt=True)

    session = _FakeSession([_FakeResponse(429, headers={"Retry-After": retry_after})])
    client = _make_client(session)
    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(), client, {CONF_MINUTES_WINDOW: 60}
    )
    coordinator.data = {"veh1": {"name": "Unit Test"}}

    monkeypatch.setattr(coordinator, "_utcnow", lambda: now)
    asyncio.run(coordinator._async_update_data())

    assert session.calls == 1
    assert coordinator._next_allowed_at is not None
    assert abs((coordinator._next_allowed_at - retry_at).total_seconds()) < 0.5


def test_x_ms_retry_after_ms_sets_next_allowed(monkeypatch):
    """x-ms-retry-after-ms header sets next_allowed_at in milliseconds."""

    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    session = _FakeSession(
        [_FakeResponse(429, headers={"x-ms-retry-after-ms": "1500"})]
    )
    client = _make_client(session)
    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(), client, {CONF_MINUTES_WINDOW: 60}
    )
    coordinator.data = {"veh1": {"name": "Unit Test"}}

    monkeypatch.setattr(coordinator, "_utcnow", lambda: now)
    asyncio.run(coordinator._async_update_data())

    assert session.calls == 1
    assert coordinator._next_allowed_at is not None
    assert abs(
        (coordinator._next_allowed_at - (now + timedelta(seconds=1.5))).total_seconds()
    ) < 0.1


def test_fallback_backoff_when_no_headers(monkeypatch):
    """Fallback backoff doubles when no Retry-After headers are present."""

    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    session = _FakeSession([_FakeResponse(429), _FakeResponse(429)])
    client = _make_client(session)
    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(), client, {CONF_MINUTES_WINDOW: 60}
    )
    coordinator.data = {"veh1": {"name": "Unit Test"}}

    monkeypatch.setattr(coordinator, "_utcnow", lambda: now)
    asyncio.run(coordinator._async_update_data())
    assert coordinator._next_allowed_at == now + timedelta(seconds=5)

    later = now + timedelta(seconds=6)
    monkeypatch.setattr(coordinator, "_utcnow", lambda: later)
    asyncio.run(coordinator._async_update_data())
    assert coordinator._next_allowed_at == later + timedelta(seconds=10)


def test_no_overlap_single_request_in_flight():
    """Concurrent refresh calls should not overlap HTTP requests."""

    async def _run_test():
        event = asyncio.Event()

        class _SlowClient:
            def __init__(self, ready: asyncio.Event) -> None:
                self.calls = 0
                self.active = 0
                self.max_active = 0
                self.last_http_status = 200
                self._ready = ready

            async def async_get_devices(self, *, limit=1, minutes=60, filter_vehicle=None):
                self.calls += 1
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await self._ready.wait()
                self.active -= 1
                return {"data": {}}

        client = _SlowClient(event)
        coordinator = TrackMyRideDataCoordinator(HomeAssistant(), client, {})

        task1 = asyncio.create_task(coordinator.async_refresh())
        await asyncio.sleep(0)
        task2 = asyncio.create_task(coordinator.async_refresh())
        await asyncio.sleep(0)
        assert client.max_active == 1

        event.set()
        await asyncio.gather(task1, task2)
        assert client.max_active == 1

    asyncio.run(_run_test())


def test_options_flow_does_not_expose_scan_interval():
    """Options flow should not include a poll interval control."""

    entry = _FakeConfigEntry(options={"poll_interval": 15})
    handler = TrackMyRideOptionsFlowHandler(entry)
    result = asyncio.run(handler.async_step_options())
    schema = result["data_schema"].schema

    keys = []
    for key in schema:
        if hasattr(key, "schema"):
            keys.append(key.schema)
        else:
            keys.append(key)

    assert "poll_interval" not in keys


def test_poll_interval_option_is_ignored():
    """Poll interval option is ignored and does not alter update interval."""

    coordinator = TrackMyRideDataCoordinator(
        HomeAssistant(),
        client=type("_Client", (), {"last_http_status": 200})(),
        config={"poll_interval": 300},
    )
    assert coordinator.update_interval == timedelta(seconds=1)
