#!/bin/bash

# Database Migration Script for OAK Tower Watcher
# This script runs database migrations before the application starts

set -e  # Exit on any error

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

echo "==========================="
echo "Database Migration Started"
echo "==========================="
echo "Project root: $PROJECT_ROOT"
echo "Timestamp: $(date)"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not available"
    exit 1
fi

# Run the migration script
echo "Running database migrations..."

# Check if we're in a Docker container
if [ -f /.dockerenv ]; then
    echo "Running in Docker container"
    
    # In Docker, we might have specific database paths
    if [ -f "/app/oak_tower_watcher.db" ]; then
        echo "Found database at /app/oak_tower_watcher.db"
        python3 scripts/migrate_database.py --db "/app/oak_tower_watcher.db" --latest
    elif [ -f "/app/data/oak_tower_watcher.db" ]; then
        echo "Found database at /app/data/oak_tower_watcher.db"
        python3 scripts/migrate_database.py --db "/app/data/oak_tower_watcher.db" --latest
    else
        echo "Searching for all database files..."
        python3 scripts/migrate_database.py --all --latest
    fi
else
    echo "Running in development environment"
    
    # In development, search for all database files
    echo "Searching for all database files..."
    python3 scripts/migrate_database.py --all --latest
fi

migration_result=$?

if [ $migration_result -eq 0 ]; then
    echo ""
    echo "✅ Database migration completed successfully"
    echo "==========================="
    echo ""
else
    echo ""
    echo "❌ Database migration failed with exit code: $migration_result"
    echo "==========================="
    echo ""
    exit $migration_result
fi