# Production Deployment Guide for OAK Tower Watcher User Portal

## Overview

This guide explains how to deploy the OAK Tower Watcher with the new user portal in a production environment using Docker and proper security configurations.

## Production Setup Options

### Option 1: Docker Deployment (Recommended)

#### 1. Update Docker Configuration

The existing Docker setup needs to be modified to use the new Flask application with user authentication.

**Update `Dockerfile.web`:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copy application code
COPY . .

# Create directory for SQLite database
RUN mkdir -p /app/web/instance

# Set environment variables
ENV FLASK_APP=web.backend.app:app
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "web/run_app.py"]
```

#### 2. Environment Variables

Create a `.env.prod` file with production settings:
```bash
# Flask Configuration
SECRET_KEY=your-super-secret-production-key-here-change-this
FLASK_ENV=production
DEBUG=False

# Database Configuration
DATABASE_URL=sqlite:///instance/users.db

# Server Configuration
HOST=0.0.0.0
PORT=8080

# Security
WTF_CSRF_ENABLED=True
```

#### 3. Docker Compose for Production

Update `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    ports:
      - "8080:8080"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:///instance/users.db
      - FLASK_ENV=production
      - DEBUG=False
    volumes:
      - ./data:/app/web/instance  # Persist database
      - ./config.json:/app/config.json:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - web
    restart: unless-stopped
```

#### 4. Nginx Configuration

Update `nginx/nginx.conf` for the new application:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream flask_app {
        server web:8080;
    }

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL Configuration
        ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Static files
        location /static/ {
            alias /app/web/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Main application
        location / {
            proxy_pass http://flask_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Security
            proxy_hide_header X-Powered-By;
        }
    }
}
```

### Option 2: Direct Server Deployment

#### 1. Server Setup

```bash
# Install Python and dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx

# Create application user
sudo useradd -m -s /bin/bash oakwatcher
sudo su - oakwatcher

# Clone and setup application
git clone <your-repo> oak_tower_watcher
cd oak_tower_watcher
python3 -m venv web_env
source web_env/bin/activate
pip install -r requirements_web.txt
```

#### 2. Production WSGI Server

Install and configure Gunicorn:
```bash
pip install gunicorn

# Create Gunicorn configuration
cat > gunicorn.conf.py << EOF
bind = "127.0.0.1:8080"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
EOF
```

#### 3. Systemd Service

Create `/etc/systemd/system/oakwatcher.service`:
```ini
[Unit]
Description=OAK Tower Watcher Web Application
After=network.target

[Service]
Type=exec
User=oakwatcher
Group=oakwatcher
WorkingDirectory=/home/oakwatcher/oak_tower_watcher
Environment=PATH=/home/oakwatcher/oak_tower_watcher/web_env/bin
Environment=SECRET_KEY=your-production-secret-key
Environment=DATABASE_URL=sqlite:///instance/users.db
Environment=FLASK_ENV=production
ExecStart=/home/oakwatcher/oak_tower_watcher/web_env/bin/gunicorn -c gunicorn.conf.py web.backend.app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable oakwatcher
sudo systemctl start oakwatcher
```

## Database Considerations

### SQLite (Default - Good for Small Scale)
- Suitable for single-server deployments
- Automatic backups recommended
- File-based, easy to backup

### PostgreSQL (Recommended for Production)

Update your environment variables:
```bash
DATABASE_URL=postgresql://username:password@localhost/oakwatcher
```

Install PostgreSQL adapter:
```bash
pip install psycopg2-binary
```

## Security Checklist

### Essential Security Measures

1. **Change Default Secret Key**
   ```bash
   # Generate a secure secret key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use HTTPS Only**
   - Configure SSL certificates (Let's Encrypt recommended)
   - Redirect all HTTP traffic to HTTPS
   - Set secure cookie flags

3. **Database Security**
   - Regular backups
   - Restrict file permissions (SQLite)
   - Use connection pooling (PostgreSQL)

4. **Environment Variables**
   - Never commit secrets to version control
   - Use environment-specific configuration files
   - Restrict file permissions on config files

5. **Firewall Configuration**
   ```bash
   # Allow only necessary ports
   sudo ufw allow 22    # SSH
   sudo ufw allow 80    # HTTP
   sudo ufw allow 443   # HTTPS
   sudo ufw enable
   ```

## Monitoring and Maintenance

### Health Checks
The application includes a health check endpoint at `/api/health`

### Logging
Configure proper logging in production:
```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/oakwatcher.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
```

### Backup Strategy
```bash
#!/bin/bash
# backup-script.sh
DATE=$(date +%Y%m%d_%H%M%S)
cp /path/to/web/instance/users.db /backups/users_db_$DATE.db
find /backups -name "users_db_*.db" -mtime +7 -delete
```

## Deployment Commands

### Docker Deployment
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Update application
git pull
docker-compose -f docker-compose.prod.yml up -d --build
```

### Direct Deployment
```bash
# Update application
git pull
source web_env/bin/activate
pip install -r requirements_web.txt
sudo systemctl restart oakwatcher
```

## Troubleshooting

### Common Issues

1. **Database Permission Errors**
   ```bash
   sudo chown -R oakwatcher:oakwatcher /path/to/web/instance/
   chmod 644 /path/to/web/instance/users.db
   ```

2. **Static Files Not Loading**
   - Check Nginx configuration
   - Verify file permissions
   - Clear browser cache

3. **Session Issues**
   - Verify SECRET_KEY is set and consistent
   - Check cookie settings
   - Ensure HTTPS is properly configured

### Log Locations
- Application logs: `/var/log/oakwatcher/`
- Nginx logs: `/var/log/nginx/`
- System logs: `journalctl -u oakwatcher`

## Performance Optimization

1. **Use a proper WSGI server** (Gunicorn, uWSGI)
2. **Enable Nginx caching** for static files
3. **Database optimization** (indexes, connection pooling)
4. **Monitor resource usage** (CPU, memory, disk)
5. **Implement rate limiting** for authentication endpoints

This production setup provides a secure, scalable foundation for the OAK Tower Watcher user portal.