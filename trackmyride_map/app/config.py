from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from pydantic import AnyHttpUrl, BaseModel, ValidationError, field_validator


class Settings(BaseModel):
    api_base_url: AnyHttpUrl
    api_key: str
    vehicle_ids: list[str]
    poll_interval: int = 30
    track_history_minutes: int = 120
    enable_debug: bool = False

    @field_validator("vehicle_ids", mode="before")
    @classmethod
    def _split_vehicle_ids(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable):
            return [str(item) for item in value if str(item).strip()]
        raise ValueError("vehicle_ids must be a list or comma-separated string")

    @field_validator("poll_interval", "track_history_minutes")
    @classmethod
    def _validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be greater than zero")
        return value


def load_settings() -> Settings:
    """Load settings from /data/options.json with environment overrides."""
    options_path = Path(os.environ.get("OPTIONS_PATH", "/data/options.json"))
    payload: dict[str, Any] = {}

    if options_path.exists():
        with options_path.open("r", encoding="utf-8") as handle:
            payload.update(json.load(handle))

    env_map = {
        "api_base_url": "API_BASE_URL",
        "api_key": "API_KEY",
        "vehicle_ids": "VEHICLE_IDS",
        "poll_interval": "POLL_INTERVAL",
        "track_history_minutes": "TRACK_HISTORY_MINUTES",
        "enable_debug": "ENABLE_DEBUG",
    }

    for key, env_var in env_map.items():
        if env_var not in os.environ:
            continue
        payload[key] = os.environ[env_var]

    try:
        return Settings(**payload)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid configuration: {exc}") from exc
