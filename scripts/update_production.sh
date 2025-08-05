#!/bin/bash
set -e

# Production Update Script for OAK Tower Watcher
# This script updates the production deployment with minimal downtime

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    log_error ".env file not found. Please run deploy_production.sh first."
    exit 1
fi

log "Starting OAK Tower Watcher Production Update..."

# Pull latest changes if this is a git repository
if [ -d .git ]; then
    log "Pulling latest changes from git..."
    git pull origin main || git pull origin master || log_warning "Git pull failed or not needed"
fi

# Backup current configuration
log "Backing up current configuration..."
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Build new images
log "Building updated Docker images..."
docker compose -f docker-compose.prod.yml build --no-cache

# Perform rolling update
log "Performing rolling update..."

# Update monitoring service first (less critical)
log "Updating VATSIM monitoring service..."
docker compose -f docker-compose.prod.yml up -d --no-deps vatsim-monitor

# Wait a moment
sleep 5

# Update web API service
log "Updating web API service..."
docker compose -f docker-compose.prod.yml up -d --no-deps web-api

# Wait for web service to be ready
log "Waiting for web service to be ready..."
sleep 10

# Check web API health
for i in {1..30}; do
    if docker compose -f docker-compose.prod.yml exec -T web-api curl -f -s http://localhost:8080/api/health > /dev/null 2>&1; then
        log_success "Web API is healthy after update"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "Web API failed to become healthy after update"
        log "Rolling back..."
        docker compose -f docker-compose.prod.yml restart web-api
        exit 1
    fi
    sleep 2
done

# Update nginx (reload configuration)
log "Reloading nginx configuration..."
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload || {
    log_warning "Nginx reload failed, restarting nginx container..."
    docker compose -f docker-compose.prod.yml restart nginx
}

# Clean up old images
log "Cleaning up old Docker images..."
docker image prune -f

# Display service status
log "Updated service status:"
docker compose -f docker-compose.prod.yml ps

# Check overall health
log "Performing health checks..."

# Check HTTPS
if curl -f -s -k https://localhost/api/health > /dev/null 2>&1; then
    log_success "HTTPS is working"
else
    log_error "HTTPS health check failed"
    exit 1
fi

# Check nginx health
if curl -f -s http://localhost/nginx-health > /dev/null 2>&1; then
    log_success "Nginx is healthy"
else
    log_warning "Nginx health check failed"
fi

# Display recent logs
log "Recent logs from updated services:"
docker compose -f docker-compose.prod.yml logs --tail=5 web-api
docker compose -f docker-compose.prod.yml logs --tail=5 vatsim-monitor

log_success "Production update completed successfully! 🚀"
log "Services are running and healthy."

# Check SSL certificate expiry
log "Checking SSL certificate expiry..."
if [ -f "certbot/conf/live/$(grep DOMAIN_NAME .env | cut -d'=' -f2)/fullchain.pem" ]; then
    DOMAIN_NAME=$(grep DOMAIN_NAME .env | cut -d'=' -f2)
    CERT_EXPIRY=$(openssl x509 -enddate -noout -in "certbot/conf/live/$DOMAIN_NAME/fullchain.pem" | cut -d= -f2)
    CERT_EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( (CERT_EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
    
    if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
        log_warning "SSL certificate expires in $DAYS_UNTIL_EXPIRY days. Consider renewing soon."
    else
        log_success "SSL certificate is valid for $DAYS_UNTIL_EXPIRY more days."
    fi
fi

log "Update complete!"