# VATSIM Tower Monitor

A configurable system tray application that monitors VATSIM for tower controllers at any airport and provides real-time notifications when controllers come online or go offline.

## Features

- **Real-time Monitoring**: Continuously monitors VATSIM API for configurable tower controllers
- **System Tray Integration**: Runs quietly in the system tray with color-coded status indicators
- **Smart Notifications**: Custom toast notifications with sound alerts for status changes
- **Push Notifications**: Optional Pushover integration for mobile/desktop push notifications
- **Multiple Controller Types**: Monitors tower, supporting facilities, and ground controllers
- **Controller Information**: Displays detailed controller information including callsign, name, frequency, and more
- **ARTCC Integration**: Automatically fetches controller names from configurable ARTCC roster
- **Customizable Settings**: Adjustable check intervals (minimum 30 seconds)
- **Cross-platform**: Works on Windows, macOS, and Linux

## Status Indicators

The system tray icon changes color based on current status:

- 🟣 **Purple**: Full coverage (Tower + Supporting facilities online)
- 🟢 **Green**: Tower online only
- 🟡 **Yellow**: Supporting facilities online (Tower offline)
- 🔴 **Red**: All facilities offline
- ⚫ **Gray**: Monitoring stopped or API error

## Configuration

The application uses a `config.json` file for all configuration settings. This file is automatically created with default values on first run if it doesn't exist.

### Configuration File Structure

```json
{
  "airport": {
    "code": "KOAK",
    "name": "Oakland International Airport",
    "display_name": "Oakland Tower"
  },
  "monitoring": {
    "check_interval": 60,
    "comment": "Check interval in seconds (minimum 30)"
  },
  "callsigns": {
    "tower": [
      "OAK_TWR",
      "OAK_1_TWR"
    ],
    "supporting": [
      "NCT_APP",
      "OAK_36_CTR",
      "OAK_62_CTR"
    ],
    "ground": [
      "OAK_GND",
      "OAK_1_GND"
    ]
  },
  "api": {
    "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
    "roster_url": "https://oakartcc.org/about/roster"
  },
  "notifications": {
    "sound_enabled": true,
    "sound_file": "ding.mp3",
    "toast_duration": 3000
  }
}
```

### Airport Configuration

The application can be configured to monitor any airport by updating the airport section:

```json
{
  "airport": {
    "code": "KOAK",
    "name": "Oakland International Airport",
    "display_name": "KOAK Tower"
  }
}
```

- `code`: Airport ICAO code (used for identification)
- `name`: Full airport name (for documentation)
- `display_name`: Name shown in notifications and UI

### Customizing Monitored Facilities

You can customize which callsigns to monitor by editing the `config.json` file:

#### Default Configuration (Oakland International Airport)
- **Tower Controllers**: `OAK_TWR`, `OAK_1_TWR`
- **Supporting Facilities**: `NCT_APP`, `OAK_36_CTR`, `OAK_62_CTR`
- **Ground Controllers**: `OAK_GND`, `OAK_1_GND`

**Note**: You can add or remove callsigns from any category by editing the corresponding arrays in `config.json`. Changes take effect after restarting the application.

## Installation

### Docker Deployment (Recommended for Headless)

For headless monitoring (no GUI), Docker provides the easiest cross-platform deployment:

#### Quick Start with Docker

