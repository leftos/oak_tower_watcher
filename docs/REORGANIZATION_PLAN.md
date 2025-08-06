# Oak Tower Watcher - Codebase Reorganization Plan

## Current Structure Analysis

The project currently has three distinct implementations mixed together in the root directory:

### 1. Windows Desktop Implementation (PyQt6 GUI)
**Main Entry Points:**
- `main.py` - Main entry point for Windows desktop app
- `vatsim_monitor.py` - Main application class with system tray

**Dependencies:**
- PyQt6 for GUI
- python-vlc for audio
- System tray integration

**Associated Files:**
- `src/gui_components.py` - GUI dialogs and toast notifications
- `src/vatsim_worker.py` - PyQt6 worker thread
- `requirements.txt` - Mixed dependencies (needs cleanup)

### 2. Cross-Platform Headless Implementation
**Main Entry Point:**
- `headless_monitor.py` - Headless monitoring service

**Dependencies:**
- Minimal (requests, beautifulsoup4)
- No GUI dependencies

**Associated Files:**
- `src/headless_worker.py` - Threading-based worker
- `requirements_headless.txt` - Minimal dependencies
- Docker deployment files

### 3. Web Application Implementation
**Main Entry Points:**
- `web_api.py` - Legacy Flask API (deprecated)
- `web/backend/app.py` - New Flask application with auth
- `web/run_app.py` - Web app launcher

**Dependencies:**
- Flask and related packages
- SQLAlchemy for user database
- SendGrid for email

**Associated Files:**
- `web/` directory - All web-related files
- `requirements_web.txt` - Web dependencies
- Web-specific Docker files

### Shared/Common Files
- `src/vatsim_core.py` - Core VATSIM API logic (no GUI dependencies)
- `src/notification_manager.py` - Notification management
- `src/pushover_service.py` - Pushover integration
- `src/utils.py` - Utility functions
- `config/config.py` - Configuration loader
- `config.sample.json` - Sample configuration

## Proposed New Structure

```
oak_tower_watcher/
├── desktop/                    # Windows Desktop Implementation
│   ├── main.py                # Entry point
│   ├── vatsim_monitor.py      # Main application class
│   ├── gui/
│   │   └── components.py      # GUI components (from src/gui_components.py)
│   ├── worker.py              # PyQt6 worker (from src/vatsim_worker.py)
│   ├── requirements.txt       # Desktop-specific dependencies
│   └── README.md              # Desktop app documentation
│
├── headless/                  # Cross-Platform Headless Implementation
│   ├── main.py               # Entry point (from headless_monitor.py)
│   ├── worker.py             # Threading worker (from src/headless_worker.py)
│   ├── requirements.txt      # Minimal dependencies
│   ├── Dockerfile            # Headless-specific Dockerfile
│   ├── docker-compose.yml    # Headless Docker compose
│   └── README.md             # Headless documentation
│
├── web/                      # Web Application (existing structure, enhanced)
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── app.py           # Main Flask app
│   │   ├── api.py           # API routes
│   │   ├── auth.py          # Authentication
│   │   ├── models.py        # Database models
│   │   ├── forms.py         # Web forms
│   │   ├── email_service.py # Email handling
│   │   ├── sendgrid_service.py
│   │   ├── security.py      # Security utilities
│   │   └── status_service.py # Status checking service
│   ├── templates/           # HTML templates
│   ├── static/              # CSS, JS, images
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   ├── run_app.py          # Web app launcher
│   ├── requirements.txt     # Web dependencies
│   ├── Dockerfile          # Web-specific Dockerfile
│   ├── docker-compose.yml  # Web Docker compose
│   └── README.md           # Web app documentation
│
├── shared/                  # Shared components across all implementations
│   ├── __init__.py
│   ├── vatsim_core.py      # Core VATSIM API logic
│   ├── notification_manager.py
│   ├── pushover_service.py
│   ├── utils.py
│   ├── updater.py          # Auto-update functionality
│   └── bulk_notification_service.py
│
├── config/                  # Configuration files
│   ├── __init__.py
│   ├── config.py           # Configuration loader
│   ├── env_config.py       # Environment configuration
│   ├── config.sample.json  # Sample configuration
│   └── systemd/            # Linux service files
│       ├── vatsim-monitor.service
│       └── vatsim-monitor-docker.service
│
├── assets/                  # Shared assets
│   ├── airport-tower.png
│   └── ding.mp3
│
├── scripts/                 # Deployment and utility scripts
│   ├── deploy/
│   │   ├── deploy_docker.sh
│   │   ├── deploy_docker.bat
│   │   ├── deploy_production.sh
│   │   └── deploy_to_droplet.sh
│   ├── setup/
│   │   ├── setup_dev_env.sh
│   │   ├── setup_autostart.sh
│   │   └── setup_nginx_config.sh
│   └── utils/
│       ├── create_deployment_package.py
│       ├── package.py
│       └── test_email.sh
│
├── docs/                    # Documentation
│   ├── README.md           # Main documentation
│   ├── DESKTOP.md          # Desktop app guide
│   ├── HEADLESS.md         # Headless deployment guide
│   ├── WEB.md              # Web app guide
│   ├── DOCKER.md           # Docker deployment guide
│   ├── PRODUCTION.md       # Production deployment guide
│   └── API.md              # API documentation
│
├── tests/                   # Test files
│   ├── test_bulk_notifications.py
│   └── test_production.sh
│
├── nginx/                   # Nginx configuration
│   └── conf.d/
│       └── default.conf.template
│
├── monitoring/              # Monitoring setup
│   ├── docker-compose.monitoring.yml
│   └── prometheus.yml
│
├── .gitignore
├── .env.sample             # Sample environment file
├── .env.prod.template      # Production environment template
├── README.md               # Main README
└── LICENSE

```

