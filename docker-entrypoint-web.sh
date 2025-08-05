#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting VATSIM Tower Monitor Web Interface..."

# Create config.json from sample if it doesn't exist
if [ ! -f config.json ]; then
    log "Creating config.json from sample..."
    cp config.sample.json config.json
fi

# Ensure logs directory exists
mkdir -p logs

# Set default values for Gunicorn if not provided
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
export GUNICORN_BIND=${GUNICORN_BIND:-0.0.0.0:8080}
export GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}

log "Configuration:"
log "  Workers: $GUNICORN_WORKERS"
log "  Bind: $GUNICORN_BIND"
log "  Timeout: $GUNICORN_TIMEOUT"
log "  Flask Environment: ${FLASK_ENV:-development}"

# Wait a moment for any dependencies
sleep 2

log "Starting web service..."

# Execute the command passed to the container
exec "$@"