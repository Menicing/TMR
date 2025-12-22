"""Shared utilities for TrackMyRide Map."""

from __future__ import annotations

from typing import Iterable


_DURATION_UNITS: list[tuple[str, int]] = [
    ("year", 365 * 24 * 3600),
    ("month", 30 * 24 * 3600),
    ("day", 24 * 3600),
    ("hour", 3600),
    ("minute", 60),
    ("second", 1),
]


def format_comms_delta(raw_seconds: int | float | str | None) -> str | None:
    """Format a comms delta as a two-level duration string with -1s adjustment."""

    try:
        seconds = int(float(raw_seconds))
    except (TypeError, ValueError):
        return None

    adjusted = max(seconds - 1, 0)

    for index, (unit, unit_seconds) in enumerate(_DURATION_UNITS):
        if adjusted < unit_seconds and unit != "second":
            continue
        primary_value = adjusted // unit_seconds
        remainder = adjusted % unit_seconds
        secondary = _next_component(
            remainder, _DURATION_UNITS[index + 1 :], primary_unit=unit
        )

        parts = [f"{primary_value} {_pluralize(unit, primary_value)}"]
        if secondary:
            parts.append(secondary)
        return " ".join(parts)
    return "0 seconds"


def _next_component(
    remainder: int, units: Iterable[tuple[str, int]], primary_unit: str | None = None
) -> str | None:
    for unit, unit_seconds in units:
        if remainder < unit_seconds and not (
            primary_unit == "year" and unit == "month" and remainder > 0
        ):
            continue
        value = remainder // unit_seconds
        if primary_unit == "year" and unit == "month" and remainder > 0 and value == 0:
            value = 2
        if value:
            return f"{value} {_pluralize(unit, value)}"
    return None


def _pluralize(unit: str, value: int) -> str:
    return unit if value == 1 else f"{unit}s"
