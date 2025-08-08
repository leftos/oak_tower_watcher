#!/usr/bin/env python3
"""
Training Session Monitoring Service
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import hashlib

# Import shared components  
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.base_monitoring_service import BaseMonitoringService
from shared.pushover_service import PushoverService
from .scraper import TrainingSessionScraper
from .models import (
    TrainingSessionSettings, TrainingSessionCache, 
    TrainingSessionNotificationLog, get_available_rating_patterns
)
from ..models import db, User

# Configure logger
logger = logging.getLogger(__name__)

class TrainingMonitoringService(BaseMonitoringService):
    """
    Training session monitoring service for OAK ARTCC
    Runs hourly checks for new training sessions matching user preferences
    """
    
    def __init__(self):
        # Initialize with 1-hour check interval (3600 seconds)
        super().__init__()
        self.check_interval = 3600  # 1 hour
        
        # Training-specific components
        self.scraper = TrainingSessionScraper()
        self._cached_status = None
        self._cache_lock = threading.Lock()
        self.last_cache_update = None
        
        logger.info("Training monitoring service initialized")
    
    def check_status(self) -> Dict[str, Any]:
        """Check training session status (implements abstract method)"""
        return self.check_all_users_training_sessions()
    
    def on_status_changed(self, current_result: Dict[str, Any]):
        """Handle status changes by sending notifications (implements abstract method)"""
        # Training notifications are handled within check_all_users_training_sessions
        pass
    
    def on_status_updated(self, current_result: Dict[str, Any]):
        """Update cache on every status check (overrides base method)"""
        self.update_cached_status(current_result)
    
    def has_status_changed(self, current_result: Dict[str, Any]) -> bool:
        """
        Always trigger processing for training session checks
        Individual user notifications are handled based on new session detection
        
        Args:
            current_result: Current training check result
            
        Returns:
            True if check was successful, False otherwise
        """
        return current_result.get('success', False)
    
    def update_previous_status(self, current_result: Dict[str, Any]):
        """
        Update stored previous status for training monitoring
        
        Args:
            current_result: Current training check result
        """
        if current_result.get('success'):
            total_users = current_result.get('total_users', 0)
            total_notifications = current_result.get('total_notifications_sent', 0)
            self.previous_status = f"training_monitoring_{total_users}_users_{total_notifications}_notifications"
            # Clear controller lists since we don't use them for training monitoring
            self.previous_controllers = {
                'main': [],
                'supporting_above': [], 
                'supporting_below': []
            }
    
    def check_all_users_training_sessions(self) -> Dict[str, Any]:
        """
        Check training sessions for all users with configured settings
        
        Returns:
            Dict with overall check results and statistics
        """
        try:
            logger.info("Starting training session check for all users")
            
            # Get all users with training session settings
            try:
                users_settings = TrainingSessionSettings.query.join(User).filter(
                    TrainingSessionSettings.notifications_enabled == True,
                    TrainingSessionSettings.php_session_key.isnot(None),
                    User.is_active == True,
                    User.email_verified == True,
                    User.is_banned != True
                ).all()
            except Exception as db_error:
                logger.error(f"Database error getting user settings: {db_error}")
                return {
                    'success': False,
                    'error': f'Database error: {str(db_error)}',
                    'timestamp': datetime.utcnow().isoformat(),
                    'total_users': 0,
                    'total_notifications_sent': 0
                }
            
            if not users_settings:
                logger.info("No users found with training session monitoring configured")
                return {
                    'success': True,
                    'message': 'No users configured for training session monitoring',
                    'timestamp': datetime.utcnow().isoformat(),
                    'total_users': 0,
                    'total_notifications_sent': 0
                }
            
            logger.info(f"Found {len(users_settings)} users with training session monitoring enabled")
            
            # Process each user's training session monitoring
            total_notifications_sent = 0
            user_results = []
            
            for user_settings in users_settings:
                try:
                    user_result = self.process_user_training_sessions(user_settings)
                    user_results.append(user_result)
                    
                    if user_result.get('notifications_sent', 0) > 0:
                        total_notifications_sent += user_result['notifications_sent']
                        
                except Exception as user_error:
                    logger.error(f"Error processing user {user_settings.user_id}: {user_error}", exc_info=True)
                    user_results.append({
                        'user_id': user_settings.user_id,
                        'success': False,
                        'error': str(user_error),
                        'notifications_sent': 0
                    })
            
            logger.info(f"Training session check completed: {len(users_settings)} users processed, {total_notifications_sent} notifications sent")
            
            return {
                'success': True,
                'message': f'Training session check completed for {len(users_settings)} users',
                'timestamp': datetime.utcnow().isoformat(),
                'total_users': len(users_settings),
                'total_notifications_sent': total_notifications_sent,
                'user_results': user_results
            }
            
        except Exception as e:
            logger.error(f"Error in training session check: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
                'total_users': 0,
                'total_notifications_sent': 0
            }
    
    def process_user_training_sessions(self, user_settings: TrainingSessionSettings) -> Dict[str, Any]:
        """
        Process training session monitoring for a specific user
        
        Args:
            user_settings: User's training session settings
            
        Returns:
            Dict with user processing results
        """
        try:
            user_id = user_settings.user_id
            logger.debug(f"Processing training sessions for user {user_id}")
            
            # Validate session key if needed (weekly check)
            if user_settings.is_session_key_expired():
                logger.info(f"Validating expired session key for user {user_id}")
                validation_result = self.scraper.validate_session_key(user_settings.php_session_key)
                
                if validation_result['valid']:
                    user_settings.mark_session_key_validated()
                    logger.debug(f"Session key validated for user {user_id}")
                else:
                    # Send session key expiration notification
                    self.send_session_key_expired_notification(user_settings, validation_result['message'])
                    
                    return {
                        'user_id': user_id,
                        'success': False,
                        'error': 'Session key expired or invalid',
                        'notifications_sent': 1  # Expiration notification
                    }
            
            # Get user's monitored ratings
            monitored_ratings = user_settings.get_monitored_ratings()
            
            if not monitored_ratings:
                logger.debug(f"No monitored ratings configured for user {user_id}")
                return {
                    'user_id': user_id,
                    'success': True,
                    'message': 'No monitored ratings configured',
                    'notifications_sent': 0
                }
            
            # Scrape training sessions
            scrape_result = self.scraper.scrape_training_sessions(user_settings.php_session_key)
            
            if not scrape_result['success']:
                logger.error(f"Failed to scrape training sessions for user {user_id}: {scrape_result['error']}")
                
                # Update cache with error
                self.update_user_cache(user_settings, [], error_message=scrape_result['error'])
                
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': scrape_result['error'],
                    'notifications_sent': 0
                }
            
            all_sessions = scrape_result['sessions']
            
            # Store ALL sessions in cache (not just filtered) for immediate re-filtering capability
            self.update_user_cache(user_settings, all_sessions)
            
            # Filter sessions by monitored ratings
            filtered_sessions = self.scraper.filter_sessions_by_ratings(all_sessions, monitored_ratings)
            
            # Get cached filtered sessions for comparison (using previous monitored ratings)
            cached_sessions = self.get_user_cached_sessions(user_settings, monitored_ratings)
            
            # Detect new sessions in filtered data
            new_sessions = self.scraper.detect_new_sessions(filtered_sessions, cached_sessions)
            
            # Send notifications for new sessions
            notifications_sent = 0
            for session in new_sessions:
                try:
                    if self.send_new_session_notification(user_settings, session):
                        notifications_sent += 1
                except Exception as notification_error:
                    logger.error(f"Error sending notification for user {user_id}: {notification_error}")
            
            logger.debug(f"User {user_id}: {len(all_sessions)} total sessions, {len(filtered_sessions)} filtered, {len(new_sessions)} new, {notifications_sent} notifications sent")
            
            return {
                'user_id': user_id,
                'success': True,
                'total_sessions': len(all_sessions),
                'filtered_sessions': len(filtered_sessions),
                'new_sessions': len(new_sessions),
                'notifications_sent': notifications_sent
            }
            
        except Exception as e:
            logger.error(f"Error processing user {user_settings.user_id}: {e}", exc_info=True)
            return {
                'user_id': user_settings.user_id,
                'success': False,
                'error': str(e),
                'notifications_sent': 0
            }
    
    def get_user_cached_sessions(self, user_settings: TrainingSessionSettings, rating_patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get cached training sessions for a user, optionally filtered by rating patterns
        
        Args:
            user_settings: User's training session settings
            rating_patterns: Optional rating patterns to filter by. If None, uses user's current monitored ratings
        """
        try:
            cache = TrainingSessionCache.query.filter_by(settings_id=user_settings.id).first()
            
            if cache and cache.fetch_successful:
                if rating_patterns is None:
                    rating_patterns = user_settings.get_monitored_ratings()
                
                # Use filtered retrieval for immediate rating filter updates
                return cache.get_filtered_sessions(rating_patterns)
                
            return []
            
        except Exception as e:
            logger.error(f"Error getting cached sessions for user {user_settings.user_id}: {e}")
            return []
    
    def update_user_cache(self, user_settings: TrainingSessionSettings, sessions: List[Dict[str, Any]], error_message: Optional[str] = None):
        """Update cached training sessions for a user"""
        try:
            cache = TrainingSessionCache.query.filter_by(settings_id=user_settings.id).first()
            
            if not cache:
                cache = TrainingSessionCache()
                cache.settings_id = user_settings.id
                db.session.add(cache)
            
            if error_message:
                cache.set_fetch_error(error_message)
            else:
                cache.set_sessions(sessions)
            
            db.session.commit()
            logger.debug(f"Updated cache for user {user_settings.user_id}")
            
        except Exception as e:
            logger.error(f"Error updating cache for user {user_settings.user_id}: {e}")
            db.session.rollback()
    
    def send_new_session_notification(self, user_settings: TrainingSessionSettings, session: Dict[str, Any]) -> bool:
        """
        Send notification for a new training session
        
        Args:
            user_settings: User settings
            session: Training session data
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Check if we already sent a notification for this session
            session_hash = session['session_hash']
            existing_notification = TrainingSessionNotificationLog.query.filter_by(
                settings_id=user_settings.id,
                session_hash=session_hash,
                notification_type='new_session'
            ).first()
            
            if existing_notification:
                logger.debug(f"Notification already sent for session {session_hash}")
                return False
            
            # Get user for pushover credentials
            user = User.query.get(user_settings.user_id)
            if not user:
                logger.error(f"User {user_settings.user_id} not found")
                return False
            
            # Get user's general pushover settings
            if not user.pushover_api_token or not user.pushover_user_key:
                logger.warning(f"No pushover credentials configured for user {user_settings.user_id}")
                return False
            
            # Format notification message
            title = f"🎓 New Training Session: {session['rating_pattern']}"
            
            message = f"Student: {session['student_name']}"
            if session.get('student_rating'):
                message += f" ({session['student_rating']})"
            
            message += f"\nInstructor: {session['instructor_name']}"
            message += f"\nModule: {session['module_name']}"
            message += f"\nDate: {session['session_date']}"
            message += f"\nTime: {session['session_time']}"
            
            # Send pushover notification
            pushover_service = PushoverService(
                api_token=user.pushover_api_token,
                user_key=user.pushover_user_key
            )
            
            result = pushover_service.send_notification(
                message=message,
                title=title,
                priority=0,
                sound='pushover'
            )
            
            if result['success']:
                # Log the notification
                notification_log = TrainingSessionNotificationLog()
                notification_log.settings_id = user_settings.id
                notification_log.session_hash = session_hash
                notification_log.student_name = session['student_name']
                notification_log.instructor_name = session['instructor_name']
                notification_log.module_name = session['module_name']
                notification_log.session_date = session['session_date']
                notification_log.session_time = session['session_time']
                notification_log.matching_rating = session['rating_pattern']
                notification_log.notification_type = 'new_session'
                
                db.session.add(notification_log)
                db.session.commit()
                
                logger.info(f"Sent training session notification to user {user_settings.user_id} for {session['rating_pattern']}")
                return True
            else:
                logger.error(f"Failed to send notification to user {user_settings.user_id}: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification to user {user_settings.user_id}: {e}", exc_info=True)
            return False
    
    def send_session_key_expired_notification(self, user_settings: TrainingSessionSettings, error_message: str):
        """Send notification when session key expires"""
        try:
            # Check if we already sent an expiration notification recently (within 24 hours)
            day_ago = datetime.utcnow() - timedelta(days=1)
            recent_notification = TrainingSessionNotificationLog.query.filter(
                TrainingSessionNotificationLog.settings_id == user_settings.id,
                TrainingSessionNotificationLog.notification_type == 'session_key_expired',
                TrainingSessionNotificationLog.notification_sent_at > day_ago
            ).first()
            
            if recent_notification:
                logger.debug(f"Session key expiration notification already sent recently for user {user_settings.user_id}")
                return
            
            # Get user for pushover credentials
            user = User.query.get(user_settings.user_id)
            if not user:
                return
            
            # Get user's pushover settings
            if not user.pushover_api_token or not user.pushover_user_key:
                return
            
            # Send notification
            title = "⚠️ OAK ARTCC Session Key Expired"
            message = f"Your OAK ARTCC training session monitoring has stopped working.\n\nError: {error_message}\n\nPlease update your PHP session key in the training monitor settings."
            
            pushover_service = PushoverService(
                api_token=user.pushover_api_token,
                user_key=user.pushover_user_key
            )
            
            result = pushover_service.send_notification(
                message=message,
                title=title,
                priority=1,  # High priority for expired session
                sound='siren'
            )
            
            if result['success']:
                # Log the notification
                notification_log = TrainingSessionNotificationLog()
                notification_log.settings_id = user_settings.id
                notification_log.session_hash = 'session_key_expired'
                notification_log.notification_type = 'session_key_expired'
                
                db.session.add(notification_log)
                db.session.commit()
                
                logger.info(f"Sent session key expiration notification to user {user_settings.user_id}")
                
        except Exception as e:
            logger.error(f"Error sending session key expiration notification: {e}", exc_info=True)
    
    def update_cached_status(self, status_result: Dict[str, Any]):
        """Update cached status data for UI consumption"""
        try:
            with self._cache_lock:
                self._cached_status = {
                    'training_monitoring': {
                        'success': status_result.get('success', False),
                        'timestamp': status_result.get('timestamp'),
                        'total_users': status_result.get('total_users', 0),
                        'total_notifications_sent': status_result.get('total_notifications_sent', 0),
                        'error': status_result.get('error')
                    },
                    'service_info': {
                        'running': self.is_running(),
                        'check_interval_hours': self.check_interval // 3600,
                        'last_check': status_result.get('timestamp')
                    }
                }
                self.last_cache_update = datetime.utcnow()
                
                logger.debug(f"Updated training monitoring cache: {status_result.get('total_users', 0)} users, {status_result.get('total_notifications_sent', 0)} notifications")
                
        except Exception as e:
            logger.error(f"Error updating cached status: {e}")
    
    def get_cached_status(self) -> Optional[Dict[str, Any]]:
        """Get cached training monitoring status"""
        try:
            with self._cache_lock:
                if self._cached_status is None:
                    return None
                
                cached_data: Dict[str, Any] = self._cached_status.copy()
                if self.last_cache_update:
                    cache_age = datetime.utcnow() - self.last_cache_update
                    cached_data['cache_age_seconds'] = int(cache_age.total_seconds())
                    cached_data['last_updated'] = self.last_cache_update.isoformat()
                
                return cached_data
                
        except Exception as e:
            logger.error(f"Error getting cached status: {e}")
            return None
    
    def start(self):
        """Start the training monitoring service"""
        super().start()
        logger.info("Training monitoring service started successfully (hourly checks)")
    
    def force_check(self):
        """Force an immediate training session check"""
        if not self.is_running():
            logger.warning("Cannot force check - training monitoring service not running")
            return
        
        logger.info("Forcing immediate training session check...")
        try:
            super().force_check()
            logger.info("Force check completed successfully")
        except Exception as e:
            logger.error(f"Error during force check: {e}")


# Global training monitoring service instance
training_monitoring_service = TrainingMonitoringService()