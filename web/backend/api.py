from flask import Blueprint, jsonify
import logging
from datetime import datetime
from .status_service import status_api

api_bp = Blueprint('api', __name__)

@api_bp.route('/status')
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

@api_bp.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "OAK Tower Watcher API",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@api_bp.route('/config')
def get_config():
    """Get basic configuration information"""
    try:
        return jsonify({
            "airport_code": status_api.airport_code,
            "display_name": status_api.display_name,
            "airport_name": status_api.airport_config.get("name", "Oakland International Airport"),
            "check_interval": status_api.config.get("monitoring", {}).get("check_interval", 30),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Config API error: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500