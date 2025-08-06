#!/usr/bin/env python3
"""
Main Flask application with user authentication and API endpoints
"""

import json
import logging
import os
import sys
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from config.config import load_config
from src.vatsim_core import VATSIMCore
from src.utils import load_artcc_roster, get_controller_name
from .models import db, User
from .auth import auth_bp

def create_app():
    """Application factory"""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../',
                static_url_path='/static')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///users.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Configure logging
    log_level = logging.DEBUG if os.environ.get('DEBUG', 'False').lower() == 'true' else logging.INFO
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging with both file and console output
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'web_app.log')),
            logging.StreamHandler()
        ]
    )
    
    # Set specific log levels for different modules
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Reduce Flask request logging noise
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)  # Reduce SQLAlchemy noise
    
    app.logger.info("Logging configured successfully")
    
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")
            raise
    
    return app

app = create_app()

class StatusAPI:
    def __init__(self):
        self.config = load_config()
        self.airport_config = self.config.get("airport", {})
        self.airport_code = self.airport_config.get("code", "KOAK")
        self.display_name = self.airport_config.get("display_name", "Oakland Tower")
        
        # Load ARTCC roster for controller names
        roster_url = self.config.get("api", {}).get(
            "roster_url", "https://oakartcc.org/about/roster"
        )
        self.controller_names = load_artcc_roster(roster_url)
        
        # Create a core VATSIM client instance
        self.vatsim_core = VATSIMCore(self.config)
        
        logging.info(f"Status API initialized for {self.display_name}")

    def get_current_status(self):
        """Get current VATSIM status"""
        try:
            # Use the core VATSIM client to check status
            result = self.vatsim_core.check_status()
            
            if not result["success"]:
                return {
                    "error": result.get("error", "Failed to query VATSIM API"),
                    "status": "error",
                    "timestamp": result["timestamp"]
                }
            
            # Format controller data
            def format_controllers(controllers):
                if not controllers:
                    return []
                
                formatted = []
                for controller in controllers:
                    formatted.append({
                        "callsign": controller.get("callsign", "Unknown"),
                        "name": get_controller_name(controller, self.controller_names),
                        "frequency": controller.get("frequency", "Unknown"),
                        "cid": controller.get("cid", "Unknown"),
                        "logon_time": controller.get("logon_time", "Unknown"),
                        "server": controller.get("server", "Unknown"),
                        "rating": controller.get("rating", 0)
                    })
                return formatted
            
            return {
                "status": result["status"],
                "airport_code": self.airport_code,
                "display_name": self.display_name,
                "timestamp": result["timestamp"],
                "main_controllers": format_controllers(result["main_controllers"]),
                "supporting_above": format_controllers(result["supporting_above"]),
                "supporting_below": format_controllers(result["supporting_below"]),
                "config": {
                    "check_interval": self.config.get("monitoring", {}).get("check_interval", 30),
                    "airport_name": self.airport_config.get("name", "Oakland International Airport")
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting status: {e}")
            return {
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }

# Create global status API instance
status_api = StatusAPI()

# Main routes
@app.route('/')
def index():
    """Serve the homepage"""
    return send_from_directory('../', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from web directory"""
    # Check if it's a template file that should be rendered
    if filename.endswith('.html') and filename != 'index.html':
        try:
            return render_template(filename)
        except:
            pass
    return send_from_directory('../', filename)

# API routes
@app.route('/api/status')
def get_status():
    """Get current VATSIM monitoring status"""
    try:
        status_data = status_api.get_current_status()
        return jsonify(status_data)
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "OAK Tower Watcher API",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/config')
def get_config():
    """Get basic configuration information"""
    return jsonify({
        "airport_code": status_api.airport_code,
        "display_name": status_api.display_name,
        "airport_name": status_api.airport_config.get("name", "Oakland International Airport"),
        "check_interval": status_api.config.get("monitoring", {}).get("check_interval", 30),
        "timestamp": datetime.now().isoformat()
    })

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
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logging.info(f"Starting OAK Tower Watcher Web API on {host}:{port}")
    logging.info(f"Debug mode: {debug}")
    
    try:
        with app.app_context():
            db.create_all()
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logging.info("Shutting down web API...")
    except Exception as e:
        logging.error(f"Error starting web API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()