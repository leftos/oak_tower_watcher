#!/usr/bin/env python3
"""
Security middleware and utilities for the Flask application
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, abort, current_app, redirect, url_for, render_template
from flask_login import current_user

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory for simplicity)
# In production, consider using Redis
rate_limit_storage = defaultdict(lambda: deque())
blocked_ips = {}

# Suspicious patterns that indicate scanning/probing
SUSPICIOUS_PATHS = [
    '/dns-query',
    '/query',
    '/resolve',
    '/.env',
    '/.well-known/',
    '/wp-admin',
    '/wp-login.php',
    '/phpmyadmin',
    '/xmlrpc.php',
    '/config/',
    '/backup/',
    '/.git/',
    '/server-status',
    '/server-info',
    # Block generic admin scanning attempts but allow our legitimate admin routes
    '/administrator',
    '/admin.php',
    '/admin/',
    '/admin/index.php',
    '/admin/admin.php',
]

# Legitimate admin routes that should be allowed
LEGITIMATE_ADMIN_PATHS = [
    '/admin/login',
    '/admin/logout',
    '/admin/dashboard',
    '/admin/users',
    '/admin/user/',
    '/admin/api/',
]

# User agents that are commonly associated with scanning
SUSPICIOUS_USER_AGENTS = [
    'Go-http-client',
    'python-requests',
    'curl/',
    'wget/',
    'nmap',
    'nikto',
    'sqlmap',
    'masscan',
    'zmap',
]

def email_verification_required(f):
    """
    Decorator to ensure user has verified their email address before accessing protected routes.
    This provides an additional layer of security beyond the login check.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated first
        if not current_user.is_authenticated:
            # Let Flask-Login's @login_required handle this
            return f(*args, **kwargs)
        
        # Check if email is verified
        if not current_user.email_verified:
            logger.warning(f"Unverified user attempted to access protected route: {current_user.email} -> {request.endpoint}")
            
            # For API endpoints, return JSON error
            if request.endpoint and (request.endpoint.startswith('api.') or request.path.startswith('/api/')):
                return jsonify({
                    "error": "Email verification required",
                    "message": "Please verify your email address before accessing this feature.",
                    "requires_verification": True,
                    "timestamp": datetime.now().isoformat()
                }), 403
            
            # For web endpoints, redirect to verification required page
            return render_template('auth/email_verification_required.html',
                                 title='Email Verification Required',
                                 user_email=current_user.email)
        
        return f(*args, **kwargs)
    return decorated_function

def is_suspicious_request():
    """Check if the current request looks suspicious"""
    path = request.path.lower()
    user_agent = request.headers.get('User-Agent', '').lower()
    client_ip = get_client_ip()
    
    # Allow health checks from localhost/internal monitoring
    if path == '/api/health':
        # Allow health checks from localhost and internal Docker networks
        if client_ip and (client_ip in ['127.0.0.1', '::1'] or client_ip.startswith('172.') or client_ip.startswith('192.168.')):
            return False, None
    
    # Check if this is a legitimate admin route first
    for legitimate_path in LEGITIMATE_ADMIN_PATHS:
        if path.startswith(legitimate_path.lower()):
            return False, None
    
    # Check for suspicious paths
    for suspicious_path in SUSPICIOUS_PATHS:
        if path.startswith(suspicious_path.lower()):
            return True, f"Suspicious path: {path}"
    
    # Check for suspicious user agents, but be more lenient for known endpoints
    if path not in ['/api/health', '/api/status', '/api/config']:
        for suspicious_ua in SUSPICIOUS_USER_AGENTS:
            if suspicious_ua.lower() in user_agent:
                return True, f"Suspicious user agent: {user_agent}"
    
    # Check for DNS query parameters (DoH probing)
    if 'dns=' in request.query_string.decode('utf-8', errors='ignore'):
        return True, "DNS query parameter detected"
    
    # Check for common scanning parameters
    scanning_params = ['name=', 'type=a', 'type=aaaa', 'type=mx']
    query_string = request.query_string.decode('utf-8', errors='ignore').lower()
    for param in scanning_params:
        if param in query_string:
            return True, f"Scanning parameter detected: {param}"
    
    return False, None

def rate_limit(max_requests=60, window_minutes=5, block_minutes=15):
    """
    Rate limiting decorator
    
    Args:
        max_requests: Maximum requests allowed in the window
        window_minutes: Time window in minutes
        block_minutes: How long to block IP after exceeding limit
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = get_client_ip()
            current_time = datetime.now()
            
            # Check if IP is currently blocked
            if client_ip in blocked_ips:
                block_until = blocked_ips[client_ip]
                if current_time < block_until:
                    logger.warning(f"Blocked IP attempted access: {client_ip}")
                    abort(429)  # Too Many Requests
                else:
                    # Block expired, remove from blocked list
                    del blocked_ips[client_ip]
            
            # Get request history for this IP
            requests = rate_limit_storage[client_ip]
            window_start = current_time - timedelta(minutes=window_minutes)
            
            # Remove old requests outside the window
            while requests and requests[0] < window_start:
                requests.popleft()
            
            # Check if limit exceeded
            if len(requests) >= max_requests:
                # Block the IP
                block_until = current_time + timedelta(minutes=block_minutes)
                blocked_ips[client_ip] = block_until
                logger.warning(f"Rate limit exceeded, blocking IP {client_ip} until {block_until}")
                abort(429)
            
            # Add current request to history
            requests.append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_client_ip():
    """Get the real client IP address, considering proxies"""
    # Check for forwarded headers (common with reverse proxies)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    return request.remote_addr

def block_suspicious_requests():
    """Middleware to block suspicious requests"""
    client_ip = get_client_ip()
    
    # Check if request is suspicious
    is_suspicious, reason = is_suspicious_request()
    
    if is_suspicious:
        logger.warning(f"Blocking suspicious request from {client_ip}: {reason} - Path: {request.path}, Method: {request.method}, User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        
        # Immediately block suspicious IPs for longer
        block_until = datetime.now() + timedelta(hours=1)
        blocked_ips[client_ip] = block_until
        
        # Return 403 Forbidden for suspicious requests
        return jsonify({
            "error": "Forbidden",
            "message": "Suspicious activity detected",
            "timestamp": datetime.now().isoformat()
        }), 403
    
    return None

def add_security_headers(response):
    """Add security headers to all responses"""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Enable XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Strict transport security (HTTPS only)
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Content Security Policy
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'"
    )
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Feature Policy / Permissions Policy
    response.headers['Permissions-Policy'] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "accelerometer=(), "
        "gyroscope=()"
    )
    
    return response

def init_security(app):
    """Initialize security middleware for the Flask app"""
    
    @app.before_request
    def security_middleware():
        """Run security checks on every request"""
        return block_suspicious_requests()
    
    @app.after_request
    def after_request_security(response):
        """Add security headers to all responses"""
        return add_security_headers(response)
    
    # Custom 429 error handler
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle rate limit exceeded errors"""
        client_ip = get_client_ip()
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return jsonify({
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later.",
            "timestamp": datetime.now().isoformat()
        }), 429
    
    logger.info("Security middleware initialized")