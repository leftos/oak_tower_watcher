#!/bin/bash
set -e

# VATSIM Tower Monitor - Line Endings Fix Script
# Run this script on the Ubuntu droplet after copying files with SCP

echo "=== Fixing Line Endings for VATSIM Tower Monitor ==="

# Get the project directory (default to current directory)
PROJECT_DIR="${1:-.}"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Directory $PROJECT_DIR does not exist"
    exit 1
fi

echo "Fixing line endings in: $PROJECT_DIR"

# Install dos2unix if not already installed
if ! command -v dos2unix &> /dev/null; then
    echo "Installing dos2unix..."
    sudo apt update
    sudo apt install -y dos2unix
fi

# Fix line endings for all shell scripts
echo "Converting shell scripts..."
find "$PROJECT_DIR" -name "*.sh" -exec dos2unix {} \;

# Fix line endings for Python files (just in case)
echo "Converting Python files..."
find "$PROJECT_DIR" -name "*.py" -exec dos2unix {} \;

# Fix line endings for configuration files
echo "Converting configuration files..."
find "$PROJECT_DIR" -name "*.json" -exec dos2unix {} \;
find "$PROJECT_DIR" -name "*.yml" -exec dos2unix {} \;
find "$PROJECT_DIR" -name "*.yaml" -exec dos2unix {} \;
find "$PROJECT_DIR" -name "*.txt" -exec dos2unix {} \;
find "$PROJECT_DIR" -name "*.md" -exec dos2unix {} \;

# Make shell scripts executable
echo "Making shell scripts executable..."
find "$PROJECT_DIR" -name "*.sh" -exec chmod +x {} \;

# Fix Docker entrypoint specifically
if [ -f "$PROJECT_DIR/docker-entrypoint.sh" ]; then
    echo "Fixing docker-entrypoint.sh specifically..."
    dos2unix "$PROJECT_DIR/docker-entrypoint.sh"
    chmod +x "$PROJECT_DIR/docker-entrypoint.sh"
fi

echo ""
echo "=== Line Endings Fixed ==="
echo "All files have been converted to Unix line endings (LF)"
echo "Shell scripts have been made executable"
echo ""
echo "You can now run:"
echo "  docker-compose build --no-cache"
echo "  docker-compose up -d"