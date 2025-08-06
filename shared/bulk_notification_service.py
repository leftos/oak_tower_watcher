#!/usr/bin/env python3
"""
Bulk Notification Service for VATSIM Tower Monitor
Handles sending notifications to all users in the database with valid Pushover credentials.
"""

import logging
from typing import List, Dict, Any, Optional
from .pushover_service import PushoverService
from .utils import format_push_notification
from .database_interface import DatabaseInterface


class BulkNotificationService:
    """Service for sending notifications to all users with valid Pushover credentials"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.db_interface = DatabaseInterface(database_url)
        self.enabled = self.db_interface.enabled
        
        if self.enabled:
            logging.info("Bulk notification service initialized successfully")
        else:
            logging.warning("Bulk notification service disabled - database interface not available")
    
    def get_notification_users(self, service_name: str = 'oak_tower_watcher') -> List[Dict[str, Any]]:
        """
        Get all users with valid Pushover credentials and notifications enabled
        
        Args:
            service_name: The service name to filter by
            
        Returns:
            List of user notification settings with facility patterns
        """
        return self.db_interface.get_notification_users(service_name)
    
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

    def send_personalized_bulk_notification(
        self,
        status_change: str,
        priority: int = 0,
        sound: Optional[str] = None,
        service_name: str = 'oak_tower_watcher'
    ) -> Dict[str, Any]:
        """
        Send personalized notifications to users based on their facility configurations
        
        Args:
            status_change: Type of status change ('main_online', 'supporting_online', 'all_offline', etc.)
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
        
        # Import here to avoid circular imports
        try:
            from config.config import load_config
            from shared.vatsim_core import VATSIMCore
        except ImportError as e:
            logging.error(f"Failed to import required modules: {e}")
            return {
                'success': False,
                'error': 'Required modules not available',
                'sent_count': 0,
                'failed_count': 0,
                'details': []
            }
        
        users = self.get_notification_users(service_name)
        
        if not users:
            logging.info("No users found with valid Pushover settings - skipping personalized bulk notification")
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
        
        # Load base config for fallback
        base_config = load_config()
        
        for user in users:
            try:
                # Get user's facility patterns
                user_patterns = user.get('facility_patterns', {})
                
                # Create user-specific config or use default
                if any(user_patterns.values()):  # User has custom patterns
                    user_config = base_config.copy()
                    user_config['callsigns'] = user_patterns
                    vatsim_core = VATSIMCore(user_config)
                    config_type = "custom"
                else:  # Use default patterns
                    vatsim_core = VATSIMCore(base_config)
                    config_type = "default"
                
                # Check current status with user's configuration
                status_result = vatsim_core.check_status()
                
                if not status_result['success']:
                    logging.warning(f"Failed to get status for user {user['user_email']}: {status_result.get('error', 'Unknown error')}")
                    continue
                
                # Determine if this user should be notified based on their status
                should_notify = False
                title = ""
                message = ""
                
                current_status = status_result['status']
                main_controllers = status_result.get('main_controllers', [])
                supporting_above = status_result.get('supporting_above', [])
                supporting_below = status_result.get('supporting_below', [])
                
                if current_status in ['main_facility_and_supporting_above_online', 'main_facility_online', 'supporting_above_online', 'all_offline']:
                    should_notify = True
                    
                    # Use shared notification formatting function
                    notification_data = format_push_notification(
                        current_status=current_status,
                        main_controllers=main_controllers,
                        supporting_above=supporting_above,
                        supporting_below=supporting_below,
                        include_priority_sound=False,
                        is_test=False
                    )
                    
                    title = notification_data['title']
                    message = notification_data['message']
                
                if should_notify:                    
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
                        logging.debug(f"Personalized notification sent to user {user['user_email']} (status: {current_status}, config: {config_type})")
                        details.append({
                            'user_email': user['user_email'],
                            'status': 'sent',
                            'message': f'Success - {current_status} ({config_type} config)',
                            'current_status': current_status,
                            'config_type': config_type
                        })
                    else:
                        failed_count += 1
                        logging.warning(f"Failed to send personalized notification to user {user['user_email']}: {result.get('error', 'Unknown error')}")
                        details.append({
                            'user_email': user['user_email'],
                            'status': 'failed',
                            'message': result.get('error', 'Unknown error'),
                            'current_status': current_status,
                            'config_type': config_type
                        })
                else:
                    # User doesn't need notification for current status
                    details.append({
                        'user_email': user['user_email'],
                        'status': 'skipped',
                        'message': f'No notification needed - {current_status} ({config_type} config)',
                        'current_status': current_status,
                        'config_type': config_type
                    })
                    
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                logging.error(f"Error processing personalized notification for user {user['user_email']}: {error_msg}")
                details.append({
                    'user_email': user['user_email'],
                    'status': 'error',
                    'message': error_msg
                })
        
        # Log summary
        logging.info(f"Personalized bulk notification complete - Sent: {sent_count}, Failed: {failed_count}")
        
        return {
            'success': True,
            'message': f'Personalized bulk notification complete',
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