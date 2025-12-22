from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Iterable

from .trackmyride_client import VehiclePosition


@dataclass
class VehicleState:
    vehicle_id: str
    last_position: VehiclePosition | None = None
    history: Deque[VehiclePosition] = field(default_factory=deque)
    last_error: str | None = None
    updated_at: datetime | None = None

    def add_position(self, position: VehiclePosition, retention_minutes: int) -> None:
        self.last_position = position
        self.updated_at = datetime.utcnow()
        self.last_error = None
        self.history.append(position)
        self._trim_history(retention_minutes)

    def add_error(self, message: str) -> None:
        self.last_error = message
        self.updated_at = datetime.utcnow()

    def _trim_history(self, retention_minutes: int) -> None:
        if retention_minutes <= 0:
            self.history.clear()
            return
        cutoff = datetime.utcnow() - timedelta(minutes=retention_minutes)
        while self.history and self.history[0].recorded_at < cutoff:
            self.history.popleft()

    def as_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "last_position": _position_as_dict(self.last_position),
            "history": [_position_as_dict(item) for item in self.history],
            "last_error": self.last_error,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def _position_as_dict(position: VehiclePosition | None) -> dict | None:
    if position is None:
        return None
    return {
        "vehicle_id": position.vehicle_id,
        "latitude": position.latitude,
        "longitude": position.longitude,
        "recorded_at": position.recorded_at.isoformat(),
        "speed_kmh": position.speed_kmh,
        "heading": position.heading,
    }


def to_serializable(state: Iterable[VehicleState]) -> list[dict]:
    return [item.as_dict() for item in state]