## Benefits of New Structure

1. **Clear Separation**: Each implementation has its own directory with all related files
2. **Shared Code Reuse**: Common functionality in `shared/` directory
3. **Easier Maintenance**: Changes to one implementation won't affect others
4. **Better Documentation**: Each implementation has its own README
5. **Cleaner Dependencies**: Separate requirements.txt for each implementation
6. **Improved Deployment**: Implementation-specific Docker files
7. **Organized Scripts**: Scripts categorized by purpose
8. **Centralized Configuration**: All config in one place

## Migration Steps

### Phase 1: Create New Directory Structure
1. Create all new directories
2. Create placeholder README files

### Phase 2: Move Desktop Implementation
1. Move `main.py` → `desktop/main.py`
2. Move `vatsim_monitor.py` → `desktop/vatsim_monitor.py`
3. Move `src/gui_components.py` → `desktop/gui/components.py`
4. Move `src/vatsim_worker.py` → `desktop/worker.py`
5. Create desktop-specific `requirements.txt`

### Phase 3: Move Headless Implementation
1. Move `headless_monitor.py` → `headless/main.py`
2. Move `src/headless_worker.py` → `headless/worker.py`
3. Move `requirements_headless.txt` → `headless/requirements.txt`
4. Create headless-specific Dockerfile

### Phase 4: Reorganize Web Implementation
1. Move static files to `web/static/`
2. Consolidate web-specific files
3. Remove legacy `web_api.py`

### Phase 5: Move Shared Components
1. Move core files to `shared/`
2. Update all import statements

### Phase 6: Update Import Statements
1. Update imports in all Python files
2. Update Docker file paths
3. Update script references

### Phase 7: Update Documentation
1. Update main README
2. Create implementation-specific docs
3. Update deployment guides

### Phase 8: Testing
1. Test each implementation independently
2. Verify Docker builds
3. Test deployment scripts

## Import Statement Updates

### Desktop Implementation
```python
# Old
from src.vatsim_worker import VATSIMWorker
from src.gui_components import CustomToast

# New
from desktop.worker import VATSIMWorker
from desktop.gui.components import CustomToast
from shared.vatsim_core import VATSIMCore
```

### Headless Implementation
```python
# Old
from src.headless_worker import HeadlessVATSIMWorker
from src.notification_manager import NotificationManager

# New
from headless.worker import HeadlessVATSIMWorker
from shared.notification_manager import NotificationManager
from shared.vatsim_core import VATSIMCore
```

### Web Implementation
```python
# Old
from src.vatsim_core import VATSIMCore
from config.config import load_config

# New
from shared.vatsim_core import VATSIMCore
from config.config import load_config
```

## Docker Updates

### Desktop Dockerfile
```dockerfile
# Not needed - Desktop is GUI-based
```

### Headless Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY headless/ ./headless/
COPY shared/ ./shared/
COPY config/ ./config/
COPY assets/ ./assets/
COPY headless/requirements.txt .
RUN pip install -r requirements.txt
CMD ["python", "-m", "headless.main"]
```

### Web Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY web/ ./web/
COPY shared/ ./shared/
COPY config/ ./config/
COPY web/requirements.txt .
RUN pip install -r requirements.txt
CMD ["python", "-m", "web.run_app"]
```

## Risks and Mitigation

1. **Import Path Issues**
   - Risk: Broken imports after reorganization
   - Mitigation: Systematic update of all imports, thorough testing

2. **Docker Build Failures**
   - Risk: Docker contexts need updating
   - Mitigation: Update all Dockerfiles and test builds

3. **Script Breakage**
   - Risk: Deployment scripts reference old paths
   - Mitigation: Update all scripts and test thoroughly

4. **Documentation Outdated**
   - Risk: Docs reference old structure
   - Mitigation: Update all documentation systematically

## Timeline

- **Day 1**: Create new directory structure, move desktop implementation
- **Day 2**: Move headless and web implementations
- **Day 3**: Move shared components, update imports
- **Day 4**: Update Docker files and scripts
- **Day 5**: Update documentation and testing
- **Day 6**: Final testing and validation

## Success Criteria

1. All three implementations work independently
2. No broken imports or missing files
3. Docker builds succeed for headless and web
4. All scripts function correctly
5. Documentation is accurate and complete
6. Tests pass for all implementations