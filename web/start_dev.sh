#!/bin/bash
# Development launch script for OAK Tower Watcher Web Application
# Usage: ./web/start_dev.sh (from root) or ./start_dev.sh (from web dir)

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the web directory
cd "$SCRIPT_DIR"

# Activate the virtual environment
source venv/bin/activate

# Load environment variables from .env file if it exists (excluding comments)
if [ -f "../env/.env" ]; then
    export $(cat ../env/.env | grep -v '^#' | xargs)
fi

# Override with development-specific settings
export APP_ENV=development
export FLASK_ENV=development
export DATABASE_URL="sqlite:///${SCRIPT_DIR}/per_env/dev/data/users.db"
export DEBUG=True

# Launch the Flask development server
echo "Starting OAK Tower Watcher Web Application in development mode..."
echo "Environment: $APP_ENV"
echo "Flask Environment: $FLASK_ENV"
echo "Host: ${HOST:-localhost}"
echo "Port: ${PORT:-8080}"
echo ""

python run_app.py