# OAK Tower Watcher - Production Deployment Guide

This guide will help you deploy the OAK Tower Watcher web interface in a production environment with HTTPS, reverse proxy, and proper security configurations.

## Overview

The production setup includes:
- **Flask Web Application** running with Gunicorn WSGI server
- **Nginx Reverse Proxy** with SSL termination and security headers
- **Let's Encrypt SSL Certificates** with automatic renewal
- **Docker Containers** for easy deployment and management
- **Monitoring Service** for VATSIM data collection
- **Production Security** configurations and optimizations

## Prerequisites

1. **Server Requirements**:
   - Linux server (Ubuntu 20.04+ recommended)
   - Docker and Docker Compose installed
   - Domain name pointing to your server (e.g., leftos.dev)
   - Ports 80 and 443 open in firewall

2. **Accounts Needed**:
   - [Pushover](https://pushover.net/) account for notifications (optional)
   - Domain registrar access for DNS configuration

3. **System Dependencies**:
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker compose
   sudo chmod +x /usr/local/bin/docker compose
   ```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/oak_tower_watcher.git
cd oak_tower_watcher
```

### 2. Configure Environment

```bash
# Copy the production environment template
cp .env.prod .env

# Edit the configuration
nano .env
```

**Required Configuration**:
```env
# Domain Configuration
DOMAIN_NAME=your-domain.com
SSL_EMAIL=your-email@domain.com

# Pushover Configuration (optional but recommended)
PUSHOVER_API_TOKEN=your_pushover_api_token
PUSHOVER_USER_KEY=your_pushover_user_key

# Application Configuration
CHECK_INTERVAL=30
AIRPORT_CODE=KOAK
TZ=UTC

# Web Server Configuration
GUNICORN_WORKERS=4
FLASK_ENV=production
```

### 3. Deploy to Production

```bash
# Run the automated deployment script
./scripts/deploy_production.sh
```

The script will:
- Validate your configuration
- Build Docker images
- Generate SSL certificates
- Start all services
- Configure automatic SSL renewal
- Perform health checks

### 4. Verify Deployment

After deployment, your services will be available at:
- **HTTPS Website**: `https://your-domain.com`
- **API Endpoint**: `https://your-domain.com/api/status`
- **Health Check**: `https://your-domain.com/api/health`

## Architecture

### Service Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Internet      │    │   Nginx Proxy    │    │  Web API        │
│   (Port 443)    │───▶│   (SSL Term.)    │───▶│  (Gunicorn)     │
│                 │    │   Security       │    │  Flask App      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  VATSIM Monitor  │
                       │  (Background)    │
                       │  Notifications   │
                       └──────────────────┘
```

### Docker Services

1. **nginx**: Reverse proxy with SSL termination
2. **web-api**: Flask application with Gunicorn
3. **vatsim-monitor**: Background monitoring service
4. **certbot**: SSL certificate management

## Configuration Details

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DOMAIN_NAME` | Your domain name | - | Yes |
| `SSL_EMAIL` | Email for Let's Encrypt | - | Yes |
| `PUSHOVER_API_TOKEN` | Pushover API token | - | No |
| `PUSHOVER_USER_KEY` | Pushover user key | - | No |
| `CHECK_INTERVAL` | Monitoring interval (seconds) | 30 | No |
| `AIRPORT_CODE` | Airport to monitor | KOAK | No |
| `GUNICORN_WORKERS` | Number of web workers | 4 | No |
| `FLASK_ENV` | Flask environment | production | No |

### Security Features

- **SSL/TLS Encryption**: Let's Encrypt certificates with automatic renewal
- **Security Headers**: HSTS, CSP, X-Frame-Options, etc.
- **Rate Limiting**: API and static content rate limits
- **Non-root Containers**: All services run as non-root users
- **Resource Limits**: Memory and CPU limits for containers
- **Firewall Ready**: Only exposes ports 80 and 443

### Performance Optimizations

- **Gzip Compression**: Automatic compression for text content
- **Static File Caching**: Long-term caching for assets
- **Connection Pooling**: Efficient HTTP connection handling
- **Worker Processes**: Multiple Gunicorn workers for concurrency
- **Health Checks**: Automatic service health monitoring

## Management Commands

### Daily Operations

```bash
# View service status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Start services
docker compose -f docker-compose.prod.yml up -d
```

### Updates and Maintenance

```bash
# Update to latest version
./scripts/update_production.sh

# Manual SSL certificate renewal
docker compose -f docker-compose.prod.yml run --rm certbot renew
docker compose -f docker-compose.prod.yml restart nginx

# View SSL certificate status
openssl x509 -enddate -noout -in certbot/conf/live/your-domain.com/fullchain.pem
```

### Monitoring and Debugging

```bash
# Check service health
curl -f https://your-domain.com/api/health
curl -f https://your-domain.com/nginx-health

# View container resource usage
docker stats

# Access container shell for debugging
docker compose -f docker-compose.prod.yml exec web-api bash
docker compose -f docker-compose.prod.yml exec nginx sh
```

## Troubleshooting

### Common Issues

#### SSL Certificate Generation Fails
```bash
# Check DNS configuration
nslookup your-domain.com

# Verify port 80 is accessible
curl -I http://your-domain.com/.well-known/acme-challenge/test

# Check certbot logs
docker compose -f docker-compose.prod.yml logs certbot
```

#### Web Service Not Responding
```bash
# Check web-api logs
docker compose -f docker-compose.prod.yml logs web-api

# Test internal connectivity
docker compose -f docker-compose.prod.yml exec nginx curl http://web-api:8080/api/health

# Restart web service
docker compose -f docker-compose.prod.yml restart web-api
```

#### High Resource Usage
```bash
# Monitor resource usage
docker stats

# Adjust worker count in .env
GUNICORN_WORKERS=2

# Restart with new configuration
docker compose -f docker-compose.prod.yml restart web-api
```

### Log Locations

- **Application Logs**: `./logs/`
- **Nginx Logs**: `docker compose logs nginx`
- **SSL Logs**: `docker compose logs certbot`
- **System Logs**: `journalctl -u docker`

## Security Considerations

### Firewall Configuration

```bash
# UFW example
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### Regular Maintenance

1. **System Updates**: Keep the host system updated
2. **Docker Updates**: Regularly update Docker images
3. **SSL Monitoring**: Monitor certificate expiry (automated)
4. **Log Rotation**: Ensure logs don't fill disk space
5. **Backup**: Regular backups of configuration and data

### Monitoring Recommendations

- Set up external monitoring (e.g., UptimeRobot)
- Configure log aggregation (e.g., ELK stack)
- Monitor resource usage and set alerts
- Regular security scans and updates

## Scaling and Performance

### Horizontal Scaling

To handle more traffic, you can:
1. Increase `GUNICORN_WORKERS` in `.env`
2. Add more web-api containers with load balancing
3. Use external database for session storage
4. Implement Redis for caching

### Vertical Scaling

Adjust resource limits in `docker compose.prod.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '2.0'
```

## Backup and Recovery

### Configuration Backup
```bash
# Backup configuration
tar -czf backup-$(date +%Y%m%d).tar.gz .env nginx/ certbot/conf/

# Restore configuration
tar -xzf backup-20231201.tar.gz
```

### Database Backup (if applicable)
```bash
# If using external database
pg_dump your_database > backup.sql
```

## Support and Maintenance

### Health Monitoring

The deployment includes built-in health checks:
- Web API: `https://your-domain.com/api/health`
- Nginx: `https://your-domain.com/nginx-health`
- Container health: `docker compose ps`

### Automated Maintenance

- SSL certificates renew automatically
- Log rotation is configured
- Container restart policies handle failures
- Cron job for certificate renewal is set up

### Getting Help

1. Check the logs first: `docker compose logs`
2. Verify configuration: Review `.env` file
3. Test connectivity: Use curl commands
4. Check system resources: `docker stats`
5. Review documentation: This guide and Docker docs

## Cost Estimation

**Monthly Costs** (approximate):
- **VPS/Cloud Server**: $5-20/month (depending on provider and specs)
- **Domain Name**: $10-15/year
- **SSL Certificate**: Free (Let's Encrypt)
- **Total**: ~$5-25/month for 24/7 operation

**Recommended Specs**:
- **CPU**: 1-2 cores
- **RAM**: 1-2 GB
- **Storage**: 20-40 GB SSD
- **Bandwidth**: 1-5 TB/month

This production setup provides a robust, secure, and scalable deployment for the OAK Tower Watcher web interface with minimal ongoing maintenance requirements.