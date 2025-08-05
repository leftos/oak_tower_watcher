#!/bin/bash

# VATSIM Tower Monitor - Auto-start Verification Script
# This script verifies that the Docker container is configured to start on boot

echo "🔍 Verifying VATSIM Tower Monitor auto-start configuration..."
echo ""

# Check if Docker is installed and enabled
echo "1. Checking Docker service..."
if systemctl is-enabled docker &>/dev/null; then
    echo "   ✅ Docker service is enabled to start on boot"
else
    echo "   ❌ Docker service is NOT enabled to start on boot"
    echo "   Run: sudo systemctl enable docker"
fi

if systemctl is-active docker &>/dev/null; then
    echo "   ✅ Docker service is currently running"
else
    echo "   ❌ Docker service is NOT running"
    echo "   Run: sudo systemctl start docker"
fi

echo ""

# Check Docker Compose restart policy
echo "2. Checking Docker Compose restart policy..."
if [ -f "docker-compose.yml" ]; then
    if grep -q "restart: unless-stopped" docker-compose.yml; then
        echo "   ✅ Container has 'restart: unless-stopped' policy"
    else
        echo "   ❌ Container does NOT have proper restart policy"
        echo "   Add 'restart: unless-stopped' to your docker-compose.yml"
    fi
else
    echo "   ❌ docker-compose.yml not found in current directory"
fi

echo ""

# Check if systemd service exists and is enabled
echo "3. Checking systemd service (optional)..."
if [ -f "/etc/systemd/system/vatsim-monitor-docker.service" ]; then
    if systemctl is-enabled vatsim-monitor-docker.service &>/dev/null; then
        echo "   ✅ Systemd service is installed and enabled"
        if systemctl is-active vatsim-monitor-docker.service &>/dev/null; then
            echo "   ✅ Systemd service is currently running"
        else
            echo "   ⚠️  Systemd service is enabled but not running"
        fi
    else
        echo "   ⚠️  Systemd service is installed but not enabled"
        echo "   Run: sudo systemctl enable vatsim-monitor-docker.service"
    fi
else
    echo "   ℹ️  Systemd service not installed (using Docker restart policy only)"
fi

echo ""

# Check if container is currently running
echo "4. Checking container status..."
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "vatsim-tower-monitor"; then
    echo "   ✅ Container is currently running"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep "vatsim-tower-monitor"
else
    echo "   ❌ Container is NOT running"
    echo "   Run: docker-compose up -d"
fi

echo ""

# Check configuration
echo "5. Checking configuration..."
if [ -f ".env" ]; then
    echo "   ✅ .env file exists"
    if grep -q "PUSHOVER_API_TOKEN=" .env && grep -q "PUSHOVER_USER_KEY=" .env; then
        echo "   ✅ Pushover credentials are configured"
    else
        echo "   ⚠️  Pushover credentials may not be configured"
    fi
else
    echo "   ⚠️  .env file not found"
    echo "   Run: cp .env.sample .env && nano .env"
fi

echo ""
echo "📋 Summary:"
echo "   Your Docker container will start on boot if:"
echo "   - Docker service is enabled ✓"
echo "   - Container has restart policy ✓"
echo "   - Container was running when system shut down"
echo ""
echo "💡 To test auto-start:"
echo "   1. Make sure container is running: docker-compose up -d"
echo "   2. Reboot your system: sudo reboot"
echo "   3. After reboot, check: docker ps"