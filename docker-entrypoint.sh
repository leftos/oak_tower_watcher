#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting VATSIM Tower Monitor (Headless) Docker Container"

# Check if config.json exists, if not create from sample
if [ ! -f "/app/config.json" ]; then
    log "No config.json found, creating from sample..."
    cp /app/config.sample.json /app/config.json
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

# Ensure logs directory exists and has correct permissions
mkdir -p /app/logs
# Only try to change permissions if we can (ignore errors for mounted volumes)
chmod 755 /app/logs 2>/dev/null || true

log "Configuration complete, starting monitor..."

# Execute the main command
exec "$@"