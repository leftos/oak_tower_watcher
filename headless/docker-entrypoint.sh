#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting VATSIM Tower Monitor (Headless) Docker Container"

# Check if config.json exists, if not create using Python config module
if [ ! -f "/app/config.json" ]; then
    log "No config.json found, generating default config..."
    python3 -c "
import sys
sys.path.append('/app')
from config.config import load_config
load_config()  # This will create the default config.json if it doesn't exist
"
    log "Created config.json with default settings"
else
    log "Using existing config.json"
fi

# Override configuration with environment variables if provided
if [ -n "$PUSHOVER_API_TOKEN" ] || [ -n "$PUSHOVER_USER_KEY" ]; then
    log "Updating Pushover configuration from environment variables..."
    
    # Use Python to update the JSON configuration
    python3 -c "
import json
import os

# Load existing config
with open('/app/config.json', 'r') as f:
    config = json.load(f)

# Update Pushover settings from environment variables
if 'PUSHOVER_API_TOKEN' in os.environ:
    config['pushover']['api_token'] = os.environ['PUSHOVER_API_TOKEN']
    config['pushover']['enabled'] = True
    print('Updated Pushover API token from environment')

if 'PUSHOVER_USER_KEY' in os.environ:
    config['pushover']['user_key'] = os.environ['PUSHOVER_USER_KEY']
    config['pushover']['enabled'] = True
    print('Updated Pushover user key from environment')

# Save updated config
with open('/app/config.json', 'w') as f:
    json.dump(config, f, indent=2)
"
fi

# Override other settings from environment variables
if [ -n "$CHECK_INTERVAL" ]; then
    log "Setting check interval to $CHECK_INTERVAL seconds"
    python3 -c "
import json
import os

with open('/app/config.json', 'r') as f:
    config = json.load(f)

config['monitoring']['check_interval'] = int(os.environ['CHECK_INTERVAL'])

with open('/app/config.json', 'w') as f:
    json.dump(config, f, indent=2)
"
fi

if [ -n "$AIRPORT_CODE" ]; then
    log "Setting airport code to $AIRPORT_CODE"
    python3 -c "
import json
import os

with open('/app/config.json', 'r') as f:
    config = json.load(f)

config['airport']['code'] = os.environ['AIRPORT_CODE']

with open('/app/config.json', 'w') as f:
    json.dump(config, f, indent=2)
"
fi

# Configure database environment for bulk notifications
if [ -n "$DATABASE_URL" ]; then
    log "Setting up database environment for bulk notifications"
    export DATABASE_URL="$DATABASE_URL"
    
    log "Database URL configured: ${DATABASE_URL}"
fi

# Ensure logs directory exists and has correct permissions
mkdir -p /app/logs
# Set proper ownership and permissions for logs directory
chown vatsim:vatsim /app/logs 2>/dev/null || true
chmod 755 /app/logs 2>/dev/null || true
# Ensure the user can write to the logs directory
touch /app/logs/vatsim_monitor_headless.log 2>/dev/null || true
chown vatsim:vatsim /app/logs/vatsim_monitor_headless.log 2>/dev/null || true
chmod 644 /app/logs/vatsim_monitor_headless.log 2>/dev/null || true

log "Configuration complete, starting monitor..."

# Switch to vatsim user and execute the main command
exec "$@"