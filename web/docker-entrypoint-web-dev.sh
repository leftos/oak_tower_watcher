#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEV: $1"
}

log "Starting web-api development service setup..."

# This script runs as root. We set correct ownership of mounted volumes.
log "Ensuring correct ownership for mounted volumes..."

# Set ownership for writable mounted directories only
# Note: Most volumes are mounted read-only, so we only handle the writable ones
if [ -d "/app/web/per_env/dev/data" ]; then
    chown -R vatsim:vatsim /app/web/per_env/dev/data
fi

if [ -d "/app/web/per_env/dev/logs" ]; then
    chown -R vatsim:vatsim /app/web/per_env/dev/logs
fi

# These are for legacy support if they exist as separate mounts
if [ -d "/app/logs" ]; then
    chown -R vatsim:vatsim /app/logs
fi

if [ -d "/app/data" ]; then
    chown -R vatsim:vatsim /app/data
fi

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

# Set development environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1
export APP_ENV=development
export PYTHONPATH=/app:/app/web
export DATABASE_URL=${DATABASE_URL:-sqlite:////app/web/per_env/dev/data/users.db}

log "Development environment configured:"
log "  - FLASK_ENV: $FLASK_ENV"
log "  - FLASK_DEBUG: $FLASK_DEBUG"
log "  - APP_ENV: $APP_ENV"
log "  - DATABASE_URL: $DATABASE_URL"
log "  - PYTHONPATH: $PYTHONPATH"

# Run database migrations before starting the application
log "Running database migrations..."
if [ -f "/app/scripts/migrate_database.sh" ]; then
    cd /app && bash scripts/migrate_database.sh
    if [ $? -ne 0 ]; then
        log "ERROR: Database migration failed!"
        exit 1
    fi
    log "Database migrations completed successfully"
else
    log "WARNING: Migration script not found at /app/scripts/migrate_database.sh"
fi

log "Starting application as 'vatsim' user..."

# Drop privileges and execute the main command as the 'vatsim' user
exec gosu vatsim "$@"