# VATSIM Tower Monitor - DigitalOcean Deployment Guide

This guide will help you deploy the headless VATSIM Tower Monitor on a DigitalOcean droplet to receive push notifications without running the Windows application.

## Prerequisites

1. **DigitalOcean Account**: Create an account at [DigitalOcean](https://www.digitalocean.com/)
2. **Pushover Account**: Sign up at [Pushover.net](https://pushover.net/) for push notifications
3. **SSH Key**: Set up SSH key authentication for secure access

## Step 1: Create a DigitalOcean Droplet

1. **Log into DigitalOcean** and click "Create" → "Droplets"

2. **Choose Configuration**:
   - **Image**: Ubuntu 22.04 (LTS) x64
   - **Plan**: Basic ($4/month droplet is sufficient)
   - **CPU Options**: Regular Intel (1 GB RAM, 1 vCPU)
   - **Datacenter**: Choose closest to your location
   - **Authentication**: SSH Key (recommended) or Password
   - **Hostname**: `vatsim-monitor` (or your preference)

3. **Create the droplet** and note the IP address

## Step 2: Initial Server Setup

1. **Connect to your droplet**:
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```

2. **Create a non-root user** (replace `username` with your preferred username):
   ```bash
   adduser username
   usermod -aG sudo username
   ```

3. **Set up SSH key for the new user** (if using SSH keys):
   ```bash
   rsync --archive --chown=username:username ~/.ssh /home/username
   ```

4. **Exit and reconnect as the new user**:
   ```bash
   exit
   ssh username@YOUR_DROPLET_IP
   ```

## Step 3: Run the Deployment Script

1. **Download the deployment script**:
   ```bash
   wget https://raw.githubusercontent.com/YOUR_REPO/oak_tower_watcher/main/deploy_to_droplet.sh
   chmod +x deploy_to_droplet.sh
   ```

2. **Run the deployment script**:
   ```bash
   ./deploy_to_droplet.sh
   ```

   This script will:
   - Update the system packages
   - Install Python 3 and required dependencies
   - Create a `vatsim` user for running the service
   - Set up the application directory structure
   - Create a Python virtual environment

## Step 4: Upload Application Files

1. **Create a local deployment package** on your Windows machine:
   ```bash
   # In your project directory
   mkdir deployment_package
   cp headless_monitor.py deployment_package/
   cp headless_worker.py deployment_package/
   cp notification_manager.py deployment_package/
   cp config.py deployment_package/
   cp utils.py deployment_package/
   cp pushover_service.py deployment_package/
   cp config.json deployment_package/
   cp vatsim-monitor.service deployment_package/
   ```

2. **Upload files to the droplet** using SCP:
   ```bash
   scp -r deployment_package/* username@YOUR_DROPLET_IP:/tmp/
   ```

3. **Move files to the application directory**:
   ```bash
   ssh username@YOUR_DROPLET_IP
   sudo cp /tmp/*.py /opt/vatsim-monitor/app/
   sudo cp /tmp/config.json /opt/vatsim-monitor/app/
   sudo chown -R vatsim:vatsim /opt/vatsim-monitor/app/
   ```

## Step 5: Configure Pushover

1. **Get your Pushover credentials**:
   - Go to [Pushover.net](https://pushover.net/) and log in
   - Create a new application to get your **API Token**
   - Note your **User Key** from your dashboard

2. **Edit the configuration file**:
   ```bash
   sudo -u vatsim nano /opt/vatsim-monitor/app/config.json
   ```

3. **Update the Pushover settings**:
   ```json
   {
     "pushover": {
       "enabled": true,
       "api_token": "YOUR_API_TOKEN_HERE",
       "user_key": "YOUR_USER_KEY_HERE"
     }
   }
   ```

4. **Customize other settings** as needed (airport, callsigns, check interval, etc.)

## Step 6: Set Up the Systemd Service

1. **Install the service file**:
   ```bash
   sudo cp /tmp/vatsim-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

2. **Enable the service** to start on boot:
   ```bash
   sudo systemctl enable vatsim-monitor
   ```

3. **Start the service**:
   ```bash
   sudo systemctl start vatsim-monitor
   ```

## Step 7: Verify Installation

1. **Check service status**:
   ```bash
   sudo systemctl status vatsim-monitor
   ```

2. **View logs**:
   ```bash
   sudo journalctl -u vatsim-monitor -f
   ```

3. **Test Pushover notifications**:
   ```bash
   # The service should automatically test Pushover on startup
   # Check the logs for "Pushover test successful"
   ```

## Managing the Service

### Common Commands

- **Start the service**: `sudo systemctl start vatsim-monitor`
- **Stop the service**: `sudo systemctl stop vatsim-monitor`
- **Restart the service**: `sudo systemctl restart vatsim-monitor`
- **Check status**: `sudo systemctl status vatsim-monitor`
- **View logs**: `sudo journalctl -u vatsim-monitor -f`
- **View recent logs**: `sudo journalctl -u vatsim-monitor --since "1 hour ago"`

### Updating Configuration

1. **Edit the config file**:
   ```bash
   sudo -u vatsim nano /opt/vatsim-monitor/app/config.json
   ```

2. **Restart the service** to apply changes:
   ```bash
   sudo systemctl restart vatsim-monitor
   ```

### Updating Application Code

1. **Upload new files** to `/tmp/` as in Step 4
2. **Stop the service**:
   ```bash
   sudo systemctl stop vatsim-monitor
   ```
3. **Copy new files**:
   ```bash
   sudo cp /tmp/*.py /opt/vatsim-monitor/app/
   sudo chown -R vatsim:vatsim /opt/vatsim-monitor/app/
   ```
4. **Start the service**:
   ```bash
   sudo systemctl start vatsim-monitor
   ```

## Troubleshooting

### Service Won't Start

1. **Check the logs**:
   ```bash
   sudo journalctl -u vatsim-monitor --no-pager
   ```

2. **Common issues**:
   - Missing Python dependencies: Reinstall with the deployment script
   - Permission issues: Ensure files are owned by `vatsim:vatsim`
   - Configuration errors: Check `config.json` syntax

### No Notifications Received

1. **Verify Pushover credentials** in `config.json`
2. **Check logs** for Pushover errors:
   ```bash
   sudo journalctl -u vatsim-monitor | grep -i pushover
   ```
3. **Test manually** by restarting the service (it sends a test notification on startup)

### High CPU/Memory Usage

1. **Check the monitoring interval** in `config.json` (minimum 30 seconds recommended)
2. **Monitor resource usage**:
   ```bash
   htop
   ```

## Security Considerations

- The service runs as a dedicated `vatsim` user with limited privileges
- The systemd service includes security hardening options
- Only necessary ports are exposed (none for this application)
- Regular system updates are recommended:
  ```bash
  sudo apt update && sudo apt upgrade
  ```

## Cost Estimation

- **DigitalOcean Droplet**: $4-6/month (Basic plan is sufficient)
- **Bandwidth**: Minimal (only API calls to VATSIM and Pushover)
- **Total**: ~$5/month for 24/7 monitoring with push notifications

## Support

If you encounter issues:

1. Check the logs first: `sudo journalctl -u vatsim-monitor -f`
2. Verify your configuration file syntax
3. Ensure Pushover credentials are correct
4. Check that the VATSIM API is accessible from your droplet

The headless monitor provides the same functionality as the Windows GUI version but runs continuously in the cloud, ensuring you never miss controller status changes!