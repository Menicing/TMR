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
| Minutes window | `devices#get` window for recent points (0–4320 minutes, default: 60). |

## Entities

- One `device_tracker` entity is created per vehicle with:
  - Native `latitude`/`longitude` properties and `source_type = gps`, allowing the
    entity to appear on Home Assistant maps.
  - Home Assistant's native zone-derived state: `home`, `not_home`, or the name of
    the smallest matching custom zone.
  - GPS attributes: `gps_accuracy`, speed (m/s and km/h), the UTC timestamp of the
    last valid GPS fix, and vehicle registration when available.
- Unique IDs come directly from the TrackMyRide `unique_id` field.
- Additional entities per vehicle:
  - Sensors: `Odometer` (km), `External Voltage` (V), `Engine On Time` (min), `Internal Battery` (status), and `Zone` (the TrackMyRide API zone with parsed zone IDs/count attributes).
  - Binary sensors: `External Power` (power) and `Engine` (running).

### Location history

Home Assistant's Recorder stores device-tracker coordinate changes, so no separate
location database is required. Recorder and History are enabled by default. If you
use `recorder` entity filters, make sure the TMR `device_tracker` entities are not
excluded. A Map card with a non-zero **Hours to show** value displays their recorded
route. The integration rejects malformed coordinate pairs and retains the last valid
fix rather than moving a vehicle to a partial or out-of-range location.

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
