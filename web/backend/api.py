from flask import Blueprint, jsonify
import logging
from datetime import datetime
from flask_login import login_required, current_user
import sys
import os

# Add the project root to Python path for importing src modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.pushover_service import PushoverService
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

@api_bp.route('/test-pushover', methods=['POST'])
@login_required
def test_pushover():
    """Send a test Pushover notification using user's credentials"""
    try:
        # Get user's OAK Tower Watcher settings
        oak_settings = current_user.get_service_settings('oak_tower_watcher')
        
        if not oak_settings:
            return jsonify({
                "success": False,
                "error": "User settings not found",
                "timestamp": datetime.now().isoformat()
            }), 404
        
        # Check if Pushover is configured
        if not oak_settings.pushover_api_token or not oak_settings.pushover_user_key:
            return jsonify({
                "success": False,
                "error": "Pushover credentials not configured",
                "message": "Please configure your Pushover API Token and User Key first",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Check if notifications are enabled
        if not oak_settings.notifications_enabled:
            return jsonify({
                "success": False,
                "error": "Notifications are disabled",
                "message": "Please enable notifications in your settings first",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Create Pushover service with user's credentials
        pushover_service = PushoverService(
            api_token=oak_settings.pushover_api_token,
            user_key=oak_settings.pushover_user_key
        )
        
        # Send test notification
        result = pushover_service.send_test_notification()
        
        if result["success"]:
            logging.info(f"Test pushover notification sent successfully for user: {current_user.email}")
            return jsonify({
                "success": True,
                "message": "Test notification sent successfully! Check your device.",
                "timestamp": datetime.now().isoformat()
            })
        else:
            logging.error(f"Test pushover notification failed for user {current_user.email}: {result['error']}")
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "message": f"Failed to send test notification: {result.get('error', 'Unknown error')}",
                "timestamp": datetime.now().isoformat()
            }), 400
    
    except Exception as e:
        logging.error(f"Error during test pushover for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred while sending the test notification",
            "timestamp": datetime.now().isoformat()
        }), 500