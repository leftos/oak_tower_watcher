# Headless VATSIM Tower Monitor

This is the headless (no GUI) version of the VATSIM Tower Monitor, designed to run as a background service on servers, Docker containers, or any system where a graphical interface isn't needed.

## Features

- ✅ **Cross-platform**: Runs on Windows, Linux, macOS
- ✅ **Docker support**: Ready-to-use Docker container
- ✅ **Minimal dependencies**: Only requires requests and beautifulsoup4
- ✅ **Pushover notifications**: Push notifications to mobile devices
- ✅ **Systemd integration**: Can run as a Linux service
- ✅ **Instance locking**: Prevents multiple instances from running
- ✅ **Graceful shutdown**: Handles SIGINT and SIGTERM signals properly

## Quick Start

### Method 1: Docker (Recommended)

1. **Build the Docker image**:
   ```bash
   docker build -f headless/Dockerfile -t vatsim-headless .
   ```

2. **Run the container**:
   ```bash
   docker run -d \
     --name vatsim-headless \
     --restart unless-stopped \
     -v $(pwd)/config.json:/app/config.json:ro \
     -v $(pwd)/logs:/app/logs \
     vatsim-headless
   ```

3. **View logs**:
   ```bash
   docker logs -f vatsim-headless
   ```

### Method 2: Direct Python Execution

1. **Install dependencies**:
   ```bash
   pip install -r headless/requirements.txt
   ```

2. **Configure your settings** in `config.json` (copy from `config.sample.json`)

3. **Run the monitor**:
   ```bash
   python -m headless.main
   ```

## Configuration

The headless monitor uses the same configuration format as other implementations. Key settings:

```json
{
  "airport": {
    "code": "KOAK",
    "display_name": "Oakland Tower"
  },
  "monitoring": {
    "check_interval": 60
  },
  "pushover": {
    "enabled": true,
    "api_token": "your_pushover_api_token",
    "user_key": "your_pushover_user_key"
  }
}
```

## Dependencies

- **Python 3.8+**
- **requests** - For VATSIM API calls
- **beautifulsoup4** - For parsing ARTCC roster

## Docker Details

The included Dockerfile:
- Uses Python 3.11 slim base image
- Runs as non-root user for security
- Includes health checks
- Sets appropriate environment variables
- Creates proper log directory structure

## Systemd Service

For Linux systems, you can run this as a systemd service:

```ini
[Unit]
Description=VATSIM Headless Tower Monitor
After=network.target

[Service]
Type=simple
User=vatsim
WorkingDirectory=/opt/vatsim-monitor
ExecStart=/usr/bin/python3 -m headless.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Logging

Logs are written to:
- **Console**: For Docker and interactive use
- **File**: `logs/vatsim_monitor_headless.log` (if writable)

## Architecture

```
headless/
├── main.py          # Entry point and main application class
├── worker.py        # Threading-based VATSIM API worker
├── requirements.txt # Minimal dependencies
├── Dockerfile       # Docker container definition
└── README.md        # This file
```

## Shared Components

The headless implementation uses shared components:
- `shared/vatsim_core.py` - Core VATSIM API logic
- `shared/notification_manager.py` - Notification handling
- `shared/pushover_service.py` - Pushover integration
- `shared/utils.py` - Utility functions

## Differences from GUI Version

| Feature | Headless | Desktop GUI |
|---------|----------|-------------|
| **GUI** | ❌ None | ✅ PyQt6 system tray |
| **Notifications** | 📱 Pushover only | 🔔 Toast + Pushover |
| **Dependencies** | 📦 Minimal | 📦 Heavy (PyQt6, VLC) |
| **Platform** | 🌐 Any | 🖥️ Desktop required |
| **Docker** | ✅ Native support | ❌ Not suitable |
| **Server** | ✅ Perfect | ❌ Not suitable |

## Monitoring and Health Checks

The Docker container includes a health check that monitors the Python process. You can also check status manually:

```bash
# Check if process is running
docker exec vatsim-headless pgrep -f "python.*headless.main"

# View recent logs
docker logs --tail 50 vatsim-headless

# Check resource usage
docker stats vatsim-headless
```

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you're running from the project root directory
2. **Permission errors**: Ensure logs directory is writable
3. **API errors**: Check network connectivity to VATSIM API
4. **Pushover failures**: Verify API token and user key

### Debug Mode

Enable debug logging by modifying the logging level in `main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
```

## Performance

The headless monitor is very lightweight:
- **Memory**: ~50MB typical usage
- **CPU**: Minimal, only during API checks
- **Network**: ~1KB per check interval
- **Disk**: Log files only

## Security

- Runs as non-root user in Docker
- No exposed ports
- Read-only configuration mounting
- Isolated container environment
- No GUI attack surface

This implementation is ideal for production deployments where you need reliable monitoring without desktop dependencies.