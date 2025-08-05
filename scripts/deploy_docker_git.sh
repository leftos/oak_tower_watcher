#!/bin/bash
set -e

# VATSIM Tower Monitor - Git-based Docker Deployment Script
# This script deploys using Git to ensure proper line endings

echo "=== VATSIM Tower Monitor Git-based Docker Deployment ==="
echo "Deploying headless monitor using Git and Docker..."

# Configuration
REPO_URL="${REPO_URL:-https://github.com/yourusername/oak_tower_watcher.git}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/vatsim-monitor}"
BRANCH="${BRANCH:-main}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "This script should not be run as root for security reasons."
   echo "Please run as a regular user with sudo privileges."
   exit 1
fi

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo "Installing system dependencies..."
sudo apt install -y git curl wget dos2unix docker.io docker-compose-plugin

# Add current user to docker group
echo "Adding user to docker group..."
sudo usermod -aG docker $USER

# Start and enable Docker
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Create deployment directory
echo "Setting up deployment directory..."
sudo mkdir -p $DEPLOY_DIR
sudo chown $USER:$USER $DEPLOY_DIR

# Clone or update repository
if [ -d "$DEPLOY_DIR/.git" ]; then
    echo "Updating existing repository..."
    cd $DEPLOY_DIR
    git fetch origin
    git reset --hard origin/$BRANCH
    git clean -fd
else
    echo "Cloning repository..."
    git clone -b $BRANCH $REPO_URL $DEPLOY_DIR
    cd $DEPLOY_DIR
fi

# Ensure all shell scripts have correct line endings and permissions
echo "Fixing line endings and permissions for shell scripts..."
find . -name "*.sh" -exec dos2unix {} \;
find . -name "*.sh" -exec chmod +x {} \;

# Create logs directory
mkdir -p logs

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from sample..."
    if [ -f .env.sample ]; then
        cp .env.sample .env
        echo "Please edit .env file with your configuration:"
        echo "  nano .env"
        echo ""
        echo "Required settings:"
        echo "  - PUSHOVER_API_TOKEN=your_api_token"
        echo "  - PUSHOVER_USER_KEY=your_user_key"
        echo "  - AIRPORT_CODE=KOAK (or your preferred airport)"
        echo ""
        read -p "Press Enter after editing .env file..."
    fi
fi

# Build and start the container
echo "Building and starting Docker container..."
docker compose build --no-cache
docker compose up -d

# Show status
echo ""
echo "=== Deployment Complete ==="
echo "Container status:"
docker compose ps

echo ""
echo "To view logs:"
echo "  docker compose logs -f"
echo ""
echo "To stop the container:"
echo "  docker compose down"
echo ""
echo "To restart the container:"
echo "  docker compose restart"
echo ""
echo "Container should now be running without line ending issues!"