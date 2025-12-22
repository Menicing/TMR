# TrackMyRide Map – Home Assistant Custom Integration

This repository provides a **Home Assistant custom integration** (HACS-style) that creates `device_tracker` entities for TrackMyRide vehicles so they appear on the Home Assistant map. It runs entirely inside Home Assistant—no Supervisor add-on or extra Docker container is required.

> The previous Supervisor add-on has been archived under [`addon_archive/`](addon_archive/). Use this integration instead.

## Installation (HACS or manual)

1. Add this repository as a **custom repository** in HACS (or copy `custom_components/trackmyride_map` into `/config/custom_components/`).
2. Restart Home Assistant to load the integration.
3. Go to **Settings → Devices & Services → Add Integration** and search for **TrackMyRide Map**.
4. Enter your TrackMyRide API base URL and API key/token. Optionally add an account identifier and a preferred identity field if your API payload lacks a stable vehicle ID.

## Configuration & options

The integration uses Home Assistant Config Entries with an Options flow:

| Setting | Description |
| --- | --- |
| API base URL | Base endpoint for the TrackMyRide API. |
| API key/token | Stored securely in the config entry. |
| Account identifier (optional) | Included in deterministic IDs for accounts without stable IDs. |
| Identity field (optional) | Field name to treat as the stable vehicle identifier when the API doesn’t expose one. |
| Poll interval | Select 15/30/60/120/300 seconds (default: 60s). Backoff increases temporarily after failures. |

## Entities

- One `device_tracker` entity is created per vehicle with:
  - `latitude`/`longitude`, `gps_accuracy`, `source_type = gps`
  - Attributes: `stable_id`, `speed_kmh`, `heading`, `battery_level`, `last_update`
- Unique IDs prefer API-stable fields (`id`, `uuid`, `vin`, `imei`, etc.). If none exist, deterministic SHA-1 hashes are generated (optionally including your account identifier).

## Troubleshooting

- **Vehicles missing from the map:** Enable an identity field in Options if your API response lacks `id/uuid/vin/imei`. Deterministic hashes are used as a fallback and a warning is logged.
- **Slow updates or API errors:** The coordinator applies a capped backoff after failures; check Home Assistant logs for error details.
- **No Supervisor install:** This project is a custom integration, not a Supervisor add-on. Do not install it via the Add-on Store.

## Development notes

- The integration polls using `DataUpdateCoordinator` with timezone-aware timestamps and defensive parsing of TrackMyRide payloads.
- Device tracker entities update automatically when new vehicles appear; polling is throttled to avoid API spam.

