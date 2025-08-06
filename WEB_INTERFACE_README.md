# OAK Tower Watcher Web Interface

A simple web dashboard for monitoring the OAK Tower Watcher VATSIM monitoring service.

## Features

### Homepage (`/`)
- **Server Services Dashboard**: Overview of all available services
- **Service Cards**: Visual cards showing different monitoring services
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### OAK Tower Watcher Status Page (`/oak-tower-status.html`)
- **Real-time Status**: Live monitoring of VATSIM controllers at Oakland International Airport (KOAK)
- **Controller Information**: Detailed info including callsign, name, frequency, and online duration
- **Multiple Controller Types**:
  - 🏗️ **Tower Controllers**: Main facility controllers (OAK_TWR, etc.)
  - 📡 **Supporting Above**: Approach/Center controllers (NCT_APP, OAK_CTR, etc.)
  - 🛬 **Ground/Delivery**: Ground and delivery controllers (OAK_GND, OAK_DEL, etc.)
- **Status Indicators**: Color-coded status with animated indicators
- **Auto-refresh**: Automatic updates every 30 seconds
- **Manual Controls**: Force refresh and pause/resume auto-refresh

## API Endpoints

### Health Check
```
GET /api/health
```
Returns service health status.

### Current Status
```
GET /api/status
```
Returns current VATSIM monitoring status with controller information.

### Configuration
```
GET /api/config
```
Returns basic configuration information.

## Installation & Setup

### Prerequisites
- Python 3.7+
- Virtual environment (recommended)

### Installation
1. Create and activate virtual environment:
```bash
python3 -m venv web_env
source web_env/bin/activate  # On Windows: web_env\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements_web.txt
```

3. Ensure you have a valid configuration file:
```bash
cp config.sample.json config.json
# Edit config.json as needed
```

### Running the Web Interface
```bash
# Using the virtual environment
web_env/bin/python web_api.py

# Or if virtual environment is activated
python web_api.py
```

The web interface will be available at:
- Local: http://127.0.0.1:8080
- Network: http://[your-ip]:8080

### Environment Variables
- `PORT`: Server port (default: 8080)
- `HOST`: Server host (default: 0.0.0.0)
- `DEBUG`: Enable debug mode (default: False)

## Architecture

### Core Components
- **`src/vatsim_core.py`**: Core VATSIM API functionality (no GUI dependencies)
- **`web_api.py`**: Flask web server and API endpoints
- **`web/`**: Static web files (HTML, CSS, JavaScript)

### Refactored Design
The codebase has been refactored to separate GUI dependencies from core logic:
- **Core Logic**: `src/vatsim_core.py` - Pure Python, no PyQt6 dependencies
- **GUI Worker**: `src/vatsim_worker.py` - PyQt6-based threaded worker using core logic
- **Web API**: `web_api.py` - Flask-based web interface using core logic

This allows the same VATSIM monitoring logic to be used by both the desktop GUI application and the web interface.

## Status Indicators

### Main Status Colors
- 🟣 **Purple**: Full coverage (Tower + Supporting facilities online)
- 🟢 **Green**: Tower online only
- 🟡 **Yellow**: Supporting facilities online (Tower offline)
- 🔴 **Red**: All facilities offline
- ⚫ **Gray**: Error or monitoring stopped

### Controller Information
Each controller card shows:
- **Callsign**: Controller's callsign (e.g., OAK_TWR, NCT_APP)
- **Name**: Real name from ARTCC roster
- **Frequency**: Radio frequency
- **CID**: VATSIM Controller ID
- **Online Duration**: How long the controller has been online

## Development

### File Structure
```
web/
├── index.html              # Homepage
├── oak-tower-status.html   # Status page
├── styles.css              # Main stylesheet
├── status-page.css         # Status page specific styles
└── status-page.js          # Status page JavaScript

src/
├── vatsim_core.py          # Core VATSIM functionality
└── vatsim_worker.py        # PyQt6 worker (refactored)

web_api.py                  # Flask web server
requirements_web.txt        # Web dependencies
```

### Adding New Services
To add new services to the dashboard:
1. Add a new service card to `web/index.html`
2. Create the corresponding page and functionality
3. Update the API endpoints in `web_api.py` if needed

## Troubleshooting

### Common Issues
1. **Config file not found**: Ensure `config.json` exists (copy from `config.sample.json`)
2. **Port already in use**: Change the port using `PORT=8081 python web_api.py`
3. **API errors**: Check that the VATSIM API is accessible and configuration is correct

### Logs
The web API logs to both console and file. Check the console output for real-time information.

## Production Deployment

For production deployment, consider:
1. Using a production WSGI server (e.g., Gunicorn, uWSGI)
2. Setting up a reverse proxy (e.g., Nginx)
3. Enabling HTTPS
4. Setting appropriate environment variables
5. Using a process manager (e.g., systemd, supervisor)

Example with Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 web_api:app