#!/bin/bash
set -e

# VATSIM Tower Monitor - DigitalOcean Droplet Deployment Script
# This script sets up the headless VATSIM monitor on a fresh Ubuntu droplet

echo "=== VATSIM Tower Monitor Deployment Script ==="
echo "Setting up headless monitor on DigitalOcean droplet..."

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
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Create vatsim user if it doesn't exist
if ! id "vatsim" &>/dev/null; then
    echo "Creating vatsim user..."
    sudo useradd -r -s /bin/bash -d /opt/vatsim-monitor -m vatsim
fi

# Create application directory
echo "Setting up application directory..."
sudo mkdir -p /opt/vatsim-monitor
sudo chown vatsim:vatsim /opt/vatsim-monitor

# Switch to vatsim user for application setup
echo "Setting up application as vatsim user..."
sudo -u vatsim bash << 'EOF'
cd /opt/vatsim-monitor

# Create Python virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install requests beautifulsoup4

# Note: Additional dependencies will be installed from requirements_headless.txt
# when the application files are uploaded

# Create application files directory with proper structure
mkdir -p app/src app/config app/logs
cd app

echo "Application setup complete for vatsim user."
EOF

echo "=== Manual Steps Required ==="
echo ""
echo "1. Create and upload your deployment package:"
echo "   Run: python scripts/create_deployment_package.py"
echo "   Then upload: scp -r deployment_package username@YOUR_DROPLET_IP:/tmp/"
echo ""
echo "   Or manually copy files maintaining directory structure:"
echo "   - headless_monitor.py -> /opt/vatsim-monitor/app/"
echo "   - src/headless_worker.py -> /opt/vatsim-monitor/app/src/"
echo "   - src/notification_manager.py -> /opt/vatsim-monitor/app/src/"
echo "   - src/utils.py -> /opt/vatsim-monitor/app/src/"
echo "   - src/pushover_service.py -> /opt/vatsim-monitor/app/src/"
echo "   - config/config.py -> /opt/vatsim-monitor/app/config/"
echo "   - config/requirements_headless.txt -> /opt/vatsim-monitor/app/config/"
echo "   - config.json -> /opt/vatsim-monitor/app/"
echo ""
echo "2. Move files to application directory:"
echo "   sudo cp -r /tmp/deployment_package/* /opt/vatsim-monitor/app/"
echo "   sudo chown -R vatsim:vatsim /opt/vatsim-monitor/app/"
echo ""
echo "3. Install additional Python dependencies:"
echo "   sudo -u vatsim bash -c 'cd /opt/vatsim-monitor && source venv/bin/activate && pip install -r app/config/requirements_headless.txt'"
echo ""
echo "4. Set up the systemd service:"
echo "   sudo cp /opt/vatsim-monitor/app/config/vatsim-monitor.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable vatsim-monitor"
echo ""
echo "5. Configure your settings in /opt/vatsim-monitor/app/config.json"
echo "   Make sure to set up your Pushover API credentials!"
echo ""
echo "6. Start the service:"
echo "   sudo systemctl start vatsim-monitor"
echo ""
echo "7. Check service status:"
echo "   sudo systemctl status vatsim-monitor"
echo "   sudo journalctl -u vatsim-monitor -f"
echo ""
echo "=== Deployment script completed ==="
echo "The system is ready for your VATSIM monitor application!"