# Track My Ride Map – Home Assistant Custom Integration

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
  - State `travelling` while moving. A transition from `travelling` to `away` is delayed for three minutes so normal traffic-light, congestion, and roadwork stops do not end a trip. Resolved zones still take precedence while stopped.
  - Attributes: `latitude`, `longitude`, `speed_kmh`, `volts`, `last_comms`, `rego`, `last_update`
- Unique IDs come directly from the TrackMyRide `unique_id` field.
- Additional entities per vehicle:
  - Sensors: `Odometer` (km), `External Voltage` (V), `Engine On Time` (min), `Internal Battery` (status), `Zone` (raw zone string with parsed zone_ids/count attributes), and `GPS Location` (formatted coordinates with numeric latitude/longitude attributes).
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

- HACS uses GitHub releases to show friendly semantic versions and expose pending
  updates through Home Assistant's `update` entities. Without a release, HACS falls
  back to displaying a short commit hash such as `6a41e27`.
- Merging a manifest version change into `main` runs the `Publish HACS release`
  workflow. It creates a `vX.Y.Z` tag and GitHub release from the manifest version,
  allowing HACS to discover the release during its next metadata refresh and offer
  the update through Home Assistant.
- Keep `manifest.json` on a three-part semantic version. For example, manifest
  version `0.7.1` is automatically published as release and tag `v0.7.1`.
- The workflow is idempotent and can also be run manually from GitHub Actions if a
  metadata refresh or previous workflow run needs to be retried.
