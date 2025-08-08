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
    TrainingSessionSettings, TrainingSessionCache, GlobalTrainingSessionCache,
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
    
    def __init__(self, app=None):
        # Initialize with 1-hour check interval (3600 seconds)
        super().__init__()
        self.check_interval = 3600  # 1 hour
        self.app = app  # Store Flask app instance for context
        
        # Training-specific components
        self.scraper = TrainingSessionScraper()
        self._cached_status = None
        self._cache_lock = threading.Lock()
        self.last_cache_update = None
        
        logger.info("Training monitoring service initialized")
    
    def set_app(self, app):
        """Set Flask app instance for context"""
        self.app = app
    
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
        Check training sessions using centralized scraping approach:
        1. Scrape all sessions once using service key
        2. Store in global cache
        3. For each user, filter global cache by their monitored ratings
        4. Compare with their previous filtered cache and send notifications
        
        Returns:
            Dict with overall check results and statistics
        """
        if not self.app:
            logger.error("Flask app not set - cannot access database")
            return {
                'success': False,
                'error': 'Flask app not configured',
                'timestamp': datetime.utcnow().isoformat(),
                'total_users': 0,
                'total_notifications_sent': 0
            }
        
        with self.app.app_context():
            try:
                logger.info("Starting centralized training session check")
                
                # Step 1: Perform global scraping using service session key
                global_scrape_result = self.perform_global_training_scrape()
                
                if not global_scrape_result['success']:
                    logger.error(f"Global training scrape failed: {global_scrape_result['error']}")
                    return {
                        'success': False,
                        'error': f"Global scrape failed: {global_scrape_result['error']}",
                        'timestamp': datetime.utcnow().isoformat(),
                        'total_users': 0,
                        'total_notifications_sent': 0
                    }
                
                # Step 2: Get all users with training session settings
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
                        'message': 'No users configured for training session monitoring - global scrape completed',
                        'timestamp': datetime.utcnow().isoformat(),
                        'total_users': 0,
                        'total_notifications_sent': 0,
                        'total_sessions_scraped': global_scrape_result.get('total_sessions', 0)
                    }
                
                logger.info(f"Found {len(users_settings)} users with training session monitoring enabled")
                
                # Step 3: Process each user by filtering global cache
                total_notifications_sent = 0
                user_results = []
                
                for user_settings in users_settings:
                    try:
                        user_result = self.process_user_from_global_cache(user_settings)
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
                
                logger.info(f"Training session check completed: {global_scrape_result.get('total_sessions', 0)} sessions scraped, {len(users_settings)} users processed, {total_notifications_sent} notifications sent")
                
                return {
                    'success': True,
                    'message': f'Training session check completed for {len(users_settings)} users',
                    'timestamp': datetime.utcnow().isoformat(),
                    'total_users': len(users_settings),
                    'total_notifications_sent': total_notifications_sent,
                    'total_sessions_scraped': global_scrape_result.get('total_sessions', 0),
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
    
    def perform_global_training_scrape(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Perform global scraping of training sessions using service session key
        Store results in global cache for all users to filter from
        
        NOTE: This method is called from within an app context, so no additional context needed
        
        Args:
            force_refresh: If True, bypass cache staleness check and force a fresh scrape
        
        Returns:
            Dict with scrape results
        """
        try:
            logger.info(f"Starting global training session scrape (force_refresh={force_refresh})")
            
            # Check if service has a session key configured
            if not self.scraper.has_service_session_key():
                logger.error("No service-level PHP session key configured")
                return {
                    'success': False,
                    'error': 'No service-level PHP session key configured',
                    'total_sessions': 0
                }
            
            # Get or create global cache entry
            global_cache = GlobalTrainingSessionCache.query.first()
            if not global_cache:
                global_cache = GlobalTrainingSessionCache()
                db.session.add(global_cache)
            
            # Check if cache is still fresh (unless forcing refresh)
            if not force_refresh and not global_cache.is_cache_stale():
                logger.debug("Global cache is still fresh, skipping scrape")
                sessions = global_cache.get_all_sessions()
                return {
                    'success': True,
                    'message': 'Using fresh global cache',
                    'total_sessions': len(sessions),
                    'cache_age_minutes': (datetime.utcnow() - global_cache.last_scraped_at).total_seconds() / 60
                }
            
            # Perform scraping using service key
            scrape_result = self.scraper.scrape_training_sessions(
                user_session_key=None,
                use_service_key=True
            )
            
            if scrape_result['success']:
                # Store in global cache
                sessions = scrape_result['sessions']
                global_cache.set_sessions(sessions, session_key_type='service')
                db.session.commit()
                
                logger.info(f"Global scrape successful: {len(sessions)} sessions cached")
                
                return {
                    'success': True,
                    'message': f'Successfully scraped {len(sessions)} training sessions',
                    'total_sessions': len(sessions)
                }
            else:
                # Store error in global cache
                global_cache.set_scrape_error(scrape_result['error'], session_key_type='service')
                db.session.commit()
                
                logger.error(f"Global scrape failed: {scrape_result['error']}")
                
                return {
                    'success': False,
                    'error': scrape_result['error'],
                    'total_sessions': 0
                }
                
        except Exception as e:
            logger.error(f"Error in global training scrape: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total_sessions': 0
            }
    
    def process_user_from_global_cache(self, user_settings: TrainingSessionSettings) -> Dict[str, Any]:
        """
        Process a user by filtering global cache based on their monitored ratings
        Compare with their previous filtered cache and send notifications for new sessions
        
        Args:
            user_settings: User's training session settings
            
        Returns:
            Dict with user processing results
        """
        try:
            user_id = user_settings.user_id
            logger.debug(f"Processing user {user_id} from global cache")
            
            # Validate user session key periodically (for authorization)
            if user_settings.is_session_key_expired():
                logger.debug(f"Validating user session key for authorization (user {user_id})")
                validation_result = self.scraper.validate_session_key(user_settings.php_session_key)
                
                if validation_result['valid']:
                    user_settings.mark_session_key_validated()
                    logger.debug(f"User session key validated for user {user_id}")
                else:
                    # Send session key expiration notification
                    self.send_session_key_expired_notification(user_settings, validation_result['message'])
                    
                    return {
                        'user_id': user_id,
                        'success': False,
                        'error': 'User session key expired or invalid - not authorized',
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
            
            # Get global cache
            global_cache = GlobalTrainingSessionCache.query.first()
            
            if not global_cache or not global_cache.scrape_successful:
                logger.warning(f"No valid global cache available for user {user_id}")
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': 'No valid global training data available',
                    'notifications_sent': 0
                }
            
            # Filter global cache by user's monitored ratings
            current_filtered_sessions = global_cache.filter_sessions_by_ratings(monitored_ratings)
            
            # Get user's previous filtered cache for comparison
            previous_filtered_sessions = self.get_user_cached_sessions(user_settings, monitored_ratings)
            
            # Detect new sessions
            new_sessions = self.scraper.detect_new_sessions(current_filtered_sessions, previous_filtered_sessions)
            
            # Update user's individual cache with current filtered data
            self.update_user_cache_from_global(user_settings, current_filtered_sessions)
            
            # Send notifications for new sessions
            notifications_sent = 0
            for session in new_sessions:
                try:
                    if self.send_new_session_notification(user_settings, session):
                        notifications_sent += 1
                except Exception as notification_error:
                    logger.error(f"Error sending notification for user {user_id}: {notification_error}")
            
            logger.debug(f"User {user_id}: {len(current_filtered_sessions)} filtered sessions, {len(new_sessions)} new, {notifications_sent} notifications sent")
            
            return {
                'user_id': user_id,
                'success': True,
                'filtered_sessions': len(current_filtered_sessions),
                'new_sessions': len(new_sessions),
                'notifications_sent': notifications_sent
            }
            
        except Exception as e:
            logger.error(f"Error processing user {user_settings.user_id} from global cache: {e}", exc_info=True)
            return {
                'user_id': user_settings.user_id,
                'success': False,
                'error': str(e),
                'notifications_sent': 0
            }
    
    def update_user_cache_from_global(self, user_settings: TrainingSessionSettings, filtered_sessions: List[Dict[str, Any]]):
        """
        Update user's individual cache with their filtered sessions from global cache
        
        Args:
            user_settings: User's training session settings
            filtered_sessions: Sessions already filtered for this user's monitored ratings
        """
        try:
            cache = TrainingSessionCache.query.filter_by(settings_id=user_settings.id).first()
            
            if not cache:
                cache = TrainingSessionCache()
                cache.settings_id = user_settings.id
                db.session.add(cache)
            
            # Store the filtered sessions for this user
            cache.set_sessions(filtered_sessions)
            db.session.commit()
            
            logger.debug(f"Updated user cache for user {user_settings.user_id} with {len(filtered_sessions)} filtered sessions")
            
        except Exception as e:
            logger.error(f"Error updating user cache from global for user {user_settings.user_id}: {e}")
            db.session.rollback()

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
            
            # Validate user session key if needed (weekly check)
            # This ensures the user is still authorized to access OAK ARTCC training pages
            if user_settings.is_session_key_expired():
                logger.info(f"Validating expired user session key for user {user_id}")
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
            
            # Scrape training sessions using service-level key
            # The user's session key was validated above to ensure authorization
            # The service key is used for actual data scraping for consistency and reliability
            scrape_result = self.scraper.scrape_training_sessions(
                user_session_key=user_settings.php_session_key,
                use_service_key=True
            )
            
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
    
    def _perform_initial_check(self):
        """
        Override base method to handle Flask app context and force global cache refresh
        """
        if not self.app:
            logger.warning("Flask app not set - skipping initial training session check")
            return
        
        logger.info("Performing initial training session check with global cache refresh...")
        
        try:
            with self.app.app_context():
                # First ensure we have fresh global data
                global_scrape_result = self.perform_global_training_scrape(force_refresh=True)
                
                if global_scrape_result['success']:
                    logger.info(f"Initial global cache refresh successful: {global_scrape_result.get('total_sessions', 0)} sessions cached")
                else:
                    logger.warning(f"Initial global cache refresh failed: {global_scrape_result.get('error', 'Unknown error')}")
                
                # Then perform the standard initial check
                super()._perform_initial_check()
                
        except Exception as e:
            logger.error(f"Error during initial training session check: {e}", exc_info=True)
            self.on_error(f"Initial check failed: {str(e)}")
    
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