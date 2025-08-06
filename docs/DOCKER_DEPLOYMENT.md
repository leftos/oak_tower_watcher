# Deployment Configuration

This directory contains Docker Compose files and deployment configurations for the OAK Tower Watcher project.

## Files

### Docker Compose Files
- **`docker-compose.yml`**: Main Docker Compose configuration for headless implementation
- **`docker-compose.prod.yml`**: Production Docker Compose configuration
- **`docker-compose.monitoring.yml`**: Monitoring stack with Prometheus
- **`.dockerignore`**: Docker ignore file

## Implementation-Specific Docker Files

Docker files are now organized within their respective implementation directories:

### Headless Implementation
- **`../headless/Dockerfile`**: Headless Docker image
- **`../headless/docker-entrypoint.sh`**: Headless container entry script

### Web Implementation
- **`../web/Dockerfile.web`**: Web application Docker image
- **`../web/docker-entrypoint-web.sh`**: Web container entry script

## Usage

### From Deployment Directory

**Build and run headless implementation:**
```bash
cd deployment/
docker-compose up --build
```

**Production deployment:**
```bash
cd deployment/
docker-compose -f docker-compose.prod.yml up -d
```

**With monitoring stack:**
```bash
cd deployment/
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Build Context

Docker Compose files reference implementation-specific Dockerfiles:

```
oak_tower_watcher/
├── headless/
│   ├── Dockerfile          # Headless implementation
│   └── docker-entrypoint.sh
├── web/
│   ├── Dockerfile.web      # Web implementation
│   └── docker-entrypoint-web.sh
├── shared/                 # Shared components
├── config/                 # Configuration files
└── deployment/             # This directory
    ├── docker-compose.yml  # References ../headless/Dockerfile
    └── docker-compose.prod.yml
```

### Environment Variables

The containers support configuration via environment variables:

```bash
# Pushover notifications
PUSHOVER_API_TOKEN=your-token
PUSHOVER_USER_KEY=your-user-key

# Monitoring settings  
CHECK_INTERVAL=30
AIRPORT_CODE=KOAK

# Web application (for web containers)
SECRET_KEY=your-secret-key
SENDGRID_API_KEY=your-sendgrid-key
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

### Volume Mounts

- **Logs**: `../logs:/app/logs`
- **Config**: `../config/config.json:/app/config.json` (optional)

## Health Checks

All containers include health checks to monitor application status:

```bash
# Check container health
docker-compose ps

# View container logs
docker-compose logs -f vatsim-monitor
```

## Implementation-Specific Deployment

For implementation-specific Docker configurations, see:
- [`../headless/README.md`](../headless/README.md) - Headless Docker deployment
- [`../web/README.md`](../web/README.md) - Web application deployment

## Troubleshooting

**Build Context Issues:**
- Ensure you're running commands from the `docker/` directory
- Build context is set to `..` (project root) in compose files

**Path Issues:**
- All paths in Docker files are relative to project root
- Volume mounts use `../` to reference parent directories

**Permission Issues:**
- Containers run as non-root `vatsim` user
- Ensure log directories have proper permissions