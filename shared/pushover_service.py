#!/usr/bin/env python3
"""
Pushover notification service for VATSIM Tower Monitor
Provides push notification functionality via Pushover API using only requests library.
"""

import requests
import logging
import json
from typing import Optional, Dict, Any, Union


class PushoverService:
    """Service class for sending Pushover notifications"""
    
    def __init__(self, api_token: str, user_key: Optional[str] = None):
        """
        Initialize Pushover service
        
        Args:
            api_token: Pushover application API token
            user_key: User key (can be set later via set_user_key)
        """
        self.api_token = api_token
        self.user_key = user_key
        self.api_url = "https://api.pushover.net/1/messages.json"
        
    def set_user_key(self, user_key: str):
        """Set the user key for notifications"""
        self.user_key = user_key
        
    def send_notification(
        self,
        message: str,
        title: Optional[str] = None,
        priority: int = 0,
        sound: Optional[str] = None,
        url: Optional[str] = None,
        url_title: Optional[str] = None,
        device: Optional[str] = None,
        timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a push notification via Pushover
        
        Args:
            message: The message content (required)
            title: Message title
            priority: Priority level (-2 to 2)
                     -2: No notification/alert
                     -1: Quiet notification
                      0: Normal priority (default)
                      1: High priority
                      2: Emergency priority (requires retry/expire)
            sound: Notification sound name
            url: Supplementary URL
            url_title: Title for the URL
            device: Target device name
            timestamp: Unix timestamp for message
            
        Returns:
            Dict containing response status and message
        """
        if not self.user_key:
            return {
                "success": False,
                "error": "User key not configured"
            }
            
        if not message:
            return {
                "success": False,
                "error": "Message is required"
            }
            
        # Prepare the payload
        payload = {
            "token": self.api_token,
            "user": self.user_key,
            "message": message
        }
        
        # Add optional parameters
        if title:
            payload["title"] = title
        if priority is not None:
            payload["priority"] = str(priority)
        if sound:
            payload["sound"] = sound
        if url:
            payload["url"] = url
        if url_title:
            payload["url_title"] = url_title
        if device:
            payload["device"] = device
        if timestamp:
            payload["timestamp"] = str(timestamp)
            
        try:
            # Send the request
            response = requests.post(
                self.api_url,
                data=payload,
                timeout=10
            )
            
            # Parse response
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status") == 1:
                logging.info(f"Pushover notification sent successfully: {title or 'Notification'}")
                return {
                    "success": True,
                    "message": "Notification sent successfully",
                    "response": response_data
                }
            else:
                error_msg = response_data.get("errors", ["Unknown error"])[0] if response_data.get("errors") else "Unknown error"
                logging.error(f"Pushover notification failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "response": response_data
                }
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout - Pushover API did not respond"
            logging.error(f"Pushover notification failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error - Unable to reach Pushover API"
            logging.error(f"Pushover notification failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            logging.error(f"Pushover notification failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except json.JSONDecodeError:
            error_msg = "Invalid JSON response from Pushover API"
            logging.error(f"Pushover notification failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logging.error(f"Pushover notification failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def validate_user_key(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate a user key with Pushover API
        
        Args:
            user_key: User key to validate (uses instance user_key if not provided)
            
        Returns:
            Dict containing validation result
        """
        key_to_validate = user_key or self.user_key
        
        if not key_to_validate:
            return {
                "success": False,
                "error": "No user key provided"
            }
            
        validate_url = "https://api.pushover.net/1/users/validate.json"
        payload = {
            "token": self.api_token,
            "user": key_to_validate
        }
        
        try:
            response = requests.post(validate_url, data=payload, timeout=10)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status") == 1:
                logging.info("Pushover user key validation successful")
                return {
                    "success": True,
                    "message": "User key is valid",
                    "response": response_data
                }
            else:
                error_msg = response_data.get("errors", ["Invalid user key"])[0] if response_data.get("errors") else "Invalid user key"
                logging.error(f"Pushover user key validation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "response": response_data
                }
                
        except Exception as e:
            error_msg = f"Validation request failed: {str(e)}"
            logging.error(f"Pushover user key validation failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def send_test_notification(self) -> Dict[str, Any]:
        """
        Send a test notification to verify configuration
        
        Returns:
            Dict containing test result
        """
        return self.send_notification(
            message="This is a test notification from VATSIM Tower Monitor.",
            title="VATSIM Monitor Test",
            priority=0,
            sound="pushover"
        )


def create_pushover_service(config: Dict[str, Any]) -> Optional[PushoverService]:
    """
    Create a PushoverService instance from configuration
    
    Args:
        config: Configuration dictionary containing pushover settings
        
    Returns:
        PushoverService instance or None if not configured
    """
    pushover_config = config.get("pushover", {})
    
    if not pushover_config.get("enabled", False):
        return None
        
    api_token = pushover_config.get("api_token")
    user_key = pushover_config.get("user_key")
    
    if not api_token:
        logging.warning("Pushover API token not configured")
        return None
        
    service = PushoverService(api_token, user_key)
    return service


def get_priority_for_status(status: str) -> int:
    """
    Get appropriate Pushover priority level for VATSIM status
    
    Args:
        status: VATSIM status string
        
    Returns:
        Priority level (-2 to 2)
    """
    priority_map = {
        "main_facility_and_supporting_above_online": 1,  # High priority - full coverage
        "main_facility_online": 0,                       # Normal priority - tower online
        "supporting_above_online": 0,                    # Normal priority - supporting online
        "all_offline": 0,                               # Normal priority - facilities offline
        "error": -1                                     # Low priority - error conditions
    }
    
    return priority_map.get(status, 0)


def get_sound_for_status(status: str) -> str:
    """
    Get appropriate Pushover sound for VATSIM status
    
    Args:
        status: VATSIM status string
        
    Returns:
        Sound name for Pushover
    """
    sound_map = {
        "main_facility_and_supporting_above_online": "magic",     # Full coverage - special sound
        "main_facility_online": "pushover",                      # Tower online - default sound
        "supporting_above_online": "intermission",               # Supporting online - softer sound
        "all_offline": "falling",                               # Facilities offline - descending sound
        "error": "none"                                         # Error - no sound
    }
    
    return sound_map.get(status, "pushover")