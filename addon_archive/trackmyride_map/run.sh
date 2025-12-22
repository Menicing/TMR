#!/usr/bin/with-contenv bashio

set -euo pipefail

export API_BASE_URL
export API_KEY
export VEHICLE_IDS
export POLL_INTERVAL
export TRACK_HISTORY_MINUTES
export ENABLE_DEBUG

API_BASE_URL=$(bashio::config 'api_base_url')
API_KEY=$(bashio::config 'api_key')
VEHICLE_IDS=$(bashio::config 'vehicle_ids | join(",")')
POLL_INTERVAL=$(bashio::config 'poll_interval')
TRACK_HISTORY_MINUTES=$(bashio::config 'track_history_minutes')
ENABLE_DEBUG=$(bashio::config 'enable_debug')

if bashio::var.has_value "${ENABLE_DEBUG}" && [ "${ENABLE_DEBUG}" = "true" ]; then
    export LOG_LEVEL=debug
else
    export LOG_LEVEL=info
fi

echo "Starting TrackMyRide Map add-on..."
echo "Tracking vehicles: ${VEHICLE_IDS}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8099
