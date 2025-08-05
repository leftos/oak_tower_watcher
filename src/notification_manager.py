#!/usr/bin/env python3
"""
Notification Manager for VATSIM Tower Monitor
Handles notification logic and formatting that can be shared between GUI and headless versions.
"""

import logging
from datetime import datetime
from .utils import get_controller_name, get_controller_initials
from .pushover_service import create_pushover_service, get_priority_for_status, get_sound_for_status


class NotificationManager:
    """Manages notifications and status transitions for VATSIM Monitor"""

    def __init__(self, config, controller_names=None):
        self.config = config
        self.controller_names = controller_names or {}
        
        # Get airport configuration
        self.airport_config = config.get("airport", {})
        self.airport_code = self.airport_config.get("code", "KOAK")
        self.display_name = self.airport_config.get(
            "display_name", f"{self.airport_code} Main Facility"
        )
        
        # Setup Pushover service
        self.pushover_service = create_pushover_service(config)
        if self.pushover_service:
            logging.info("Pushover service initialized in NotificationManager")

    def format_supporting_below_controllers_info(self, supporting_below_controllers):
        """Format supporting below controllers information for notifications (with full names)"""
        if not supporting_below_controllers:
            return ""

        supporting_below_info = []
        for supporting_below in supporting_below_controllers:
            callsign = supporting_below.get("callsign", "Unknown")
            name = get_controller_name(supporting_below, self.controller_names)
            supporting_below_info.append(f"{callsign} ({name})")

        if len(supporting_below_info) == 1:
            return f"\nBelow: {supporting_below_info[0]}"
        else:
            return f"\nBelow: {', '.join(supporting_below_info)}"

    def format_multiple_controllers_info(self, controllers, prefix=""):
        """Format multiple controllers information for display"""
        if not controllers:
            return ""

        if isinstance(controllers, dict):  # Handle legacy single controller format
            controllers = [controllers]

        controller_info = []
        for controller in controllers:
            callsign = controller.get("callsign", "Unknown")
            name = get_controller_name(controller, self.controller_names)
            controller_info.append(f"{callsign} ({name})")

        if len(controller_info) == 1:
            return f"{prefix}{controller_info[0]}"
        else:
            return f"{prefix}{', '.join(controller_info)}"

    def get_transition_notification(
        self,
        previous_status,
        current_status,
        controller_info,
        supporting_info,
        supporting_below_controllers,
    ):
        """Generate appropriate notification message based on state transition"""

        # Get supporting below controller info for all messages
        supporting_below_info = self.format_supporting_below_controllers_info(
            supporting_below_controllers
        )

        # Handle transitions to full coverage
        if current_status == "main_facility_and_supporting_above_online":
            main_facility_info = self.format_multiple_controllers_info(
                controller_info, f"{self.display_name}: "
            )
            support_info = self.format_multiple_controllers_info(
                supporting_info, "Supporting Above: "
            )
            message = f"{main_facility_info}\n{support_info}{supporting_below_info}"

            if previous_status == "main_facility_online":
                title = "Supporting Above Facilities Now Online!"
                return title, message, "success"
            elif previous_status == "supporting_above_online":
                title = f"{self.display_name} Now Online!"
                return title, message, "success"
            else:  # from all_offline
                title = "Full Coverage Online!"
                return title, message, "success"

        # Handle transitions to main facility only
        elif current_status == "main_facility_online":
            main_facility_info = self.format_multiple_controllers_info(controller_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = "Supporting Above Facilities Now Offline"
                message = f"Only {self.display_name} remains online\n{main_facility_info}{supporting_below_info}"
                return title, message, "warning"
            elif previous_status == "supporting_above_online":
                title = f"{self.display_name} Now Online!"
                message = f"{self.display_name} controller is now online\n{main_facility_info}{supporting_below_info}"
                return title, message, "success"
            else:  # from all_offline
                title = f"{self.display_name} Online!"
                message = f"{main_facility_info} is now online!{supporting_below_info}"
                return title, message, "success"

        # Handle transitions to supporting above only
        elif current_status == "supporting_above_online":
            support_info = self.format_multiple_controllers_info(supporting_info)

            if previous_status == "main_facility_and_supporting_above_online":
                title = f"{self.display_name} Now Offline"
                message = (
                    f"Only supporting above facility remains online\n"
                    f"{support_info}{supporting_below_info}"
                )
                return title, message, "warning"
            elif previous_status == "main_facility_online":
                title = f"{self.display_name} Now Offline"
                message = f"{self.display_name} went offline, but {support_info} is online{supporting_below_info}"
                return title, message, "warning"
            else:  # from all_offline
                title = "Supporting Above Facility Online"
                message = f"{self.display_name} is offline, but {support_info} is online{supporting_below_info}"
                return title, message, "warning"

        # Handle transitions to all offline
        else:  # all_offline
            if previous_status == "main_facility_and_supporting_above_online":
                title = "All Facilities Now Offline"
                message = (
                    f"Both {self.display_name} and supporting above controllers have gone offline"
                    + f"{supporting_below_info}"
                )
            elif previous_status == "main_facility_online":
                title = f"{self.display_name} Now Offline"
                message = (
                    f"{self.display_name} controller has gone offline{supporting_below_info}"
                )
            elif previous_status == "supporting_above_online":
                title = "Supporting Above Facility Now Offline"
                message = f"Supporting above controller has gone offline{supporting_below_info}"
            else:
                title = "All Facilities Offline"
                message = f"No {self.display_name} or supporting above controllers found{supporting_below_info}"

            return title, message, "error"

    def send_pushover_notification(self, title: str, message: str, status: str):
        """Send a Pushover notification if configured"""
        if not self.pushover_service:
            return False

        try:
            # Get priority and sound based on status
            priority = get_priority_for_status(status)
            sound = get_sound_for_status(status)
            
            # Override with config values if available
            pushover_config = self.config.get("pushover", {})
            priority_levels = pushover_config.get("priority_levels", {})
            sounds = pushover_config.get("sounds", {})
            
            if status in priority_levels:
                priority = priority_levels[status]
            if status in sounds:
                sound = sounds[status]

            # Send the notification
            result = self.pushover_service.send_notification(
                message=message,
                title=title,
                priority=priority,
                sound=sound
            )
            
            if result["success"]:
                logging.info(f"Pushover notification sent: {title}")
                return True
            else:
                logging.error(f"Pushover notification failed: {result['error']}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending Pushover notification: {e}")
            return False

    def test_pushover(self):
        """Test Pushover notification"""
        if not self.pushover_service:
            logging.error("Pushover service not configured")
            return False
            
        try:
            result = self.pushover_service.send_test_notification()
            
            if result["success"]:
                logging.info("Pushover test notification sent successfully")
                return True
            else:
                logging.error(f"Pushover test failed: {result['error']}")
                return False
                
        except Exception as e:
            logging.error(f"Pushover test error: {e}")
            return False

    def update_controller_names(self, controller_names):
        """Update the controller names dictionary"""
        self.controller_names = controller_names