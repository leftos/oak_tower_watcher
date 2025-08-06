from flask import Blueprint, jsonify
import logging
from datetime import datetime
from flask_login import login_required, current_user
import sys
import os

# Import shared components using new structure
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.pushover_service import PushoverService
from shared.bulk_notification_service import BulkNotificationService
from shared.utils import format_push_notification
from .status_service import status_api
from .security import email_verification_required

api_bp = Blueprint('api', __name__)

@api_bp.route('/status')
def get_status():
    """Get current VATSIM monitoring status"""
    try:
        # Check if user is authenticated to provide user-specific configuration
        user_id = None
        if current_user.is_authenticated:
            user_id = current_user.id
            logging.debug(f"Getting status for authenticated user: {current_user.email}")
        
        status_data = status_api.get_current_status(user_id=user_id)
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
@email_verification_required
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


@api_bp.route('/test-bulk-pushover', methods=['POST'])
@login_required
@email_verification_required
def test_bulk_pushover():
    """Test bulk Pushover notifications to all users with valid credentials"""
    try:
        logging.info(f"Bulk Pushover test requested by user: {current_user.email}")
        
        # Check if user has admin privileges (for now, any logged-in user can test)
        # In production, you might want to add role-based access control
        
        # Initialize bulk notification service
        bulk_service = BulkNotificationService()
        
        if not bulk_service.enabled:
            logging.warning("Bulk notification service not available")
            return jsonify({
                "success": False,
                "error": "Bulk notification service not available",
                "message": "Database connection or web modules not available for bulk notifications",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Send test notification to all users
        result = bulk_service.test_bulk_notification()
        
        if result["success"]:
            sent_count = result.get('sent_count', 0)
            failed_count = result.get('failed_count', 0)
            
            logging.info(f"Bulk Pushover test completed - Sent: {sent_count}, Failed: {failed_count}")
            
            message = f"Bulk test completed successfully!"
            if sent_count > 0:
                message += f" Sent to {sent_count} users."
            if failed_count > 0:
                message += f" Failed for {failed_count} users."
            if sent_count == 0 and failed_count == 0:
                message += " No users found with valid Pushover settings."
            
            return jsonify({
                "success": True,
                "message": message,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "details": result.get('details', []),
                "timestamp": datetime.now().isoformat()
            })
        else:
            logging.error(f"Bulk Pushover test failed: {result.get('error', 'Unknown error')}")
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "message": f"Failed to send bulk test notifications: {result.get('error', 'Unknown error')}",
                "timestamp": datetime.now().isoformat()
            }), 400

    except Exception as e:
        logging.error(f"Error in test_bulk_pushover: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred while testing bulk notifications",
            "timestamp": datetime.now().isoformat()
        }), 500


@api_bp.route('/bulk-notification-stats', methods=['GET'])
@login_required
@email_verification_required
def bulk_notification_stats():
    """Get statistics about users with valid Pushover settings"""
    try:
        logging.info(f"Bulk notification stats requested by user: {current_user.email}")
        
        # Initialize bulk notification service
        bulk_service = BulkNotificationService()
        
        if not bulk_service.enabled:
            return jsonify({
                "success": False,
                "error": "Bulk notification service not available",
                "message": "Database connection or web modules not available",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Get users with valid Pushover settings
        users = bulk_service.get_notification_users()
        
        # Anonymize user data for privacy
        user_stats = []
        for user in users:
            user_stats.append({
                "user_email": user['user_email'][:3] + "***@" + user['user_email'].split('@')[1] if '@' in user['user_email'] else "***",
                "service_name": user['service_name'],
                "has_api_token": bool(user.get('pushover_api_token')),
                "has_user_key": bool(user.get('pushover_user_key'))
            })
        
        return jsonify({
            "success": True,
            "message": f"Found {len(users)} users with valid Pushover settings",
            "total_users": len(users),
            "users": user_stats,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"Error in bulk_notification_stats: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred while getting stats",
            "timestamp": datetime.now().isoformat()
        }), 500


@api_bp.route('/test-personalized-bulk-notification', methods=['POST'])
@login_required
@email_verification_required
def test_personalized_bulk_notification():
    """Test personalized bulk notifications based on user configurations"""
    try:
        logging.info(f"Personalized bulk notification test requested by user: {current_user.email}")
        
        # Initialize bulk notification service
        bulk_service = BulkNotificationService()
        
        if not bulk_service.enabled:
            logging.warning("Bulk notification service not available")
            return jsonify({
                "success": False,
                "error": "Bulk notification service not available",
                "message": "Database connection or web modules not available for bulk notifications",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Send personalized test notifications to all users
        result = bulk_service.send_personalized_bulk_notification(
            status_change="test",
            priority=0,
            sound="pushover"
        )
        
        if result["success"]:
            sent_count = result.get('sent_count', 0)
            failed_count = result.get('failed_count', 0)
            details = result.get('details', [])
            
            logging.info(f"Personalized bulk notification test completed - Sent: {sent_count}, Failed: {failed_count}")
            
            message = f"Personalized test completed!"
            if sent_count > 0:
                message += f" Sent to {sent_count} users based on their custom configurations."
            if failed_count > 0:
                message += f" Failed for {failed_count} users."
            if sent_count == 0 and failed_count == 0:
                message += " No users found with valid Pushover settings."
            
            # Count configuration types
            custom_config_count = len([d for d in details if d.get('config_type') == 'custom'])
            default_config_count = len([d for d in details if d.get('config_type') == 'default'])
            
            return jsonify({
                "success": True,
                "message": message,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "custom_config_users": custom_config_count,
                "default_config_users": default_config_count,
                "details": details,
                "timestamp": datetime.now().isoformat()
            })
        else:
            logging.error(f"Personalized bulk notification test failed: {result.get('error', 'Unknown error')}")
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error"),
                "message": f"Failed to send personalized test notifications: {result.get('error', 'Unknown error')}",
                "timestamp": datetime.now().isoformat()
            }), 400

    except Exception as e:
        logging.error(f"Error in test_personalized_bulk_notification: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred while testing personalized notifications",
            "timestamp": datetime.now().isoformat()
        }), 500


@api_bp.route('/test-status-notification', methods=['POST'])
@login_required
@email_verification_required
def test_status_notification():
    """Send a test notification with current status information to the current user only"""
    try:
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
        
        # Get current status using user's configuration
        status_data = status_api.get_current_status(user_id=current_user.id)
        
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
            api_token=oak_settings.pushover_api_token,
            user_key=oak_settings.pushover_user_key
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