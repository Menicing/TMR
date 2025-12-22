"""Basic tests for TrackMyRide Map integration."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.trackmyride_map import api


def test_manifest_version_semver():
    """Ensure manifest version follows SemVer."""

    manifest = json.loads(
        Path("custom_components/trackmyride_map/manifest.json").read_text()
    )
    version = manifest.get("version", "")
    assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid version: {version}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abcd", "***"),
        ("secretkey", "se***ey"),
        ("", ""),
    ],
)
def test_no_secrets_in_logs_or_strings(value: str, expected: str):
    """Ensure redaction helper strips secrets from logs."""

    redacted = api._redact(value)  # noqa: SLF001
    assert redacted == expected
    assert value == "" or value not in redacted


def test_imports_load():
    """Import key modules without raising errors."""

    import custom_components.trackmyride_map  # noqa: F401
    import custom_components.trackmyride_map.api  # noqa: F401
    import custom_components.trackmyride_map.config_flow  # noqa: F401
    import custom_components.trackmyride_map.coordinator  # noqa: F401
