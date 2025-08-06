# Oak Tower Watcher - Reorganization Summary

## Overview

Your Oak Tower Watcher project currently has three different implementations (Windows Desktop, Headless, and Web) with their files mixed together in the root directory. This reorganization plan separates them into distinct folders while maintaining shared code in a common location.

## Key Benefits

1. **Cleaner Structure**: Each implementation gets its own folder
2. **Easier Maintenance**: Changes to one implementation won't affect others
3. **Better Dependencies**: Each implementation has its own requirements.txt
4. **Shared Code Reuse**: Common functionality stays in one place
5. **Improved Documentation**: Each implementation gets its own README

## The Three Implementations

### 1. Desktop (Windows GUI Application)
- **Purpose**: System tray application with GUI for Windows users
- **Main Files**: `main.py`, `vatsim_monitor.py`
- **Dependencies**: PyQt6, python-vlc
- **Features**: System tray icon, toast notifications, settings dialog

### 2. Headless (Cross-Platform Service)
- **Purpose**: Background service for servers/Docker
- **Main File**: `headless_monitor.py`
- **Dependencies**: Minimal (requests, beautifulsoup4)
- **Features**: Pushover notifications, Docker deployment

### 3. Web (Flask Web Application)
- **Purpose**: Web interface with user authentication
- **Main Files**: `web/backend/app.py`, web interface files
- **Dependencies**: Flask, SQLAlchemy, SendGrid
- **Features**: User portal, email notifications, status page

## Proposed Folder Structure

```
oak_tower_watcher/
├── desktop/          # Windows Desktop App
├── headless/         # Headless Service
├── web/              # Web Application
├── shared/           # Shared Components
├── config/           # Configuration Files
├── assets/           # Images and Sounds
├── scripts/          # Deployment Scripts
├── docs/             # Documentation
└── tests/            # Test Files
```

## What Goes Where

### Desktop Folder (`desktop/`)
- `main.py` (entry point)
- `vatsim_monitor.py` (main app class)
- `gui/components.py` (GUI dialogs)
- `worker.py` (PyQt6 worker thread)
- `requirements.txt` (PyQt6, python-vlc)

### Headless Folder (`headless/`)
- `main.py` (from `headless_monitor.py`)
- `worker.py` (threading-based worker)
- `requirements.txt` (minimal deps)
- `Dockerfile` (for Docker deployment)

### Web Folder (`web/`)
- Already well-organized
- Move static files to `web/static/`
- Remove legacy `web_api.py`

### Shared Folder (`shared/`)
- `vatsim_core.py` (VATSIM API logic)
- `notification_manager.py`
- `pushover_service.py`
- `utils.py`
- `bulk_notification_service.py`

## Migration Steps

### Step 1: Create New Structure
```bash
mkdir -p desktop/gui headless web/static shared
mkdir -p scripts/{deploy,setup,utils}
```

### Step 2: Move Files
```bash
# Desktop files
mv main.py desktop/
mv vatsim_monitor.py desktop/
mv src/gui_components.py desktop/gui/components.py
mv src/vatsim_worker.py desktop/worker.py

# Headless files
mv headless_monitor.py headless/main.py
mv src/headless_worker.py headless/worker.py

# Shared files
mv src/vatsim_core.py shared/
mv src/notification_manager.py shared/
mv src/pushover_service.py shared/
mv src/utils.py shared/
```

### Step 3: Update Imports

Example import changes:
```python
# Old
from src.vatsim_core import VATSIMCore

# New
from shared.vatsim_core import VATSIMCore
```

### Step 4: Create Separate Requirements Files

**desktop/requirements.txt**:
```
PyQt6==6.5.0
python-vlc==3.0.18122
Pillow==10.0.0
# Plus shared dependencies
```

**headless/requirements.txt**:
```
requests>=2.31.0
beautifulsoup4>=4.12.2
```

**web/requirements.txt**:
```
Flask==3.1.1
Flask-Login==0.6.3
Flask-SQLAlchemy==3.1.1
# ... other web dependencies
```

## Docker Updates

Each implementation gets its own Dockerfile:

**headless/Dockerfile**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY headless/ ./headless/
COPY shared/ ./shared/
COPY config/ ./config/
RUN pip install -r headless/requirements.txt
CMD ["python", "-m", "headless.main"]
```

## Next Steps

1. **Review the Plan**: Check `docs/REORGANIZATION_PLAN.md` for full details
2. **Backup First**: Make a backup of your current code
3. **Test Incrementally**: Move and test one implementation at a time
4. **Update Documentation**: Update READMEs and guides after migration

## Questions to Consider

1. Do you want to proceed with this reorganization?
2. Should we start with one implementation first (recommend starting with headless)?
3. Do you want to keep the old structure as a backup branch?
4. Any specific concerns about the proposed structure?

## Implementation Priority

I recommend implementing in this order:
1. **Headless** (simplest, fewest dependencies)
2. **Desktop** (moderate complexity)
3. **Web** (already partially organized)
4. **Shared components** (move after testing individual implementations)

This reorganization will make your project much more maintainable and easier to deploy. Each implementation can evolve independently while sharing common functionality.