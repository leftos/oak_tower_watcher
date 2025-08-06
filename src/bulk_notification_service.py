#!/usr/bin/env python3
"""
Bulk Notification Service for VATSIM Tower Monitor
Handles sending notifications to all users in the database with valid Pushover credentials.
"""

import logging
import os
import sys
from typing import List, Dict, Any, Optional
from src.pushover_service import PushoverService

# Add the project root to the path to import web modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from web.backend.models import db, UserSettings
    from web.backend.app import create_app
    WEB_MODULES_AVAILABLE = True
except ImportError:
    WEB_MODULES_AVAILABLE = False
    logging.warning("Web modules not available - bulk notifications to database users will be disabled")


class BulkNotificationService:
    """Service for sending notifications to all users with valid Pushover credentials"""
    
    def __init__(self):
        self.app = None
        self.enabled = False
        
        if WEB_MODULES_AVAILABLE:
            try:
                # Create Flask app context for database access
                self.app = create_app()
                self.enabled = True
                logging.info("Bulk notification service initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize bulk notification service: {e}")
                self.enabled = False
        else:
            logging.warning("Web modules not available - bulk notifications disabled")
    
    def get_notification_users(self, service_name: str = 'oak_tower_watcher') -> List[Dict[str, Any]]:
        """
        Get all users with valid Pushover credentials and notifications enabled
        
        Args:
            service_name: The service name to filter by
            
        Returns:
            List of user notification settings
        """
        if not self.enabled or not self.app:
            return []
        
        try:
            with self.app.app_context():
                # Query for users with valid Pushover settings and notifications enabled
                settings = UserSettings.query.filter_by(
                    service_name=service_name,
                    notifications_enabled=True
                ).filter(
                    UserSettings.pushover_api_token.isnot(None),
                    UserSettings.pushover_user_key.isnot(None),
                    UserSettings.pushover_api_token != '',
                    UserSettings.pushover_user_key != ''
                ).all()
                
                # Convert to list of dictionaries
                user_settings = []
                for setting in settings:
                    user_settings.append({
                        'user_id': setting.user_id,
                        'user_email': setting.user.email if setting.user else 'unknown',
                        'pushover_api_token': setting.pushover_api_token,
                        'pushover_user_key': setting.pushover_user_key,
                        'service_name': setting.service_name
                    })
                
                logging.info(f"Found {len(user_settings)} users with valid Pushover settings")
                return user_settings
                
        except Exception as e:
            logging.error(f"Error querying notification users: {e}")
            return []
    
    def send_bulk_notification(
        self,
        title: str,
        message: str,
        priority: int = 0,
        sound: Optional[str] = None,
        service_name: str = 'oak_tower_watcher'
    ) -> Dict[str, Any]:
        """
        Send notification to all users with valid Pushover credentials
        
        Args:
            title: Notification title
            message: Notification message
            priority: Pushover priority level (-2 to 2)
            sound: Notification sound
            service_name: Service name to filter users by
            
        Returns:
            Dictionary with results summary
        """
        if not self.enabled:
            return {
                'success': False,
                'error': 'Bulk notification service not available',
                'sent_count': 0,
                'failed_count': 0,
                'details': []
            }
        
        users = self.get_notification_users(service_name)
        
        if not users:
            logging.info("No users found with valid Pushover settings - skipping bulk notification")
            return {
                'success': True,
                'message': 'No users to notify',
                'sent_count': 0,
                'failed_count': 0,
                'details': []
            }
        
        sent_count = 0
        failed_count = 0
        details = []
        
        for user in users:
            try:
                # Create PushoverService instance for this user
                pushover_service = PushoverService(
                    api_token=user['pushover_api_token'],
                    user_key=user['pushover_user_key']
                )
                
                # Send notification
                result = pushover_service.send_notification(
                    message=message,
                    title=title,
                    priority=priority,
                    sound=sound
                )
                
                if result['success']:
                    sent_count += 1
                    logging.debug(f"Notification sent to user {user['user_email']}")
                    details.append({
                        'user_email': user['user_email'],
                        'status': 'sent',
                        'message': 'Success'
                    })
                else:
                    failed_count += 1
                    logging.warning(f"Failed to send notification to user {user['user_email']}: {result.get('error', 'Unknown error')}")
                    details.append({
                        'user_email': user['user_email'],
                        'status': 'failed',
                        'message': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                logging.error(f"Error sending notification to user {user['user_email']}: {error_msg}")
                details.append({
                    'user_email': user['user_email'],
                    'status': 'error',
                    'message': error_msg
                })
        
        # Log summary
        logging.info(f"Bulk notification complete - Sent: {sent_count}, Failed: {failed_count}")
        
        return {
            'success': True,
            'message': f'Bulk notification complete',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'details': details
        }
    
    def test_bulk_notification(self, service_name: str = 'oak_tower_watcher') -> Dict[str, Any]:
        """
        Send a test notification to all users with valid Pushover credentials
        
        Args:
            service_name: Service name to filter users by
            
        Returns:
            Dictionary with test results
        """
        return self.send_bulk_notification(
            title="VATSIM Monitor Test",
            message="This is a test notification from VATSIM Tower Monitor to all registered users.",
            priority=0,
            sound="pushover",
            service_name=service_name
        )