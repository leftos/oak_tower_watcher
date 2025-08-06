#!/bin/bash
set -e

# Production Test Script for OAK Tower Watcher
# This script validates the production deployment

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
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✓ $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠ $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✗ $1"
}

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log "Testing: $test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        if [ "$expected_result" = "success" ]; then
            log_success "$test_name"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            log_error "$test_name (expected failure but got success)"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        if [ "$expected_result" = "failure" ]; then
            log_success "$test_name (expected failure)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            log_error "$test_name"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    fi
}

# Function to test HTTP response
test_http() {
    local url="$1"
    local expected_code="$2"
    local description="$3"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log "Testing HTTP: $description"
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response_code" = "$expected_code" ]; then
        log_success "$description (HTTP $response_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "$description (Expected HTTP $expected_code, got $response_code)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

log "Starting OAK Tower Watcher Production Tests..."

# Check if .env file exists
if [ ! -f .env ]; then
    log_error ".env file not found. Please run deploy_production.sh first."
    exit 1
fi

# Source environment variables
source .env

# Validate required environment variables
if [ -z "$DOMAIN_NAME" ]; then
    log_error "DOMAIN_NAME not set in .env file"
    exit 1
fi

log "Testing domain: $DOMAIN_NAME"

# Test 1: Docker services are running
log "=== Docker Service Tests ==="
run_test "Docker Compose services are running" "docker compose -f docker-compose.prod.yml ps | grep -q 'Up'" "success"
run_test "Nginx container is running" "docker compose -f docker-compose.prod.yml ps nginx | grep -q 'Up'" "success"
run_test "Web API container is running" "docker compose -f docker-compose.prod.yml ps web-api | grep -q 'Up'" "success"
run_test "VATSIM Monitor container is running" "docker compose -f docker-compose.prod.yml ps vatsim-monitor | grep -q 'Up'" "success"

# Test 2: Container health checks
log "=== Container Health Tests ==="
run_test "Nginx container is healthy" "docker inspect vatsim-nginx --format='{{.State.Health.Status}}' | grep -q 'healthy'" "success"
run_test "Web API container is healthy" "docker inspect vatsim-web-api --format='{{.State.Health.Status}}' | grep -q 'healthy'" "success"

# Test 3: HTTP/HTTPS connectivity tests
log "=== HTTP/HTTPS Connectivity Tests ==="

# Check if SSL certificates exist by testing HTTPS connectivity
# This is more reliable than checking file permissions
HTTPS_WORKING=false
if curl -f -s -k "https://$DOMAIN_NAME/api/health" > /dev/null 2>&1; then
    HTTPS_WORKING=true
fi

if [ "$HTTPS_WORKING" = "true" ]; then
    log "SSL certificates found - testing HTTPS configuration"
    
    # Test HTTP redirects (expected behavior for security)
    # Note: /nginx-health endpoint is designed to work on HTTP for Docker health checks
    test_http "http://localhost/nginx-health" "200" "Nginx health check (HTTP for Docker)"
    test_http "http://localhost/api/health" "301" "Web API health check (HTTP redirect)"
    
    # Test domain endpoints if domain is not localhost
    if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
        test_http "http://$DOMAIN_NAME" "301" "HTTP redirect to HTTPS"
        test_http "https://$DOMAIN_NAME" "200" "HTTPS homepage"
        test_http "https://$DOMAIN_NAME/api/health" "200" "HTTPS API health check"
        test_http "https://$DOMAIN_NAME/api/status" "200" "HTTPS API status endpoint"
        test_http "https://$DOMAIN_NAME/nginx-health" "200" "HTTPS Nginx health check"
    else
        log_warning "Skipping domain tests (localhost/127.0.0.1 detected)"
    fi
else
    log_warning "HTTPS not working - testing HTTP fallback configuration"
    test_http "http://localhost/nginx-health" "200" "Nginx health check (HTTP fallback)"
    test_http "http://localhost/api/health" "200" "Web API health check (HTTP fallback)"
    
    # Test domain endpoints if domain is not localhost
    if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
        test_http "http://$DOMAIN_NAME" "200" "HTTP homepage (fallback)"
        test_http "http://$DOMAIN_NAME/api/health" "200" "HTTP API health check (fallback)"
        test_http "http://$DOMAIN_NAME/api/status" "200" "HTTP API status endpoint (fallback)"
    else
        log_warning "Skipping domain tests (localhost/127.0.0.1 detected)"
    fi
fi

# Test 4: SSL Certificate validation
log "=== SSL Certificate Tests ==="
if [ "$HTTPS_WORKING" = "true" ]; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log "Testing: SSL certificate functionality"
    if curl -f -s "https://$DOMAIN_NAME/api/health" > /dev/null 2>&1; then
        log_success "SSL certificate is working properly"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Try to get certificate info if possible
        CERT_INFO=$(echo | openssl s_client -servername "$DOMAIN_NAME" -connect "$DOMAIN_NAME:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo "")
        if [ -n "$CERT_INFO" ]; then
            CERT_EXPIRY=$(echo "$CERT_INFO" | grep "notAfter" | cut -d= -f2)
            if [ -n "$CERT_EXPIRY" ]; then
                CERT_EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s 2>/dev/null || echo "0")
                CURRENT_EPOCH=$(date +%s)
                DAYS_UNTIL_EXPIRY=$(( (CERT_EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
                
                if [ $DAYS_UNTIL_EXPIRY -gt 7 ]; then
                    log_success "SSL certificate valid for $DAYS_UNTIL_EXPIRY more days"
                else
                    log_warning "SSL certificate expires in $DAYS_UNTIL_EXPIRY days"
                fi
            fi
        fi
    else
        log_error "SSL certificate functionality test failed"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    log_warning "HTTPS not working - SSL certificate test skipped"
fi

# Test 5: API functionality tests
log "=== API Functionality Tests ==="

# Test internal API connectivity via Docker network
TESTS_TOTAL=$((TESTS_TOTAL + 1))
log "Testing: Internal API health check"
INTERNAL_API_RESPONSE=$(docker compose -f docker-compose.prod.yml exec -T web-api curl -s http://localhost:8080/api/health 2>/dev/null || echo "")
if echo "$INTERNAL_API_RESPONSE" | grep -q '"status"'; then
    log_success "Internal API health check"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_error "Internal API health check failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test API config endpoint via Docker network
TESTS_TOTAL=$((TESTS_TOTAL + 1))
log "Testing: Internal API config endpoint"
INTERNAL_CONFIG_RESPONSE=$(docker compose -f docker-compose.prod.yml exec -T web-api curl -s http://localhost:8080/api/config 2>/dev/null || echo "")
if echo "$INTERNAL_CONFIG_RESPONSE" | grep -q '"airport_code"'; then
    log_success "Internal API config endpoint"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_error "Internal API config endpoint failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test API response content via HTTPS if domain is available
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log "Testing API response content via HTTPS"
    API_RESPONSE=$(curl -s "https://$DOMAIN_NAME/api/health" 2>/dev/null || echo "{}")
    if echo "$API_RESPONSE" | grep -q '"status"'; then
        log_success "API returns valid JSON response via HTTPS"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "API response via HTTPS is not valid JSON"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    log_warning "Skipping HTTPS API test (localhost detected)"
fi

# Test 6: Security headers
log "=== Security Headers Tests ==="
if [ "$DOMAIN_NAME" != "localhost" ] && [ "$DOMAIN_NAME" != "127.0.0.1" ]; then
    # Check if HTTPS is working to determine which URL to test
    if [ "$HTTPS_WORKING" = "true" ]; then
        HEADERS=$(curl -s -I "https://$DOMAIN_NAME" 2>/dev/null || echo "")
        PROTOCOL="HTTPS"
    else
        HEADERS=$(curl -s -I "http://$DOMAIN_NAME" 2>/dev/null || echo "")
        PROTOCOL="HTTP"
    fi
    
    log "Testing security headers via $PROTOCOL"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 4))
    
    # HSTS header (only expected for HTTPS)
    if [ "$PROTOCOL" = "HTTPS" ]; then
        if echo "$HEADERS" | grep -qi "strict-transport-security"; then
            log_success "HSTS header present"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            log_error "HSTS header missing"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        log_warning "HSTS header not expected for HTTP"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi
    
    if echo "$HEADERS" | grep -qi "x-frame-options"; then
        log_success "X-Frame-Options header present"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "X-Frame-Options header missing"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    if echo "$HEADERS" | grep -qi "x-content-type-options"; then
        log_success "X-Content-Type-Options header present"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "X-Content-Type-Options header missing"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    if echo "$HEADERS" | grep -qi "content-security-policy"; then
        log_success "Content-Security-Policy header present"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "Content-Security-Policy header missing"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    log_warning "Skipping security header tests (localhost detected)"
fi

# Test 7: Log files and directories
log "=== File System Tests ==="
run_test "Logs directory exists" "test -d logs" "success"
run_test "Nginx config directory exists" "test -d nginx" "success"
run_test "Certbot directory exists" "test -d certbot" "success"

# Test 8: Resource usage
log "=== Resource Usage Tests ==="
TESTS_TOTAL=$((TESTS_TOTAL + 1))
log "Checking container resource usage"
MEMORY_USAGE=$(docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | grep -E "(nginx|web-api|monitor)" | awk '{print $2}' | sed 's/MiB.*//' | head -1)
if [ -n "$MEMORY_USAGE" ] && [ "$MEMORY_USAGE" -lt 500 ]; then
    log_success "Memory usage is reasonable (${MEMORY_USAGE}MiB)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_warning "Memory usage might be high (${MEMORY_USAGE}MiB)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Summary
log "=== Test Summary ==="
log "Total tests: $TESTS_TOTAL"
log_success "Passed: $TESTS_PASSED"
if [ $TESTS_FAILED -gt 0 ]; then
    log_error "Failed: $TESTS_FAILED"
else
    log_success "Failed: $TESTS_FAILED"
fi

# Calculate success rate
SUCCESS_RATE=$(( (TESTS_PASSED * 100) / TESTS_TOTAL ))
log "Success rate: ${SUCCESS_RATE}%"

if [ $TESTS_FAILED -eq 0 ]; then
    log_success "🎉 All tests passed! Production deployment is healthy."
    exit 0
elif [ $SUCCESS_RATE -ge 80 ]; then
    log_warning "⚠️  Most tests passed ($SUCCESS_RATE%). Check failed tests above."
    exit 1
else
    log_error "❌ Many tests failed ($SUCCESS_RATE%). Please review the deployment."
    exit 2
fi