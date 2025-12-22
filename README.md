# TrackMyRide Map – Home Assistant Custom Integration

![TrackMyRide icon](custom_components/trackmyride_map/icon.png)

This repository provides a **Home Assistant custom integration** (HACS-style) that creates `device_tracker` entities for TrackMyRide vehicles so they appear on the Home Assistant map. It runs entirely inside Home Assistant—no Supervisor add-on or extra Docker container is required.

> The previous Supervisor add-on has been archived under [`addon_archive/`](addon_archive/). Use this integration instead.

## Installation (HACS or manual)

1. Add this repository as a **custom repository** in HACS (or copy `custom_components/trackmyride_map` into `/config/custom_components/`).
2. Restart Home Assistant to load the integration.
3. Go to **Settings → Devices & Services → Add Integration** and search for **TrackMyRide Map**.
4. Enter your TrackMyRide API base URL, API key, and user key. Optionally add an account identifier if you need to distinguish multiple accounts.

## Configuration & options

The integration uses Home Assistant Config Entries with an Options flow:

| Setting | Description |
| --- | --- |
| API base URL | TrackMyRide endpoint (defaults to `https://app.trackmyride.com.au/v2/php/api.php`). |
| API key | TrackMyRide API key (required). |
| User key | TrackMyRide user key (required). |
| Poll interval | Select 15/30/60/120/300 seconds (default: 60s). Backoff increases temporarily after failures. |
| Minutes window | `devices#get` window for recent points (0–4320 minutes, default: 60). |

## Entities

- One `device_tracker` entity is created per vehicle with:
  - `latitude`/`longitude`, `source_type = gps`
  - Attributes: `speed_kmh`, `volts`, `comms_delta`, `rego`, `last_update_epoch`
- Unique IDs come directly from the TrackMyRide `unique_id` field.
- Additional entities per vehicle:
  - Sensors: `Odometer` (km), `External Voltage` (V), `Engine On Time` (min), `Internal Battery` (status), `Zone` (raw zone string with parsed zone_ids/count attributes).
  - Binary sensors: `External Power` (power) and `Engine` (running).

> If icons are missing, ensure `icon.png`/`logo.png` exist in `custom_components/trackmyride_map` (add the binary files via normal git/GitHub upload outside Codex).

## Troubleshooting

- **Vehicles missing from the map:** Each TrackMyRide device must expose `unique_id` in the API response. Devices without `unique_id` are ignored; check your TrackMyRide account or contact support if the field is missing.
- **Slow updates or API errors:** The coordinator applies a capped backoff after failures; check Home Assistant logs for error details.
- **No Supervisor install:** This project is a custom integration, not a Supervisor add-on. Do not install it via the Add-on Store.
- **Correct API endpoint:** The TrackMyRide API endpoint must be `https://app.trackmyride.com.au/v2/php/api.php`. Copying repository tree URLs or appending `/devices` will cause 404 errors.
- **Example request for debugging:** `module=devices&action=get&json=1&limit=1&minutes=60`.
- **If you see 404s:** The endpoint is wrong. HACS/Home Assistant should only call the API endpoint above; 404s usually mean an incorrect URL path.
- **Map tracking module:** Device locations come from the Devices module (`aaData` contains `lat`, `lng`, and `epoch`); ensure your TrackMyRide account has active devices with recent points.

## Development notes

- The integration polls using `DataUpdateCoordinator` with timezone-aware timestamps and defensive parsing of TrackMyRide payloads.
- Device tracker entities update automatically when new vehicles appear; polling is throttled to avoid API spam.

## Releases / Updating

- HACS requires a Git tag/release for versioned updates. Create releases using tags that follow `vX.Y.Z` and keep the manifest `version` in sync.
- The tag name must be `v0.1.0` when the manifest version is `0.1.0` (and similarly for future releases). This allows HACS to detect the semantic version instead of falling back to a commit hash.
