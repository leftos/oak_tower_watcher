#!/bin/bash
# Development shutdown script for OAK Tower Watcher Web Application
# Usage: ./web/stop_dev.sh (from root) or ./stop_dev.sh (from web dir)

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the web directory
cd "$SCRIPT_DIR"

echo "Stopping OAK Tower Watcher Web Application..."
echo ""

# Find and kill the Flask development server process
FLASK_PID=$(pgrep -f "python.*run_app.py")

if [ -n "$FLASK_PID" ]; then
    echo "Found Flask development server running with PID(s): $FLASK_PID"
    
    # Kill the process gracefully (SIGTERM first)
    for pid in $FLASK_PID; do
        echo "Sending SIGTERM to process $pid..."
        kill -TERM "$pid" 2>/dev/null
    done
    
    # Wait a moment for graceful shutdown
    sleep 2
    
    # Check if processes are still running
    REMAINING_PIDS=$(pgrep -f "python.*run_app.py")
    
    if [ -n "$REMAINING_PIDS" ]; then
        echo "Some processes still running, sending SIGKILL..."
        for pid in $REMAINING_PIDS; do
            echo "Sending SIGKILL to process $pid..."
            kill -KILL "$pid" 2>/dev/null
        done
        sleep 1
    fi
    
    # Final check
    FINAL_CHECK=$(pgrep -f "python.*run_app.py")
    if [ -z "$FINAL_CHECK" ]; then
        echo "✅ Flask development server stopped successfully"
    else
        echo "⚠️  Warning: Some processes may still be running"
        echo "Remaining PIDs: $FINAL_CHECK"
    fi
else
    echo "ℹ️  No Flask development server process found running"
fi

echo ""
echo "Shutdown complete."