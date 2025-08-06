# Oak Tower Watcher - Architecture Diagram

## Current vs Proposed Structure

### Current Structure (Mixed Implementation)
```mermaid
graph TD
    A[oak_tower_watcher/] --> B[main.py - Desktop Entry]
    A --> C[vatsim_monitor.py - Desktop App]
    A --> D[headless_monitor.py - Headless Entry]
    A --> E[web_api.py - Legacy Web]
    A --> F[src/]
    F --> G[gui_components.py]
    F --> H[vatsim_worker.py]
    F --> I[headless_worker.py]
    F --> J[vatsim_core.py]
    F --> K[notification_manager.py]
    A --> L[web/]
    L --> M[backend/]
    L --> N[templates/]
    L --> O[*.html, *.css, *.js]
    A --> P[requirements.txt - Mixed]
    A --> Q[requirements_headless.txt]
    A --> R[requirements_web.txt]
    
    style A fill:#f9f,stroke:#333,stroke-width:4px
    style F fill:#faa,stroke:#333,stroke-width:2px
    style L fill:#aaf,stroke:#333,stroke-width:2px
```

### Proposed Structure (Clean Separation)
```mermaid
graph TD
    A[oak_tower_watcher/] --> B[desktop/]
    A --> C[headless/]
    A --> D[web/]
    A --> E[shared/]
    A --> F[config/]
    A --> G[assets/]
    A --> H[scripts/]
    A --> I[docs/]
    
    B --> B1[main.py]
    B --> B2[vatsim_monitor.py]
    B --> B3[gui/components.py]
    B --> B4[worker.py]
    B --> B5[requirements.txt]
    
    C --> C1[main.py]
    C --> C2[worker.py]
    C --> C3[requirements.txt]
    C --> C4[Dockerfile]
    
    D --> D1[backend/]
    D --> D2[templates/]
    D --> D3[static/]
    D --> D4[requirements.txt]
    D --> D5[Dockerfile]
    
    E --> E1[vatsim_core.py]
    E --> E2[notification_manager.py]
    E --> E3[pushover_service.py]
    E --> E4[utils.py]
    
    style A fill:#9f9,stroke:#333,stroke-width:4px
    style B fill:#faa,stroke:#333,stroke-width:2px
    style C fill:#aaf,stroke:#333,stroke-width:2px
    style D fill:#afa,stroke:#333,stroke-width:2px
    style E fill:#ffa,stroke:#333,stroke-width:2px
```

## Implementation Dependencies

```mermaid
graph LR
    subgraph Desktop Implementation
        D1[Desktop App] --> D2[PyQt6]
        D1 --> D3[python-vlc]
        D1 --> D4[System Tray]
    end
    
    subgraph Headless Implementation
        H1[Headless Service] --> H2[Threading]
        H1 --> H3[Minimal Deps]
    end
    
    subgraph Web Implementation
        W1[Web App] --> W2[Flask]
        W1 --> W3[SQLAlchemy]
        W1 --> W4[SendGrid]
    end
    
    subgraph Shared Components
        S1[vatsim_core] --> S2[requests]
        S1 --> S3[beautifulsoup4]
        S4[pushover_service] --> S2
        S5[notification_manager] --> S4
    end
    
    D1 --> S1
    D1 --> S5
    H1 --> S1
    H1 --> S5
    W1 --> S1
```

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant User
    participant Implementation
    participant SharedCore
    participant VATSIMAPI
    participant Pushover
    
    User->>Implementation: Start Monitoring
    Implementation->>SharedCore: Initialize Core
    loop Every Check Interval
        Implementation->>SharedCore: Check Status
        SharedCore->>VATSIMAPI: Query Controllers
        VATSIMAPI-->>SharedCore: Controller Data
        SharedCore-->>Implementation: Status Update
        alt Status Changed
            Implementation->>SharedCore: Send Notification
            SharedCore->>Pushover: Push Notification
            Pushover-->>User: Mobile Alert
        end
    end
```

## Deployment Architecture

```mermaid
graph TB
    subgraph Development
        DEV1[Desktop GUI] --> DEV2[Windows/Mac/Linux]
        DEV3[Local Testing] --> DEV4[All Implementations]
    end
    
    subgraph Production - Headless
        PROD1[Docker Container] --> PROD2[Linux Server]
        PROD1 --> PROD3[DigitalOcean Droplet]
        PROD1 --> PROD4[AWS/Azure]
    end
    
    subgraph Production - Web
        WEB1[Docker Container] --> WEB2[Nginx Reverse Proxy]
        WEB2 --> WEB3[SSL/TLS]
        WEB1 --> WEB4[Gunicorn]
        WEB4 --> WEB5[Flask App]
    end
    
    style Development fill:#ffa,stroke:#333,stroke-width:2px
    style Production - Headless fill:#aaf,stroke:#333,stroke-width:2px
    style Production - Web fill:#afa,stroke:#333,stroke-width:2px
```

## File Migration Map

```mermaid
graph LR
    subgraph Current Location
        A1[main.py]
        A2[vatsim_monitor.py]
        A3[headless_monitor.py]
        A4[src/gui_components.py]
        A5[src/vatsim_worker.py]
        A6[src/headless_worker.py]
        A7[src/vatsim_core.py]
        A8[web_api.py]
    end
    
    subgraph New Location
        B1[desktop/main.py]
        B2[desktop/vatsim_monitor.py]
        B3[headless/main.py]
        B4[desktop/gui/components.py]
        B5[desktop/worker.py]
        B6[headless/worker.py]
        B7[shared/vatsim_core.py]
        B8[REMOVED]
    end
    
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4
    A5 --> B5
    A6 --> B6
    A7 --> B7
    A8 --> B8
    
    style A8 fill:#faa,stroke:#333,stroke-width:2px
    style B8 fill:#faa,stroke:#333,stroke-width:2px
```

## Benefits Visualization

```mermaid
pie title Benefits of Reorganization
    "Easier Maintenance" : 25
    "Clear Separation" : 20
    "Better Documentation" : 15
    "Improved Deployment" : 15
    "Code Reusability" : 15
    "Cleaner Dependencies" : 10
```

## Implementation Timeline

```mermaid
gantt
    title Reorganization Timeline
    dateFormat  YYYY-MM-DD
    section Phase 1
    Create Directory Structure    :a1, 2025-01-06, 1d
    Create README Files          :a2, after a1, 1d
    
    section Phase 2
    Move Desktop Implementation  :b1, after a2, 1d
    Update Desktop Imports       :b2, after b1, 1d
    
    section Phase 3
    Move Headless Implementation :c1, after b2, 1d
    Update Headless Imports      :c2, after c1, 1d
    
    section Phase 4
    Reorganize Web Implementation :d1, after c2, 1d
    Update Web Imports           :d2, after d1, 1d
    
    section Phase 5
    Move Shared Components       :e1, after d2, 1d
    Update All Import Paths      :e2, after e1, 1d
    
    section Phase 6
    Update Docker Files          :f1, after e2, 1d
    Update Scripts              :f2, after f1, 1d
    
    section Phase 7
    Update Documentation         :g1, after f2, 1d
    Final Testing               :g2, after g1, 2d