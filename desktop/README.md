# Desktop VATSIM Tower Monitor

This is the desktop GUI version of the VATSIM Tower Monitor, designed to run as a system tray application on Windows, macOS, and Linux with full graphical interface support.

## Features

- ✅ **Cross-platform GUI**: Runs on Windows, macOS, and Linux
- ✅ **System tray integration**: Colored status indicators in system tray
- ✅ **Toast notifications**: Animated popup notifications with sound
- ✅ **Interactive dialogs**: Status details and settings configuration
- ✅ **Pushover notifications**: Mobile push notifications
- ✅ **Auto-update functionality**: Automatic application updates
- ✅ **Sound alerts**: Custom notification sounds via VLC
- ✅ **Controller roster**: Real name lookup from ARTCC roster
- ✅ **Multi-controller support**: Handles multiple active controllers

## Quick Start

### Method 1: Direct Python Execution

1. **Install dependencies**:
   ```bash
   pip install -r desktop/requirements.txt
   ```

2. **Configure your settings** in `config.json` (copy from `config.sample.json`)

3. **Run the desktop application**:
   ```bash
   python -m desktop.main
   ```

### Method 2: Windows Executable (if available)

1. Download the latest release from GitHub
2. Extract and run `vatsim_monitor.exe`
3. Configure settings through the system tray menu

## Configuration

The desktop monitor uses the same configuration format as other implementations. Key settings:

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
  },
  "notifications": {
    "sound_enabled": true,
    "sound_file": "ding.mp3",
    "toast_duration": 3000
  }
}
```

## Dependencies

- **Python 3.8+**
- **PyQt6** - GUI framework for cross-platform desktop applications
- **python-vlc** - Audio playback for notification sounds
- **Pillow** - Image processing for custom icons
- **requests** - For VATSIM API calls
- **beautifulsoup4** - For parsing ARTCC roster

## System Tray Features

### Status Colors
- 🟢 **Green**: Main facility online
- 🟣 **Purple**: Main facility + supporting above online (full coverage)
- 🟡 **Yellow**: Only supporting above facility online
- 🔴 **Red**: All facilities offline
- ⚫ **Gray**: Monitor stopped or error

### Context Menu Options
- **Status**: View detailed controller information
- **Check Now**: Force immediate status check
- **Settings**: Configure monitoring interval and Pushover
- **Test Pushover**: Send test notification to your device
- **Start/Stop Monitoring**: Control monitoring state
- **Exit**: Quit the application

## Toast Notifications

The desktop version includes animated toast notifications that:
- Slide in from the right side of the screen
- Display controller names and status changes
- Play custom sound alerts
- Auto-hide after configured duration
- Use status-based background colors

## GUI Components

### Status Dialog
- Shows detailed controller information
- Displays frequency, rating, time online
- Lists supporting controllers
- Shows last check timestamp

### Settings Dialog
- Configure monitoring check interval (minimum 30 seconds)
- Enable/disable Pushover notifications
- Set Pushover API token and user key
- Test Pushover configuration

## Architecture

```
desktop/
├── __init__.py          # Package initialization
├── main.py              # Entry point and startup logic
├── vatsim_monitor.py    # Main application class with system tray
├── worker.py            # PyQt6 worker thread for API calls
├── requirements.txt     # GUI-specific dependencies
└── gui/
    ├── __init__.py      # GUI package initialization
    └── components.py    # Toast, status, and settings dialogs
```

## Shared Components

The desktop implementation uses shared components from the `shared/` directory:
- `shared/vatsim_core.py` - Core VATSIM API logic
- `shared/notification_manager.py` - Notification handling
- `shared/pushover_service.py` - Pushover integration
- `shared/utils.py` - Utility functions
- `shared/updater.py` - Auto-update functionality

## Auto-Update System

The desktop application includes automatic update functionality:
- Checks for updates on startup
- Downloads and applies updates automatically
- Prompts user to restart after update
- Preserves user configuration during updates

## Platform-Specific Features

### Windows
- Integrates with Windows system tray
- Supports Windows notification sounds
- Can be set to start with Windows

### macOS
- Integrates with macOS menu bar
- Respects macOS notification preferences
- Can be added to Login Items

### Linux
- Integrates with system tray (requires system tray support)
- Works with various desktop environments
- Can be set up as systemd user service

## Troubleshooting

### Common Issues

1. **System tray not available**: Some Linux desktop environments may not support system tray
2. **Audio issues**: Ensure VLC is installed and working on your system
3. **PyQt6 import errors**: Install PyQt6 using `pip install PyQt6`
4. **Toast notifications not showing**: Check if notifications are enabled in system settings

### Debug Mode

Enable debug logging by modifying `desktop/main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/vatsim_monitor.log"), logging.StreamHandler()],
)
```

## Performance

The desktop monitor is lightweight:
- **Memory**: ~100-150MB typical usage (includes PyQt6 overhead)
- **CPU**: Minimal, only during API checks and GUI updates
- **Network**: ~1KB per check interval
- **Disk**: Log files and cached icons only

## Comparison with Other Implementations

| Feature | Desktop GUI | Headless | Web App |
|---------|------------|----------|---------|
| **GUI** | ✅ Full GUI | ❌ None | 🌐 Web interface |
| **System Tray** | ✅ Native | ❌ None | ❌ None |
| **Toast Notifications** | ✅ Animated | ❌ None | ❌ None |
| **Sound Alerts** | ✅ VLC audio | ❌ None | ❌ None |
| **Pushover** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Auto-Update** | ✅ Built-in | ❌ Manual | ❌ Manual |
| **Dependencies** | 📦 Heavy | 📦 Minimal | 📦 Medium |
| **Platform** | 🖥️ Desktop required | 🌐 Any | 🌐 Any |
| **Resource Usage** | 💾 High | 💾 Low | 💾 Medium |

## Development

### Building from Source

1. Clone the repository
2. Install dependencies: `pip install -r desktop/requirements.txt`
3. Run: `python -m desktop.main`

### Creating Executables

Use PyInstaller to create standalone executables:

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --onefile --windowed --icon=assets/airport-tower.ico desktop/main.py
```

## Security

- Runs with user-level privileges
- Configuration files stored in user directory
- Network connections only to VATSIM API and Pushover
- No data collection or telemetry

This desktop implementation provides the most feature-rich experience with full GUI support, making it ideal for users who want visual feedback and interactive controls.