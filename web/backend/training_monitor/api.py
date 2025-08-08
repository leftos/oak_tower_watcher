#!/usr/bin/env python3
"""
Training Session Monitor API endpoints
"""

from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
from flask_login import login_required, current_user
from typing import Dict, List, Any, Optional

from ..security import email_verification_required
from .models import (
    TrainingSessionSettings, TrainingMonitoredRating, TrainingSessionCache,
    GlobalTrainingSessionCache, TrainingSessionNotificationLog, get_available_rating_patterns
)
from .service import training_monitoring_service
from .scraper import TrainingSessionScraper
from ..models import db

# Configure logger
logger = logging.getLogger(__name__)

training_api_bp = Blueprint('training_api', __name__)

@training_api_bp.route('/status')
def get_training_status():
    """Get current training session monitoring status"""
    try:
        user_authenticated = False
        user_settings = None
        
        # Check if user is authenticated and get their settings
        if current_user.is_authenticated:
            user_authenticated = True
            logger.debug(f"Getting training status for authenticated user: {current_user.email}")
            
            # Get user's training session settings
            user_settings = TrainingSessionSettings.query.filter_by(
                user_id=current_user.id,
                service_name='oak_training_monitor'
            ).first()
        
        # Get service status from monitoring service
        service_status = training_monitoring_service.get_cached_status()
        
        if not service_status:
            # Service hasn't run yet
            service_status = {
                'training_monitoring': {
                    'success': False,
                    'error': 'Training monitoring service has not run yet',
                    'total_users': 0,
                    'total_notifications_sent': 0
                },
                'service_info': {
                    'running': training_monitoring_service.is_running(),
                    'check_interval_hours': training_monitoring_service.check_interval // 3600,
                    'last_check': None
                }
            }
        
        # Add user-specific information
        user_info = {
            'authenticated': user_authenticated,
            'settings_configured': user_settings is not None,
            'notifications_enabled': user_settings.notifications_enabled if user_settings else False,
            'session_key_configured': bool(user_settings and user_settings.php_session_key) if user_settings else False,
            'monitored_ratings': user_settings.get_monitored_ratings() if user_settings else []
        }
        
        # Get user's cached sessions if available (filtered by their monitored ratings)
        user_sessions = []
        if user_settings:
            try:
                cache = TrainingSessionCache.query.filter_by(settings_id=user_settings.id).first()
                if cache and cache.fetch_successful:
                    monitored_ratings = user_settings.get_monitored_ratings()
                    user_sessions = cache.get_filtered_sessions(monitored_ratings)
            except Exception as cache_error:
                logger.error(f"Error getting user sessions for status: {cache_error}")
        
        response_data = {
            'service_status': service_status,
            'user_info': user_info,
            'user_sessions': user_sessions,
            'available_ratings': get_available_rating_patterns(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Training API error: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "An error occurred while getting training status",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/settings', methods=['GET'])
@login_required
@email_verification_required
def get_training_settings():
    """Get user's training session monitoring settings"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        logger.info(f"Getting training settings for user: {current_user.email}")
        
        # Get or create user settings
        settings = TrainingSessionSettings.query.filter_by(
            user_id=current_user.id,
            service_name='oak_training_monitor'
        ).first()
        
        if not settings:
            # Create default settings
            settings = TrainingSessionSettings()
            settings.user_id = current_user.id
            settings.service_name = 'oak_training_monitor'
            settings.notifications_enabled = True
            
            db.session.add(settings)
            db.session.commit()
            
            logger.info(f"Created default training settings for user: {current_user.email}")
        
        # Get monitored ratings
        monitored_ratings = settings.get_monitored_ratings()
        
        settings_data = {
            'notifications_enabled': settings.notifications_enabled,
            'php_session_key_configured': bool(settings.php_session_key),
            'session_key_last_validated': settings.session_key_last_validated.isoformat() if settings.session_key_last_validated else None,
            'monitored_ratings': monitored_ratings,
            'available_ratings': get_available_rating_patterns(),
            'created_at': settings.created_at.isoformat(),
            'updated_at': settings.updated_at.isoformat()
        }
        
        return jsonify({
            'success': True,
            'settings': settings_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting training settings for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while getting training settings',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/settings', methods=['POST'])
@login_required
@email_verification_required
def update_training_settings():
    """Update user's training session monitoring settings"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        logger.info(f"Updating training settings for user: {current_user.email}")
        
        # Get or create user settings
        settings = TrainingSessionSettings.query.filter_by(
            user_id=current_user.id,
            service_name='oak_training_monitor'
        ).first()
        
        if not settings:
            settings = TrainingSessionSettings()
            settings.user_id = current_user.id
            settings.service_name = 'oak_training_monitor'
            db.session.add(settings)
        
        # Update settings
        if 'notifications_enabled' in data:
            settings.notifications_enabled = bool(data['notifications_enabled'])
        
        if 'php_session_key' in data:
            new_session_key = data['php_session_key'].strip() if data['php_session_key'] else None
            
            if new_session_key and new_session_key != settings.php_session_key:
                # New session key provided, reset validation timestamp
                settings.php_session_key = new_session_key
                settings.session_key_last_validated = None
                logger.info(f"Updated PHP session key for user: {current_user.email}")
            elif not new_session_key:
                # Remove session key
                settings.php_session_key = None
                settings.session_key_last_validated = None
        
        if 'monitored_ratings' in data:
            monitored_ratings = data['monitored_ratings']
            
            if not isinstance(monitored_ratings, list):
                return jsonify({
                    'success': False,
                    'error': 'Monitored ratings must be a list',
                    'timestamp': datetime.utcnow().isoformat()
                }), 400
            
            # Validate rating patterns
            available_ratings = get_available_rating_patterns()
            invalid_ratings = [r for r in monitored_ratings if r not in available_ratings]
            
            if invalid_ratings:
                return jsonify({
                    'success': False,
                    'error': f'Invalid rating patterns: {invalid_ratings}',
                    'available_ratings': available_ratings,
                    'timestamp': datetime.utcnow().isoformat()
                }), 400
            
            # Update monitored ratings
            old_ratings = settings.get_monitored_ratings()
            settings.set_monitored_ratings(monitored_ratings)
            
            # Log if ratings changed and trigger immediate re-filtering
            if set(old_ratings) != set(monitored_ratings):
                logger.info(f"Monitored ratings changed for user {current_user.email}: {old_ratings} -> {monitored_ratings}")
                
                # Trigger re-filtering from global cache since ratings changed
                try:
                    training_monitoring_service.process_user_from_global_cache(settings)
                    logger.debug(f"Re-filtered training sessions for user {current_user.email} after rating change")
                except Exception as refilter_error:
                    logger.warning(f"Could not re-filter sessions after rating change for user {current_user.email}: {refilter_error}")
        
        # Save settings
        db.session.commit()
        logger.info(f"Successfully updated training settings for user: {current_user.email}")
        
        return jsonify({
            'success': True,
            'message': 'Training settings updated successfully. Status page will immediately reflect rating filter changes.',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error updating training settings for user {current_user.email}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while updating training settings',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/test-session-key', methods=['POST'])
@login_required
@email_verification_required
def test_session_key():
    """Test user's PHP session key"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        data = request.get_json()
        if not data or 'php_session_key' not in data:
            return jsonify({
                'success': False,
                'error': 'PHP session key is required',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        session_key = data['php_session_key'].strip()
        if not session_key:
            return jsonify({
                'success': False,
                'error': 'PHP session key cannot be empty',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        logger.info(f"Testing PHP session key for user: {current_user.email}")
        
        # Test the session key (this validates user authorization only)
        scraper = TrainingSessionScraper()
        validation_result = scraper.validate_session_key(session_key)
        
        if validation_result['valid']:
            # Update user settings if they have them
            settings = TrainingSessionSettings.query.filter_by(
                user_id=current_user.id,
                service_name='oak_training_monitor'
            ).first()
            
            if settings:
                settings.php_session_key = session_key
                settings.mark_session_key_validated()
                db.session.commit()
            
            logger.info(f"PHP session key test successful for user: {current_user.email}")
            
            return jsonify({
                'success': True,
                'valid': True,
                'message': validation_result['message'],
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            logger.warning(f"PHP session key test failed for user {current_user.email}: {validation_result['message']}")
            
            return jsonify({
                'success': True,
                'valid': False,
                'message': validation_result['message'],
                'timestamp': datetime.utcnow().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error testing session key for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while testing session key',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/sessions')
@login_required
@email_verification_required
def get_user_sessions():
    """Get user's cached training sessions"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        logger.debug(f"Getting training sessions for user: {current_user.email}")
        
        # Get user settings
        settings = TrainingSessionSettings.query.filter_by(
            user_id=current_user.id,
            service_name='oak_training_monitor'
        ).first()
        
        if not settings:
            return jsonify({
                'success': True,
                'sessions': [],
                'message': 'No training settings configured',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Get cached sessions filtered by user's monitored ratings
        cache = TrainingSessionCache.query.filter_by(settings_id=settings.id).first()
        
        if not cache:
            return jsonify({
                'success': True,
                'sessions': [],
                'message': 'No sessions cached yet',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Get sessions filtered by current monitored ratings
        monitored_ratings = settings.get_monitored_ratings()
        sessions = cache.get_filtered_sessions(monitored_ratings)
        
        response_data = {
            'success': True,
            'sessions': sessions,
            'cache_info': {
                'last_fetched': cache.last_fetched_at.isoformat(),
                'fetch_successful': cache.fetch_successful,
                'error_message': cache.error_message,
                'is_stale': cache.is_cache_stale()
            },
            'monitored_ratings': settings.get_monitored_ratings(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting sessions for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while getting training sessions',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/refresh-sessions', methods=['POST'])
@login_required
@email_verification_required
def refresh_sessions():
    """Force refresh of user's training sessions"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        logger.info(f"Manual session refresh requested by user: {current_user.email}")
        
        # Get user settings
        settings = TrainingSessionSettings.query.filter_by(
            user_id=current_user.id,
            service_name='oak_training_monitor'
        ).first()
        
        if not settings:
            return jsonify({
                'success': False,
                'error': 'No training settings configured',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        if not settings.php_session_key:
            return jsonify({
                'success': False,
                'error': 'No PHP session key configured',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        # Process user by filtering from global cache (more efficient)
        result = training_monitoring_service.process_user_from_global_cache(settings)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Sessions refreshed successfully',
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
    except Exception as e:
        logger.error(f"Error refreshing sessions for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while refreshing sessions',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@training_api_bp.route('/notification-history')
@login_required
@email_verification_required
def get_notification_history():
    """Get user's training session notification history"""
    try:
        # Check if user has access to training monitor
        if not current_user.has_app_access('training_monitor'):
            return jsonify({
                'success': False,
                'error': 'Access denied',
                'message': 'You do not have permission to access the OAK ARTCC Training Session Monitor',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        logger.debug(f"Getting notification history for user: {current_user.email}")
        
        # Get user settings
        settings = TrainingSessionSettings.query.filter_by(
            user_id=current_user.id,
            service_name='oak_training_monitor'
        ).first()
        
        if not settings:
            return jsonify({
                'success': True,
                'notifications': [],
                'message': 'No training settings configured',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Get notification history (last 50 notifications)
        notifications = TrainingSessionNotificationLog.query.filter_by(
            settings_id=settings.id
        ).order_by(TrainingSessionNotificationLog.notification_sent_at.desc()).limit(50).all()
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'student_name': notification.student_name,
                'instructor_name': notification.instructor_name,
                'module_name': notification.module_name,
                'session_date': notification.session_date,
                'session_time': notification.session_time,
                'matching_rating': notification.matching_rating,
                'notification_type': notification.notification_type,
                'notification_sent_at': notification.notification_sent_at.isoformat(),
                'created_at': notification.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'notifications': notification_data,
            'total_count': len(notification_data),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting notification history for user {current_user.email}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An error occurred while getting notification history',
            'timestamp': datetime.utcnow().isoformat()
        }), 500