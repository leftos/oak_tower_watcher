# VATSIM Tower Monitor - Docker Deployment Guide

This guide will help you deploy the headless VATSIM Tower Monitor using Docker, which works on both Windows and Linux systems.

## Prerequisites

1. **Docker**: Install Docker Desktop (Windows/Mac) or Docker Engine (Linux)
   - Windows: [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/)
   - Linux: [Docker Engine for Linux](https://docs.docker.com/engine/install/)
   - Mac: [Docker Desktop for Mac](https://docs.docker.com/desktop/mac/install/)

2. **Docker Compose**: Usually included with Docker Desktop, or install separately on Linux

3. **Pushover Account**: Sign up at [Pushover.net](https://pushover.net/) for push notifications

## Quick Start

### Method 1: Using Docker Compose (Recommended)

1. **Clone or download the repository**:
   ```bash
   git clone https://github.com/leftos/oak_tower_watcher.git
   cd oak_tower_watcher
   ```

2. **Set up environment variables**:
   ```bash
   # Copy the sample environment file
   cp .env.sample .env
   
   # Edit .env with your settings
   nano .env  # Linux/Mac
   notepad .env  # Windows
   ```

3. **Configure your Pushover credentials in `.env`**:
   ```env
   PUSHOVER_API_TOKEN=your_pushover_api_token_here
   PUSHOVER_USER_KEY=your_pushover_user_key_here
   CHECK_INTERVAL=30
   AIRPORT_CODE=KOAK
   TZ=UTC
   ```

4. **Build and start the service**:
   ```bash
   # Build the image (required on first run or after code changes)
   docker-compose build
   
   # Start the service
   docker-compose up -d
   ```
   
   **Note**: The container will automatically create a `config.json` file from the sample if one doesn't exist. Your environment variables will be injected into this configuration.

5. **Check the logs**:
   ```bash
   docker-compose logs -f
   ```

### Method 2: Using Docker Run

1. **Build the image**:
   ```bash
   docker build -t vatsim-tower-monitor .
   ```

2. **Create a config.json file** (copy from `config.sample.json` and modify):
   ```bash
   cp config.sample.json config.json
   # Edit config.json with your Pushover credentials
   ```

3. **Run the container**:
   ```bash
   docker run -d \
     --name vatsim-tower-monitor \
     --restart unless-stopped \
     -v $(pwd)/config.json:/app/config.json:ro \
     -v $(pwd)/logs:/app/logs \
     -e PUSHOVER_API_TOKEN=your_token_here \
     -e PUSHOVER_USER_KEY=your_user_key_here \
     vatsim-tower-monitor
   ```

## Configuration

### Environment Variables

The Docker container supports the following environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PUSHOVER_API_TOKEN` | Your Pushover application API token | - | Yes |
| `PUSHOVER_USER_KEY` | Your Pushover user key | - | Yes |
| `CHECK_INTERVAL` | How often to check VATSIM (seconds) | 30 | No |
| `AIRPORT_CODE` | Airport code to monitor | KOAK | No |
| `TZ` | Timezone for container | UTC | No |

### Configuration File

You can also mount a custom `config.json` file:

```json
{
  "airport": {
    "code": "KOAK",
    "name": "Oakland International Airport",
    "display_name": "Oakland Tower"
  },
  "monitoring": {
    "check_interval": 30
  },
  "callsigns": {
    "main_facility": ["^OAK_(?:\\d+_)?TWR$"],
    "supporting_above": ["^NCT_APP$", "^OAK_\\d+_CTR$"],
    "supporting_below": ["^OAK_(?:\\d+_)?GND$", "^OAK_(?:\\d+_)?DEL$"]
  },
  "pushover": {
    "enabled": true,
    "api_token": "YOUR_TOKEN_HERE",
    "user_key": "YOUR_USER_KEY_HERE"
  }
}
```

## Managing the Container

### Docker Compose Commands

```bash
# Start the service
docker-compose up -d

# Stop the service
docker-compose down

# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Update the service (after pulling new code)
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Docker Commands

```bash
# View logs
docker logs -f vatsim-tower-monitor

# Stop the container
docker stop vatsim-tower-monitor

# Start the container
docker start vatsim-tower-monitor

# Remove the container
docker rm vatsim-tower-monitor

# View container status
docker ps
```

## Monitoring Different Airports

To monitor a different airport, update your configuration:

### Option 1: Environment Variables
```env
AIRPORT_CODE=KSFO
```

### Option 2: Custom config.json
Create a custom `config.json` with your airport's callsigns:

```json
{
  "airport": {
    "code": "KSFO",
    "name": "San Francisco International Airport",
    "display_name": "San Francisco Tower"
  },
  "callsigns": {
    "main_facility": ["^SFO_(?:\\d+_)?TWR$"],
    "supporting_above": ["^NCT_APP$", "^SFO_\\d+_CTR$"],
    "supporting_below": ["^SFO_(?:\\d+_)?GND$", "^SFO_(?:\\d+_)?DEL$"]
  }
}
```

## Troubleshooting

### Line Ending Issues (Windows to Linux Deployment)

If you're developing on Windows and deploying to Linux, you may encounter this error:
```
exec /app/docker-entrypoint.sh: no such file or directory
```

This happens because Windows uses CRLF line endings while Linux expects LF line endings.

**Solution 1: Use Git for Deployment (Recommended)**
```bash
# On your Linux server, clone/pull the repository instead of using SCP
git clone https://github.com/yourusername/oak_tower_watcher.git
cd oak_tower_watcher

# Or if already cloned, pull updates
git pull origin main

# Git automatically converts line endings correctly
docker-compose build --no-cache
docker-compose up -d
```

**Solution 2: Use the Automated Git Deployment Script**
```bash
# On your Linux server, download and run the deployment script
wget https://raw.githubusercontent.com/yourusername/oak_tower_watcher/main/scripts/deploy_docker_git.sh
chmod +x deploy_docker_git.sh
./deploy_docker_git.sh
```

**Solution 3: Fix Line Endings After SCP**
If you prefer to use SCP, run this after copying files:
```bash
# On your Linux server, after copying files with SCP
wget https://raw.githubusercontent.com/yourusername/oak_tower_watcher/main/scripts/fix_line_endings.sh
chmod +x fix_line_endings.sh
./fix_line_endings.sh /path/to/your/project

# Then rebuild the container
docker-compose build --no-cache
docker-compose up -d
```

**Solution 4: Manual Fix**
```bash
# Install dos2unix if not already installed
sudo apt install -y dos2unix

# Fix line endings for all shell scripts
find . -name "*.sh" -exec dos2unix {} \;
find . -name "*.sh" -exec chmod +x {} \;

# Specifically fix the Docker entrypoint
dos2unix docker-entrypoint.sh
chmod +x docker-entrypoint.sh

# Rebuild the container
docker-compose build --no-cache
docker-compose up -d
```

### Docker Permission Issues (Linux)

If you get permission denied errors like:
```
permission denied while trying to connect to the Docker daemon socket
```

**Solution 1: Add user to docker group (Recommended)**
```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Test Docker access
docker --version
```

**Solution 2: Use sudo (Temporary fix)**
```bash
# Prefix all docker commands with sudo
sudo docker-compose up -d
sudo docker-compose logs -f
```

**Solution 3: Fix socket permissions**
```bash
# Fix Docker socket permissions
sudo chmod 666 /var/run/docker.sock
```

### Container Won't Start

1. **Check Docker logs**:
   ```bash
   docker-compose logs
   # or
   docker logs vatsim-tower-monitor
   ```

2. **Common issues**:
   - Missing Pushover credentials
   - Invalid JSON in config.json
   - Port conflicts (shouldn't happen with this app)
   - Docker permission issues (see above)

### No Notifications Received

1. **Verify Pushover credentials** in your `.env` file or `config.json`
2. **Check container logs** for Pushover errors:
   ```bash
   docker-compose logs | grep -i pushover
   ```
3. **Test Pushover manually** by restarting the container (it sends a test notification on startup)

### High Resource Usage

1. **Check the monitoring interval** (minimum 30 seconds recommended)
2. **Monitor container resources**:
   ```bash
   docker stats vatsim-tower-monitor
   ```

### Configuration Changes Not Taking Effect

1. **Restart the container** after configuration changes:
   ```bash
   docker-compose restart
   ```

2. **For major changes**, rebuild the container:
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

## Security Considerations

- The container runs as a non-root user (`vatsim`)
- No ports are exposed (outbound-only service)
- Configuration files can be mounted read-only
- Resource limits are set in docker-compose.yml
- Logs are rotated automatically

## Updating

### Using Docker Compose

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Using Docker

```bash
# Pull latest code and rebuild
git pull
docker build -t vatsim-tower-monitor .

# Stop and remove old container
docker stop vatsim-tower-monitor
docker rm vatsim-tower-monitor

# Start new container
docker run -d \
  --name vatsim-tower-monitor \
  --restart unless-stopped \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/logs:/app/logs \
  vatsim-tower-monitor
```

## Multi-Platform Support

The Docker image works on:
- **Linux** (x86_64, ARM64)
- **Windows** (with Docker Desktop)
- **macOS** (with Docker Desktop)

## Cost Comparison

| Deployment Method | Monthly Cost | Pros | Cons |
|-------------------|--------------|------|------|
| Docker (Local) | $0 | Free, full control | Requires always-on computer |
| Docker (VPS) | $4-10 | 24/7 uptime, cloud-based | Monthly cost |
| DigitalOcean Droplet | $4-6 | Managed, reliable | Limited to Linux |

## Support

If you encounter issues:

1. Check the container logs first
2. Verify your configuration file syntax
3. Ensure Pushover credentials are correct
4. Test network connectivity to VATSIM API
5. Check Docker and Docker Compose versions

The Docker deployment provides the same functionality as the systemd service but with better portability and easier management across different operating systems!