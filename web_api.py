#!/usr/bin/env python3
"""
Simple web API for OAK Tower Watcher status
Provides REST endpoints to get current VATSIM monitoring status
"""

import json
import logging
import os
import sys
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config.config import load_config
from src.vatsim_core import VATSIMCore
from src.utils import load_artcc_roster, get_controller_name

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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

@app.route('/')
def serve_homepage():
    """Serve the homepage"""
    return send_from_directory('web', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from web directory"""
    return send_from_directory('web', filename)

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
    return jsonify({
        "error": "Not found",
        "message": "The requested resource was not found",
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.now().isoformat()
    }), 500

def main():
    """Main entry point"""
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logging.info(f"Starting OAK Tower Watcher Web API on {host}:{port}")
    logging.info(f"Debug mode: {debug}")
    
    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logging.info("Shutting down web API...")
    except Exception as e:
        logging.error(f"Error starting web API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()