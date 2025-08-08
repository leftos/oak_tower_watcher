#!/usr/bin/env python3
"""
Facility Monitor API endpoints
"""

from flask import Blueprint, jsonify
import logging
from datetime import datetime
from flask_login import login_required, current_user
import sys
import os

# Import shared components using new structure
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.pushover_service import PushoverService
from shared.utils import format_push_notification
from .service import facility_status_service
from ..security import email_verification_required
from ..web_monitoring_service import web_monitoring_service

facility_api_bp = Blueprint('facility_api', __name__)

@facility_api_bp.route('/status')
def get_status():
    """Get current VATSIM monitoring status (using comprehensive cache for instant response)"""
    try:
        user_authenticated = False
        cached_data = None
        
        # Check if user is authenticated and get their facility patterns
        if current_user.is_authenticated:
            user_authenticated = True
            logging.debug(f"Getting status for authenticated user: {current_user.email}")
            
            # Get user's facility patterns
            oak_settings = current_user.get_service_settings('oak_tower_watcher')
            if oak_settings:
                user_patterns = oak_settings.get_all_facility_patterns()
                
                # Get user-filtered status from comprehensive cached data (real-time filtering)
                cached_data = web_monitoring_service.get_user_filtered_status(user_patterns)
            else:
                # User has no settings, get default view from comprehensive cache
                cached_data = web_monitoring_service.get_user_filtered_status({})
        else:
            # User not authenticated, get default view from comprehensive cache
            cached_data = web_monitoring_service.get_user_filtered_status({})
        
        if cached_data is None:
            # No cached data available - service might be starting up, fallback to direct API call
            logging.warning("Comprehensive cache not available, falling back to direct API call")
            user_id = current_user.id if current_user.is_authenticated else None
            status_data = facility_status_service.get_current_status(user_id=user_id)
            return jsonify(status_data)
        
        # Add user authentication metadata
        cached_data['user_authenticated'] = user_authenticated
        
        return jsonify(cached_data)
        
    except Exception as e:
        logging.error(f"Facility API error: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

@facility_api_bp.route('/cached-status')
def get_cached_status():
    """Get current cached VATSIM status from monitoring service (no fresh API calls), filtered by user config if authenticated"""
    try:
        user_authenticated = False
        cached_data = None
        
        # Check if user is authenticated and get their facility patterns
        if current_user.is_authenticated:
            user_authenticated = True
            logging.debug(f"Getting cached status for authenticated user: {current_user.email}")
            
            # Get user's facility patterns
            oak_settings = current_user.get_service_settings('oak_tower_watcher')
            if oak_settings:
                user_patterns = oak_settings.get_all_facility_patterns()
                
                # Get user-filtered status from comprehensive cached data (real-time filtering)
                cached_data = web_monitoring_service.get_user_filtered_status(user_patterns)
            else:
                # User has no settings, get default view from comprehensive cache
                cached_data = web_monitoring_service.get_user_filtered_status({})
        else:
            # User not authenticated, get default view from comprehensive cache
            cached_data = web_monitoring_service.get_user_filtered_status({})
        
        if cached_data is None:
            # No cached data available - service might be starting up
            return jsonify({
                "error": "No status data available",
                "status": "initializing",
                "message": "Monitoring service is initializing, please try again in a moment",
                "timestamp": datetime.now().isoformat()
            }), 503
        
        # Add user authentication metadata
        cached_data['user_authenticated'] = user_authenticated
        
        return jsonify(cached_data)
        
    except Exception as e:
        logging.error(f"Facility API error in cached status: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

@facility_api_bp.route('/test-pushover', methods=['POST'])
@login_required
@email_verification_required
def test_pushover():
    """Send a test Pushover notification using user's credentials"""
    try:
        # Check if user has access to facility watcher
        if not current_user.has_app_access('facility_watcher'):
            return jsonify({
                "success": False,
                "error": "Access denied",
                "message": "You do not have permission to access the VATSIM Facility Watcher",
                "timestamp": datetime.now().isoformat()
            }), 403
        
        # Get user's OAK Tower Watcher settings
        oak_settings = current_user.get_service_settings('oak_tower_watcher')
        
        if not oak_settings:
            return jsonify({
                "success": False,
                "error": "User settings not found",
                "timestamp": datetime.now().isoformat()
            }), 404
        
        # Check if Pushover is configured
        if not current_user.pushover_api_token or not current_user.pushover_user_key:
            return jsonify({
                "success": False,
                "error": "Pushover credentials not configured",
                "message": "Please configure your Pushover API Token and User Key in General Settings first",
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
            api_token=current_user.pushover_api_token,
            user_key=current_user.pushover_user_key
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

@facility_api_bp.route('/test-status-notification', methods=['POST'])
@login_required
@email_verification_required
def test_status_notification():
    """Send a test notification with current status information to the current user only"""
    try:
        # Check if user has access to facility watcher
        if not current_user.has_app_access('facility_watcher'):
            return jsonify({
                "success": False,
                "error": "Access denied",
                "message": "You do not have permission to access the VATSIM Facility Watcher",
                "timestamp": datetime.now().isoformat()
            }), 403
        
        logging.info(f"Test status notification requested by user: {current_user.email}")
        
        # Get user's OAK Tower Watcher settings
        oak_settings = current_user.get_service_settings('oak_tower_watcher')
        
        if not oak_settings:
            return jsonify({
                "success": False,
                "error": "User settings not found",
                "message": "Please configure your OAK Tower Watcher settings first",
                "timestamp": datetime.now().isoformat()
            }), 404
        
        # Check if Pushover is configured
        if not current_user.pushover_api_token or not current_user.pushover_user_key:
            return jsonify({
                "success": False,
                "error": "Pushover credentials not configured",
                "message": "Please configure your Pushover API Token and User Key in General Settings first",
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
        
        # Get current status using user's configuration
        status_data = facility_status_service.get_current_status(user_id=current_user.id)
        
        if status_data.get('error'):
            return jsonify({
                "success": False,
                "error": "Failed to get current status",
                "message": f"Unable to retrieve status information: {status_data.get('error')}",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Create notification title and message based on current status
        current_status = status_data.get('status', '')
        main_controllers = status_data.get('main_controllers', [])
        supporting_above = status_data.get('supporting_above', [])
        supporting_below = status_data.get('supporting_below', [])
        using_user_config = status_data.get('using_user_config', False)
        
        # Ensure proper types for the shared function
        status_str = str(current_status) if current_status else 'unknown'
        main_list = main_controllers if isinstance(main_controllers, list) else []
        supporting_above_list = supporting_above if isinstance(supporting_above, list) else []
        supporting_below_list = supporting_below if isinstance(supporting_below, list) else []
        
        # Use shared notification formatting function
        notification_data = format_push_notification(
            current_status=status_str,
            main_controllers=main_list,
            supporting_above=supporting_above_list,
            supporting_below=supporting_below_list,
            include_priority_sound=True,
            is_test=True
        )
        
        title = notification_data['title']
        message = notification_data['message']
        priority = notification_data.get('priority', 0)
        sound = notification_data.get('sound', 'pushover')
        
        # Create Pushover service with user's credentials
        pushover_service = PushoverService(
            api_token=current_user.pushover_api_token,
            user_key=current_user.pushover_user_key
        )
        
        # Send notification
        result = pushover_service.send_notification(
            message=message,
            title=title,
            priority=priority,
            sound=sound
        )
        
        if result["success"]:
            logging.info(f"Test status notification sent successfully for user: {current_user.email} (status: {current_status})")
            return jsonify({
                "success": True,
                "message": "Test status notification sent successfully! Check your device.",
                "status": current_status,
                "using_user_config": using_user_config,
                "controllers": {
                    "main": len(main_controllers),
                    "supporting_above": len(supporting_above),
                    "supporting_below": len(supporting_below)
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            logging.error(f"Test status notification failed for user {current_user.email}: {result['error']}")
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "message": f"Failed to send test status notification: {result.get('error', 'Unknown error')}",
                "timestamp": datetime.now().isoformat()
            }), 400
    
    except Exception as e:
        logging.error(f"Error during test status notification for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred while sending the test status notification",
            "timestamp": datetime.now().isoformat()
        }), 500