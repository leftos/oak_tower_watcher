#!/bin/bash

# VATSIM Tower Monitor - Docker Deployment Script
# This script helps deploy the Docker version of the headless monitor

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Test Docker access
    if ! docker --version >/dev/null 2>&1; then
        print_error "Docker is installed but not accessible."
        print_warning "This is likely a permissions issue. Try one of these solutions:"
        echo ""
        echo "Solution 1 (Recommended): Add user to docker group"
        echo "  sudo usermod -aG docker \$USER"
        echo "  newgrp docker"
        echo ""
        echo "Solution 2: Use sudo with this script"
        echo "  sudo $0"
        echo ""
        echo "Solution 3: Fix socket permissions"
        echo "  sudo chmod 666 /var/run/docker.sock"
        exit 1
    fi
    
    if ! command_exists docker compose; then
        print_warning "docker compose not found, trying docker compose..."
        if ! docker compose version >/dev/null 2>&1; then
            print_error "Neither docker compose nor 'docker compose' is available."
            exit 1
        else
            DOCKER_COMPOSE_CMD="docker compose"
        fi
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup environment file
setup_environment() {
    print_status "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.sample" ]; then
            cp .env.sample .env
            print_success "Created .env file from sample"
        else
            print_error ".env.sample file not found"
            exit 1
        fi
    else
        print_warning ".env file already exists, skipping creation"
    fi
    
    # Check if Pushover credentials are set
    if grep -q "your_pushover_api_token_here" .env || grep -q "your_pushover_user_key_here" .env; then
        print_warning "Please update your Pushover credentials in .env file before continuing"
        echo "Edit .env and set:"
        echo "  PUSHOVER_API_TOKEN=your_actual_token"
        echo "  PUSHOVER_USER_KEY=your_actual_user_key"
        echo ""
        read -p "Press Enter after updating .env file..."
    fi
}

# Function to build and start the service
deploy_service() {
    print_status "Building and starting VATSIM Tower Monitor..."
    
    # Build the image
    print_status "Building Docker image..."
    if ! $DOCKER_COMPOSE_CMD build; then
        print_error "Failed to build Docker image"
        exit 1
    fi
    
    # Start the service
    print_status "Starting the service..."
    if ! $DOCKER_COMPOSE_CMD up -d; then
        print_error "Failed to start the service"
        exit 1
    fi
    
    print_success "Service started successfully!"
}

# Function to show status and logs
show_status() {
    print_status "Checking service status..."
    
    # Show container status
    $DOCKER_COMPOSE_CMD ps
    
    echo ""
    print_status "Recent logs (last 20 lines):"
    $DOCKER_COMPOSE_CMD logs --tail=20
    
    echo ""
    print_status "To follow logs in real-time, run:"
    echo "  $DOCKER_COMPOSE_CMD logs -f"
}

# Function to test Pushover configuration
test_pushover() {
    print_status "The service will test Pushover notifications on startup."
    print_status "Check the logs above for 'Pushover test successful' message."
    
    echo ""
    print_status "If you don't receive a test notification:"
    echo "1. Verify your Pushover credentials in .env"
    echo "2. Check the logs: $DOCKER_COMPOSE_CMD logs"
    echo "3. Restart the service: $DOCKER_COMPOSE_CMD restart"
}

# Main deployment function
main() {
    echo "=========================================="
    echo "VATSIM Tower Monitor - Docker Deployment"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    setup_environment
    deploy_service
    
    echo ""
    echo "=========================================="
    print_success "Deployment completed!"
    echo "=========================================="
    echo ""
    
    show_status
    test_pushover
    
    echo ""
    print_status "Useful commands:"
    echo "  View logs:           $DOCKER_COMPOSE_CMD logs -f"
    echo "  Stop service:        $DOCKER_COMPOSE_CMD down"
    echo "  Restart service:     $DOCKER_COMPOSE_CMD restart"
    echo "  Update service:      $DOCKER_COMPOSE_CMD down && $DOCKER_COMPOSE_CMD build --no-cache && $DOCKER_COMPOSE_CMD up -d"
    echo ""
}

# Handle command line arguments
case "${1:-}" in
    "status")
        show_status
        ;;
    "logs")
        $DOCKER_COMPOSE_CMD logs -f
        ;;
    "stop")
        print_status "Stopping VATSIM Tower Monitor..."
        $DOCKER_COMPOSE_CMD down
        print_success "Service stopped"
        ;;
    "restart")
        print_status "Restarting VATSIM Tower Monitor..."
        $DOCKER_COMPOSE_CMD restart
        print_success "Service restarted"
        ;;
    "update")
        print_status "Updating VATSIM Tower Monitor..."
        $DOCKER_COMPOSE_CMD down
        $DOCKER_COMPOSE_CMD build --no-cache
        $DOCKER_COMPOSE_CMD up -d
        print_success "Service updated and restarted"
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [status|logs|stop|restart|update]"
        echo ""
        echo "Commands:"
        echo "  (no args)  - Deploy the service"
        echo "  status     - Show service status"
        echo "  logs       - Follow service logs"
        echo "  stop       - Stop the service"
        echo "  restart    - Restart the service"
        echo "  update     - Update and restart the service"
        exit 1
        ;;
esac