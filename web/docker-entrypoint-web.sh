#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Entrypoint: Starting web-api service setup..."

# This script runs as root. We set correct ownership of mounted volumes.
log "Ensuring correct ownership for mounted volumes: /app/logs and /app/data..."
mkdir -p /app/logs /app/data
chown -R vatsim:vatsim /app/logs /app/data

# Create config.json using Python config module if it doesn't exist and set ownership
if [ ! -f /app/config.json ]; then
    log "config.json not found. Generating default config..."
    python3 -c "
import sys
sys.path.append('/app')
from config.config import load_config
load_config()  # This will create the default config.json if it doesn't exist
"
    chown vatsim:vatsim /app/config.json
fi

# Set default values for Gunicorn if not provided
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-2}
export GUNICORN_BIND=${GUNICORN_BIND:-0.0.0.0:8080}
export GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}

log "Configuration complete. Starting application as 'vatsim' user..."

# Drop privileges and execute the main command (from CMD) as the 'vatsim' user.
# 'gosu' will be installed in the Dockerfile.
exec gosu vatsim "$@"