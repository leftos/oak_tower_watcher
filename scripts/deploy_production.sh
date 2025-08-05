#!/bin/bash
set -e

# Production Deployment Script for OAK Tower Watcher
# This script sets up the production environment with HTTPS

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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if user is in docker group
if ! groups $USER | grep &>/dev/null '\bdocker\b'; then
    log_warning "User $USER is not in the docker group. You may need to use sudo for Docker commands."
    log_warning "To fix this, run: sudo usermod -aG docker $USER && newgrp docker"
fi

log "Starting OAK Tower Watcher Production Deployment..."

# Create necessary directories
log "Creating necessary directories..."
mkdir -p nginx/ssl
mkdir -p certbot/conf
mkdir -p certbot/www
mkdir -p logs

# Check if .env file exists
if [ ! -f .env ]; then
    if [ -f .env.prod ]; then
        log "Copying .env.prod to .env..."
        cp .env.prod .env
        log_warning "Please edit .env file with your actual configuration values before continuing."
        log_warning "Required values: DOMAIN_NAME, SSL_EMAIL, PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY"
        read -p "Press Enter after you've configured the .env file..."
    else
        log_error ".env file not found. Please create one based on .env.prod"
        exit 1
    fi
fi

# Source environment variables
source .env

# Validate required environment variables
if [ -z "$DOMAIN_NAME" ]; then
    log_error "Please set DOMAIN_NAME in your .env file"
    exit 1
fi

if [ -z "$SSL_EMAIL" ]; then
    log_error "Please set SSL_EMAIL in your .env file"
    exit 1
fi

if [ -z "$PUSHOVER_API_TOKEN" ] || [ "$PUSHOVER_API_TOKEN" = "your_pushover_api_token_here" ]; then
    log_warning "PUSHOVER_API_TOKEN not set. Notifications will be disabled."
fi

if [ -z "$PUSHOVER_USER_KEY" ] || [ "$PUSHOVER_USER_KEY" = "your_pushover_user_key_here" ]; then
    log_warning "PUSHOVER_USER_KEY not set. Notifications will be disabled."
fi

log "Configuration validated for domain: $DOMAIN_NAME"

# Stop existing containers if running
log "Stopping existing containers..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# Build images
log "Building Docker images..."
docker compose -f docker-compose.prod.yml build --no-cache

# Start services without nginx first (for SSL certificate generation)
log "Starting services for SSL certificate generation..."
docker compose -f docker-compose.prod.yml up -d vatsim-monitor web-api

# Wait for web service to be ready
log "Waiting for web service to be ready..."
sleep 10

# Check if SSL certificates already exist (use docker to check since files may have restricted permissions)
if ! docker run --rm -v $(pwd)/certbot/conf:/etc/letsencrypt certbot/certbot certificates 2>/dev/null | grep -q "$DOMAIN_NAME"; then
    log "Generating SSL certificates for $DOMAIN_NAME..."
    
    # Start nginx temporarily for HTTP challenge
    docker run --rm -d \
        --name temp-nginx \
        -p 80:80 \
        -v $(pwd)/certbot/www:/var/www/certbot:ro \
        nginx:alpine \
        sh -c 'echo "server { listen 80; location /.well-known/acme-challenge/ { root /var/www/certbot; } location / { return 301 https://\$host\$request_uri; } }" > /etc/nginx/conf.d/default.conf && nginx -g "daemon off;"'
    
    sleep 5
    
    # Generate certificate (non-interactive mode)
    if docker run --rm \
        -v $(pwd)/certbot/conf:/etc/letsencrypt \
        -v $(pwd)/certbot/www:/var/www/certbot \
        certbot/certbot \
        certonly --webroot --webroot-path=/var/www/certbot \
        --email $SSL_EMAIL --agree-tos --no-eff-email \
        --non-interactive --keep-until-expiring \
        -d $DOMAIN_NAME; then
        
        # Stop temporary nginx
        docker stop temp-nginx 2>/dev/null || true
        
        # Verify certificate was created (check with docker since files may have restricted permissions)
        if docker run --rm -v $(pwd)/certbot/conf:/etc/letsencrypt certbot/certbot certificates | grep -q "$DOMAIN_NAME"; then
            log_success "SSL certificates generated successfully!"
        else
            log_error "Certificate generation reported success but files not found."
            exit 1
        fi
    else
        # Stop temporary nginx even if certbot failed
        docker stop temp-nginx 2>/dev/null || true
        log_error "Failed to generate SSL certificates. Please check your domain DNS settings."
        exit 1
    fi
else
    log_success "SSL certificates already exist for $DOMAIN_NAME"
fi

# Setup Nginx configuration based on SSL certificate availability
log "Setting up Nginx configuration..."
./scripts/setup_nginx_config.sh

# Start all services including nginx
log "Starting all production services..."
docker compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
log "Waiting for services to start..."
sleep 15

# Check service health
log "Checking service health..."

# Check web API health (through nginx proxy)
if curl -f -s http://localhost/api/health > /dev/null 2>&1; then
    log_success "Web API is healthy (via HTTP)"
else
    log_warning "Web API HTTP health check failed"
fi

# Check nginx health
if curl -f -s http://localhost/nginx-health > /dev/null 2>&1; then
    log_success "Nginx is healthy"
else
    log_warning "Nginx health check failed"
fi

# Check HTTPS
if curl -f -s -k https://localhost/api/health > /dev/null 2>&1; then
    log_success "HTTPS is working"
elif curl -f -s -k https://$DOMAIN_NAME/api/health > /dev/null 2>&1; then
    log_success "HTTPS is working (via domain)"
else
    log_warning "HTTPS health check failed - may need DNS propagation time"
fi

# Display service status
log "Service Status:"
docker compose -f docker-compose.prod.yml ps

# Display logs for troubleshooting
log "Recent logs:"
docker compose -f docker-compose.prod.yml logs --tail=10

log_success "Production deployment completed!"
log_success "Your OAK Tower Watcher is now running at:"
log_success "  HTTP:  http://$DOMAIN_NAME (redirects to HTTPS)"
log_success "  HTTPS: https://$DOMAIN_NAME"
log_success "  API:   https://$DOMAIN_NAME/api/status"

log "To manage the deployment:"
log "  View logs:    docker compose -f docker-compose.prod.yml logs -f"
log "  Stop:         docker compose -f docker-compose.prod.yml down"
log "  Restart:      docker compose -f docker-compose.prod.yml restart"
log "  Update:       ./scripts/update_production.sh"

# Set up SSL certificate renewal
log "Setting up SSL certificate auto-renewal..."
(crontab -l 2>/dev/null; echo "0 12 * * * cd $(pwd) && docker compose -f docker-compose.prod.yml run --rm certbot renew --quiet && docker compose -f docker-compose.prod.yml restart nginx") | crontab -

log_success "SSL certificate auto-renewal configured!"
log "Deployment complete! 🚀"