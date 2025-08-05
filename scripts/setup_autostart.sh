#!/bin/bash

# VATSIM Tower Monitor - Docker Auto-start Setup Script
# This script sets up the Docker container to start automatically on boot

set -e

echo "Setting up VATSIM Tower Monitor Docker auto-start..."

# Get the current directory (project root)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="$PROJECT_DIR/config/vatsim-monitor-docker.service"
SYSTEMD_SERVICE_FILE="/etc/systemd/system/vatsim-monitor-docker.service"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! systemctl is-active --quiet docker; then
    echo "Error: Docker service is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Update the service file with the correct working directory and user
echo "Updating service file with current user and project directory..."
sed "s|User=leftos|User=$USER|g" "$SERVICE_FILE" > /tmp/vatsim-monitor-docker.service
sed -i "s|Group=leftos|Group=$USER|g" /tmp/vatsim-monitor-docker.service
sed -i "s|WorkingDirectory=/home/leftos/oak_tower_watcher|WorkingDirectory=$PROJECT_DIR|g" /tmp/vatsim-monitor-docker.service

# Copy the service file to systemd directory
echo "Installing systemd service..."
sudo cp /tmp/vatsim-monitor-docker.service "$SYSTEMD_SERVICE_FILE"
sudo chmod 644 "$SYSTEMD_SERVICE_FILE"

# Reload systemd and enable the service
echo "Enabling service to start on boot..."
sudo systemctl daemon-reload
sudo systemctl enable vatsim-monitor-docker.service

# Check if .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Warning: .env file not found. Please create one from .env.sample and configure your Pushover credentials."
    echo "Run: cp .env.sample .env && nano .env"
fi

echo ""
echo "✅ Auto-start setup complete!"
echo ""
echo "The VATSIM Tower Monitor Docker container will now:"
echo "1. Start automatically when the system boots"
echo "2. Restart automatically if it crashes (due to restart: unless-stopped policy)"
echo ""
echo "Available commands:"
echo "  Start service:    sudo systemctl start vatsim-monitor-docker"
echo "  Stop service:     sudo systemctl stop vatsim-monitor-docker"
echo "  Check status:     sudo systemctl status vatsim-monitor-docker"
echo "  View logs:        docker compose logs -f"
echo "  Disable autostart: sudo systemctl disable vatsim-monitor-docker"
echo ""
echo "To start the service now, run:"
echo "  sudo systemctl start vatsim-monitor-docker"