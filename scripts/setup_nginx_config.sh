#!/bin/bash

# Setup Nginx Configuration Script
# This script generates the appropriate Nginx configuration based on SSL certificate availability

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✓ $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠ $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✗ $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    log_error ".env file not found. Please create it from .env.prod template."
    exit 1
fi

# Source environment variables
source .env

# Validate required environment variables
if [ -z "$DOMAIN_NAME" ]; then
    log_error "DOMAIN_NAME not set in .env file"
    exit 1
fi

log "Setting up Nginx configuration for domain: $DOMAIN_NAME"

# Check if SSL certificates exist
SSL_CERT_PATH="certbot/conf/live/$DOMAIN_NAME/fullchain.pem"
SSL_KEY_PATH="certbot/conf/live/$DOMAIN_NAME/privkey.pem"

if [ -f "$SSL_CERT_PATH" ] && [ -f "$SSL_KEY_PATH" ]; then
    log_success "SSL certificates found, configuring HTTPS"
    
    # Use the current default.conf which assumes SSL is available
    if [ ! -f "nginx/conf.d/default.conf" ]; then
        log_error "nginx/conf.d/default.conf not found"
        exit 1
    fi
    
    # Replace domain placeholders in the existing config
    sed "s/leftos\.dev/$DOMAIN_NAME/g" nginx/conf.d/default.conf > nginx/conf.d/default.conf.tmp
    mv nginx/conf.d/default.conf.tmp nginx/conf.d/default.conf
    
    log_success "HTTPS configuration ready"
    
else
    log_warning "SSL certificates not found, configuring HTTP fallback"
    
    # Create HTTP-only configuration
    cat > nginx/conf.d/default.conf << EOF
# HTTP server - no SSL certificates available
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    
    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    # Health check endpoint
    location /nginx-health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # API endpoints - proxy to Flask app
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        add_header X-SSL-Warning "SSL certificates not configured - using HTTP" always;
        
        proxy_pass http://web-api:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Static files - proxy to Flask app
    location / {
        limit_req zone=static burst=50 nodelay;
        add_header X-SSL-Warning "SSL certificates not configured - using HTTP" always;
        
        proxy_pass http://web-api:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # Cache static assets
        location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            proxy_pass http://web-api:8080;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
    
    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
    
    # Custom error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    
    location = /404.html {
        internal;
        proxy_pass http://web-api:8080/404;
    }
    
    location = /50x.html {
        internal;
        proxy_pass http://web-api:8080/500;
    }
}
EOF
    
    log_success "HTTP fallback configuration ready"
fi

log_success "Nginx configuration setup complete"