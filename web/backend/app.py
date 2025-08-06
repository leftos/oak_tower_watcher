#!/usr/bin/env python3
"""
Main Flask application with user authentication and API endpoints
"""

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, send_from_directory, render_template, request, abort
from flask_cors import CORS
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Import shared components using new structure
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.config import load_config
from config.env_config import env_config
from shared.vatsim_core import VATSIMCore
from shared.utils import load_artcc_roster, get_controller_name
from .models import db, User
from .auth import auth_bp
from .email_service import init_mail
from .api import api_bp
from .security import init_security, rate_limit
 
def create_app():
    """Application factory with environment-specific configuration"""
    # Validate production configuration if needed
    if not env_config.validate_production_config():
        raise RuntimeError("Invalid production configuration")
    
    # Setup directories based on environment
    env_config.setup_directories()
    
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../',
                static_url_path='/static')
    
    # Get environment-specific configurations
    flask_config = env_config.get_flask_config()
    db_config = env_config.get_database_config()
    log_config = env_config.get_log_config()
    
    # Apply Flask configuration
    app.config['SECRET_KEY'] = flask_config['SECRET_KEY']
    app.config['DEBUG'] = flask_config['DEBUG']
    app.config['TESTING'] = flask_config['TESTING']
    
    # Apply database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = db_config['uri']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = db_config['track_modifications']
    app.config['SQLALCHEMY_ECHO'] = db_config['echo']
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    init_mail(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Configure environment-specific logging
    configure_logging(app, log_config)
    
    # Initialize security middleware
    init_security(app)
    
    # Log environment information
    env_info = env_config.get_environment_info()
    app.logger.info(f"Application started in {env_info['environment']} environment")
    app.logger.info(f"Database: {env_info['database_uri']}")
    app.logger.info(f"Log directory: {env_info['log_directory']}")
    app.logger.info(f"Debug mode: {env_info['debug_mode']}")
    
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            # Check if it's just a "table already exists" error, which is fine
            if "already exists" in str(e).lower():
                app.logger.info(f"Database tables already exist: {e}")
            else:
                app.logger.error(f"Error creating database tables: {e}")
                raise
    
    @app.route('/')
    @rate_limit(max_requests=30, window_minutes=5)  # More lenient for homepage
    def index():
        """Serve the homepage"""
        return send_from_directory('../', 'index.html')

    @app.route('/robots.txt')
    def robots_txt():
        """Serve robots.txt to discourage bots"""
        return send_from_directory('../', 'robots.txt')

    @app.route('/<path:filename>')
    @rate_limit(max_requests=20, window_minutes=5)  # Rate limit static files
    def serve_static(filename):
        """Serve static files from web directory - with security restrictions"""
        # Security: Block common attack paths
        forbidden_patterns = [
            '.env', 'config', 'backup', '.git', '.htaccess', '.htpasswd',
            'wp-admin', 'wp-login', 'phpmyadmin', 'admin', 'server-status',
            'xmlrpc', '.well-known'
        ]
        
        filename_lower = filename.lower()
        for pattern in forbidden_patterns:
            if pattern in filename_lower:
                app.logger.warning(f"Blocked access to forbidden file: {filename} from IP: {request.remote_addr}")
                abort(403)
        
        # Only serve known safe file types
        allowed_extensions = [
            '.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico',
            '.svg', '.woff', '.woff2', '.ttf', '.eot', '.map'
        ]
        
        if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
            app.logger.warning(f"Blocked access to disallowed file type: {filename} from IP: {request.remote_addr}")
            abort(404)  # Return 404 instead of revealing file structure
        
        # Check if file exists in templates directory for rendering
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        template_path = os.path.join(template_dir, filename)
        
        if filename.endswith('.html') and filename != 'index.html' and os.path.exists(template_path):
            try:
                return render_template(filename)
            except Exception as e:
                app.logger.warning(f"Template rendering failed for {filename}: {str(e)}")
                abort(404)
        
        # Serve as static file
        try:
            return send_from_directory('../', filename)
        except Exception as e:
            app.logger.warning(f"Static file serving failed for {filename}: {str(e)}")
            abort(404)
    return app


def configure_logging(app, log_config):
    """Configure logging based on environment"""
    # Clear any existing handlers
    app.logger.handlers.clear()
    
    # Create file handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(log_config['dir'], log_config['filename']),
        maxBytes=log_config['max_bytes'],
        backupCount=log_config['backup_count']
    )
    file_handler.setLevel(log_config['level'])
    file_handler.setFormatter(logging.Formatter(log_config['format']))
    app.logger.addHandler(file_handler)
    
    # Add console handler if enabled (typically for development)
    if log_config['console_output']:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_config['level'])
        console_handler.setFormatter(logging.Formatter(log_config['format']))
        app.logger.addHandler(console_handler)
    
    # Set the app logger level
    app.logger.setLevel(log_config['level'])
    
    # Configure other loggers based on environment
    if env_config.is_production():
        # In production, reduce noise from other loggers
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    else:
        # In development, allow more verbose logging if debug is enabled
        if log_config['level'] == logging.DEBUG:
            logging.getLogger('werkzeug').setLevel(logging.INFO)
            logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO if log_config.get('echo', False) else logging.WARNING)
        else:
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    app.logger.info("Logging configured successfully")

# Status API functionality is now handled by status_service.py

app = create_app()


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    app.logger.warning(f"404 Error - Path: {request.path}, Method: {request.method}, IP: {request.remote_addr}")
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found",
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f"500 Error - Path: {request.path}, Method: {request.method}, IP: {request.remote_addr}, Error: {str(error)}", exc_info=True)
    
    # Roll back any pending database transactions
    try:
        db.session.rollback()
    except Exception as rollback_error:
        app.logger.error(f"Error during database rollback: {str(rollback_error)}")
    
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.now().isoformat()
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all unhandled exceptions"""
    app.logger.error(f"Unhandled Exception - Path: {request.path}, Method: {request.method}, IP: {request.remote_addr}, Error: {str(error)}", exc_info=True)
    
    # Roll back any pending database transactions
    try:
        db.session.rollback()
    except Exception as rollback_error:
        app.logger.error(f"Error during database rollback: {str(rollback_error)}")
    
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.now().isoformat()
    }), 500

# Database initialization is handled in main() function

def main():
    """Main entry point"""
    flask_config = env_config.get_flask_config()
    
    host = flask_config['HOST']
    port = flask_config['PORT']
    debug = flask_config['DEBUG']
    
    app.logger.info(f"Starting OAK Tower Watcher Web API on {host}:{port}")
    app.logger.info(f"Environment: {env_config.env}")
    app.logger.info(f"Debug mode: {debug}")
    
    try:
        with app.app_context():
            db.create_all()
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        app.logger.info("Shutting down web API...")
    except Exception as e:
        app.logger.error(f"Error starting web API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()