from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import Settings, load_settings
from .state import VehicleState, to_serializable
from .trackmyride_client import TrackMyRideClient

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
LOGGER = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
settings: Settings = load_settings()

app = FastAPI(
    title="TrackMyRide Map",
    description="Home Assistant add-on for map tracking with the TrackMyRide API.",
    version="1.0.0",
)


class TrackerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = TrackMyRideClient(settings.api_base_url, settings.api_key)
        self.states: dict[str, VehicleState] = {
            vehicle_id: VehicleState(vehicle_id=vehicle_id)
            for vehicle_id in settings.vehicle_ids
        }
        self.started_at = datetime.utcnow()
        self.last_poll: datetime | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task:
            return
        await self.client.connect()
        self._task = asyncio.create_task(self._poll_loop())
        LOGGER.info(
            "Tracker started for %s vehicles with %s second interval",
            len(self.settings.vehicle_ids),
            self.settings.poll_interval,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        await self.client.disconnect()

    async def poll_once(self) -> None:
        if not self.settings.vehicle_ids:
            LOGGER.warning("No vehicle IDs configured; skipping poll")
            return

        tasks = [self._poll_vehicle(vehicle_id) for vehicle_id in self.states]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.last_poll = datetime.utcnow()

    async def _poll_vehicle(self, vehicle_id: str) -> None:
        try:
            position = await self.client.fetch_position(vehicle_id)
            state = self.states.setdefault(vehicle_id, VehicleState(vehicle_id))
            state.add_position(position, self.settings.track_history_minutes)
            LOGGER.debug(
                "Updated %s to (%s, %s)", vehicle_id, position.latitude, position.longitude
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to poll %s: %s", vehicle_id, exc)
            state = self.states.setdefault(vehicle_id, VehicleState(vehicle_id))
            state.add_error(str(exc))

    def get_state(self, vehicle_id: str) -> VehicleState:
        if vehicle_id not in self.states:
            raise KeyError(vehicle_id)
        return self.states[vehicle_id]

    @property
    def serializable_states(self) -> list[dict[str, Any]]:
        return to_serializable(self.states.values())

    async def _poll_loop(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.settings.poll_interval)


tracker = TrackerService(settings)


@app.on_event("startup")
async def startup() -> None:
    await tracker.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await tracker.stop()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "vehicles": tracker.serializable_states,
            "poll_interval": settings.poll_interval,
        },
    )


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return {
        "started_at": tracker.started_at.isoformat(),
        "last_poll": tracker.last_poll.isoformat() if tracker.last_poll else None,
        "vehicles_tracked": len(tracker.states),
        "poll_interval": settings.poll_interval,
        "track_history_minutes": settings.track_history_minutes,
    }


@app.get("/api/vehicles")
async def list_vehicles() -> list[dict[str, Any]]:
    return tracker.serializable_states


@app.get("/api/vehicles/{vehicle_id}")
async def vehicle_detail(vehicle_id: str) -> dict[str, Any]:
    try:
        return tracker.get_state(vehicle_id).as_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Vehicle not tracked") from exc


@app.get("/api/vehicles/{vehicle_id}/history")
async def vehicle_history(vehicle_id: str) -> list[dict[str, Any]]:
    try:
        state = tracker.get_state(vehicle_id)
        return [item for item in state.as_dict()["history"]]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Vehicle not tracked") from exc
