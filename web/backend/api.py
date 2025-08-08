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
# Facility status service moved to facility_monitor module
from .security import email_verification_required, require_admin_api
from .web_monitoring_service import web_monitoring_service

api_bp = Blueprint('api', __name__)

# Facility status endpoints moved to facility_monitor/api.py

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
        # Import config dynamically to avoid import issues
        from config.config import load_config
        config = load_config()
        
        return jsonify({
            "service_name": "OAK Tower Watcher",
            "check_interval": config.get("monitoring", {}).get("check_interval", 30),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Config API error: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500

# Facility-specific test endpoints moved to facility_monitor/api.py


@api_bp.route('/test-bulk-pushover', methods=['POST'])
@require_admin_api()
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
@require_admin_api()
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
@require_admin_api()
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


# Test status notification endpoint moved to facility_monitor/api.py


@api_bp.route('/web-monitor/status', methods=['GET'])
@require_admin_api()
def web_monitor_status():
    """Get web monitoring service status"""
    try:
        logging.info(f"Web monitor status requested by user: {current_user.email}")
        
        # Get monitoring service status
        is_running = web_monitoring_service.is_running()
        db_enabled = web_monitoring_service.db_interface.enabled
        
        # Get comprehensive cache info
        cached_data = web_monitoring_service.get_cached_status()
        total_controllers = 0
        cache_age_seconds = 0
        last_updated = None
        
        if cached_data:
            total_controllers = cached_data.get('total_controllers', 0)
            cache_age_seconds = cached_data.get('cache_age_seconds', 0)
            last_updated = cached_data.get('last_updated')
        
        # Get aggregated patterns info (for backwards compatibility and notifications)
        aggregated_config = web_monitoring_service.get_aggregated_config()
        pattern_counts = {}
        total_patterns = 0
        
        if aggregated_config:
            callsigns = aggregated_config.get('callsigns', {})
            for pattern_type in ['main_facility', 'supporting_above', 'supporting_below']:
                count = len(callsigns.get(pattern_type, []))
                pattern_counts[pattern_type] = count
                total_patterns += count
        
        return jsonify({
            "success": True,
            "monitoring_service": {
                "running": is_running,
                "database_enabled": db_enabled,
                "check_interval": web_monitoring_service.check_interval,
                "previous_status": web_monitoring_service.previous_status,
                "using_comprehensive_cache": True
            },
            "comprehensive_monitoring": {
                "total_controllers_cached": total_controllers,
                "cache_age_seconds": cache_age_seconds,
                "last_updated": last_updated
            },
            "legacy_facility_monitoring": {
                "total_patterns": total_patterns,
                "pattern_counts": pattern_counts,
                "using_aggregated_config": aggregated_config is not None
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting web monitor status: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred while getting monitor status",
            "timestamp": datetime.now().isoformat()
        }), 500


@api_bp.route('/web-monitor/force-check', methods=['POST'])
@require_admin_api()
def web_monitor_force_check():
    """Force immediate comprehensive status check with web monitoring service"""
    try:
        logging.info(f"Web monitor comprehensive force check requested by user: {current_user.email}")
        
        if not web_monitoring_service.is_running():
            return jsonify({
                "success": False,
                "error": "Monitoring service not running",
                "message": "Web monitoring service is not currently running",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Force immediate comprehensive check
        web_monitoring_service.force_check()
        
        # Get the result of the check
        cached_data = web_monitoring_service.get_cached_status()
        total_controllers = cached_data.get('total_controllers', 0) if cached_data else 0
        
        return jsonify({
            "success": True,
            "message": f"Comprehensive force check completed - collected {total_controllers} controllers, notifications sent to users based on their individual patterns",
            "total_controllers": total_controllers,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error during web monitor force check: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred during force check",
            "timestamp": datetime.now().isoformat()
        }), 500


@api_bp.route('/web-monitor/restart', methods=['POST'])
@require_admin_api()
def web_monitor_restart():
    """Restart the web monitoring service"""
    try:
        logging.info(f"Web monitor restart requested by user: {current_user.email}")
        
        # Stop if running
        if web_monitoring_service.is_running():
            web_monitoring_service.stop()
            # Give it a moment to stop
            import time
            time.sleep(1)
        
        # Start the service
        web_monitoring_service.start()
        
        return jsonify({
            "success": True,
            "message": "Web monitoring service restarted successfully",
            "running": web_monitoring_service.is_running(),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error restarting web monitor: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred during restart",
            "timestamp": datetime.now().isoformat()
        }), 500