# TrackMyRide Home Assistant Add-on Repository

This repository contains a Home Assistant add-on that surfaces live and historical positions from the TrackMyRide API on an embedded map. The add-on bundles a lightweight FastAPI service and a Leaflet-based UI that polls the TrackMyRide API at a configurable interval and exposes helper endpoints for use in automations.

## Add-ons

| Add-on | Description |
| --- | --- |
| **TrackMyRide Map** | Displays vehicle positions on a map, caches history, and provides JSON endpoints for automations. |

## Installation

1. In Home Assistant, open **Settings → Add-ons → Add-on Store** and choose **⋮ → Repositories**.
2. Add the URL for this repository (or copy the repository folder into your local `addons/` directory when developing).
3. Install the **TrackMyRide Map** add-on. Home Assistant will build the image locally from this repository’s Dockerfile; no prebuilt GHCR image is required.
4. Configure your TrackMyRide API settings and vehicle IDs, then start the add-on.

### Image build notes

- The add-on is configured for a local build via Home Assistant Supervisor (see `build: .` in `config.yaml`), which avoids authentication issues pulling from GHCR.
- Architectures supported by the add-on manifest are `amd64`, `armv7`, and `aarch64` to cover common Home Assistant deployments (including Raspberry Pi 64-bit).
- If you want to publish prebuilt images, push them to a public namespace such as `ghcr.io/menicing/trackmyride-map-{arch}` and update `config.yaml` accordingly, but local builds remain the default.

## Add-on configuration

The add-on exposes the following options (stored in `/data/options.json` inside the container):

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `api_base_url` | string | `https://api.trackmyride.com` | Base URL for the TrackMyRide API. |
| `api_key` | string | _empty_ | API key or token used for authorization. Stored securely via Home Assistant secrets is recommended. |
| `vehicle_ids` | list of strings | `[]` | One or more TrackMyRide vehicle IDs to track. |
| `poll_interval` | integer | `30` | How often (in seconds) to poll the TrackMyRide API for fresh positions. |
| `track_history_minutes` | integer | `120` | How many minutes of history to retain for each vehicle. |
| `enable_debug` | boolean | `false` | Enables verbose logging for troubleshooting. |

### Map and API access

- Map UI is served over ingress for convenient embedding in Home Assistant. When not using ingress, the service listens on port `8099` by default.
- REST endpoints:
  - `GET /api/status` – health information and timestamps.
  - `GET /api/vehicles` – summary of tracked vehicles and last known positions.
  - `GET /api/vehicles/{vehicle_id}` – detailed state for a single vehicle.
  - `GET /api/vehicles/{vehicle_id}/history` – ordered list of recorded points.

## Development

- The FastAPI service reads configuration from `/data/options.json`.
- Run the service locally with:
  ```bash
  API_KEY=your_token API_BASE_URL=https://api.trackmyride.com VEHICLE_IDS="veh123,veh456" \
  POLL_INTERVAL=15 TRACK_HISTORY_MINUTES=120 ENABLE_DEBUG=true \
  uvicorn app.main:app --host 0.0.0.0 --port 8099
  ```
- Home Assistant’s build system injects the appropriate base image via the `BUILD_FROM` argument defined in `config.yaml`.
