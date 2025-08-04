# VATSIM Tower Monitor

A configurable system tray application that monitors VATSIM for tower controllers at any airport and provides real-time notifications when controllers come online or go offline.

## Features

- **Real-time Monitoring**: Continuously monitors VATSIM API for configurable tower controllers
- **System Tray Integration**: Runs quietly in the system tray with color-coded status indicators
- **Smart Notifications**: Custom toast notifications with sound alerts for status changes
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

### Prerequisites

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
- **Settings**: Adjust monitoring interval
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

## Acknowledgments

- VATSIM for providing the controller data API
- Oakland ARTCC for the controller roster information
- Qt/PyQt6 for the cross-platform GUI framework
- VLC for reliable audio playback capabilities