1. **Install Docker**:
   - Windows/Mac: [Docker Desktop](https://docs.docker.com/get-docker/)
   - Linux: [Docker Engine](https://docs.docker.com/engine/install/)

2. **Clone and configure**:
   ```bash
   git clone https://github.com/leftos/oak_tower_watcher.git
   cd oak_tower_watcher
   cp .env.sample .env
   # Edit .env with your Pushover credentials
   ```

3. **Deploy**:
   ```bash
   # Linux/Mac
   ./scripts/deploy_docker.sh
   
   # Windows
   scripts\deploy_docker.bat
   
   # Or manually
   docker-compose up -d
   ```

4. **Monitor**:
   ```bash
   docker-compose logs -f
   ```

See the [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT_GUIDE.md) for detailed instructions.

### Traditional Python Installation

#### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Dependencies

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

The application requires:
- `requests` - For VATSIM API calls
- `PyQt6` - GUI framework for system tray and dialogs
- `python-vlc` - Audio playback for notification sounds
- `beautifulsoup4` - HTML parsing for Oakland ARTCC roster

### Audio Requirements

For notification sounds to work properly, you'll need VLC media player installed on your system:

- **Windows**: Download from [VLC official website](https://www.videolan.org/vlc/)
- **macOS**: Install via Homebrew: `brew install vlc` or download from VLC website
- **Linux**: Install via package manager: `sudo apt install vlc` (Ubuntu/Debian) or equivalent

## Usage

### Running the Application

#### Method 1: Direct Python execution
```bash
python oak_tower_watcher.py
```

#### Method 2: Using the batch file (Windows)
```bash
launch.bat
```

### System Tray Menu

Right-click the system tray icon to access:

- **KOAK Tower Status**: View detailed controller information
- **Check Now**: Force an immediate status check
- **Settings**: Adjust monitoring interval and configure Pushover notifications
- **Test Pushover**: Send a test push notification (if configured)
- **Start/Stop Monitoring**: Control the monitoring service
- **Exit**: Close the application

### Double-click Action

Double-click the system tray icon to quickly view the current tower status.

## Runtime Configuration

### Check Interval

The default check interval is 60 seconds. You can modify this in two ways:

#### Method 1: Settings Dialog (Recommended)
1. Right-click the system tray icon
2. Select "Settings"
3. Enter desired interval (minimum 30 seconds)
4. Click "Save"

This method automatically updates the `config.json` file and persists the setting.

#### Method 2: Direct File Edit
Edit the `check_interval` value in `config.json`:
```json
{
  "monitoring": {
    "check_interval": 120
  }
}
```

### Sound Notifications

Sound notifications can be configured in the `config.json` file:

```json
{
  "notifications": {
    "sound_enabled": true,
    "sound_file": "ding.mp3",
    "toast_duration": 3000
  }
}
```

- `sound_enabled`: Enable/disable notification sounds
- `sound_file`: Name of the audio file (must be in the same directory)
- `toast_duration`: Duration of toast notifications in milliseconds

### Pushover Notifications

The application supports push notifications via Pushover. To enable Pushover notifications, you'll need to:

1. Create a Pushover account at [pushover.net](https://pushover.net)
2. Create an application in your Pushover dashboard to get an API token
3. Note your user key from your Pushover dashboard

Configure Pushover in the application settings:

```json
{
  "pushover": {
    "enabled": true,
    "api_token": "your_application_api_token_here",
    "user_key": "your_user_key_here",
    "priority_levels": {
      "main_facility_and_supporting_above_online": 1,
      "main_facility_online": 0,
      "supporting_above_online": 0,
      "all_offline": 0,
      "error": -1
    },
    "sounds": {
      "main_facility_and_supporting_above_online": "magic",
      "main_facility_online": "pushover",
      "supporting_above_online": "intermission",
      "all_offline": "falling",
      "error": "none"
    }
  }
}
```

#### Pushover Configuration Options

- `enabled`: Enable/disable Pushover notifications
- `api_token`: Your Pushover application API token (required)
- `user_key`: Your Pushover user key (required)
- `priority_levels`: Notification priority (-2 to 2, 0 is normal)
- `sounds`: Notification sound (see Pushover documentation for available sounds)

#### Using the Settings Dialog

You can configure Pushover through the application's Settings dialog:

1. Right-click the system tray icon
2. Select "Settings"
3. Configure Pushover settings in the "Pushover Notifications" section
4. Click "Test Pushover" to verify your configuration
5. Click "Save" to apply changes

#### Priority Levels

The application automatically sets appropriate priority levels based on status:
- **High Priority (1)**: Full coverage online (tower + supporting facilities)
- **Normal Priority (0)**: Tower online, supporting facilities online, or facilities offline
- **Low Priority (-1)**: Error conditions

#### Testing Pushover

You can test your Pushover configuration in two ways:
1. **Settings Dialog**: Click "Test Pushover" in the settings
2. **System Tray Menu**: Right-click the tray icon and select "Test Pushover"

**Important**: You must provide your own Pushover API token and user key. The application does not include any pre-configured tokens to prevent abuse and ensure security.

### API Endpoints

You can customize the API endpoints used by the application:

```json
{
  "api": {
    "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
    "oakland_roster_url": "https://oakartcc.org/about/roster"
  }
}
```

## Logging

The application creates detailed logs in `vatsim_monitor.log` for troubleshooting and monitoring purposes. Logs include:

- API query results
- Controller status changes
- Error messages
- Application lifecycle events

## Instance Management

The application prevents multiple instances from running simultaneously using file-based locking:

- **Windows**: Uses `msvcrt.locking()`
- **Unix/Linux**: Uses `fcntl.flock()`

Lock file location: `~/.vatsim_monitor.lock`

## Notification Types

### Status Change Notifications

- **Full Coverage Online**: Both tower and supporting facilities come online
- **Tower Online**: Tower controller comes online
- **Supporting Facility Online**: Supporting facility comes online (tower offline)
- **Facilities Offline**: Controllers go offline

### Force Check Notifications

Manual "Check Now" always displays current status regardless of changes.

## Technical Details

### Architecture

- **Main Thread**: Qt GUI and system tray management
- **Worker Thread**: VATSIM API monitoring and data processing
- **Custom Toast System**: Cross-platform notification display

### API Integration

- **VATSIM API**: `https://data.vatsim.net/v3/vatsim-data.json`
- **Oakland ARTCC**: `https://oakartcc.org/about/roster` (for controller names)

### Error Handling

- Network timeouts and connection errors
- JSON parsing errors
- Audio playback failures
- Graceful degradation when services are unavailable

## Troubleshooting

### Common Issues

1. **No notifications appearing**
   - Check if VLC is installed for audio
   - Verify system tray is enabled
   - Check firewall/antivirus blocking network requests

2. **Application won't start**
   - Ensure all dependencies are installed
   - Check if another instance is already running
   - Review `vatsim_monitor.log` for error details

3. **API errors**
   - Verify internet connection
   - Check if VATSIM API is accessible
   - Review network proxy settings

### Log Analysis

Check `vatsim_monitor.log` for detailed error information:

```bash
tail -f vatsim_monitor.log  # Linux/macOS
type vatsim_monitor.log     # Windows
```

## Development

### Project Structure

```
oak_tower_watcher/
├── oak_tower_watcher.py    # Main application
├── config.json            # Configuration file
├── requirements.txt        # Python dependencies
├── launch.bat             # Windows launcher
├── ding.mp3              # Notification sound
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

### Key Classes

- `VATSIMMonitor`: Main application class
- `VATSIMWorker`: Background monitoring thread
- `CustomToast`: Cross-platform notification system
- `StatusDialog`: Controller information display
- `SettingsDialog`: Configuration interface

## Configuration Examples

### Monitoring Different Airports

To monitor a different airport, update both the airport information and callsigns in `config.json`:

```json
{
  "airport": {
    "code": "KLAX",
    "name": "Los Angeles International Airport",
    "display_name": "LAX Tower"
  },
  "callsigns": {
    "tower": ["LAX_TWR", "LAX_N_TWR", "LAX_S_TWR"],
    "supporting": ["SCT_APP", "LAX_APP"],
    "ground": ["LAX_GND", "LAX_N_GND", "LAX_S_GND"]
  },
  "api": {
    "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
    "roster_url": "https://socal-artcc.org/about/roster"
  }
}
```

### Disabling Sound Notifications

```json
{
  "notifications": {
    "sound_enabled": false,
    "sound_file": "ding.mp3",
    "toast_duration": 3000
  }
}
```

### Custom Check Intervals

```json
{
  "monitoring": {
    "check_interval": 30
  }
}
```

### Complete Configuration Example (Chicago O'Hare)

```json
{
  "airport": {
    "code": "KORD",
    "name": "Chicago O'Hare International Airport",
    "display_name": "ORD Tower"
  },
  "monitoring": {
    "check_interval": 45
  },
  "callsigns": {
    "tower": ["ORD_TWR", "ORD_1_TWR", "ORD_2_TWR"],
    "supporting": ["C90_APP", "ZAU_CTR"],
    "ground": ["ORD_GND", "ORD_1_GND", "ORD_2_GND"]
  },
  "api": {
    "vatsim_url": "https://data.vatsim.net/v3/vatsim-data.json",
    "roster_url": "https://zau-artcc.org/about/roster"
  },
  "notifications": {
    "sound_enabled": true,
    "sound_file": "custom_alert.mp3",
    "toast_duration": 4000
  }
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the repository for license details.

## Support

For issues, feature requests, or questions:

1. Check the troubleshooting section
2. Review application logs
3. Create an issue in the project repository

## Deployment Options Comparison

| Method | Platform | GUI | Setup Complexity | Best For |
|--------|----------|-----|------------------|----------|
| **Docker** | Windows, Linux, macOS | No | Low | Headless monitoring, servers |
| **Python GUI** | Windows, Linux, macOS | Yes | Medium | Desktop use with visual interface |
| **Systemd Service** | Linux only | No | High | Linux servers, manual setup |

### Docker Advantages
- ✅ Cross-platform (Windows, Linux, macOS)
- ✅ Easy deployment and updates
- ✅ Isolated environment
- ✅ Resource limits and health checks
- ✅ No Python/dependency management needed

### Traditional Installation Advantages
- ✅ Full GUI interface
- ✅ System tray integration
- ✅ Local audio notifications
- ✅ Direct system integration

## Acknowledgments

- VATSIM for providing the controller data API
- Oakland ARTCC for the controller roster information
- Qt/PyQt6 for the cross-platform GUI framework
- VLC for reliable audio playback capabilities
- [Control-tower icons created by Ahmad Yafie - Flaticon](https://www.flaticon.com/free-icons/control-tower)